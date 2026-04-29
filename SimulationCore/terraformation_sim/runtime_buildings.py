from __future__ import annotations

from uuid import uuid4

from .models import (
    BuildingData,
    BuildingType,
    ConstructionItem,
    ConstructionStatus,
    GoldbergTileState,
    LocalMarketState,
    SphericalBodyState,
    TerritoryQueue,
    BUILDING_CONSTRUCTION_COST,
    EB_FORMAL_CAPACITY,
    EB_FORTUNE_CAPACITY,
    EB_FORTUNE_POP_THRESHOLD,
)
from .logic import find_free_slot, init_sub_hexes
from .registry import BUILDING_REGISTRY


class BuildingsMixin:
    """Building construction, production, and management methods.

    State accessed via self:
        self._lock, self._corporations, self._buildings, self._construction_queues,
        self._markets, self._bodies, self._eco_extractions, self._tile_ownership,
        self._tick_count, self._repo
    """

    # ── Construction (Phase 10.5) ─────────────────────────────────────────────

    def construct_building(
        self,
        corp_id: str,
        body_id: str,
        tile_id: str,
        building_type: BuildingType,
        sub_hex_index: int = -1,
    ) -> ConstructionItem:
        """Enqueue a building for multi-tick construction.

        sub_hex_index: -1 = auto-select first free buildable slot.
        Returns the ConstructionItem that was added to the territory queue.
        Raises ValueError if the building already exists or is already queued.
        """
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            for b in self._buildings.values():
                if (b.corpId == corp_id and b.bodyId == body_id
                        and b.tileId == tile_id and b.buildingType == building_type):
                    raise ValueError(f"A {building_type} already exists on tile '{tile_id}'")
            for q in self._construction_queues.values():
                if q.corpId == corp_id and q.bodyId == body_id:
                    for item in q.items:
                        if item.tileId == tile_id and item.buildingType == building_type:
                            raise ValueError(
                                f"A {building_type} is already queued for tile '{tile_id}'"
                            )
            return self._enqueue_construction_locked(
                corp_id, body_id, tile_id, building_type, sub_hex_index
            )

    def _enqueue_construction_locked(
        self,
        corp_id: str,
        body_id: str,
        tile_id: str,
        building_type: BuildingType,
        sub_hex_index: int = -1,
    ) -> ConstructionItem:
        """Add item to the territory queue. Lock must be held by caller."""
        building_def = BUILDING_REGISTRY.get(building_type)

        # Terrain check + sub-hex slot resolution
        try:
            tile = self.get_body_tile(body_id, tile_id)
        except KeyError:
            tile = None  # body/tile not loaded — skip terrain and slot validation

        if tile is not None:
            if building_def and building_def.terrain_required:
                if tile.terrainType.name != building_def.terrain_required:
                    raise ValueError(
                        f"Cannot build {building_type} on {tile.terrainType.name} terrain"
                        f" — requires {building_def.terrain_required}"
                    )

            # Resolve sub-hex slot
            if tile.subHexes:
                if sub_hex_index == -1:
                    sub_hex_index = find_free_slot(tile.subHexes)
                    if sub_hex_index == -1:
                        raise ValueError(f"No free building slot on tile '{tile_id}'")
                else:
                    if sub_hex_index < 0 or sub_hex_index >= len(tile.subHexes):
                        raise ValueError(f"sub_hex_index {sub_hex_index} out of range")
                    sh = tile.subHexes[sub_hex_index]
                    if not sh.buildable:
                        raise ValueError(f"Sub-hex {sub_hex_index} is not buildable")
                    if sh.buildingId:
                        raise ValueError(f"Sub-hex {sub_hex_index} is already occupied")

        territory_id = self._get_or_create_territory_queue_locked(corp_id, body_id, tile_id)
        queue = self._construction_queues[territory_id]
        cost_pts = BUILDING_CONSTRUCTION_COST.get(building_type, 60)
        item = ConstructionItem(
            id=str(uuid4()),
            buildingType=building_type,
            tileId=tile_id,
            bodyId=body_id,
            corpId=corp_id,
            status=(
                ConstructionStatus.InProgress if not queue.items
                else ConstructionStatus.Pending
            ),
            ticksRemaining=cost_pts,
            totalCostPts=cost_pts,
            pointsAccumulated=0,
            subHexIndex=sub_hex_index,
        )

        # Reserve the slot immediately
        if tile is not None and tile.subHexes and sub_hex_index >= 0:
            body = self._bodies.get(body_id)
            if body and isinstance(body, SphericalBodyState):
                updated_sh = tile.subHexes[sub_hex_index].model_copy(
                    update={"buildingId": item.id}
                )
                new_sub_hexes = [
                    updated_sh if sh.index == sub_hex_index else sh
                    for sh in tile.subHexes
                ]
                updated_tile = tile.model_copy(update={"subHexes": new_sub_hexes})
                body.tiles = [
                    updated_tile if t.tileId == tile_id else t
                    for t in body.tiles
                ]

        queue.items.append(item)
        return item

    def _get_or_create_territory_queue_locked(
        self, corp_id: str, body_id: str, tile_id: str
    ) -> str:
        """Return territory_id, creating a TerritoryQueue if needed. Lock must be held."""
        for tid, q in self._construction_queues.items():
            if q.corpId == corp_id and q.bodyId == body_id and tile_id in q.tileIds:
                return tid
        territory_id = f"{corp_id}::{body_id}::{tile_id}"
        capacity = self._compute_territory_capacity_locked(corp_id, body_id, [tile_id])
        queue = TerritoryQueue(
            territoryId=territory_id,
            corpId=corp_id,
            bodyId=body_id,
            tileIds=[tile_id],
            constructionCapacity=capacity,
        )
        self._construction_queues[territory_id] = queue
        return territory_id

    def _compute_territory_capacity_locked(
        self, corp_id: str, body_id: str, tile_ids: list[str]
    ) -> float:
        """Sum EB production capacity across all tiles in the territory. Lock must be held."""
        tile_set = set(tile_ids)
        eb_count = sum(
            1 for b in self._buildings.values()
            if b.corpId == corp_id and b.bodyId == body_id and b.tileId in tile_set
        )
        return float(eb_count) * EB_FORMAL_CAPACITY if eb_count > 0 else 0.0

    def _process_construction_tick_locked(self) -> None:
        """Advance all construction queues by one tick. Lock must be held.

        Algorithm:
        1. Refresh territory capacity (EB count may have changed).
        2. Drain capacity through queue items with overflow.
        3. Completed items → spawn BuildingData immediately.
        4. EB de fortune: if capacity == 0 and tile has pop > 0 and Wood > 0 → grant EB_FORTUNE_CAPACITY.
        """
        for territory_id, queue in list(self._construction_queues.items()):
            if not queue.items:
                continue
            corp_id = queue.corpId
            body_id = queue.bodyId

            capacity = self._compute_territory_capacity_locked(corp_id, body_id, queue.tileIds)
            queue.constructionCapacity = capacity
            queue.isEBDeFortune = False

            if capacity == 0:
                capacity = self._check_eb_de_fortune_locked(corp_id, body_id, queue.tileIds)
                if capacity > 0:
                    queue.constructionCapacity = capacity
                    queue.isEBDeFortune = True

            if capacity <= 0:
                continue

            remaining_pts = capacity
            while remaining_pts > 0 and queue.items:
                item = queue.items[0]
                item.status = ConstructionStatus.InProgress
                pts_to_apply = min(remaining_pts, item.ticksRemaining)
                item.pointsAccumulated += pts_to_apply
                item.ticksRemaining -= pts_to_apply
                remaining_pts -= pts_to_apply

                if item.ticksRemaining <= 0:
                    item.status = ConstructionStatus.Done
                    queue.items.pop(0)
                    self._complete_construction_locked(item)
                else:
                    break

    def _check_eb_de_fortune_locked(
        self, corp_id: str, body_id: str, tile_ids: list[str]
    ) -> float:
        """Return EB de fortune capacity if a tile in the territory has population >= threshold.

        Population is read from the authoritative tile state in self._bodies (tile-centric model).
        No resource cost — the EB de fortune is unlocked by having settled population.
        Lock must be held.
        """
        corp = self._corporations.get(corp_id)
        if corp is None:
            return 0.0
        body = self._bodies.get(body_id)
        tile_id_set = set(tile_ids)
        if body is not None and isinstance(body, SphericalBodyState):
            # Primary: read from authoritative tile state (tile-centric model)
            for tile in body.tiles:
                if tile.tileId not in tile_id_set:
                    continue
                pop = sum(tier.count for tier in tile.population)
                if pop >= EB_FORTUNE_POP_THRESHOLD:
                    return EB_FORTUNE_CAPACITY
        else:
            # Fallback for tests / environments where body is not loaded in memory
            for claimed in corp.claimedTiles:
                if claimed.tileId in tile_id_set:
                    pop = sum(tier.count for tier in claimed.population)
                    if pop >= EB_FORTUNE_POP_THRESHOLD:
                        return EB_FORTUNE_CAPACITY
        return 0.0

    def _find_market_for_tile_locked(self, body_id: str, tile_id: str) -> LocalMarketState | None:
        """Find the local market that contains this tile. Lock must be held."""
        for market in self._markets.values():
            if tile_id in market.tileIds:
                return market
        return None

    def _complete_construction_locked(self, item: ConstructionItem) -> None:
        """Instantiate a BuildingData from a completed ConstructionItem. Lock must be held."""
        building_id = str(uuid4())
        building = BuildingData(
            id=building_id,
            buildingType=item.buildingType,
            tileId=item.tileId,
            bodyId=item.bodyId,
            corpId=item.corpId,
            employmentSlots=dict(BUILDING_REGISTRY.get_workers(item.buildingType)),
            subHexIndex=item.subHexIndex,
        )
        self._buildings[building_id] = building

        # Transfer slot ownership from construction item ID to building ID
        if item.subHexIndex >= 0:
            body = self._bodies.get(item.bodyId)
            if body and isinstance(body, SphericalBodyState):
                for tidx, tile in enumerate(body.tiles):
                    if tile.tileId == item.tileId and tile.subHexes:
                        updated_sh = tile.subHexes[item.subHexIndex].model_copy(
                            update={"buildingId": building_id}
                        )
                        new_sub_hexes = [
                            updated_sh if sh.index == item.subHexIndex else sh
                            for sh in tile.subHexes
                        ]
                        body.tiles[tidx] = tile.model_copy(update={"subHexes": new_sub_hexes})
                        break

        corp = self._corporations.get(item.corpId)
        if corp:
            corp.buildings.append(building)
            self._repo.save_corporation(corp)
        self._repo.save_building(building)

    def cancel_construction_item(self, corp_id: str, item_id: str) -> None:
        """Remove a pending/in-progress construction item from its queue (Phase 10.5)."""
        with self._lock:
            for queue in self._construction_queues.values():
                if queue.corpId != corp_id:
                    continue
                for i, item in enumerate(queue.items):
                    if item.id == item_id:
                        queue.items.pop(i)
                        # Free the sub-hex slot
                        if item.subHexIndex >= 0:
                            body = self._bodies.get(item.bodyId)
                            if body and isinstance(body, SphericalBodyState):
                                for tidx, tile in enumerate(body.tiles):
                                    if tile.tileId == item.tileId and tile.subHexes:
                                        freed_sh = tile.subHexes[item.subHexIndex].model_copy(
                                            update={"buildingId": ""}
                                        )
                                        new_sub_hexes = [
                                            freed_sh if sh.index == item.subHexIndex else sh
                                            for sh in tile.subHexes
                                        ]
                                        body.tiles[tidx] = tile.model_copy(
                                            update={"subHexes": new_sub_hexes}
                                        )
                                        break
                        return
            raise KeyError(f"ConstructionItem '{item_id}' not found for corp '{corp_id}'")

    # ── Building registry public API ──────────────────────────────────────────

    def demolish_building(self, corp_id: str, building_id: str) -> None:
        """Remove a building. Raises KeyError if not found, ValueError if corp mismatch."""
        with self._lock:
            building = self._buildings.get(building_id)
            if building is None:
                raise KeyError(f"Building '{building_id}' not found")
            if building.corpId != corp_id:
                raise ValueError(f"Building '{building_id}' does not belong to '{corp_id}'")
            del self._buildings[building_id]

    def list_corp_buildings(self, corp_id: str) -> list[BuildingData]:
        """Return all buildings belonging to *corp_id*.

        Renamed from list_buildings(corp_id) to avoid collision with the admin
        list_buildings() (no args) that lives on the orchestrator.
        """
        with self._lock:
            return [b for b in self._buildings.values() if b.corpId == corp_id]

    def get_building(self, building_id: str) -> BuildingData | None:
        with self._lock:
            return self._buildings.get(building_id)

    def set_building_worker_ratio(
        self, corp_id: str, building_id: str, worker_ratio: float
    ) -> BuildingData:
        with self._lock:
            building = self._buildings.get(building_id)
            if building is None:
                raise KeyError(f"Building '{building_id}' not found")
            if building.corpId != corp_id:
                raise ValueError(f"Building '{building_id}' does not belong to '{corp_id}'")
            building.workerRatio = max(0.0, min(1.0, worker_ratio))
            return building

    def upgrade_building(self, corp_id: str, building_id: str) -> BuildingData:
        """Increment building level by 1 (max 5). Phase 12."""
        with self._lock:
            building = self._buildings.get(building_id)
            if building is None:
                raise KeyError(f"Building '{building_id}' not found")
            if building.corpId != corp_id:
                raise ValueError(f"Building '{building_id}' does not belong to '{corp_id}'")
            if building.level >= 5:
                raise ValueError(f"Building '{building_id}' is already at max level (5)")
            building.level += 1
            return building

    def downgrade_building(self, corp_id: str, building_id: str) -> BuildingData:
        """Decrement building level by 1 (min 1). Phase 12."""
        with self._lock:
            building = self._buildings.get(building_id)
            if building is None:
                raise KeyError(f"Building '{building_id}' not found")
            if building.corpId != corp_id:
                raise ValueError(f"Building '{building_id}' does not belong to '{corp_id}'")
            if building.level <= 1:
                raise ValueError(f"Building '{building_id}' is already at min level (1)")
            building.level -= 1
            return building

    def _process_building_production(self) -> None:
        """Credit resources per corp per active building each tick.

        If a building has employmentSlots, workerRatio is auto-calculated from tile population.
        Building level (Phase 12): total worker slots and output both scale linearly by level.
        Ecology impact (Phase 11.6): buildings with ecology_impact deplete tile species density.
        """
        # Build tile index for ecology impact: body_id -> tile_id -> tile
        tile_index: dict[str, dict[str, GoldbergTileState]] = {}
        for body_id, body in self._bodies.items():
            if isinstance(body, SphericalBodyState) and body.tiles:
                tile_index[body_id] = {t.tileId: t for t in body.tiles}

        # Reset eco extractions accumulator
        self._eco_extractions = {}

        for building in self._buildings.values():
            corp = self._corporations.get(building.corpId)
            if corp is None:
                continue
            level = building.level

            # Phase 9.6 — auto-calculate workerRatio from tile population
            if building.employmentSlots:
                tile = next(
                    (t for t in corp.claimedTiles if t.tileId == building.tileId), None
                )
                tier_counts: dict[str, int] = {}
                if tile is not None:
                    for pop_tier in tile.population:
                        sc_name = pop_tier.socialClass.name
                        tier_counts[sc_name] = tier_counts.get(sc_name, 0) + pop_tier.count
                total_slots = sum(building.employmentSlots.values()) * level
                workers_present = sum(
                    min(tier_counts.get(sc_name, 0), slots * level)
                    for sc_name, slots in building.employmentSlots.items()
                )
                building.workerRatio = workers_present / total_slots if total_slots > 0 else 0.0

            config = BUILDING_REGISTRY.get_outputs(building.buildingType)
            building_def = BUILDING_REGISTRY.get(building.buildingType)

            # Ecology impact — deplete tile species density
            if building_def and building_def.effects_per_tick.get("ecology_impact", 0.0) != 0.0:
                impact = building_def.effects_per_tick["ecology_impact"]
                species_id = building_def.primary_species
                if (
                    species_id
                    and building.bodyId in tile_index
                    and building.tileId in tile_index[building.bodyId]
                ):
                    tile = tile_index[building.bodyId][building.tileId]
                    for i, sp in enumerate(tile.species):
                        if sp.speciesId == species_id:
                            depletion = abs(impact) * building.workerRatio * level
                            new_density = max(0.0, sp.density - depletion)
                            tile.species[i] = sp.model_copy(update={"density": new_density})

                            if depletion > 0:
                                self._eco_extractions.setdefault(building.bodyId, {}).setdefault(
                                    species_id, 0.0
                                )
                                self._eco_extractions[building.bodyId][species_id] += depletion

                            if new_density == 0.0:
                                config = {}
                            break

            for resource_id, delta in config.items():
                corp.resources[resource_id] = (
                    corp.resources.get(resource_id, 0.0)
                    + delta * building.workerRatio * level
                )
            building.ticksActive += 1
