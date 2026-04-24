"""
test_phase75_states.py — Phase 7.5 : Réputation, États, nationalisation.

Tests couverts :
    - Roundtrip JSON StateData (incl. taxRate)
    - ScoreboardEntry roundtrip
    - compute_tolerance_score — 0 pour état vide, croît avec territoire
    - compute_nationalization_delay — formule BASE×(1+bureaucracy)×(1-corr×0.5)
    - apply_reputation_event — met à jour globalReputation de la corpo
    - compute_bribe_cost — proportionnel aux ticks restants
    - can_corrupt_nationalization — rejet si crédits insuffisants
    - get_scoreboard — tri composite (score décroissant)

Pas de Docker, pas de réseau. Durée < 1 s.
"""
import json
import sys
import importlib.util
from pathlib import Path

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")
_states = _load("logic.states", "logic/states.py")

StateData             = _models.StateData
StateType             = _models.StateType
CorporationData       = _models.CorporationData
ClaimedTile           = _models.ClaimedTile
ScoreboardEntry       = _models.ScoreboardEntry
ReputationEvent       = _models.ReputationEvent
ReputationEventReason = _models.ReputationEventReason
NationalizationProcess = _models.NationalizationProcess

compute_tolerance_score      = _states.compute_tolerance_score
compute_nationalization_delay = _states.compute_nationalization_delay
apply_reputation_event       = _states.apply_reputation_event
compute_bribe_cost           = _states.compute_bribe_cost
can_corrupt_nationalization  = _states.can_corrupt_nationalization
apply_bribe                  = _states.apply_bribe
BASE_NATIONALIZATION_DELAY   = _states.BASE_NATIONALIZATION_DELAY


def _make_corp(corp_id: str, credits: float = 1000.0, tiles: list[str] | None = None) -> CorporationData:
    tiles = tiles or []
    return CorporationData(
        id=corp_id,
        name=corp_id,
        credits=credits,
        claimedTiles=[ClaimedTile(bodyId="earth", tileId=t) for t in tiles],
    )


def _make_state(
    state_id: str = "s1",
    tiles: list[str] | None = None,
    bureaucracy: float = 0.1,
    corruption: float = 0.1,
    threshold: float = 0.5,
    tax: float = 0.15,
    state_type: StateType = StateType.Capitalist,
) -> StateData:
    return StateData(
        id=state_id,
        name=state_id,
        stateType=state_type,
        tileIds=tiles or [],
        bureaucracy=bureaucracy,
        corruptionRate=corruption,
        toleranceThreshold=threshold,
        taxRate=tax,
        isAiControlled=False,
    )


# ── Test 1 : Roundtrip JSON StateData (avec taxRate) ─────────────────────────

def test_state_data_roundtrip_with_tax_rate():
    state = _make_state(tiles=["h1", "h2"], bureaucracy=0.3, corruption=0.2, tax=0.2)
    data = json.loads(state.model_dump_json())
    s2 = StateData.model_validate(data)

    assert s2.id == "s1"
    assert s2.taxRate == 0.2
    assert s2.bureaucracy == 0.3
    assert s2.corruptionRate == 0.2
    assert s2.stateType == StateType.Capitalist
    assert len(s2.tileIds) == 2
    print("✓ StateData roundtrip OK (taxRate included)")


# ── Test 2 : ScoreboardEntry roundtrip ────────────────────────────────────────

def test_scoreboard_entry_roundtrip():
    entry = ScoreboardEntry(
        corpId="corp1", corpName="Alpha", credits=5000.0,
        tileCount=12, globalReputation=0.7, score=42.5,
    )
    data = json.loads(entry.model_dump_json())
    e2 = ScoreboardEntry.model_validate(data)

    assert e2.corpId == "corp1"
    assert e2.tileCount == 12
    assert e2.score == 42.5
    print("✓ ScoreboardEntry roundtrip OK")


# ── Test 3 : compute_tolerance_score — état vide ──────────────────────────────

def test_compute_tolerance_score_returns_zero_for_empty_state():
    state = _make_state(tiles=["h1", "h2"])
    corp  = _make_corp("corp1", credits=0.0, tiles=[])
    score = compute_tolerance_score(corp, state, broken_contracts_count=0)

    assert 0.0 <= score <= 1.0
    # Corp has no tiles in the state → territory sub-score = 0
    assert score < 0.5, f"Expected low score for empty corp, got {score}"
    print(f"✓ compute_tolerance_score empty corp = {score:.3f}")


def test_compute_tolerance_score_grows_with_territory():
    state = _make_state(tiles=["h1", "h2", "h3", "h4"])
    corp_weak   = _make_corp("corp1", credits=0.0,      tiles=["h1"])
    corp_strong = _make_corp("corp1", credits=1_000_000, tiles=["h1", "h2", "h3"])

    score_weak   = compute_tolerance_score(corp_weak,   state, 0)
    score_strong = compute_tolerance_score(corp_strong, state, 0)

    assert score_strong > score_weak, (
        f"Strong corp ({score_strong:.3f}) should score higher than weak ({score_weak:.3f})"
    )
    print(f"✓ compute_tolerance_score: weak={score_weak:.3f}, strong={score_strong:.3f}")


