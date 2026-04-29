"""
test_phase112_llm_corp.py — Phase 11.2 M2 : LLM stratégique pour les corporations IA.

Tests couverts :
    [logic pure — no runtime, no noise, always run]
    T01  build_corp_system_prompt Economiste contains 'production efficiency'
    T02  build_corp_system_prompt Expansionniste contains 'territory'
    T03  build_corp_system_prompt Militariste contains 'dominance'
    T04  build_corp_context includes corp fields + environment
    T05  build_corp_context includes scoreboard when provided
    T06  build_corp_context includes memory when provided
    T07  build_corp_context recent_events when provided
    T08  CORP_AGENT_TOOLS_SCHEMA has 4 tools (NoOp, UpdateFsmThresholds, ReorderConstructionQueue, ProposeContract)
    T09  parse_action_from_json handles UpdateFsmThresholds correctly
    T10  parse_action_from_tool_call handles UpdateFsmThresholds
    T11  parse_action_from_json handles ReorderConstructionQueue correctly
    T12  parse_action_from_tool_call handles ReorderConstructionQueue
    T13  parse_action_from_json handles ClaimTile (tipo 10)
    T14  run_corp_agent returns NoOp when LLM env vars are missing
    T15  run_corp_agent calls LLM and parses result (mock)
    T16  run_corp_agent falls back to NoOp on LLM exception

    [runtime — skipped si noise absent]
    T17  get_corp_agent_context returns dict for registered corp
    T18  get_corp_agent_context returns None for unknown corp_id
    T19  run_agent_for_corp raises ValueError for unknown corp
    T20  run_agent_for_corp returns NoOp AgentAction (no LLM env vars)

Pas de Docker, pas de réseau. Durée < 3 s.
"""
import sys
import importlib.util
import json
import types
import unittest.mock
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading helpers (same isolation pattern as test_phase112_corp_fsm.py)
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
_corp_fsm = _load("logic.corp_fsm", "logic/corp_fsm.py")
_agent = _load("logic.agent", "logic/agent.py")

import pytest

CorpProfile     = _models.CorpProfile
BotFSMState     = _models.BotFSMState
AgentActionType = _models.AgentActionType
CorporationData = _models.CorporationData
AgentMemory     = _models.AgentMemory
ScoreboardEntry = _models.ScoreboardEntry

CorpSimSnapshot            = _corp_fsm.CorpSimSnapshot
build_corp_system_prompt   = _agent.build_corp_system_prompt
build_corp_context         = _agent.build_corp_context
run_corp_agent             = _agent.run_corp_agent
CORP_AGENT_TOOLS_SCHEMA    = _agent.CORP_AGENT_TOOLS_SCHEMA
parse_action_from_json     = _agent.parse_action_from_json
parse_action_from_tool_call = _agent.parse_action_from_tool_call


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

def _make_corp(profile: "CorpProfile" = None, credits: float = 1000.0) -> "CorporationData":
    if profile is None:
        profile = CorpProfile.Economiste
    return CorporationData(
        id="corp-test",
        name="TestCorp",
        isAI=True,
        credits=credits,
        profile=profile,
        fsmState=BotFSMState.Idle,
    )


def _make_snapshot(corp_id: str = "corp-test") -> "CorpSimSnapshot":
    return CorpSimSnapshot(
        corp_id=corp_id,
        current_tick=10,
        free_tile_ids_adj=["tile-1", "tile-2"],
        credits=1000.0,
        resource_stocks={"Iron": 50.0, "Food": 10.0},
        market_prices={"Iron": 2.5, "Food": 1.0},
        rival_corp_ids=["rival-1"],
        rival_tile_counts={"rival-1": 3},
        production_bottleneck=False,
        has_active_construction=False,
    )


# ---------------------------------------------------------------------------
# T01-T03 : build_corp_system_prompt
# ---------------------------------------------------------------------------

def test_T01_economiste_system_prompt():
    corp = _make_corp(CorpProfile.Economiste)
    prompt = build_corp_system_prompt(corp)
    assert "production efficiency" in prompt.lower() or "economically" in prompt.lower()


