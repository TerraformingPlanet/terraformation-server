"""
corp_fsm.py — Phase 11.2 : FSM déterministe pour les corporations IA.

Toutes les fonctions sont **pures** : elles reçoivent un snapshot et un
CorporationData, retournent des valeurs sans toucher au runtime ni au lock.

Pattern d'utilisation dans runtime.py :
    snapshot = _build_corp_snapshot_locked(corp)   # sous lock, rapide
    # ---- release lock ----
    new_state, actions = compute_bot_tick(corp, snapshot)
    # ---- re-acquire lock ----
    _apply_bot_actions_locked(corp, new_state, actions)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terraformation_sim.models import (
        AgentAction,
        AgentActionType,
        BotFSMState,
        CorpProfile,
        CorporationData,
    )


# ---------------------------------------------------------------------------
# Snapshot (construit sous lock, traité hors lock)
# ---------------------------------------------------------------------------

@dataclass
class CorpSimSnapshot:
    """Read-only view of the world relevant to one AI corporation.

    Built under the runtime lock (fast read), then passed to pure FSM
    functions which run lock-free — including the LLM in M2.
    """
    corp_id: str
    current_tick: int

    # Tiles
    free_tile_ids_adj: list[str] = field(default_factory=list)
    """H3 tile IDs adjacent to at least one claimed tile and unclaimed."""

    # Economy
    credits: float = 0.0
    resource_stocks: dict[str, float] = field(default_factory=dict)
    """ResourceType.name → quantity in corp stocks."""
    market_prices: dict[str, float] = field(default_factory=dict)
    """ResourceType.name → current price on nearest market."""

    # Competition
    rival_corp_ids: list[str] = field(default_factory=list)
    """Corp IDs whose claimed tiles are adjacent to this corp's tiles."""
    rival_tile_counts: dict[str, int] = field(default_factory=dict)
    """corp_id → number of their tiles adjacent to our territory."""

    # Production
    production_bottleneck: bool = False
    """True when a building's workerRatio < 0.5 for 2+ consecutive ticks."""
    has_active_construction: bool = False
    """True when TerritoryQueue has pending or in-progress items."""


# ---------------------------------------------------------------------------
# FSM defaults
# ---------------------------------------------------------------------------

# Overridable per-corp via CorporationData.fsmThresholds (same key names)
CORP_FSM_DEFAULTS: dict[str, float] = {
    # Expansionniste
    "expand_min_credits":        500.0,   # min credits before claiming
    "expand_max_tiles":           20.0,   # stop expanding beyond this count
    # Economiste
    "build_bottleneck_threshold": 0.5,    # workerRatio below which Building triggered
    "trade_price_margin":         1.3,    # price multiplier that triggers Trading
    # Militariste
    "raid_force_ratio":           1.2,    # our_tiles / rival_adj_tiles before Raiding
    # General
    "idle_min_credits":          200.0,   # below this: always Idle (save credits)
}


def _threshold(corp: "CorporationData", key: str) -> float:
    """Return per-corp override or global default for a threshold key."""
    return float(corp.fsmThresholds.get(key, CORP_FSM_DEFAULTS[key]))


# ---------------------------------------------------------------------------
# FSM transition functions (one per profile)
# ---------------------------------------------------------------------------

def _next_state_economiste(
    corp: "CorporationData",
    snap: CorpSimSnapshot,
) -> "BotFSMState":
    from terraformation_sim.models import BotFSMState

    if snap.credits < _threshold(corp, "idle_min_credits"):
        return BotFSMState.Idle

    if snap.production_bottleneck:
        return BotFSMState.Building

    # Check if any market price is above our margin threshold
    if snap.market_prices:
        avg_price = sum(snap.market_prices.values()) / len(snap.market_prices)
        for price in snap.market_prices.values():
            if price > avg_price * _threshold(corp, "trade_price_margin"):
                return BotFSMState.Trading

    if snap.has_active_construction:
        return BotFSMState.Building

    return BotFSMState.Idle


def _next_state_expansionniste(
    corp: "CorporationData",
    snap: CorpSimSnapshot,
) -> "BotFSMState":
    from terraformation_sim.models import BotFSMState

    if snap.credits < _threshold(corp, "idle_min_credits"):
        return BotFSMState.Idle

    claimed_count = len(corp.claimedTiles)
    if (
        snap.free_tile_ids_adj
        and snap.credits >= _threshold(corp, "expand_min_credits")
        and claimed_count < _threshold(corp, "expand_max_tiles")
    ):
        return BotFSMState.Expanding

    if snap.has_active_construction:
        return BotFSMState.Building

    return BotFSMState.Idle


