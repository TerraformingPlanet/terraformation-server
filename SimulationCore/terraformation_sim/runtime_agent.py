from __future__ import annotations

import json
import os
import threading

from .models import (
    AgentAction,
    AgentActionType,
    AgentMemory,
    BuildingType,
    ClaimedTile,
    StateType,
)
from .logic.states import build_scoreboard_entry, compute_nationalization_delay


class AgentMixin:
    """Agent LLM (States + Corporations), FSM bot, and GM world agent methods.

    State accessed via self:
        self._lock, self._states, self._corporations, self._game_events,
        self._reputations, self._agent_memories, self._tick_count,
        self._markets, self._buildings, self._construction_queues,
        self._tile_ownership, self._nationalizations
    """

    # ── Agent LLM (Phase 8.5) ─────────────────────────────────────────────────

    def get_agent_memory(self, state_id: str) -> AgentMemory | None:
        """Return the current in-memory AgentMemory for a state, or None."""
        with self._lock:
            return self._agent_memories.get(state_id)

    def get_agent_context(self, state_id: str) -> dict | None:
        """
        Return a snapshot dict usable as LLM context for the given state.

        Returns None if the state does not exist.
        """
        with self._lock:
            state = self._states.get(state_id)
            if state is None:
                return None
            scoreboard = [
                build_scoreboard_entry(c).model_dump()
                for c in self._corporations.values()
            ]
            recent_events = [
                {"name": ev.name, "description": ev.description, "tick": ev.tick}
                for ev in reversed(self._game_events[-5:])
            ]
            reputations = {
                str(k): v
                for k, v in self._reputations.items()
                if state_id in k
            }
            memory = self._agent_memories.get(state_id)
            return {
                "stateId": state_id,
                "tick": self._tick_count,
                "state": state.model_dump(),
                "scoreboard": scoreboard,
                "recentEvents": recent_events,
                "reputations": reputations,
                "memory": memory.model_dump() if memory else None,
            }

    def run_agent_for_state(self, state_id: str) -> AgentAction:
        """
        Synchronously run one LLM agent cycle for the given state.

        Applies the resulting action and updates agent memory.
        Raises ValueError if the state does not exist.
        """
        with self._lock:
            state = self._states.get(state_id)
            if state is None:
                raise ValueError(f"State {state_id!r} not found")
            tick = self._tick_count
            scoreboard = [
                build_scoreboard_entry(c).model_dump()
                for c in self._corporations.values()
            ]
            recent_events = [
                {"name": ev.name, "description": ev.description, "tick": ev.tick}
                for ev in reversed(self._game_events[-5:])
            ]
            reputations = {
                str(k): v
                for k, v in self._reputations.items()
                if state_id in k
            }
            memory = self._agent_memories.get(state_id)

        # LLM call happens OUTSIDE the lock to avoid blocking the tick loop
        from .logic.agent import run_agent as _run_agent_llm  # lazy import — breaks circular dep
        action = _run_agent_llm(
            state=state,
            tick=tick,
            memory=memory,
            scoreboard=scoreboard,
            recent_events=recent_events,
            reputations=reputations,
        )

        with self._lock:
            self._apply_agent_action_locked(action)
            self._update_agent_memory_locked(state_id, action, tick)

        return action

    def _run_agent_for_state_bg(self, state_id: str) -> None:
        """Background thread wrapper — swallows exceptions to avoid daemon crashes."""
        try:
            self.run_agent_for_state(state_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Agent background run failed for %s: %s", state_id, exc)

    def get_corp_agent_context(self, corp_id: str) -> dict | None:
        """
        Return a snapshot dict usable as LLM context for the given corporation.

        Returns None if the corporation does not exist.
        """
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                return None
            snapshot = self._build_corp_snapshot_locked(corp)
            scoreboard = [
                build_scoreboard_entry(c).model_dump()
                for c in self._corporations.values()
            ]
            recent_events = [
                {"name": ev.name, "description": ev.description, "tick": ev.tick}
                for ev in reversed(self._game_events[-5:])
            ]
            memory = self._agent_memories.get(corp_id)
            return {
                "corpId": corp_id,
                "tick": self._tick_count,
                "corp": corp.model_dump(),
                "environment": {
                    "freeTilesAdjacent": len(snapshot.free_tile_ids_adj),
                    "resourceStocks": snapshot.resource_stocks,
                    "marketPrices": snapshot.market_prices,
                    "rivals": [
                        {"corpId": cid, "adjTiles": cnt}
                        for cid, cnt in snapshot.rival_tile_counts.items()
                    ],
                    "productionBottleneck": snapshot.production_bottleneck,
                    "hasActiveConstruction": snapshot.has_active_construction,
                },
                "scoreboard": scoreboard,
                "recentEvents": recent_events,
                "memory": memory.model_dump() if memory else None,
            }

    def run_agent_for_corp(self, corp_id: str) -> AgentAction:
        """
        Synchronously run one LLM agent cycle for an AI corporation.

        Snapshot is built under lock (fast read), LLM runs outside lock,
        then the resulting action is applied under lock — same pattern as
        run_agent_for_state.
        Raises ValueError if the corporation does not exist.
        """
        from terraformation_sim.logic.agent import run_corp_agent

        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise ValueError(f"Corporation {corp_id!r} not found")
            snapshot = self._build_corp_snapshot_locked(corp)
            tick = self._tick_count
            scoreboard = [
                build_scoreboard_entry(c).model_dump()
                for c in self._corporations.values()
            ]
            recent_events = [
                {"name": ev.name, "description": ev.description, "tick": ev.tick}
                for ev in reversed(self._game_events[-5:])
            ]
            memory = self._agent_memories.get(corp_id)

        # LLM call happens OUTSIDE the lock to avoid blocking the tick loop
        action = run_corp_agent(
            corp=corp,
            tick=tick,
            snapshot=snapshot,
            memory=memory,
            scoreboard=scoreboard,
            recent_events=recent_events,
        )

        with self._lock:
            self._apply_agent_action_locked(action)
            self._update_agent_memory_locked(corp_id, action, tick)

        return action

    def _run_corp_agent_bg(self, corp_id: str) -> None:
        """Background thread wrapper for corpo LLM — swallows exceptions."""
        try:
            self.run_agent_for_corp(corp_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Corp agent background run failed for %s: %s", corp_id, exc
            )

    def _build_corp_snapshot_locked(self, corp) -> "CorpSimSnapshot":
        """Build a read-only world view for one AI corporation.
        Must be called with self._lock held. Fast: only dict lookups.
        """
        from terraformation_sim.logic.corp_fsm import CorpSimSnapshot

        # Adjacent free tiles: neighbors of all claimed tiles not already owned
        free_adj: list[str] = []
        rival_tile_counts: dict[str, int] = {}
        try:
            import h3 as _h3
            for claimed in corp.claimedTiles:
                try:
                    for neighbor in _h3.grid_disk(claimed.tileId, 1):
                        if neighbor == claimed.tileId:
                            continue
                        # Find if owned
                        owner_id = self._tile_ownership.get(claimed.bodyId, {}).get(neighbor)
                        if owner_id is None:
                            if neighbor not in free_adj:
                                free_adj.append(neighbor)
                        elif owner_id != corp.id:
                            rival_tile_counts[owner_id] = rival_tile_counts.get(owner_id, 0) + 1
                except Exception:
                    pass
        except ImportError:
            pass

        # Market prices from first available market for this corp
        market_prices: dict[str, float] = {}
        for mkt in self._markets.values():
            if mkt.ownerEntityId == corp.id:
                for listing in mkt.listings:
                    market_prices[listing.resourceType.name] = listing.price
                break

        # Production bottleneck: any building workerRatio < 0.5
        prod_bottleneck = any(
            b.workerRatio < 0.5
            for b in self._buildings.values()
            if b.corpId == corp.id
        )

        # Active construction queue
        has_construction = any(
            bool(q.items)
            for q in self._construction_queues.values()
            if q.corpId == corp.id
        )

        return CorpSimSnapshot(
            corp_id=corp.id,
            current_tick=self._tick_count,
            free_tile_ids_adj=free_adj,
            credits=corp.credits,
            resource_stocks=dict(corp.resources),
            market_prices=market_prices,
            rival_corp_ids=list(rival_tile_counts.keys()),
            rival_tile_counts=rival_tile_counts,
            production_bottleneck=prod_bottleneck,
            has_active_construction=has_construction,
        )

    def _run_bot_fsm_bg(self, corp_id: str) -> None:
        """Background thread: build snapshot, run FSM (always), then optionally LLM.
        Swallows exceptions to avoid daemon crashes.
        """
        try:
            from terraformation_sim.logic.corp_fsm import (
                compute_fsm_actions,
                compute_next_fsm_state,
            )
            with self._lock:
                corp = self._corporations.get(corp_id)
                if corp is None or not corp.isAI:
                    return
                snapshot = self._build_corp_snapshot_locked(corp)
                current_tick = self._tick_count

            # ←—— hors lock : FSM tourne librement sans bloquer le tick ——→
            new_state = compute_next_fsm_state(corp, snapshot)
            actions = compute_fsm_actions(corp, snapshot, new_state)

            with self._lock:
                corp2 = self._corporations.get(corp_id)
                if corp2 is None:
                    return
                corp2.fsmState = new_state
                self._corporations[corp_id] = corp2
                for action in actions:
                    self._apply_agent_action_locked(action)

            # ── Phase 11.2 M2 — LLM strategic override ───────────────────
            corp_agent_interval = int(
                os.environ.get("CORP_AGENT_TICK_INTERVAL", "50")
            )
            if corp_agent_interval > 0 and current_tick % corp_agent_interval == 0:
                threading.Thread(
                    target=self._run_corp_agent_bg,
                    args=(corp_id,),
                    daemon=True,
                    name=f"corp-llm-{corp_id[:8]}",
                ).start()

        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Bot FSM run failed for corp %s: %s", corp_id, exc
            )

    def _process_bot_tick_locked(self) -> None:
        """Spawn a background FSM thread for each AI corporation.
        Lock must be held (called from _advance_tick_locked).
        """
        for corp in self._corporations.values():
            if corp.isAI:
                threading.Thread(
                    target=self._run_bot_fsm_bg,
                    args=(corp.id,),
                    daemon=True,
                    name=f"bot-fsm-{corp.id[:8]}",
                ).start()

    # ── Phase 11.1 — Agent Monde centralisé ──────────────────────────────────

    def run_world_agent_cycle(self, reason: str = "periodic") -> list[str]:
        """
        Iterate over all AI-controlled States and Corporations and fire their agent.

        Each entity agent runs in a separate daemon thread (non-blocking).
        Returns the list of entity IDs whose agents were triggered.
        """
        with self._lock:
            ai_state_ids = [
                s.id for s in self._states.values()
                if s.isAiControlled and s.stateType != StateType.Alien
            ]
            ai_corp_ids  = [c.id for c in self._corporations.values() if c.isAI]

        triggered: list[str] = []

        for state_id in ai_state_ids:
            threading.Thread(
                target=self._run_agent_for_state_bg,
                args=(state_id,),
                daemon=True,
                name=f"agent-state-{state_id[:8]}",
            ).start()
            triggered.append(state_id)

        # Phase 11.2 — FSM bots run in background threads
        for corp_id in ai_corp_ids:
            threading.Thread(
                target=self._run_bot_fsm_bg,
                args=(corp_id,),
                daemon=True,
                name=f"bot-fsm-{corp_id[:8]}",
            ).start()
            triggered.append(corp_id)

        # Phase 11.3 M1 — GM balance check (runs synchronously, fast)
        self.run_gm_narrative_check()

        return triggered

    def trigger_agent_for_entity(self, entity_id: str, reason: str = "") -> None:
        """
        Trigger an AI agent cycle for a single entity (State or Corporation).

        Runs in a background daemon thread so the caller is not blocked.
        Raises KeyError if no AI entity with that ID exists.
        """
        with self._lock:
            state = self._states.get(entity_id)
            corp  = self._corporations.get(entity_id)
            is_ai_state = state is not None and state.isAiControlled
            is_ai_corp  = corp  is not None and getattr(corp, "isAI", False)

        if is_ai_state:
            threading.Thread(
                target=self._run_agent_for_state_bg,
                args=(entity_id,),
                daemon=True,
                name=f"agent-trigger-{entity_id[:8]}",
            ).start()
        elif is_ai_corp:
            threading.Thread(
                target=self._run_bot_fsm_bg,
                args=(entity_id,),
                daemon=True,
                name=f"bot-trigger-{entity_id[:8]}",
            ).start()
        else:
            raise KeyError(f"Entity {entity_id!r} not found or not AI-controlled")

    def _get_ai_state_ids_near_tile_locked(self, body_id: str, tile_id: str) -> list[str]:
        """
        Return AI-controlled state IDs whose territory includes H3 neighbors of tile_id.
        Used to trigger agents when a player claims a nearby tile.
        Must be called under self._lock.
        """
        try:
            import h3 as _h3
            neighbors = set(_h3.grid_disk(tile_id, 1))
        except Exception:
            return []

        result: list[str] = []
        for state in self._states.values():
            if state.isAiControlled and neighbors.intersection(state.tileIds):
                result.append(state.id)
        return result

    def _apply_agent_action_locked(self, action: AgentAction) -> None:
        """Dispatch an agent action (State or Corporation). Must be called under self._lock."""
        from terraformation_sim.models import AgentActionType as _AAT

        # —— Corporation FSM actions (Phase 11.2) ——
        if action.actionType == _AAT.ClaimTile:
            corp = self._corporations.get(action.entityId)
            if corp is None:
                return
            tile_id = action.params.get("tile_id", "")
            # Find which body has that tile as a neighbor (use first claimed tile's body)
            body_id = corp.claimedTiles[0].bodyId if corp.claimedTiles else ""
            if tile_id and body_id:
                try:
                    existing = self._tile_ownership.get(body_id, {}).get(tile_id)
                    if existing is None:
                        self._tile_ownership.setdefault(body_id, {})[tile_id] = corp.id
                        from terraformation_sim.models import ClaimedTile
                        from terraformation_sim.logic.states import auto_init_tile_population
                        new_tile = auto_init_tile_population(
                            ClaimedTile(bodyId=body_id, tileId=tile_id)
                        )
                        corp.claimedTiles.append(new_tile)
                        self._corporations[corp.id] = corp
                except Exception:
                    pass
            return

        if action.actionType == _AAT.ConstructBuilding:
            corp = self._corporations.get(action.entityId)
            if corp is None:
                return
            tile_id  = action.params.get("tile_id", "")
            btype_nm = action.params.get("building_type", "")
            body_id  = corp.claimedTiles[0].bodyId if corp.claimedTiles else ""
            if tile_id and btype_nm and body_id:
                try:
                    bt = BuildingType[btype_nm]
                    self._enqueue_construction_locked(corp.id, body_id, tile_id, bt)
                except Exception:
                    pass
            return

        if action.actionType == _AAT.UpdateFsmThresholds:
            corp = self._corporations.get(action.entityId)
            if corp is not None:
                corp.fsmThresholds.update(action.params)
                self._corporations[corp.id] = corp
            return

        if action.actionType == _AAT.ReorderConstructionQueue:
            # params: {"territory_id": str, "new_order": list[str]} (item IDs)
            territory_id = action.params.get("territory_id", "")
            new_order: list[str] = action.params.get("new_order", [])
            queue = self._construction_queues.get(territory_id)
            if queue and new_order:
                id_to_item = {item.id: item for item in queue.items}
                reordered = [id_to_item[iid] for iid in new_order if iid in id_to_item]
                # Append any items not mentioned in new_order at the end
                mentioned = set(new_order)
                reordered += [item for item in queue.items if item.id not in mentioned]
                queue.items = reordered
                self._construction_queues[territory_id] = queue
            return

        # —— State agent actions (Phase 8.5) ——
        state = self._states.get(action.entityId)
        if state is None:
            return
        if action.actionType == AgentActionType.SetTolerance:
            new_threshold = float(action.params.get("newThreshold", state.toleranceThreshold))
            state.toleranceThreshold = max(0.0, min(1.0, new_threshold))
            self._states[action.entityId] = state
        elif action.actionType == AgentActionType.TriggerNationalization:
            # Delegate to existing nationalization logic via a synthetic call
            target_corp_id = action.params.get("targetCorpId", "")
            tile_id = action.params.get("tileId", "")
            if target_corp_id and tile_id:
                from uuid import uuid4
                from .models import NationalizationProcess
                delay_ticks = compute_nationalization_delay(state)
                proc_id = str(uuid4())
                process = NationalizationProcess(
                    id=proc_id,
                    stateId=action.entityId,
                    corpId=target_corp_id,
                    tileId=tile_id,
                    startTick=self._tick_count,
                    completionTick=self._tick_count + delay_ticks,
                    cancelled=False,
                )
                self._nationalizations[proc_id] = process
        # ProposeContract and NoOp are deferred / no-op at MVP stage

    def _update_agent_memory_locked(self, state_id: str, action: AgentAction, tick: int) -> None:
        """Update rolling AgentMemory after an action. Must be called under self._lock."""
        mem = self._agent_memories.get(state_id) or AgentMemory(entityId=state_id)
        decision_summary = f"[tick {tick}] {action.actionType.name}: {json.dumps(action.params)}"
        mem.recentDecisions = (mem.recentDecisions + [decision_summary])[-5:]
        mem.lastTickActed = tick
        self._agent_memories[state_id] = mem