def test_T02_expansionniste_system_prompt():
    corp = _make_corp(CorpProfile.Expansionniste)
    prompt = build_corp_system_prompt(corp)
    assert "territory" in prompt.lower() or "expansion" in prompt.lower()


def test_T03_militariste_system_prompt():
    corp = _make_corp(CorpProfile.Militariste)
    prompt = build_corp_system_prompt(corp)
    assert "dominance" in prompt.lower() or "militarist" in prompt.lower()


# ---------------------------------------------------------------------------
# T04-T07 : build_corp_context
# ---------------------------------------------------------------------------

def test_T04_context_includes_corp_and_environment():
    corp = _make_corp()
    snap = _make_snapshot()
    raw = build_corp_context(corp, tick=10, snapshot=snap)
    ctx = json.loads(raw)
    assert ctx["tick"] == 10
    assert ctx["corp"]["id"] == "corp-test"
    assert ctx["corp"]["profile"] == "Economiste"
    assert ctx["corp"]["fsmState"] == "Idle"
    assert "environment" in ctx
    assert ctx["environment"]["freeTilesAdjacent"] == 2


def test_T05_context_includes_scoreboard():
    corp = _make_corp()
    snap = _make_snapshot()
    sb = [{"corpId": "c1", "score": 100.0}]
    ctx = json.loads(build_corp_context(corp, tick=5, snapshot=snap, scoreboard=sb))
    assert ctx["scoreboard"][0]["corpId"] == "c1"


def test_T06_context_includes_memory():
    corp = _make_corp()
    snap = _make_snapshot()
    mem = AgentMemory(entityId="corp-test", entityType="corporation",
                      recentDecisions=["dec1", "dec2"], lastTickActed=5)
    ctx = json.loads(build_corp_context(corp, tick=6, snapshot=snap, memory=mem))
    assert ctx["memory"]["recentDecisions"] == ["dec1", "dec2"]
    assert ctx["memory"]["lastTickActed"] == 5


def test_T07_context_includes_recent_events():
    corp = _make_corp()
    snap = _make_snapshot()
    events = [{"name": "TempeteSolaire", "description": "Solar storm!", "tick": 3}]
    ctx = json.loads(build_corp_context(corp, tick=7, snapshot=snap, recent_events=events))
    assert ctx["recentEvents"][0]["name"] == "TempeteSolaire"


# ---------------------------------------------------------------------------
# T08 : CORP_AGENT_TOOLS_SCHEMA
# ---------------------------------------------------------------------------

def test_T08_corp_tools_schema_has_four_tools():
    names = {t["function"]["name"] for t in CORP_AGENT_TOOLS_SCHEMA}
    assert "NoOp" in names
    assert "UpdateFsmThresholds" in names
    assert "ReorderConstructionQueue" in names
    assert "ProposeContract" in names
    assert len(CORP_AGENT_TOOLS_SCHEMA) == 4


# ---------------------------------------------------------------------------
# T09-T13 : action parsing
# ---------------------------------------------------------------------------

def test_T09_parse_json_update_fsm_thresholds():
    raw = {
        "action": "UpdateFsmThresholds",
        "params": {"thresholds": {"expand_min_credits": 300.0}},
        "reasoning": "economy changed",
    }
    action = parse_action_from_json(raw, "corp-test")
    assert action.actionType == AgentActionType.UpdateFsmThresholds
    assert action.params["thresholds"]["expand_min_credits"] == 300.0


def test_T10_parse_tool_call_update_fsm_thresholds():
    tool_call = {
        "name": "UpdateFsmThresholds",
        "arguments": {"thresholds": {"idle_min_credits": 100.0}},
    }
    action = parse_action_from_tool_call(tool_call, "corp-test")
    assert action.actionType == AgentActionType.UpdateFsmThresholds


