from __future__ import annotations

from uuid import uuid4

from .models import (
    EcoMarketState,
    EventData,
    EventEffect,
    EventType,
    StateType,
    SphericalBodyState,
)
from .logic.events import draw_event, apply_event_to_corporation
from .logic.eco_market import compute_eco_market
from .logic.states import build_scoreboard_entry


class EventsMixin:
    """Gameplay events, ecology tick, eco-market tick, and GM narrative methods.

    State accessed via self:
        self._lock, self._game_events, self._event_rng, self._corporations,
        self._states, self._bodies, self._eco_markets, self._eco_extractions,
        self._bio_tile_history, self._tick_count, self._gm_cooldown_tick,
        self._gm_last_lever, self._territories, self._tile_ownership
    """

    _EVENT_TICK_PROBABILITY: float = 0.05  # 5 % chance of event per tick

    # ── Gameplay Events (Phase 8) ─────────────────────────────────────────────

    def _process_event_tick_locked(self) -> None:
        """Maybe draw and record a gameplay event this tick. Assumes lock held."""
        if self._event_rng.random() > self._EVENT_TICK_PROBABILITY:
            return
        # Pick one active corporation as affected entity, or leave blank
        corp_id = ""
        if self._corporations:
            corp_id = self._event_rng.choice(list(self._corporations.keys()))
        event = draw_event(self._tick_count, self._event_rng, corp_id)
        # Apply economic effects immediately to the corporation
        if corp_id and corp_id in self._corporations:
            self._corporations[corp_id] = apply_event_to_corporation(
                event, self._corporations[corp_id]
            )
        self._game_events.append(event)
        # Keep at most 200 events in memory
        if len(self._game_events) > 200:
            self._game_events = self._game_events[-200:]

    def _process_ecology_tick_locked(self) -> None:
        """Advance species populations on all colonized spherical bodies. Assumes lock held.

        Species densities (e.g. forest density = remaining trees on tile) evolve each tick.
        The aggregate body.ecologyResources reflects total potential yield — actual resource
        production (Wood, etc.) is handled by buildings (scieries) reading tile forest density.
        """
        from terraformation_sim.logic.ecology import compute_tile_ecology, aggregate_ecology_output, compute_terrain_transition
        from terraformation_sim.models import SphericalBodyState
        for body_id, body in self._bodies.items():
            if not isinstance(body, SphericalBodyState) or not body.tiles:
                continue
            o2_ratio = body.atmosphere.fraction_of("O2")
            updated_tiles = []
            for tile in body.tiles:
                new_species = compute_tile_ecology(tile, o2_ratio)
                new_terrain = compute_terrain_transition(tile, new_species)
                updated_tile = tile.model_copy(update={"species": new_species, "terrainType": new_terrain})
                updated_tiles.append(updated_tile)
                self._update_bio_tile_history_locked(updated_tile)
            body.tiles = updated_tiles
            body.ecologyResources = aggregate_ecology_output(updated_tiles)
            self._bodies[body_id] = body

    def _process_eco_market_tick_locked(self) -> None:
        """Compute eco-market state for all spherical bodies. Assumes lock held.

        Called after ecology tick to reflect updated species densities and extractions.
        """
        from terraformation_sim.models import SphericalBodyState
        for body_id, body in self._bodies.items():
            if not isinstance(body, SphericalBodyState) or not body.tiles:
                continue
            extractions = self._eco_extractions.get(body_id, {})
            listings = compute_eco_market(body.tiles, extractions, self._tick_count)
            self._eco_markets[body_id] = EcoMarketState(
                bodyId=body_id,
                listings=listings,
                tickComputed=self._tick_count,
            )

    def list_game_events(self, limit: int = 20) -> list[EventData]:
        """Return the *limit* most recent gameplay events (latest first)."""
        with self._lock:
            return list(reversed(self._game_events[-limit:]))

    def _inject_event_locked(self, event: EventData) -> None:
        """Append *event* to _game_events and trim to 200. Caller must hold the lock."""
        self._game_events.append(event)
        if len(self._game_events) > 200:
            self._game_events = self._game_events[-200:]

    # ── Phase 11.3 M2+M3 — GM lever helpers ─────────────────────────────────

    def _build_gm_context_locked(self) -> dict:
        """
        Build an enriched context dict for GM lever selection.

        Caller MUST hold self._lock.
        Returns a dict with keys: imbalanceRatio, mostColonizedBodyId,
        candidateTileIds, allTileIds, allCorpIds, topCorpId, tick.
        """
        from .logic.gm import compute_leaderboard_imbalance

        scoreboard = [build_scoreboard_entry(c) for c in self._corporations.values()]
        imbalance_ratio = compute_leaderboard_imbalance(scoreboard)

        # Per-body owned-tile sets (via _tile_ownership)
        owned_per_body: dict[str, set[str]] = {}
        for body_id, tile_map in self._tile_ownership.items():
            owned_per_body.setdefault(body_id, set()).update(tile_map.keys())

        # Body with the most claimed tiles = most colonized
        most_colonized_body_id = ""
        max_owned = 0
        for body_id, owned_set in owned_per_body.items():
            if len(owned_set) > max_owned:
                max_owned = len(owned_set)
                most_colonized_body_id = body_id

        # Free tiles on that body (candidate landing zones)
        candidate_tile_ids: list[str] = []
        if most_colonized_body_id and most_colonized_body_id in self._bodies:
            body = self._bodies[most_colonized_body_id]
            owned_on_body = owned_per_body.get(most_colonized_body_id, set())
            candidate_tile_ids = [
                t.tileId for t in body.tiles if t.tileId not in owned_on_body
            ]

        # All tile IDs across every body (for empire_galactique)
        all_tile_ids: list[str] = [
            t.tileId
            for body in self._bodies.values()
            for t in body.tiles
        ]

        top_corp_id = ""
        if scoreboard:
            top_entry = max(scoreboard, key=lambda e: e.score)
            top_corp_id = top_entry.corpId

        return {
            "imbalanceRatio": imbalance_ratio,
            "mostColonizedBodyId": most_colonized_body_id,
            "candidateTileIds": candidate_tile_ids,
            "allTileIds": all_tile_ids,
            "allCorpIds": list(self._corporations.keys()),
            "topCorpId": top_corp_id,
            "tick": self._tick_count,
        }

    def execute_gm_lever(self, lever_name: str, context: dict) -> None:
        """
        Dispatch and execute a GM narrative lever.

        Safe to call without holding the lock — internal helpers manage
        locking appropriately.

        Supported levers:
            "alien_pop"        — spawn a small alien State + RencontreAlienne event
            "megastructure"    — inject a DecouverteMegastructure event
            "empire_galactique"— spawn a large alien State + EmpireGalactique event per corp
        """
        from .logic.gm import (
            build_alien_pop_plan,
            build_megastructure_plan,
            build_empire_galactique_plan,
        )

        tick = context.get("tick", 0)

        if lever_name == "alien_pop":
            candidate_tile_ids = context.get("candidateTileIds", [])
            tile_ids = build_alien_pop_plan(tick, candidate_tile_ids, n=6)
            state = self.create_state(
                name=f"Pop Alien {tick}",
                state_type=StateType.Alien,
                tile_ids=tile_ids,
                bureaucracy=0.05,
                corruption_rate=0.0,
                tolerance_threshold=0.0,
                is_ai_controlled=True,
            )
            event = EventData(
                id=str(uuid4()),
                eventType=EventType.RencontreAlienne,
                name="Première Rencontre Aliène",
                description=(
                    f"Une population alien inconnue a été détectée au tique {tick}."
                ),
                tick=tick,
                affectedEntityId=state.id,
                affectedEntityType="state",
                effect=EventEffect(),
                isResolved=False,
            )
            with self._lock:
                self._inject_event_locked(event)

        elif lever_name == "megastructure":
            event_name, description = build_megastructure_plan(tick)
            candidate_tile_ids = context.get("candidateTileIds", [])
            affected_tile = candidate_tile_ids[0] if candidate_tile_ids else ""
            event = EventData(
                id=str(uuid4()),
                eventType=EventType.DecouverteMegastructure,
                name=event_name,
                description=description,
                tick=tick,
                affectedEntityId=affected_tile,
                affectedEntityType="tile",
                effect=EventEffect(),
                isResolved=False,
            )
            with self._lock:
                self._inject_event_locked(event)

        elif lever_name == "empire_galactique":
            all_tile_ids = context.get("allTileIds", [])
            tile_ids = build_empire_galactique_plan(tick, all_tile_ids, n=15)
            state = self.create_state(
                name=f"Empire Galactique {tick}",
                state_type=StateType.Alien,
                tile_ids=tile_ids,
                bureaucracy=0.02,
                corruption_rate=0.0,
                tolerance_threshold=0.0,
                is_ai_controlled=True,
            )
            all_corp_ids = context.get("allCorpIds", [])
            with self._lock:
                for corp_id in all_corp_ids:
                    event = EventData(
                        id=str(uuid4()),
                        eventType=EventType.EmpireGalactique,
                        name="Ultimatum de l'Empire Galactique",
                        description=(
                            f"L'Empire Galactique exige votre soumission au tique {tick}."
                        ),
                        tick=tick,
                        affectedEntityId=corp_id,
                        affectedEntityType="corporation",
                        effect=EventEffect(),
                        isResolved=False,
                    )
                    self._inject_event_locked(event)

    def run_gm_narrative_check(self) -> str | None:
        """
        Phase 11.3 — Detect leaderboard imbalance, select and execute a GM lever.

        Runs synchronously (pure detection + plan-builders, no LLM call).
        Returns the lever name selected, or None when cooldown is active or
        no imbalance is detected.

        Cooldown duration is read from GM_COOLDOWN_TICKS env var (default 20).
        Imbalance threshold from GM_IMBALANCE_THRESHOLD (default 2.5).
        """
        import os as _os
        from .logic.gm import pick_gm_lever
        import logging

        with self._lock:
            current_tick = self._tick_count
            cooldown_tick = self._gm_cooldown_tick
            last_lever = self._gm_last_lever
            context = self._build_gm_context_locked()

        if current_tick < cooldown_tick:
            return None

        cooldown_duration = int(_os.environ.get("GM_COOLDOWN_TICKS", "20"))
        threshold = float(_os.environ.get("GM_IMBALANCE_THRESHOLD", "2.5"))

        if context["imbalanceRatio"] < threshold:
            return None

        lever = pick_gm_lever(last_lever, context)

        with self._lock:
            self._gm_cooldown_tick = current_tick + cooldown_duration
            self._gm_last_lever = lever

        logging.getLogger(__name__).info(
            "GM narrative check: lever=%r at tick=%d", lever, current_tick
        )

        if lever != "none":
            self.execute_gm_lever(lever, context)

        return lever
