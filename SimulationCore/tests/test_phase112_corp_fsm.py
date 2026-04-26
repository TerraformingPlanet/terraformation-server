"""
test_phase112_corp_fsm.py — Phase 11.2 M1 : FSM BotCorporation.

Tests couverts :
    [models — no runtime, always run]
    T01  CorpProfile enum values
    T02  BotFSMState enum values
    T03  CorporationData default fields (profile, fsmState, fsmThresholds)
    T04  AgentActionType nouveaux membres (10-13)
    T05  CorporationData round-trip JSON (profile + fsmState sérialisés)

    [logic pure — no runtime, no noise, always run]
    T06  Economiste → Idle (credits < threshold)
    T07  Economiste → Building (production_bottleneck)
    T08  Economiste → Trading (high market price)
    T09  Expansionniste → Expanding (credits + free tiles)
    T10  Expansionniste → Idle (pas de tuile adjacente libre)
    T11  Militariste → Raiding (force_ratio ≥ threshold)
    T12  Militariste → Idle (pas de rivals)
    T13  compute_fsm_actions: Expanding → ClaimTile action
    T14  compute_fsm_actions: Raiding → NoOp (stub M1)
    T15  _pick_building_to_construct: Food faible → Farm

    [runtime FSM loop — skipped si noise absent]
    T16  register_corporation accepte profile=Expansionniste
    T17  _build_corp_snapshot_locked (base case — no h3)
    T18  _process_bot_tick_locked (smoke — pas de crash, fsmState mis à jour)
    T19  run_world_agent_cycle inclut les corps IA
    T20  trigger_agent_for_entity sur une corp IA (pas de KeyError)

Pas de Docker, pas de réseau. Durée < 3 s.
"""
import sys
import importlib.util
import json
import time
import types
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading helpers
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


# Stub the package itself so that lazy `from terraformation_sim.X import ...`
# inside corp_fsm.py resolves against pre-loaded modules without triggering
# the full __init__.py (which pulls noise, h3 generation, etc.).
def _stub_package(full_name: str, path: Path) -> None:
    if full_name not in sys.modules:
        pkg = types.ModuleType(full_name)
        pkg.__path__ = [str(path)]           # type: ignore[attr-defined]
        pkg.__package__ = full_name
        sys.modules[full_name] = pkg


_stub_package("terraformation_sim", _SIM)
# Load logic package properly (stub would be empty, breaking runtime imports)
if "terraformation_sim.logic" not in sys.modules:
    if str(_SIM.parent) not in sys.path:
        sys.path.insert(0, str(_SIM.parent))
    import terraformation_sim.logic as _logic_pkg  # noqa: F401

_models = _load("models", "models.py")
_corp_fsm = _load("logic.corp_fsm", "logic/corp_fsm.py")

import pytest

CorpProfile     = _models.CorpProfile
BotFSMState     = _models.BotFSMState
AgentActionType = _models.AgentActionType
CorporationData = _models.CorporationData
ClaimedTile     = _models.ClaimedTile

# ---------------------------------------------------------------------------
# Skip guard (bruit nécessaire uniquement pour les tests runtime)
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


# ===========================================================================
# Fixtures runtime
# ===========================================================================

@pytest.fixture
def rt():
    """Fresh InMemorySimulationRuntime with a minimal bootstrap."""
    from terraformation_sim.runtime import InMemorySimulationRuntime
    from terraformation_sim.persistence import InMemoryRepository
    repo = InMemoryRepository()
    runtime = InMemorySimulationRuntime(repository=repo)
    runtime.bootstrap()
    return runtime


# ===========================================================================
# T01 — CorpProfile enum values
# ===========================================================================

def test_T01_corp_profile_values():
    assert CorpProfile.Economiste     == 0
    assert CorpProfile.Expansionniste == 1
    assert CorpProfile.Militariste    == 2


# ===========================================================================
# T02 — BotFSMState enum values
# ===========================================================================

def test_T02_bot_fsm_state_values():
    assert BotFSMState.Idle      == 0
    assert BotFSMState.Expanding == 1
    assert BotFSMState.Building  == 2
    assert BotFSMState.Trading   == 3
    assert BotFSMState.Raiding   == 4


# ===========================================================================
# T03 — CorporationData default fields
# ===========================================================================

def test_T03_corporation_data_defaults():
    corp = CorporationData(id="c1", name="Test Corp")
    assert corp.profile      == CorpProfile.Economiste
    assert corp.fsmState     == BotFSMState.Idle
    assert corp.fsmThresholds == {}


