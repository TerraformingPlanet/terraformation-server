"""
test_phase85_agent_logic.py — Pure unit tests for logic/agent.py (Phase 8.5).

No Docker, no LLM calls, no network. All tests run in < 0.5 s.
Tests cover: build_system_prompt, build_state_context, parse_action_from_json,
             parse_action_from_tool_call, run_agent fallback with missing env.
"""
import json
import os
import sys
import importlib.util
from pathlib import Path
from unittest.mock import patch

# ── Load models.py and logic/agent.py without triggering __init__.py ─────────

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models    = _load("models", "models.py")
# logic/corp_fsm.py is imported by agent.py — pre-register it to avoid
# triggering terraformation_sim/__init__.py → generation.py → noise
_corp_fsm  = _load("logic.corp_fsm", "logic/corp_fsm.py")
# logic/agent.py imports from ..models — the sys.modules entry above satisfies it
_agent     = _load("logic.agent", "logic/agent.py")

AgentAction     = _models.AgentAction
AgentActionType = _models.AgentActionType
AgentMemory     = _models.AgentMemory
StateData       = _models.StateData
StateType       = _models.StateType

build_system_prompt      = _agent.build_system_prompt
build_state_context      = _agent.build_state_context
parse_action_from_json   = _agent.parse_action_from_json
parse_action_from_tool_call = _agent.parse_action_from_tool_call
run_agent                = _agent.run_agent

# ── build_system_prompt ───────────────────────────────────────────────────────

def test_build_system_prompt_capitalist():
    state = StateData(id="s1", name="Terra Prima", stateType=StateType.Capitalist)
    prompt = build_system_prompt(state)
    assert "capitalist" in prompt.lower()
    # 5 IMPORTANT RULES must all be present
    for i in range(1, 6):
        assert f"{i}." in prompt


def test_build_system_prompt_nationalist():
    state = StateData(id="s2", name="Nova Patria", stateType=StateType.Nationalist)
    prompt = build_system_prompt(state)
    assert "nationalist" in prompt.lower()
    assert "nationalization" in prompt.lower()


# ── build_state_context ───────────────────────────────────────────────────────

def test_build_state_context_minimal():
    state = StateData(id="s3", name="Minimis", stateType=StateType.Capitalist)
    ctx_str = build_state_context(state, tick=42)
    ctx = json.loads(ctx_str)
    assert ctx["tick"] == 42
    assert ctx["state"]["id"] == "s3"
    assert ctx["state"]["type"] == "Capitalist"
    assert "scoreboard" not in ctx
    assert "recentEvents" not in ctx


def test_build_state_context_full():
    state = StateData(id="s4", name="Maximus", stateType=StateType.Nationalist,
                      bureaucracy=0.3, corruptionRate=0.2, toleranceThreshold=0.4)
    mem = AgentMemory(entityId="s4", recentDecisions=["NoOp", "SetTolerance"],
                      lastTickActed=10)
    ctx_str = build_state_context(
        state, tick=100,
        scoreboard=[{"corpId": "c1", "totalTiles": 5}],
        recent_events=[{"type": "TaxCollected"}],
        memory=mem,
        reputations={"c1": 0.8},
    )
    ctx = json.loads(ctx_str)
    assert ctx["scoreboard"][0]["corpId"] == "c1"
    assert ctx["recentEvents"][0]["type"] == "TaxCollected"
    assert ctx["reputations"]["c1"] == 0.8
    assert ctx["memory"]["recentDecisions"] == ["NoOp", "SetTolerance"]
    assert ctx["memory"]["lastTickActed"] == 10
    # State fields propagated
    assert ctx["state"]["bureaucracy"] == 0.3
    assert ctx["state"]["toleranceThreshold"] == 0.4


def test_build_state_context_memory_rolling_max_5():
    """build_state_context only exposes the last 5 decisions from memory."""
    state = StateData(id="s5", name="Overflow")
    mem = AgentMemory(entityId="s5",
                      recentDecisions=["A", "B", "C", "D", "E", "F", "G"])
    ctx = json.loads(build_state_context(state, tick=1, memory=mem))
    assert ctx["memory"]["recentDecisions"] == ["C", "D", "E", "F", "G"]


# ── parse_action_from_json ────────────────────────────────────────────────────

def test_parse_action_from_json_set_tolerance():
    raw = {"action": "SetTolerance", "params": {"newThreshold": 0.4},
           "reasoning": "corps too powerful"}
    action = parse_action_from_json(raw, "s1")
    assert action.entityId   == "s1"
    assert action.actionType == AgentActionType.SetTolerance
    assert action.params     == {"newThreshold": 0.4}
    assert action.reasoning  == "corps too powerful"


def test_parse_action_from_json_unknown_action():
    """Unknown action name → NoOp fallback."""
    raw = {"action": "LaunchNukes", "params": {}, "reasoning": "yolo"}
    action = parse_action_from_json(raw, "s2")
    assert action.actionType == AgentActionType.NoOp
    assert action.entityId   == "s2"


def test_parse_action_from_json_malformed_input():
    """None input → NoOp fallback, no exception raised."""
    action = parse_action_from_json(None, "s3")  # type: ignore[arg-type]
    assert action.actionType == AgentActionType.NoOp
    assert action.entityId   == "s3"


# ── parse_action_from_tool_call ───────────────────────────────────────────────

def test_parse_action_from_tool_call_noop():
    tool = {"name": "NoOp", "arguments": {}}
    action = parse_action_from_tool_call(tool, "s4")
    assert action.actionType == AgentActionType.NoOp
    assert action.params     == {}


def test_parse_action_from_tool_call_nationalization():
    tool = {"name": "TriggerNationalization",
            "arguments": {"targetCorpId": "corp-x", "tileId": "tile-42"}}
    action = parse_action_from_tool_call(tool, "s5")
    assert action.actionType        == AgentActionType.TriggerNationalization
    assert action.params["targetCorpId"] == "corp-x"
    assert action.params["tileId"]       == "tile-42"


# ── run_agent fallback ────────────────────────────────────────────────────────

def test_run_agent_no_env_vars_returns_noop():
    """run_agent returns NoOp immediately when LLM env vars are missing."""
    state = StateData(id="s6", name="Isolated", isAiControlled=True)
    with patch.dict(os.environ, {"LLM_BASE_URL": "", "LLM_MODEL": "", "LLM_API_KEY": ""},
                    clear=False):
        action = run_agent(state, tick=1)
    assert action.actionType == AgentActionType.NoOp
    assert action.entityId   == "s6"
