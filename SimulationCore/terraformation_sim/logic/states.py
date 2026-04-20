"""
Pure logic functions for the State & Reputation layer (Phase 7.5).

No side effects, no runtime access, no self.
All functions receive Pydantic model instances and return new instances.
"""
from __future__ import annotations

from ..models import (
    CorporationData,
    NationalizationProcess,
    ReputationEvent,
    ReputationEventReason,
    ScoreboardEntry,
    StateData,
)

# ── Tunable constants ─────────────────────────────────────────────────────────

# Base delay in ticks before nationalisation takes effect (before bureaucracy/corruption modifiers).
BASE_NATIONALIZATION_DELAY: int = 10

# Minimum delay regardless of modifiers.
MIN_NATIONALIZATION_DELAY: int = 1

# Weight factors for tolerance score computation.
# Adjust these without touching any other code.
TOLERANCE_WEIGHT_TERRITORY: float = 0.5   # share of state tiles controlled by corp
TOLERANCE_WEIGHT_CREDITS:   float = 0.2   # relative wealth
TOLERANCE_WEIGHT_BROKEN:    float = 0.3   # broken-contract penalty per contract

# Credits reference scale for the credit weight term (corp.credits / CREDIT_SCALE).
CREDIT_SCALE: float = 10_000.0

# Broken-contract penalty per broken contract in the tolerance score.
BROKEN_CONTRACT_PENALTY: float = 0.05

# (delta_global, delta_bilateral) applied when a ReputationEvent is emitted.
REPUTATION_DELTAS: dict[ReputationEventReason, tuple[float, float]] = {
    ReputationEventReason.ContractCompleted:        (+5.0,  +10.0),
    ReputationEventReason.ContractBroken:           (-8.0,  -15.0),
    ReputationEventReason.NationalizationTriggered: (-3.0,  -20.0),
    ReputationEventReason.NationalizationCancelled: (+1.0,  +5.0),
    ReputationEventReason.CorruptionDetected:       (-10.0, -5.0),
}

# Bribe cost per delay-tick remaining when corrupting a nationalisation process.
BRIBE_COST_PER_TICK: float = 50.0

# Minimum bribe amount to cancel outright.
BRIBE_THRESHOLD: float = 200.0


# ── Core formula functions ────────────────────────────────────────────────────

def compute_tolerance_score(
    corp: CorporationData,
    state: StateData,
    broken_contracts_count: int = 0,
) -> float:
    """
    Compute how much a corporation 'threatens' a state.

    Returns a float 0..∞.
    Compare to state.toleranceThreshold: if score > threshold, nationalisation should be triggered.

    All weights live in module-level constants above — change them to rebalance without
    touching the runtime or server.
    """
    if not state.tileIds:
        return 0.0

    # Territory term: fraction of state tiles the corp controls.
    corp_tile_set = {t.tileId for t in corp.claimedTiles}
    state_tiles_controlled = sum(1 for tid in state.tileIds if tid in corp_tile_set)
    territory_ratio = state_tiles_controlled / len(state.tileIds)

    # Credit term: relative wealth (clamped at 1.0 so very rich corps don't dominate alone).
    credit_ratio = min(1.0, corp.credits / CREDIT_SCALE) if CREDIT_SCALE > 0 else 0.0

    # Behaviour term: penalise broken contracts.
    behaviour_penalty = broken_contracts_count * BROKEN_CONTRACT_PENALTY

    score = (
        territory_ratio * TOLERANCE_WEIGHT_TERRITORY
        + credit_ratio  * TOLERANCE_WEIGHT_CREDITS
        + behaviour_penalty * TOLERANCE_WEIGHT_BROKEN
    )
    return score


def compute_nationalization_delay(state: StateData) -> int:
    """
    Delay in ticks before nationalisation takes effect.

    Formula: BASE_DELAY × (1 + bureaucracy) × (1 - corruptionRate × 0.5)
    Clamp to MIN_NATIONALIZATION_DELAY.
    """
    delay = BASE_NATIONALIZATION_DELAY * (1.0 + state.bureaucracy) * (1.0 - state.corruptionRate * 0.5)
    return max(MIN_NATIONALIZATION_DELAY, round(delay))


def apply_reputation_event(corp: CorporationData, event: ReputationEvent) -> CorporationData:
    """Apply delta_global from a ReputationEvent to a corp's globalReputation score."""
    return corp.model_copy(update={"globalReputation": corp.globalReputation + event.deltaGlobal})


def compute_bribe_cost(process: NationalizationProcess, current_tick: int) -> float:
    """
    Bribe cost to cancel a nationalisation process outright.

    Cost scales with ticks remaining (more bureaucracy still to undo = more expensive).
    Minimum is BRIBE_THRESHOLD.
    """
    ticks_remaining = max(0, process.completionTick - current_tick)
    return max(BRIBE_THRESHOLD, ticks_remaining * BRIBE_COST_PER_TICK)


def can_corrupt_nationalization(
    corp: CorporationData,
    process: NationalizationProcess,
    bribe_amount: float,
    current_tick: int,
) -> tuple[bool, str]:
    """Return (ok, reason) for a corruption attempt."""
    if process.cancelled:
        return False, "Nationalisation already cancelled"
    if current_tick >= process.completionTick:
        return False, "Nationalisation already completed"
    if corp.id != process.corpId:
        return False, "Corporation is not the target of this nationalisation"
    required = compute_bribe_cost(process, current_tick)
    if bribe_amount < required:
        return False, f"Bribe of {bribe_amount:.0f} is below required {required:.0f}"
    if corp.credits < bribe_amount:
        return False, f"Insufficient credits ({corp.credits:.0f} < {bribe_amount:.0f})"
    return True, ""


def apply_bribe(
    corp: CorporationData,
    process: NationalizationProcess,
    bribe_amount: float,
) -> tuple[NationalizationProcess, CorporationData]:
    """Deduct bribe from corp credits and mark the nationalisation as cancelled."""
    new_process = process.model_copy(update={"cancelled": True})
    new_corp    = corp.model_copy(update={"credits": corp.credits - bribe_amount})
    return new_process, new_corp


def compute_scoreboard_score(corp: CorporationData) -> float:
    """Composite score for the scoreboard: credits + territory + reputation."""
    tile_count = len(corp.claimedTiles)
    return corp.credits + tile_count * 1_000.0 + corp.globalReputation * 100.0


def build_scoreboard_entry(corp: CorporationData) -> ScoreboardEntry:
    """Build a ScoreboardEntry from a CorporationData."""
    return ScoreboardEntry(
        corpId=corp.id,
        corpName=corp.name,
        credits=corp.credits,
        tileCount=len(corp.claimedTiles),
        globalReputation=corp.globalReputation,
        score=compute_scoreboard_score(corp),
    )