# ===========================================================================
# T04 — AgentActionType nouveaux membres
# ===========================================================================

def test_T04_agent_action_type_new_members():
    assert AgentActionType.ClaimTile             == 10
    assert AgentActionType.ConstructBuilding      == 11
    assert AgentActionType.UpdateFsmThresholds    == 12
    assert AgentActionType.ReorderConstructionQueue == 13


# ===========================================================================
# T05 — CorporationData round-trip JSON
# ===========================================================================

def test_T05_corporation_data_round_trip_json():
    corp = CorporationData(
        id="c1",
        name="Bot Corp",
        isAI=True,
        profile=CorpProfile.Expansionniste,
        fsmState=BotFSMState.Expanding,
        fsmThresholds={"expand_min_credits": 300.0},
    )
    data = json.loads(corp.model_dump_json())
    assert data["profile"]      == CorpProfile.Expansionniste
    assert data["fsmState"]     == BotFSMState.Expanding
    assert data["fsmThresholds"]["expand_min_credits"] == 300.0


# ===========================================================================
# Helpers FSM logic tests
# ===========================================================================

def _make_corp(profile: CorpProfile, credits: float = 1000.0, tiles: int = 0) -> CorporationData:
    claimed = [
        ClaimedTile(bodyId="b0", tileId=f"tile{i}")
        for i in range(tiles)
    ]
    return CorporationData(
        id="bot1",
        name="Bot",
        isAI=True,
        profile=profile,
        credits=credits,
        claimedTiles=claimed,
    )


def _make_snapshot(**kwargs):
    CorpSimSnapshot = _corp_fsm.CorpSimSnapshot
    defaults = dict(
        corp_id="bot1",
        current_tick=1,
        free_tile_ids_adj=[],
        credits=1000.0,
        resource_stocks={},
        market_prices={},
        rival_corp_ids=[],
        rival_tile_counts={},
        production_bottleneck=False,
        has_active_construction=False,
    )
    defaults.update(kwargs)
    return CorpSimSnapshot(**defaults)


# ===========================================================================
# T06 — Economiste → Idle (credits < threshold)
# ===========================================================================

def test_T06_economiste_idle_low_credits():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    corp = _make_corp(CorpProfile.Economiste, credits=50.0)
    snap = _make_snapshot(credits=50.0)
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Idle


# ===========================================================================
# T07 — Economiste → Building (production bottleneck)
# ===========================================================================

def test_T07_economiste_building_bottleneck():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    corp = _make_corp(CorpProfile.Economiste, credits=500.0)
    snap = _make_snapshot(credits=500.0, production_bottleneck=True)
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Building


# ===========================================================================
# T08 — Economiste → Trading (high market price)
# ===========================================================================

def test_T08_economiste_trading_high_price():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    corp = _make_corp(CorpProfile.Economiste, credits=500.0)
    # price margin default = 1.3 — one resource at 2× average triggers Trading
    snap = _make_snapshot(
        credits=500.0,
        market_prices={"Food": 1.0, "Energy": 3.0},  # 3.0 > avg(2.0)*1.3
    )
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Trading


# ===========================================================================
# T09 — Expansionniste → Expanding
# ===========================================================================

def test_T09_expansionniste_expanding():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    corp = _make_corp(CorpProfile.Expansionniste, credits=700.0, tiles=2)
    snap = _make_snapshot(credits=700.0, free_tile_ids_adj=["neighbor1"])
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Expanding


# ===========================================================================
# T10 — Expansionniste → Idle (pas de tuile adjacente libre)
# ===========================================================================

def test_T10_expansionniste_idle_no_free_tiles():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    corp = _make_corp(CorpProfile.Expansionniste, credits=700.0, tiles=1)
    snap = _make_snapshot(credits=700.0, free_tile_ids_adj=[])
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Idle


# ===========================================================================
# T11 — Militariste → Raiding (force_ratio ≥ threshold)
# ===========================================================================

def test_T11_militariste_raiding():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    # 5 tiles vs 3 rival adjacent → ratio = 5/3 ≈ 1.67 ≥ 1.2 threshold
    corp = _make_corp(CorpProfile.Militariste, credits=500.0, tiles=5)
    snap = _make_snapshot(
        credits=500.0,
        rival_corp_ids=["rival1"],
        rival_tile_counts={"rival1": 3},
    )
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Raiding


# ===========================================================================
# T12 — Militariste → Idle (pas de rivals)
# ===========================================================================

