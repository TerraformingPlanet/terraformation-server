"""
test_phase113_gm.py — Phase 11.3 M1 : GM narratif (détection déséquilibre).

Tests couverts :
    [logic pure — no runtime, no noise, always run]
    T01  compute_leaderboard_imbalance returns 0.0 with < 2 corps
    T02  compute_leaderboard_imbalance returns 0.0 with 0 corps
    T03  compute_leaderboard_imbalance returns correct ratio (balanced)
    T04  compute_leaderboard_imbalance returns correct ratio (unbalanced)
    T05  compute_leaderboard_imbalance ignores corps with score <= 0
    T06  detect_imbalance returns False below threshold
    T07  detect_imbalance returns True at or above threshold
    T08  detect_imbalance default threshold 2.5
    T09  pick_gm_lever always returns 'none' (M1 stub)
    T10  pick_gm_lever ignores last_lever and context

    [runtime — skipped si noise absent]
    T11  run_gm_narrative_check returns None when no corps
    T12  run_gm_narrative_check returns None when balanced
    T13  run_gm_narrative_check returns 'none' lever when imbalanced
    T14  run_gm_narrative_check respects cooldown (second call returns None)
    T15  bootstrap_sol resets GM cooldown and last lever

Pas de Docker, pas de réseau. Durée < 3 s.
"""
import sys
import importlib.util
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading helpers (same isolation pattern)
# ---------------------------------------------------------------------------

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    full_name = f"terraformation_sim.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(full_name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_package(full_name: str, path: Path) -> None:
    if full_name not in sys.modules:
        pkg = types.ModuleType(full_name)
        pkg.__path__ = [str(path)]  # type: ignore[attr-defined]
        pkg.__package__ = full_name
        sys.modules[full_name] = pkg


_stub_package("terraformation_sim", _SIM)
# Load logic package properly (stub would be empty, breaking runtime imports)
if "terraformation_sim.logic" not in sys.modules:
    if str(_SIM.parent) not in sys.path:
        sys.path.insert(0, str(_SIM.parent))
    import terraformation_sim.logic as _logic_pkg  # noqa: F401

_models = _load("models", "models.py")
_gm = _load("logic.gm", "logic/gm.py")

import pytest

ScoreboardEntry               = _models.ScoreboardEntry
EventType                     = _models.EventType
StateType                     = _models.StateType
compute_leaderboard_imbalance = _gm.compute_leaderboard_imbalance
detect_imbalance              = _gm.detect_imbalance
pick_gm_lever                 = _gm.pick_gm_lever
build_alien_pop_plan          = _gm.build_alien_pop_plan
build_megastructure_plan      = _gm.build_megastructure_plan
build_empire_galactique_plan  = _gm.build_empire_galactique_plan


# ---------------------------------------------------------------------------
# Skip guard (runtime tests only)
# ---------------------------------------------------------------------------

def _noise_available() -> bool:
    try:
        import noise  # noqa: F401
        return True
    except ImportError:
        return False