def test_T11_parse_json_reorder_construction_queue():
    raw = {
        "action": "ReorderConstructionQueue",
        "params": {"territoryId": "t1", "newOrder": ["Farm", "Mine"]},
        "reasoning": "food shortage",
    }
    action = parse_action_from_json(raw, "corp-test")
    assert action.actionType == AgentActionType.ReorderConstructionQueue
    assert action.params["newOrder"] == ["Farm", "Mine"]


def test_T12_parse_tool_call_reorder_construction_queue():
    tool_call = {
        "name": "ReorderConstructionQueue",
        "arguments": {"territoryId": "t2", "newOrder": ["Mine"]},
    }
    action = parse_action_from_tool_call(tool_call, "corp-test")
    assert action.actionType == AgentActionType.ReorderConstructionQueue


def test_T13_parse_json_claim_tile():
    raw = {"action": "ClaimTile", "params": {"tile_id": "abc123"}, "reasoning": "expand"}
    action = parse_action_from_json(raw, "corp-test")
    assert action.actionType == AgentActionType.ClaimTile


# ---------------------------------------------------------------------------
# T14-T16 : run_corp_agent
# ---------------------------------------------------------------------------

def test_T14_run_corp_agent_noop_when_no_env(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    corp = _make_corp()
    snap = _make_snapshot()
    action = run_corp_agent(corp, tick=1, snapshot=snap)
    assert action.entityId == "corp-test"
    assert action.actionType == AgentActionType.NoOp


def test_T15_run_corp_agent_parses_llm_json(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://fake-llm")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setenv("LLM_MODE", "json")

    fake_llm_response = {
        "action": "UpdateFsmThresholds",
        "params": {"thresholds": {"expand_min_credits": 400.0}},
        "reasoning": "credits are comfortable",
    }

    with unittest.mock.patch.object(
        _agent, "call_llm_json", return_value=fake_llm_response
    ):
        corp = _make_corp()
        snap = _make_snapshot()
        action = run_corp_agent(corp, tick=5, snapshot=snap)

    assert action.actionType == AgentActionType.UpdateFsmThresholds
    assert action.params["thresholds"]["expand_min_credits"] == 400.0
    assert action.entityId == "corp-test"


def test_T16_run_corp_agent_fallback_on_exception(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://fake-llm")
    monkeypatch.setenv("LLM_MODEL", "fake-model")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setenv("LLM_MODE", "json")

    with unittest.mock.patch.object(
        _agent, "call_llm_json", side_effect=RuntimeError("network error")
    ):
        corp = _make_corp()
        snap = _make_snapshot()
        action = run_corp_agent(corp, tick=5, snapshot=snap)

    assert action.actionType == AgentActionType.NoOp
    assert action.entityId == "corp-test"


# ---------------------------------------------------------------------------
# T17-T20 : runtime tests (skip if no noise)
# ---------------------------------------------------------------------------

@_skip_no_noise
def test_T17_get_corp_agent_context_returns_dict():
    from terraformation_sim.runtime import SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap()
    cid = rt.register_corporation("BotCorp", profile="Expansionniste", is_ai=True).id
    ctx = rt.get_corp_agent_context(cid)
    assert ctx is not None
    assert ctx["corpId"] == cid
    assert "environment" in ctx


@_skip_no_noise
def test_T18_get_corp_agent_context_none_for_unknown():
    from terraformation_sim.runtime import SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap()
    result = rt.get_corp_agent_context("unknown-id")
    assert result is None


@_skip_no_noise
def test_T19_run_agent_for_corp_raises_for_unknown():
    from terraformation_sim.runtime import SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap()
    with pytest.raises(ValueError, match="not found"):
        rt.run_agent_for_corp("unknown-id")


@_skip_no_noise
def test_T20_run_agent_for_corp_noop_without_llm_env(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from terraformation_sim.runtime import SimulationRuntime
    rt = SimulationRuntime()
    rt.bootstrap()
    cid = rt.register_corporation("BotCorp", profile="Economiste", is_ai=True).id
    action = rt.run_agent_for_corp(cid)
    assert action.entityId == cid
    assert action.actionType == AgentActionType.NoOp