def test_T12_militariste_idle_no_rivals():
    compute_next_fsm_state = _corp_fsm.compute_next_fsm_state
    corp = _make_corp(CorpProfile.Militariste, credits=500.0, tiles=3)
    snap = _make_snapshot(credits=500.0, rival_corp_ids=[], rival_tile_counts={})
    assert compute_next_fsm_state(corp, snap) == BotFSMState.Idle


# ===========================================================================
# T13 — compute_fsm_actions: Expanding → ClaimTile
# ===========================================================================

def test_T13_actions_expanding_claim_tile():
    compute_fsm_actions = _corp_fsm.compute_fsm_actions
    corp = _make_corp(CorpProfile.Expansionniste, tiles=1)
    snap = _make_snapshot(free_tile_ids_adj=["target_tile"])
    actions = compute_fsm_actions(corp, snap, BotFSMState.Expanding)
    assert len(actions) >= 1
    claim = actions[0]
    assert claim.actionType == AgentActionType.ClaimTile
    assert claim.params.get("tile_id") == "target_tile"


# ===========================================================================
# T14 — compute_fsm_actions: Raiding → NoOp (stub M1)
# ===========================================================================

def test_T14_actions_raiding_noop_stub():
    compute_fsm_actions = _corp_fsm.compute_fsm_actions
    corp = _make_corp(CorpProfile.Militariste, tiles=3)
    snap = _make_snapshot(rival_corp_ids=["r1"], rival_tile_counts={"r1": 2})
    actions = compute_fsm_actions(corp, snap, BotFSMState.Raiding)
    assert len(actions) >= 1
    assert actions[0].actionType == AgentActionType.NoOp
    assert actions[0].params.get("target_corp_id") == "r1"


# ===========================================================================
# T15 — _pick_building_to_construct: Food faible → Farm
# ===========================================================================

def test_T15_pick_building_low_food():
    _pick_building_to_construct = _corp_fsm._pick_building_to_construct
    corp = _make_corp(CorpProfile.Economiste)
    snap = _make_snapshot(resource_stocks={"Food": 5.0, "Energy": 100.0})
    result = _pick_building_to_construct(corp, snap)
    assert result == "Farm"


# ===========================================================================
# T16 — register_corporation accepte profile
# ===========================================================================

@_skip_no_noise
def test_T16_register_corp_with_profile(rt):
    corp = rt.register_corporation("BotCorp", is_ai=True, profile=CorpProfile.Expansionniste)
    assert corp.isAI
    assert corp.profile == CorpProfile.Expansionniste
    assert corp.fsmState == BotFSMState.Idle


# ===========================================================================
# T17 — _build_corp_snapshot_locked (base case)
# ===========================================================================

@_skip_no_noise
def test_T17_build_corp_snapshot_locked(rt):
    corp = rt.register_corporation("BotSnap", is_ai=True, profile=CorpProfile.Economiste)
    with rt._lock:
        snap = rt._build_corp_snapshot_locked(corp)
    assert snap.corp_id == corp.id
    assert snap.current_tick == rt._tick_count
    assert isinstance(snap.free_tile_ids_adj, list)
    assert isinstance(snap.rival_tile_counts, dict)


# ===========================================================================
# T18 — _process_bot_tick_locked (smoke)
# ===========================================================================

@_skip_no_noise
def test_T18_process_bot_tick_locked_smoke(rt):
    corp = rt.register_corporation("BotTick", is_ai=True, profile=CorpProfile.Expansionniste)
    with rt._lock:
        rt._process_bot_tick_locked()
    # Threads launched — wait briefly for completion
    time.sleep(0.3)
    updated = rt.get_corporation(corp.id)
    assert updated is not None
    # fsmState is a valid BotFSMState value
    assert updated.fsmState in list(BotFSMState)


# ===========================================================================
# T19 — run_world_agent_cycle inclut les corps IA
# ===========================================================================

@_skip_no_noise
def test_T19_run_world_agent_cycle_includes_ai_corps(rt):
    corp = rt.register_corporation("BotCycle", is_ai=True)
    triggered = rt.run_world_agent_cycle()
    assert corp.id in triggered


# ===========================================================================
# T20 — trigger_agent_for_entity sur une corp IA (pas de KeyError)
# ===========================================================================

@_skip_no_noise
def test_T20_trigger_agent_for_entity_corp(rt):
    corp = rt.register_corporation("BotTrigger", is_ai=True, profile=CorpProfile.Militariste)
    try:
        rt.trigger_agent_for_entity(corp.id, "test_event")
    except KeyError:
        pytest.fail("trigger_agent_for_entity raised KeyError for an existing AI corporation")
    time.sleep(0.1)  # let daemon thread start
