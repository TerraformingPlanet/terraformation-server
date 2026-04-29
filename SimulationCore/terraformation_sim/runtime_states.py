from __future__ import annotations

from uuid import uuid4

from .models import (
    StateData,
    StateType,
    NationalizationProcess,
    ReputationEvent,
    ReputationEventReason,
    ScoreboardEntry,
    _corp_color_rgb,
    _state_color_rgb,
)
from .logic.states import (
    compute_tolerance_score,
    compute_nationalization_delay,
    apply_reputation_event,
    can_corrupt_nationalization,
    apply_bribe,
    build_scoreboard_entry,
    REPUTATION_DELTAS,
)


class StatesMixin:
    """State registry, reputation, nationalisation, and scoreboard methods.

    State accessed via self:
        self._lock, self._states, self._corporations, self._territories,
        self._territory_tile_index, self._tile_ownership, self._reputations,
        self._nationalizations, self._contracts, self._tick_count, self._repo
    """

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 7.5 — States & Reputation: public API
    # ══════════════════════════════════════════════════════════════════════════

    def create_state(
        self,
        name: str,
        state_type: StateType,
        tile_ids: list[str],
        bureaucracy: float = 0.1,
        corruption_rate: float = 0.1,
        tolerance_threshold: float = 0.5,
        is_ai_controlled: bool = False,
    ) -> StateData:
        """Register a new in-game State on the server."""
        with self._lock:
            state_id = str(uuid4())
            state = StateData(
                id=state_id,
                name=name,
                stateType=state_type,
                tileIds=list(tile_ids),
                bureaucracy=max(0.0, min(1.0, bureaucracy)),
                corruptionRate=max(0.0, min(1.0, corruption_rate)),
                toleranceThreshold=tolerance_threshold,
                isAiControlled=is_ai_controlled,
            )
            self._states[state_id] = state
            self._repo.save_state(state)
            return state

    def get_state(self, state_id: str) -> StateData | None:
        with self._lock:
            return self._states.get(state_id)

    def list_states(self) -> list[StateData]:
        with self._lock:
            return list(self._states.values())

    def get_tile_state(self, body_id: str, tile_id: str) -> dict | None:
        """Return the StateData and TerritoryData owning a tile, or None if unowned."""
        with self._lock:
            territory_id = self._territory_tile_index.get(f"{body_id}::{tile_id}")
            if territory_id is None:
                return None
            territory = self._territories.get(territory_id)
            if territory is None:
                return None
            state = self._states.get(territory.stateId)
            return {"state": state, "territory": territory}

    def get_body_state_tile_colors(self, body_id: str) -> list[dict]:
        """Return compact {tileId, stateId, stateName, profileKey} for all state-owned tiles on a body."""
        with self._lock:
            prefix = f"{body_id}::"
            result: list[dict] = []
            # Cache per territory to avoid repeated dict lookups
            terr_cache: dict[str, dict] = {}
            for key, territory_id in self._territory_tile_index.items():
                if not key.startswith(prefix):
                    continue
                tile_id = key[len(prefix):]
                if territory_id not in terr_cache:
                    terr = self._territories.get(territory_id)
                    if terr is None:
                        continue
                    st = self._states.get(terr.stateId)
                    if st is None:
                        continue
                    terr_cache[territory_id] = {
                        "stateId": st.id,
                        "stateName": st.name,
                        "profileKey": st.profileKey,
                    }
                info = terr_cache[territory_id]
                color_r, color_g, color_b = _state_color_rgb(info["stateId"])
                result.append({
                    "tileId": tile_id,
                    "stateId": info["stateId"],
                    "stateName": info["stateName"],
                    "profileKey": info["profileKey"],
                    "colorR": color_r,
                    "colorG": color_g,
                    "colorB": color_b,
                })
            return result

    def get_body_ownership_tiles(self, body_id: str) -> list[dict]:
        """Return compact {tileId, corpId, colorR, colorG, colorB} for all claimed tiles on a body."""
        with self._lock:
            prefix = f"{body_id}::"
            result: list[dict] = []
            # Cache per corp to avoid repeated color calculations
            corp_cache: dict[str, tuple[float, float, float]] = {}
            for key, corp_id in self._tile_ownership.items():
                if not key.startswith(prefix):
                    continue
                tile_id = key[len(prefix):]
                if corp_id not in corp_cache:
                    corp_cache[corp_id] = _corp_color_rgb(corp_id)
                color_r, color_g, color_b = corp_cache[corp_id]
                result.append({
                    "tileId": tile_id,
                    "corpId": corp_id,
                    "colorR": color_r,
                    "colorG": color_g,
                    "colorB": color_b,
                })
            return result

    def get_reputation(self, source_id: str, target_id: str) -> float:
        """Return bilateral reputation score from source_id toward target_id."""
        with self._lock:
            return self._reputations.get((source_id, target_id), 0.0)

    def list_reputations(self, corp_id: str) -> dict[str, float]:
        """Return a mapping of target_id → bilateral score for all scores involving corp_id."""
        with self._lock:
            result: dict[str, float] = {}
            for (src, tgt), score in self._reputations.items():
                if src == corp_id:
                    result[tgt] = score
            return result

    def corrupt_nationalization(
        self,
        process_id: str,
        corp_id: str,
        bribe_amount: float,
    ) -> NationalizationProcess:
        """Attempt to cancel a nationalisation via a bribe.

        Raises ValueError if the attempt is not allowed or corporation is not found.
        Deducts the bribe from corp credits and marks the process cancelled.
        Emits a CorruptionDetected ReputationEvent (penalty for the bribing corp).
        """
        with self._lock:
            process = self._nationalizations.get(process_id)
            if process is None:
                raise ValueError(f"Nationalisation process '{process_id}' not found")
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise ValueError(f"Corporation '{corp_id}' not found")

            ok, reason = can_corrupt_nationalization(corp, process, bribe_amount, self._tick_count)
            if not ok:
                raise ValueError(reason)

            new_process, new_corp = apply_bribe(corp, process, bribe_amount)
            self._nationalizations[process_id] = new_process
            self._corporations[corp_id] = new_corp
            self._repo.save_nationalization(new_process)
            self._repo.save_corporation(new_corp)

            # Corruption detected — reputation hit
            event = ReputationEvent(
                sourceId=process.stateId,
                targetId=corp_id,
                deltaGlobal=REPUTATION_DELTAS[ReputationEventReason.CorruptionDetected][0],
                deltaBilateral=REPUTATION_DELTAS[ReputationEventReason.CorruptionDetected][1],
                reason=ReputationEventReason.CorruptionDetected,
                tick=self._tick_count,
            )
            self._apply_reputation_event_locked(event)
            return new_process

    def cancel_nationalization_via_contract(
        self,
        process_id: str,
        contract_id: str,
    ) -> NationalizationProcess:
        """Cancel a nationalisation process by honouring a contract with the state.

        The contract must exist, be accepted, and have the State as the proposer.
        Raises ValueError if preconditions are not met.
        """
        with self._lock:
            process = self._nationalizations.get(process_id)
            if process is None:
                raise ValueError(f"Nationalisation process '{process_id}' not found")
            if process.cancelled:
                raise ValueError("Nationalisation already cancelled")
            contract = self._contracts.get(contract_id)
            if contract is None:
                raise ValueError(f"Contract '{contract_id}' not found")
            if contract.proposerId != process.stateId:
                raise ValueError("Contract proposer must be the State that initiated nationalisation")

            new_process = process.model_copy(update={"cancelled": True})
            self._nationalizations[process_id] = new_process
            self._repo.save_nationalization(new_process)

            event = ReputationEvent(
                sourceId=process.stateId,
                targetId=process.corpId,
                deltaGlobal=REPUTATION_DELTAS[ReputationEventReason.NationalizationCancelled][0],
                deltaBilateral=REPUTATION_DELTAS[ReputationEventReason.NationalizationCancelled][1],
                reason=ReputationEventReason.NationalizationCancelled,
                tick=self._tick_count,
            )
            self._apply_reputation_event_locked(event)
            return new_process

    def list_nationalizations(self, corp_id: str | None = None) -> list[NationalizationProcess]:
        """Return all nationalisation processes, optionally filtered by corp."""
        with self._lock:
            if corp_id:
                return [p for p in self._nationalizations.values() if p.corpId == corp_id]
            return list(self._nationalizations.values())

    def get_scoreboard(self) -> list[ScoreboardEntry]:
        """Return all corporations sorted by composite score descending."""
        with self._lock:
            entries = [build_scoreboard_entry(c) for c in self._corporations.values()]
            entries.sort(key=lambda e: e.score, reverse=True)
            return entries

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _apply_reputation_event_locked(self, event: ReputationEvent) -> None:
        """Apply global and bilateral deltas. Assumes lock already held."""
        corp = self._corporations.get(event.targetId)
        if corp is not None:
            self._corporations[event.targetId] = apply_reputation_event(corp, event)
        key = (event.sourceId, event.targetId)
        self._reputations[key] = self._reputations.get(key, 0.0) + event.deltaBilateral
        self._repo.upsert_reputation(event.sourceId, event.targetId, self._reputations[key])

    def _process_reputation_tick_locked(self) -> None:
        """Evaluate nationalisations each tick. Assumes lock already held."""
        broken_counts: dict[str, int] = {}
        for contract in self._contracts.values():
            from .models import ContractStatus as _CS
            if contract.status == _CS.Broken and contract.acceptorId:
                broken_counts[contract.acceptorId] = broken_counts.get(contract.acceptorId, 0) + 1

        for state in self._states.values():
            for corp_id, corp in self._corporations.items():
                # Skip corps with no tiles in this state
                corp_tile_set = {t.tileId for t in corp.claimedTiles}
                if not any(tid in corp_tile_set for tid in state.tileIds):
                    continue

                score = compute_tolerance_score(corp, state, broken_counts.get(corp_id, 0))
                if score <= state.toleranceThreshold:
                    continue

                # Check if an active process already exists for this (state, corp)
                already_active = any(
                    p for p in self._nationalizations.values()
                    if p.stateId == state.id and p.corpId == corp_id and not p.cancelled
                    and self._tick_count < p.completionTick
                )
                if already_active:
                    continue

                # Trigger one nationalisation per tile controlled in this state
                for tile in corp.claimedTiles:
                    if tile.tileId not in state.tileIds:
                        continue
                    delay = compute_nationalization_delay(state)
                    proc_id = str(uuid4())
                    process = NationalizationProcess(
                        id=proc_id,
                        stateId=state.id,
                        corpId=corp_id,
                        tileId=tile.tileId,
                        startTick=self._tick_count,
                        completionTick=self._tick_count + delay,
                    )
                    self._nationalizations[proc_id] = process
                    self._repo.save_nationalization(process)
                    # Emit reputation event
                    event = ReputationEvent(
                        sourceId=state.id,
                        targetId=corp_id,
                        deltaGlobal=REPUTATION_DELTAS[ReputationEventReason.NationalizationTriggered][0],
                        deltaBilateral=REPUTATION_DELTAS[ReputationEventReason.NationalizationTriggered][1],
                        reason=ReputationEventReason.NationalizationTriggered,
                        tick=self._tick_count,
                    )
                    self._apply_reputation_event_locked(event)

        # Process completions
        for proc_id, process in list(self._nationalizations.items()):
            if process.cancelled or self._tick_count < process.completionTick:
                continue
            # Completed — remove tile from corp
            corp = self._corporations.get(process.corpId)
            if corp is None:
                continue
            remaining_tiles = [t for t in corp.claimedTiles if t.tileId != process.tileId]
            if len(remaining_tiles) == len(corp.claimedTiles):
                continue  # tile already gone
            self._corporations[process.corpId] = corp.model_copy(update={"claimedTiles": remaining_tiles})
            if process.tileId in self._tile_ownership:
                del self._tile_ownership[process.tileId]
            # Mark as cancelled=True to signal completion (so we don't reprocess)
            completed = process.model_copy(update={"cancelled": True})
            self._nationalizations[proc_id] = completed
            self._repo.save_nationalization(completed)
            self._repo.save_corporation(self._corporations[process.corpId])