def _next_state_militariste(
    corp: "CorporationData",
    snap: CorpSimSnapshot,
) -> "BotFSMState":
    from terraformation_sim.models import BotFSMState

    if snap.credits < _threshold(corp, "idle_min_credits"):
        return BotFSMState.Idle

    our_tiles = len(corp.claimedTiles)
    if our_tiles > 0 and snap.rival_corp_ids:
        max_rival_adj = max(snap.rival_tile_counts.values(), default=0)
        if our_tiles > 0 and max_rival_adj > 0:
            force_ratio = our_tiles / max_rival_adj
            if force_ratio >= _threshold(corp, "raid_force_ratio"):
                return BotFSMState.Raiding

    if snap.has_active_construction:
        return BotFSMState.Building

    return BotFSMState.Idle


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def compute_next_fsm_state(
    corp: "CorporationData",
    snap: CorpSimSnapshot,
) -> "BotFSMState":
    """Return the next FSM state for this AI corporation.

    Pure — no side effects, no lock, no runtime access.
    """
    from terraformation_sim.models import BotFSMState, CorpProfile

    _dispatch = {
        CorpProfile.Economiste:     _next_state_economiste,
        CorpProfile.Expansionniste: _next_state_expansionniste,
        CorpProfile.Militariste:    _next_state_militariste,
    }
    fn = _dispatch.get(corp.profile, _next_state_economiste)
    return fn(corp, snap)


def compute_fsm_actions(
    corp: "CorporationData",
    snap: CorpSimSnapshot,
    new_state: "BotFSMState",
) -> list["AgentAction"]:
    """Return a list of AgentAction to execute given the FSM new_state.

    Pure — no side effects. Actions are validated and applied by the runtime.
    """
    from terraformation_sim.models import AgentAction, AgentActionType, BotFSMState

    actions: list[AgentAction] = []

    if new_state == BotFSMState.Expanding and snap.free_tile_ids_adj:
        # Claim the first adjacent free tile
        target_tile = snap.free_tile_ids_adj[0]
        actions.append(AgentAction(
            entityId=corp.id,
            actionType=AgentActionType.ClaimTile,
            params={"tile_id": target_tile},
            reasoning=f"Expansionniste: claiming adjacent free tile {target_tile}",
        ))

    elif new_state == BotFSMState.Building and not snap.has_active_construction:
        # Queue the most profitable building given current stocks
        building_type = _pick_building_to_construct(corp, snap)
        if building_type and corp.claimedTiles:
            tile_id = corp.claimedTiles[0].tileId
            actions.append(AgentAction(
                entityId=corp.id,
                actionType=AgentActionType.ConstructBuilding,
                params={"building_type": building_type, "tile_id": tile_id},
                reasoning=f"Building: constructing {building_type} on {tile_id}",
            ))

    elif new_state == BotFSMState.Trading:
        # Propose a short-term supply contract — stub until ContractData expansion
        pass  # Phase 11.2 M2 will wire LLM contract proposals

    elif new_state == BotFSMState.Raiding:
        # Economic raiding = target the highest-rival-density adjacent tile
        if snap.rival_corp_ids:
            top_rival = max(snap.rival_tile_counts, key=lambda k: snap.rival_tile_counts[k])
            actions.append(AgentAction(
                entityId=corp.id,
                actionType=AgentActionType.NoOp,
                params={"target_corp_id": top_rival},
                reasoning=f"Militariste: observing rival {top_rival} (active raids Phase 11.2 M2)",
            ))

    return actions


# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------

def _pick_building_to_construct(
    corp: "CorporationData",
    snap: CorpSimSnapshot,
) -> str | None:
    """Heuristic: choose the building type most needed given current stocks.

    Returns a BuildingType.name string, or None if nothing urgent.
    """
    stocks = snap.resource_stocks
    food   = stocks.get("Food", 0.0)
    energy = stocks.get("Energy", 0.0)

    if food < 10.0:
        return "Farm"
    if energy < 5.0:
        return "EnergyPlant"
    # Default: mine minerals
    return "Mine"
