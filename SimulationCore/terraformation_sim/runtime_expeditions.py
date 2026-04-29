from __future__ import annotations

from uuid import uuid4

from .models import (
    ClaimedTile,
    ConstructionItem,
    ConstructionStatus,
    EventData,
    EventEffect,
    EventType,
    ExpeditionStatus,
    ExpeditionUnit,
    TerritoryQueue,
    TradeRoute,
    TradeRouteActivityStatus,
    TradeRouteType,
)
from .logic.expeditions import (
    compute_expedition_path,
    compute_expedition_total_ticks,
    compute_route_efficiency,
    propagate_prices,
)
from .logic.market import auto_init_tile_population


_EXPEDITION_CONFIG_ATTENUATION: dict[str, float] = {
    "Land":     0.7,
    "Maritime": 0.8,
    "Orbital":  0.9,
}


class ExpeditionsMixin:
    """Trade route and expedition lifecycle, plus construction item listing.

    State accessed via self:
        self._lock, self._corporations, self._tile_ownership, self._trade_routes,
        self._expeditions, self._construction_queues, self._markets, self._buildings,
        self._game_events, self._expedition_rng, self._tick_count, self._repo
    """

    # ── Trade Routes (Phase 9.2) ───────────────────────────────────────────────

    def create_trade_route(
        self,
        corp_id: str,
        body_id: str,
        from_tile_id: str,
        to_tile_id: str,
        route_type: int = 0,
    ) -> TradeRoute:
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            owned = self._tile_ownership.get(body_id, {})
            if owned.get(from_tile_id) != corp_id:
                raise ValueError(f"Tile '{from_tile_id}' is not claimed by '{corp_id}'")
            if owned.get(to_tile_id) != corp_id:
                raise ValueError(f"Tile '{to_tile_id}' is not claimed by '{corp_id}'")
            rt = TradeRouteType(route_type)
            path = compute_expedition_path(from_tile_id, to_tile_id, rt)
            route = TradeRoute(
                id=str(uuid4()),
                routeType=rt,
                fromTileId=from_tile_id,
                toTileId=to_tile_id,
                bodyId=body_id,
                pathTileIds=path,
                ownerCorpId=corp_id,
                tickCreated=self._tick_count,
            )
            self._trade_routes[route.id] = route
            self._repo.save_trade_route(route)
            return route

    def list_trade_routes(self, corp_id: str = "") -> list[TradeRoute]:
        with self._lock:
            routes = list(self._trade_routes.values())
            if corp_id:
                routes = [r for r in routes if r.ownerCorpId == corp_id]
            return routes

    def get_trade_route(self, route_id: str) -> TradeRoute | None:
        with self._lock:
            return self._trade_routes.get(route_id)

    def suspend_trade_route(self, route_id: str) -> TradeRoute:
        with self._lock:
            route = self._trade_routes.get(route_id)
            if route is None:
                raise KeyError(f"Trade route '{route_id}' not found")
            updated = route.model_copy(update={"status": TradeRouteActivityStatus.Suspended})
            self._trade_routes[route_id] = updated
            self._repo.save_trade_route(updated)
            return updated

    def resume_trade_route(self, route_id: str) -> TradeRoute:
        with self._lock:
            route = self._trade_routes.get(route_id)
            if route is None:
                raise KeyError(f"Trade route '{route_id}' not found")
            updated = route.model_copy(update={"status": TradeRouteActivityStatus.Active})
            self._trade_routes[route_id] = updated
            self._repo.save_trade_route(updated)
            return updated

    def delete_trade_route(self, route_id: str) -> None:
        with self._lock:
            if route_id not in self._trade_routes:
                raise KeyError(f"Trade route '{route_id}' not found")
            del self._trade_routes[route_id]
            self._repo.delete_trade_route(route_id)

    # ── Expeditions (Phase 9.2) ────────────────────────────────────────────────

    def launch_expedition(
        self,
        corp_id: str,
        route_id: str,
        cargo: dict[str, float] | None = None,
    ) -> ExpeditionUnit:
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            route = self._trade_routes.get(route_id)
            if route is None:
                raise KeyError(f"Trade route '{route_id}' not found")
            if route.ownerCorpId != corp_id:
                raise ValueError(f"Route '{route_id}' does not belong to '{corp_id}'")
            path = compute_expedition_path(route.fromTileId, route.toTileId, route.routeType)
            total_ticks = compute_expedition_total_ticks(path, route.routeType)
            expedition = ExpeditionUnit(
                id=str(uuid4()),
                ownerCorpId=corp_id,
                fromPortTileId=route.fromTileId,
                toPortTileId=route.toTileId,
                bodyId=route.bodyId,
                routeType=route.routeType,
                ticksRemaining=total_ticks,
                totalTicks=total_ticks,
                pathTileIds=path,
                cargo=cargo or {},
            )
            self._expeditions[expedition.id] = expedition
            self._repo.save_expedition(expedition)
            return expedition

    def list_construction_items(self, corp_id: str = "") -> list[ConstructionItem]:
        """Return all non-done ConstructionItems, optionally filtered to one corporation."""
        with self._lock:
            items: list[ConstructionItem] = []
            for q in self._construction_queues.values():
                if corp_id and q.corpId != corp_id:
                    continue
                for item in q.items:
                    if item.status != ConstructionStatus.Done:
                        items.append(item)
            return items

    def get_territory_queue(self, corp_id: str, body_id: str, tile_id: str) -> TerritoryQueue | None:
        """Return the TerritoryQueue that contains tile_id for corp_id on body_id, or None."""
        with self._lock:
            for q in self._construction_queues.values():
                if q.corpId == corp_id and q.bodyId == body_id and tile_id in q.tileIds:
                    return q
            return None

    def list_expeditions(self, corp_id: str = "") -> list[ExpeditionUnit]:
        with self._lock:
            exps = list(self._expeditions.values())
            if corp_id:
                exps = [e for e in exps if e.ownerCorpId == corp_id]
            return exps

    def get_expedition(self, expedition_id: str) -> ExpeditionUnit | None:
        with self._lock:
            return self._expeditions.get(expedition_id)

    def _process_expedition_tick_locked(self) -> None:
        """Tick all active expeditions and update route efficiencies. Lock must be held."""
        _FAIL_PROB  = 0.02
        _DELAY_PROB = 0.05
        _DELAY_TICKS = 2
        _TRAVEL_EVENT_PROB = 0.03

        for exp_id, expedition in list(self._expeditions.items()):
            if expedition.status != ExpeditionStatus.InTransit:
                continue
            # Roll for failure
            if self._expedition_rng.random() < _FAIL_PROB:
                self._expeditions[exp_id] = expedition.model_copy(
                    update={"status": ExpeditionStatus.Failed}
                )
                continue
            # Roll for delay
            if self._expedition_rng.random() < _DELAY_PROB:
                expedition = expedition.model_copy(
                    update={"ticksRemaining": expedition.ticksRemaining + _DELAY_TICKS}
                )
                self._expeditions[exp_id] = expedition
            # Roll for travel event
            if self._expedition_rng.random() < _TRAVEL_EVENT_PROB:
                event_type = self._expedition_rng.choice([
                    EventType.Piraterie,
                    EventType.Panne,
                    EventType.Decouverte,
                ])
                event_name = {
                    EventType.Piraterie: "Attaque de pirates",
                    EventType.Panne: "Panne mécanique",
                    EventType.Decouverte: "Découverte stellaire",
                }[event_type]
                event_desc = {
                    EventType.Piraterie: f"L'expédition {exp_id} a été attaquée par des pirates spatiaux.",
                    EventType.Panne: f"L'expédition {exp_id} a subi une panne mécanique.",
                    EventType.Decouverte: f"L'expédition {exp_id} a fait une découverte stellaire précieuse.",
                }[event_type]

                effect = EventEffect()
                if event_type == EventType.Piraterie:
                    if expedition.cargo:
                        lost_resource = self._expedition_rng.choice(list(expedition.cargo.keys()))
                        lost_amount = expedition.cargo[lost_resource] * 0.5
                        effect.resourceType = lost_resource
                        effect.resourceDelta = -lost_amount
                elif event_type == EventType.Panne:
                    expedition = expedition.model_copy(
                        update={"ticksRemaining": expedition.ticksRemaining + 1}
                    )
                    self._expeditions[exp_id] = expedition
                elif event_type == EventType.Decouverte:
                    effect.reputationDelta = 0.1

                event = EventData(
                    id=f"travel_event_{self._tick_count}_{exp_id}",
                    eventType=event_type,
                    name=event_name,
                    description=event_desc,
                    tick=self._tick_count,
                    affectedEntityId=expedition.ownerCorpId,
                    affectedEntityType="corporation",
                    effect=effect,
                )
                # BUG FIX: was self._events.append(event) — attribute doesn't exist
                self._game_events.append(event)

                if expedition.ownerCorpId in self._corporations:
                    corp = self._corporations[expedition.ownerCorpId]
                    if effect.resourceType and effect.resourceDelta < 0:
                        corp.resources[effect.resourceType] = max(
                            0.0,
                            corp.resources.get(effect.resourceType, 0.0) + effect.resourceDelta,
                        )
                    if effect.reputationDelta != 0:
                        corp.globalReputation = max(
                            0.0, min(1.0, corp.globalReputation + effect.reputationDelta)
                        )
                    self._corporations[expedition.ownerCorpId] = corp

            # Advance
            remaining = expedition.ticksRemaining - 1
            if remaining <= 0:
                dest_corp_id = ""
                for body_ownership in self._tile_ownership.values():
                    if expedition.toPortTileId in body_ownership:
                        dest_corp_id = body_ownership[expedition.toPortTileId]
                        break
                if dest_corp_id and dest_corp_id in self._corporations:
                    dest_corp = self._corporations[dest_corp_id]
                    for resource_key, amount in expedition.cargo.items():
                        dest_corp.resources[resource_key] = (
                            dest_corp.resources.get(resource_key, 0.0) + amount
                        )

                # Caravane colonisation (Phase 10 M5): land expedition on unclaimed tile claims it
                if (
                    expedition.routeType == TradeRouteType.Land
                    and expedition.ownerCorpId
                    and expedition.bodyId
                    and expedition.toPortTileId
                ):
                    body_ownership = self._tile_ownership.setdefault(expedition.bodyId, {})
                    if expedition.toPortTileId not in body_ownership:
                        body_ownership[expedition.toPortTileId] = expedition.ownerCorpId
                        owner_corp = self._corporations.get(expedition.ownerCorpId)
                        if owner_corp is not None:
                            new_tile = auto_init_tile_population(
                                ClaimedTile(bodyId=expedition.bodyId, tileId=expedition.toPortTileId)
                            )
                            owner_corp.claimedTiles.append(new_tile)

                self._expeditions[exp_id] = expedition.model_copy(
                    update={"ticksRemaining": 0, "status": ExpeditionStatus.Success}
                )
            else:
                self._expeditions[exp_id] = expedition.model_copy(
                    update={"ticksRemaining": remaining}
                )

        # Update route efficiencies and propagate prices
        all_buildings = list(self._buildings.values())
        for route_id, route in list(self._trade_routes.items()):
            if route.status != TradeRouteActivityStatus.Active:
                continue
            malus_from, malus_to, efficiency = compute_route_efficiency(route, all_buildings)
            self._trade_routes[route_id] = route.model_copy(update={
                "portMalusFrom":    malus_from,
                "portMalusTo":      malus_to,
                "currentEfficiency": efficiency,
            })
            market_from = next(
                (m for m in self._markets.values() if route.fromTileId in m.tileIds), None
            )
            market_to = next(
                (m for m in self._markets.values() if route.toTileId in m.tileIds), None
            )
            if market_from is not None and market_to is not None:
                attenuation = (
                    _EXPEDITION_CONFIG_ATTENUATION.get(route.routeType.name, 0.7) * efficiency
                )
                updated_from, updated_to = propagate_prices(market_from, market_to, attenuation)
                self._markets[market_from.territoryId] = updated_from
                self._markets[market_to.territoryId] = updated_to
