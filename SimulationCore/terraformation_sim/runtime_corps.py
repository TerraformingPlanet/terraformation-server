from __future__ import annotations

from uuid import uuid4

from .models import (
    CorporationData,
    CorpProfile,
    TerritoryData,
    _corp_color_rgb,
)


class CorpsMixin:
    """Corporation registry, loyalty/dependence, and territory query methods.

    State accessed via self:
        self._lock, self._corporations, self._states,
        self._territories, self._territory_tile_index, self._repo
    """

    # Weights: corruptionRate×W1 + loyalty×W2 + globalRep(norm)×W3
    _DEPENDENCE_W1: float = 0.4
    _DEPENDENCE_W2: float = 0.4
    _DEPENDENCE_W3: float = 0.2

    # ── Corporation registry (Phase 7.1) ──────────────────────────────────

    def register_corporation(
        self,
        name: str,
        is_ai: bool = False,
        profile: CorpProfile | str | None = None,
        owner_id: str = "",
    ) -> CorporationData:
        with self._lock:
            corp_id = str(uuid4())
            color_r, color_g, color_b = _corp_color_rgb(corp_id)
            if isinstance(profile, str):
                profile = CorpProfile[profile]
            corp = CorporationData(
                id=corp_id,
                name=name,
                credits=5000.0,
                isAI=is_ai,
                profile=profile if profile is not None else CorpProfile.Economiste,
                colorR=color_r,
                colorG=color_g,
                colorB=color_b,
                ownerId=owner_id,
            )
            self._corporations[corp_id] = corp
            self._repo.save_corporation(corp)
            return corp

    def find_corporation_by_owner(self, player_id: str) -> CorporationData | None:
        """Return the first corp whose ownerId matches player_id, or None."""
        if not player_id:
            return None
        with self._lock:
            for corp in self._corporations.values():
                if corp.ownerId == player_id:
                    return corp
        return None

    def list_corporations(self) -> list[CorporationData]:
        with self._lock:
            return list(self._corporations.values())

    def get_corporation(self, corp_id: str) -> CorporationData | None:
        with self._lock:
            return self._corporations.get(corp_id)

    # ── Vassal / loyalty system (Phase Colonisation) ──────────────────────────

    def set_loyalty(self, state_id: str, corp_id: str, delta: float) -> float:
        """Adjust bilateral loyalty corp→state by delta, clamped to [0, 1].

        Returns the new loyalty value.
        """
        with self._lock:
            state = self._states.get(state_id)
            if state is None:
                raise KeyError(f"State '{state_id}' not found")
            current = state.loyalty.get(corp_id, 0.0)
            new_value = max(0.0, min(1.0, current + delta))
            state.loyalty[corp_id] = new_value
            self._repo.save_state(state)
            return new_value

    def get_dependence_score(self, state_id: str, corp_id: str) -> float:
        """Compute the dependenceScore of a state toward a corp.

        dependenceScore = corruptionRate×W1 + loyalty[corp_id]×W2 + (globalRep/100)×W3
        Higher score → state is more submissive to the corp.
        """
        with self._lock:
            state = self._states.get(state_id)
            if state is None:
                raise KeyError(f"State '{state_id}' not found")
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            loyalty = state.loyalty.get(corp_id, 0.0)
            rep_norm = max(0.0, min(1.0, corp.globalReputation / 100.0))
            return (
                state.corruptionRate * self._DEPENDENCE_W1
                + loyalty * self._DEPENDENCE_W2
                + rep_norm * self._DEPENDENCE_W3
            )

    # ── Territory registry (Phase Colonisation) ────────────────────────────────

    def list_territories(self, body_id: str | None = None) -> list[TerritoryData]:
        """Return all TerritoryData, optionally filtered by bodyId."""
        with self._lock:
            if body_id is None:
                return [t.model_copy(deep=True) for t in self._territories.values()]
            return [
                t.model_copy(deep=True)
                for t in self._territories.values()
                if t.bodyId == body_id
            ]

    def get_territory(self, territory_id: str) -> TerritoryData:
        """Return a TerritoryData by id. Raises KeyError if not found."""
        with self._lock:
            terr = self._territories.get(territory_id)
            if terr is None:
                raise KeyError(f"Territory '{territory_id}' not found")
            return terr.model_copy(deep=True)

    def get_tile_territory(self, body_id: str, tile_id: str) -> TerritoryData | None:
        """Return the TerritoryData that owns a given tile, or None if unclaimed."""
        with self._lock:
            terr_id = self._territory_tile_index.get(f"{body_id}::{tile_id}")
            if terr_id is None:
                return None
            terr = self._territories.get(terr_id)
            return terr.model_copy(deep=True) if terr else None