_skip_no_noise = pytest.mark.skipif(
    not _noise_available(),
    reason="noise C extension not available (Windows build skip)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sb(corp_id: str, score: float) -> "ScoreboardEntry":
    return ScoreboardEntry(corpId=corp_id, corpName=corp_id, score=score)


# ---------------------------------------------------------------------------
# T01-T05 : compute_leaderboard_imbalance
# ---------------------------------------------------------------------------

def test_T01_imbalance_zero_with_one_corp():
    sb = [_sb("c1", 100.0)]
    assert compute_leaderboard_imbalance(sb) == 0.0


def test_T02_imbalance_zero_with_empty_scoreboard():
    assert compute_leaderboard_imbalance([]) == 0.0


def test_T03_imbalance_balanced():
    # scores = [100, 100] → max=100, median=100 → ratio=1.0
    sb = [_sb("c1", 100.0), _sb("c2", 100.0)]
    assert compute_leaderboard_imbalance(sb) == pytest.approx(1.0)


def test_T04_imbalance_unbalanced():
    # scores = [300, 100, 100] → max=300, median=100 → ratio=3.0
    sb = [_sb("c1", 300.0), _sb("c2", 100.0), _sb("c3", 100.0)]
    result = compute_leaderboard_imbalance(sb)
    assert result == pytest.approx(3.0)


def test_T05_imbalance_ignores_zero_score_corps():
    # Only c1 (100) and c2 (200) count; c3 (0) is ignored
    # max=200, median=150 (even: avg of 100,200) → ratio = 200/150 ≈ 1.333
    sb = [_sb("c1", 100.0), _sb("c2", 200.0), _sb("c3", 0.0)]
    result = compute_leaderboard_imbalance(sb)
    assert result == pytest.approx(200.0 / 150.0, rel=1e-3)


# ---------------------------------------------------------------------------
# T06-T08 : detect_imbalance
# ---------------------------------------------------------------------------

def test_T06_detect_imbalance_false_below_threshold():
    sb = [_sb("c1", 100.0), _sb("c2", 100.0)]  # ratio = 1.0
    assert detect_imbalance(sb, threshold=2.5) is False


def test_T07_detect_imbalance_true_above_threshold():
    sb = [_sb("c1", 300.0), _sb("c2", 100.0), _sb("c3", 100.0)]  # ratio = 3.0
    assert detect_imbalance(sb, threshold=2.5) is True


def test_T08_detect_imbalance_default_threshold():
    # ratio exactly 2.5 → True (>= threshold)
    # scores [250, 100] → median=175 → ratio=250/175≈1.43 → not 2.5
    # Let's use [500, 200] → median=350 → ratio=500/350≈1.43 — still not 2.5
    # [500, 100, 100] → median=100 → ratio=5.0 ≥ 2.5 → True
    sb = [_sb("c1", 500.0), _sb("c2", 100.0), _sb("c3", 100.0)]
    assert detect_imbalance(sb) is True


# ---------------------------------------------------------------------------
# T09-T10 : pick_gm_lever (M2 context-based)
# ---------------------------------------------------------------------------

def test_T09_pick_gm_lever_alien_pop_when_no_context():
    # ratio=0.0 (default), last=None → last != 'alien_pop' → alien_pop
    assert pick_gm_lever(None, {}) == "alien_pop"


def test_T10_pick_gm_lever_alien_pop_when_unknown_last():
    # last_lever not 'alien_pop' → alien_pop
    assert pick_gm_lever("tax_leader", {"tick": 99, "corpCount": 5}) == "alien_pop"


# ---------------------------------------------------------------------------
# T11-T15 : runtime tests (skip if no noise)
# ---------------------------------------------------------------------------

@_skip_no_noise
def test_T11_gm_check_returns_none_when_no_corps():
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap_sol()
    result = rt.run_gm_narrative_check()
    assert result is None


@_skip_no_noise
def test_T12_gm_check_returns_none_when_balanced(monkeypatch):
    monkeypatch.setenv("GM_IMBALANCE_THRESHOLD", "2.5")
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap_sol()
    # Register two corps with equal credits (score=0 initially → both return 0)
    rt.register_corporation("CorpA", is_ai=True)
    rt.register_corporation("CorpB", is_ai=True)
    # With scores all zero → < 2 positive scores → imbalance = 0.0 → no trigger
    result = rt.run_gm_narrative_check()
    assert result is None


@_skip_no_noise
def test_T13_gm_check_returns_lever_when_imbalanced(monkeypatch):
    monkeypatch.setenv("GM_IMBALANCE_THRESHOLD", "2.5")
    monkeypatch.setenv("GM_COOLDOWN_TICKS", "20")
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    from unittest.mock import patch
    rt = SimulationRuntime()
    rt.bootstrap_sol()

    ctx = {
        "imbalanceRatio": 3.0, "candidateTileIds": [], "allTileIds": [],
        "allCorpIds": [], "topCorpId": "", "mostColonizedBodyId": "", "tick": 0,
    }
    with patch.object(rt, "_build_gm_context_locked", return_value=ctx):
        result = rt.run_gm_narrative_check()

    # M2: returns a real lever name (not None, not 'none')
    assert result is not None
    assert result in {"alien_pop", "megastructure", "empire_galactique"}
    rt.bootstrap_sol()

    # Mock detect_imbalance to always return True
    import terraformation_sim.logic.gm as gm_mod
    with patch.object(gm_mod, "detect_imbalance", return_value=True):
        result = rt.run_gm_narrative_check()

    # When detect_imbalance returns True but no context is available, returns None
    assert result is None


@_skip_no_noise
def test_T14_gm_check_cooldown_prevents_second_call(monkeypatch):
    monkeypatch.setenv("GM_IMBALANCE_THRESHOLD", "2.5")
    monkeypatch.setenv("GM_COOLDOWN_TICKS", "20")
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    from unittest.mock import patch
    rt = SimulationRuntime()
    rt.bootstrap_sol()

    ctx = {
        "imbalanceRatio": 3.0, "candidateTileIds": [], "allTileIds": [],
        "allCorpIds": [], "topCorpId": "", "mostColonizedBodyId": "", "tick": 0,
    }
    with patch.object(rt, "_build_gm_context_locked", return_value=ctx):
        first = rt.run_gm_narrative_check()
        second = rt.run_gm_narrative_check()

    assert first is not None
    assert first != "none"
    assert second is None  # cooldown active


@_skip_no_noise
def test_T15_bootstrap_sol_resets_gm_state(monkeypatch):
    monkeypatch.setenv("GM_IMBALANCE_THRESHOLD", "2.5")
    monkeypatch.setenv("GM_COOLDOWN_TICKS", "20")
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    from unittest.mock import patch
    rt = SimulationRuntime()
    rt.bootstrap_sol()

    ctx = {
        "imbalanceRatio": 3.0, "candidateTileIds": [], "allTileIds": [],
        "allCorpIds": [], "topCorpId": "", "mostColonizedBodyId": "", "tick": 0,
    }
    with patch.object(rt, "_build_gm_context_locked", return_value=ctx):
        rt.run_gm_narrative_check()
        assert rt._gm_cooldown_tick > 0

    # Re-bootstrap should reset
    rt.bootstrap_sol()
    assert rt._gm_cooldown_tick == 0
    assert rt._gm_last_lever == ""


# ---------------------------------------------------------------------------
# T16-T22 : Phase 11.3 M2 — new enum values + lever logic + plan-builders
# ---------------------------------------------------------------------------

def test_T16_state_type_alien_value():
    assert int(StateType.Alien) == 2


def test_T17_event_type_megastructure_and_empire_values():
    assert int(EventType.DecouverteMegastructure) == 7
    assert int(EventType.EmpireGalactique) == 8


def test_T18_pick_gm_lever_empire_when_ratio_high():
    # ratio >= 5.0 and last != 'empire_galactique' → 'empire_galactique'
    result = pick_gm_lever(None, {"imbalanceRatio": 6.0})
    assert result == "empire_galactique"


def test_T19_pick_gm_lever_alien_pop_after_empire():
    # ratio >= 5.0 but last == 'empire_galactique' → skip empire → alien_pop
    result = pick_gm_lever("empire_galactique", {"imbalanceRatio": 6.0})
    assert result == "alien_pop"


def test_T20_pick_gm_lever_megastructure_after_alien_pop():
    # ratio < 5.0, last == 'alien_pop' → fallback to 'megastructure'
    result = pick_gm_lever("alien_pop", {"imbalanceRatio": 3.0})
    assert result == "megastructure"


def test_T21_pick_gm_lever_alien_pop_when_ratio_low_and_no_last():
    # ratio < 5.0, last = None != 'alien_pop' → 'alien_pop'
    result = pick_gm_lever(None, {"imbalanceRatio": 1.0})
    assert result == "alien_pop"


def test_T22_build_alien_pop_plan_returns_n_tiles():
    candidates = ["a", "b", "c", "d", "e", "f", "g"]
    result = build_alien_pop_plan(10, candidates, n=3)
    assert len(result) == 3
    assert all(t in candidates for t in result)


# ---------------------------------------------------------------------------
# T23-T25 : runtime lever execution (skip if no noise)
# ---------------------------------------------------------------------------

@_skip_no_noise
def test_T23_execute_alien_pop_creates_alien_state():
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap_sol()
    ctx = {
        "tick": 1,
        "candidateTileIds": ["a", "b", "c", "d", "e", "f"],
        "allTileIds": ["a", "b", "c"],
        "allCorpIds": [],
        "topCorpId": "",
        "imbalanceRatio": 3.0,
        "mostColonizedBodyId": "",
    }
    rt.execute_gm_lever("alien_pop", ctx)
    states = rt.list_states()
    alien_states = [s for s in states if s.stateType == StateType.Alien]
    assert len(alien_states) >= 1
    assert alien_states[0].isAiControlled is True


@_skip_no_noise
def test_T24_execute_megastructure_injects_event():
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap_sol()
    ctx = {
        "tick": 5,
        "candidateTileIds": ["tile_x"],
        "allTileIds": [],
        "allCorpIds": [],
        "topCorpId": "",
        "imbalanceRatio": 0.0,
        "mostColonizedBodyId": "",
    }
    rt.execute_gm_lever("megastructure", ctx)
    events = rt.list_game_events(limit=5)
    assert any(e.eventType == EventType.DecouverteMegastructure for e in events)


@_skip_no_noise
def test_T25_execute_empire_galactique_creates_state_and_events():
    from terraformation_sim.runtime import InMemorySimulationRuntime as SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap_sol()
    corp_a = rt.register_corporation("CorpA", is_ai=False)
    corp_b = rt.register_corporation("CorpB", is_ai=False)
    all_corp_ids = [corp_a.id, corp_b.id]
    ctx = {
        "tick": 10,
        "candidateTileIds": [],
        "allTileIds": ["t1", "t2", "t3"],
        "allCorpIds": all_corp_ids,
        "topCorpId": "",
        "imbalanceRatio": 6.0,
        "mostColonizedBodyId": "",
    }
    rt.execute_gm_lever("empire_galactique", ctx)
    states = rt.list_states()
    alien_states = [s for s in states if s.stateType == StateType.Alien]
    assert len(alien_states) >= 1
    events = rt.list_game_events(limit=20)
    empire_events = [e for e in events if e.eventType == EventType.EmpireGalactique]
    assert len(empire_events) == len(all_corp_ids)