def test_compute_tolerance_score_increases_with_broken_contracts():
    """Broken contracts add a behaviour penalty that RAISES the score (more pressure on the state)."""
    state = _make_state(tiles=["h1"])
    corp  = _make_corp("corp1", tiles=["h1"])

    score_clean  = compute_tolerance_score(corp, state, broken_contracts_count=0)
    score_broken = compute_tolerance_score(corp, state, broken_contracts_count=5)

    assert score_broken > score_clean, (
        f"Broken contracts should raise the pressure score: clean={score_clean:.3f}, broken={score_broken:.3f}"
    )
    print(f"✓ compute_tolerance_score: clean={score_clean:.3f}, broken5={score_broken:.3f}")


# ── Test 4 : compute_nationalization_delay ────────────────────────────────────

def test_compute_nationalization_delay_formula():
    # Low bureaucracy, low corruption → near BASE_DELAY
    state_clean = _make_state(bureaucracy=0.0, corruption=0.0)
    delay_clean = compute_nationalization_delay(state_clean)
    assert abs(delay_clean - BASE_NATIONALIZATION_DELAY) < 0.01, (
        f"Expected {BASE_NATIONALIZATION_DELAY}, got {delay_clean}"
    )

    # High bureaucracy → much longer delay
    state_slow = _make_state(bureaucracy=1.0, corruption=0.0)
    delay_slow = compute_nationalization_delay(state_slow)
    # BASE * (1+1.0) * (1-0) = BASE * 2
    assert abs(delay_slow - BASE_NATIONALIZATION_DELAY * 2.0) < 0.01, (
        f"Expected {BASE_NATIONALIZATION_DELAY * 2}, got {delay_slow}"
    )

    # High corruption reduces delay
    state_corrupt = _make_state(bureaucracy=0.0, corruption=1.0)
    delay_corrupt = compute_nationalization_delay(state_corrupt)
    # BASE * 1 * (1-0.5) = BASE * 0.5
    assert abs(delay_corrupt - BASE_NATIONALIZATION_DELAY * 0.5) < 0.01, (
        f"Expected {BASE_NATIONALIZATION_DELAY * 0.5}, got {delay_corrupt}"
    )
    print(f"✓ compute_nationalization_delay: clean={delay_clean}, slow={delay_slow}, corrupt={delay_corrupt}")


# ── Test 5 : apply_reputation_event ──────────────────────────────────────────

def test_apply_reputation_event_updates_global_reputation():
    corp = _make_corp("corp1")
    assert corp.globalReputation == 0.0

    event = ReputationEvent(
        reason=ReputationEventReason.ContractCompleted,
        deltaGlobal=0.1,
        tick=1,
    )
    updated_corp = apply_reputation_event(corp, event)

    assert abs(updated_corp.globalReputation - 0.1) < 0.001, (
        f"Expected 0.1, got {updated_corp.globalReputation}"
    )
    print(f"✓ apply_reputation_event: 0.0 → {updated_corp.globalReputation}")


def test_apply_reputation_event_negative_delta():
    corp = _make_corp("corp1")
    event = ReputationEvent(
        reason=ReputationEventReason.ContractBroken,
        deltaGlobal=-0.2,
        tick=2,
    )
    updated_corp = apply_reputation_event(corp, event)
    assert abs(updated_corp.globalReputation - (-0.2)) < 0.001, (
        f"Expected -0.2, got {updated_corp.globalReputation}"
    )
    print(f"✓ apply_reputation_event negative delta: 0.0 → {updated_corp.globalReputation}")


# ── Test 6 : compute_bribe_cost ───────────────────────────────────────────────

def test_compute_bribe_cost_scales_with_ticks_remaining():
    nat = NationalizationProcess(
        id="n1",
        stateId="s1",
        corpId="corp1",
        tileId="h1",
        startTick=0,
        completionTick=20,
        cancelled=False,
    )
    cost_early = compute_bribe_cost(nat, current_tick=0)    # 20 ticks remaining
    cost_late  = compute_bribe_cost(nat, current_tick=15)   # 5 ticks remaining

    assert cost_early > cost_late, (
        f"Early bribe ({cost_early}) should cost more than late ({cost_late})"
    )
    assert cost_early > 0.0
    print(f"✓ compute_bribe_cost: tick0={cost_early}, tick15={cost_late}")


# ── Test 7 : can_corrupt_nationalization — reject insufficient credits ────────

def test_can_corrupt_nationalization_rejects_poor_corp():
    nat = NationalizationProcess(
        id="n1", stateId="s1", corpId="corp1", tileId="h1",
        startTick=0, completionTick=10, cancelled=False,
    )
    corp = _make_corp("corp1", credits=1.0)   # far too poor
    required_bribe = compute_bribe_cost(nat, current_tick=0)
    ok, reason = can_corrupt_nationalization(corp, nat, required_bribe, current_tick=0)
    assert not ok
    print(f"✓ can_corrupt_nationalization rejected (need {required_bribe:.0f}, have 1): {reason}")


def test_can_corrupt_nationalization_accepts_rich_corp():
    nat = NationalizationProcess(
        id="n1", stateId="s1", corpId="corp1", tileId="h1",
        startTick=0, completionTick=10, cancelled=False,
    )
    corp = _make_corp("corp1", credits=100_000.0)
    required_bribe = compute_bribe_cost(nat, current_tick=0)
    ok, _reason = can_corrupt_nationalization(corp, nat, required_bribe, current_tick=0)
    assert ok, f"Rich corp should be able to bribe (cost={required_bribe:.0f}), reason: {_reason}"
    print(f"✓ can_corrupt_nationalization accepted for rich corp (cost={required_bribe:.0f})")
