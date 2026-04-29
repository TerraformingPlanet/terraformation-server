from __future__ import annotations

from .models import (
    ClaimedTile,
    EcoMarketState,
    GlobalMarketState,
    LocalMarketState,
    SphericalBodyState,
    TileBioListing,
    TileBioMarketState,
)
from .logic.market import (
    compute_market_prices,
    compute_population_demand,
    compute_territories,
    apply_social_mobility,
    init_market_listings,
    compute_global_market,
)


class MarketMixin:
    """Local, global, eco-market, and bio-market methods.

    State accessed via self:
        self._lock, self._markets, self._corporations, self._buildings,
        self._states, self._bodies, self._eco_markets, self._bio_tile_history,
        self._tick_count
    """

    # ── Internal tick processor ────────────────────────────────────────────────

    def _process_market_tick_locked(self) -> None:
        """Update local markets per territory (Phase 7.3). Lock must be held."""
        active_territory_ids: set[str] = set()

        for corp_id, corp in self._corporations.items():
            claimed_tiles = list(corp.claimedTiles)

            # Compute connected components for this corp's tiles
            territories = compute_territories(corp_id, claimed_tiles)

            # Social-mobility data: tile → avg worker ratio
            tile_worker_ratios: dict[str, list[float]] = {}
            for building in self._buildings.values():
                if building.corpId == corp_id:
                    tile_worker_ratios.setdefault(building.tileId, []).append(building.workerRatio)

            for territory_id, tile_ids in territories:
                active_territory_ids.add(territory_id)
                tile_id_set = set(tile_ids)
                territory_tiles = [t for t in claimed_tiles if t.tileId in tile_id_set]

                connectivity = self._markets.get(territory_id, LocalMarketState()).connectivity
                supply_global: dict[str, float] = {k: v for k, v in corp.resources.items()}
                supply_eff: dict[str, float] = {k: v * connectivity for k, v in supply_global.items()}

                demand = compute_population_demand(territory_tiles)

                prev_market = self._markets.get(territory_id)
                listings = prev_market.listings if prev_market is not None else init_market_listings()

                updated_listings = compute_market_prices(listings, supply_eff, demand)

                # Deduct consumption from corp resources
                for listing in updated_listings:
                    key = listing.resourceType.name
                    consumed = min(demand.get(key, 0.0), supply_global.get(key, 0.0))
                    if consumed > 0.0:
                        corp.resources[key] = max(0.0, corp.resources.get(key, 0.0) - consumed)

                self._markets[territory_id] = LocalMarketState(
                    territoryId=territory_id,
                    ownerEntityId=corp_id,
                    tileIds=tile_ids,
                    listings=updated_listings,
                    taxRate=self._resolve_tax_rate_locked(set(tile_ids)),
                    connectivity=connectivity,
                    tickComputed=self._tick_count,
                )

            # Apply social mobility per tile
            new_tiles: list[ClaimedTile] = []
            for tile in claimed_tiles:
                ratios = tile_worker_ratios.get(tile.tileId, [])
                emp_ratio = sum(ratios) / len(ratios) if ratios else 0.0
                new_tiles.append(apply_social_mobility(tile, emp_ratio))
            corp.claimedTiles = new_tiles

        # Purge territories whose tiles are no longer owned
        for tid in [k for k in self._markets if k not in active_territory_ids]:
            del self._markets[tid]

    def _resolve_tax_rate_locked(self, tile_id_set: set[str]) -> float:
        """Return the taxRate of the first State overlapping this territory. Lock must be held."""
        for state in self._states.values():
            if any(tid in tile_id_set for tid in state.tileIds):
                return state.taxRate
        return 0.0

    # ── Public market API (Phase 7.3 + 9.5 + 11.6) ──────────────────────────────

    def get_market_states_for_entity(self, entity_id: str) -> list[LocalMarketState]:
        with self._lock:
            return [m for m in self._markets.values() if m.ownerEntityId == entity_id]

    def get_market_state(self, corp_id: str) -> LocalMarketState | None:
        """Return the first local market state owned by *corp_id*, or None."""
        with self._lock:
            return next((m for m in self._markets.values() if m.ownerEntityId == corp_id), None)

    def get_market_state_by_tile(self, tile_id: str) -> LocalMarketState | None:
        with self._lock:
            return next((m for m in self._markets.values() if tile_id in m.tileIds), None)

    def list_market_states(self) -> list[LocalMarketState]:
        with self._lock:
            return list(self._markets.values())

    def get_global_market(self, system_id: str = "sol") -> GlobalMarketState:
        """Aggregated market state for a system (Phase 9.5)."""
        with self._lock:
            local_markets = list(self._markets.values())
            data = compute_global_market(local_markets, system_id, self._tick_count)
            return GlobalMarketState.model_validate(data)

    def get_eco_market(self, body_id: str) -> EcoMarketState | None:
        """Eco-market state for a spherical body (Phase 11.6)."""
        with self._lock:
            return self._eco_markets.get(body_id)

    def get_tile_bio_market(self, tile_id: str) -> TileBioMarketState | None:
        """Bio-market state for a single tile (Phase 11.6b).

        Returns None if tile_id is not found in any body.
        """
        with self._lock:
            for body in self._bodies.values():
                if not isinstance(body, SphericalBodyState) or not body.tiles:
                    continue
                tile = next((t for t in body.tiles if t.tileId == tile_id), None)
                if tile is None:
                    continue
                resource_abundance: dict[str, tuple[float, str]] = {}
                for sp in tile.species:
                    for resource, base_output in sp.marketOutput.items():
                        abundance = sp.density * base_output
                        if resource not in resource_abundance:
                            resource_abundance[resource] = (abundance, sp.speciesId)
                        else:
                            prev_ab, prev_sp = resource_abundance[resource]
                            resource_abundance[resource] = (prev_ab + abundance, prev_sp)

                tile_hist = self._bio_tile_history.get(tile_id, {})
                listings = [
                    TileBioListing(
                        resource=resource,
                        speciesId=species_id,
                        abundance=round(abundance, 4),
                        abundanceHistory=list(tile_hist.get(resource, [])),
                    )
                    for resource, (abundance, species_id) in resource_abundance.items()
                ]
                return TileBioMarketState(
                    tileId=tile_id,
                    listings=listings,
                    tickComputed=self._tick_count,
                )
            return None

    def _update_bio_tile_history_locked(self, tile) -> None:
        """Push current species abundances into per-tile ring buffers (max 8). Lock must be held."""
        if not tile.species:
            return
        tile_hist = self._bio_tile_history.setdefault(tile.tileId, {})
        for sp in tile.species:
            for resource, base_output in sp.marketOutput.items():
                abundance = sp.density * base_output
                buf = tile_hist.setdefault(resource, [])
                buf.append(round(abundance, 4))
                if len(buf) > 8:
                    buf.pop(0)
