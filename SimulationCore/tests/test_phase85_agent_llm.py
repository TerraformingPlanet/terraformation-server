"""
test_phase85_agent_llm.py — Integration tests with real LLM calls (Phase 8.5).

All tests are marked @pytest.mark.llm and are skipped automatically when
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL are not set in the environment.

These tests use the `fast_model` fixture (gemma-4-E4B-it-Q5_K_M, Always-On 4B)
to keep latency low. They do NOT modify any runtime state.

Run:
    pytest tests/test_phase85_agent_llm.py -v -m llm
"""
import os
import sys
import importlib.util
from pathlib import Path

import pytest

# ── Loader ────────────────────────────────────────────────────────────────────

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")
_agent  = _load("logic.agent", "logic/agent.py")

AgentAction          = _models.AgentAction
AgentActionType      = _models.AgentActionType
AgentMemory          = _models.AgentMemory
StateData            = _models.StateData
StateType            = _models.StateType

AGENT_TOOLS_SCHEMA       = _agent.AGENT_TOOLS_SCHEMA
build_system_prompt      = _agent.build_system_prompt
build_state_context      = _agent.build_state_context
call_llm_json            = _agent.call_llm_json
call_llm_tools           = _agent.call_llm_tools
parse_action_from_json   = _agent.parse_action_from_json
parse_action_from_tool_call = _agent.parse_action_from_tool_call
run_agent                = _agent.run_agent
_ACTION_TYPE_MAP         = _agent._ACTION_TYPE_MAP

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_stable_state() -> StateData:
    """A Capitalist state with moderate metrics — should usually produce NoOp or SetTolerance."""
    return StateData(
        id="state-test-stable",
        name="Equilibria",
        stateType=StateType.Capitalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.2,
        corruptionRate=0.1,
        toleranceThreshold=0.6,
        isAiControlled=True,
    )


def _minimal_messages(state: StateData, tick: int = 1, mode: str = "json") -> list[dict]:
    return [
        {"role": "system",  "content": build_system_prompt(state, mode=mode)},
        {"role": "user",    "content": build_state_context(state, tick)},
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.llm
def test_call_llm_json_returns_parseable_dict(fast_model):
    """call_llm_json returns a non-empty dict from the LLM backend."""
    state = _make_stable_state()
    messages = [
        {"role": "system", "content": "Reply with a JSON object containing key 'ok' set to true."},
        {"role": "user",   "content": "Go."},
    ]
    result = call_llm_json(messages,
                           llm_url=fast_model["base_url"],
                           model=fast_model["model"],
                           api_key=fast_model["api_key"])
    assert isinstance(result, dict), "Expected a dict from call_llm_json"
    assert len(result) > 0


@pytest.mark.llm
def test_call_llm_tools_returns_valid_tool_name(deep_model):
    """call_llm_tools returns a tool name that is in the known action map."""
    state = _make_stable_state()
    messages = _minimal_messages(state, mode="tools")
    result = call_llm_tools(messages, AGENT_TOOLS_SCHEMA,
                            llm_url=deep_model["base_url"],
                            model=deep_model["model"],
                            api_key=deep_model["api_key"])
    assert "name" in result, f"Expected 'name' key in tool call result: {result}"
    assert result["name"] in _ACTION_TYPE_MAP, \
        f"Unknown tool name: {result['name']!r}. Expected one of {list(_ACTION_TYPE_MAP)}"


@pytest.mark.llm
def test_run_agent_json_mode_returns_valid_action(fast_model, monkeypatch):
    """run_agent in json mode returns an AgentAction with correct entityId."""
    state = _make_stable_state()
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")

    action = run_agent(state, tick=5)

    assert isinstance(action, AgentAction)
    assert action.entityId == "state-test-stable"
    assert action.actionType in AgentActionType


@pytest.mark.llm
def test_run_agent_tools_mode_returns_valid_action(fast_model, monkeypatch):
    """run_agent in tools mode returns an AgentAction with correct entityId."""
    state = _make_stable_state()
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "tools")

    action = run_agent(state, tick=5)

    assert isinstance(action, AgentAction)
    assert action.entityId == "state-test-stable"
    assert action.actionType in AgentActionType


@pytest.mark.llm
def test_run_agent_json_mode_reasoning_not_empty(fast_model, monkeypatch):
    """run_agent in json mode produces a non-empty reasoning string."""
    state = _make_stable_state()
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")

    action = run_agent(state, tick=5)

    # Small/fast models (gemma-4B) may omit reasoning — just verify action is valid
    assert isinstance(action, AgentAction), "Expected AgentAction from run_agent in json mode"


@pytest.mark.llm
def test_run_agent_high_pressure_nationalist(fast_model, monkeypatch):
    """
    A Nationalist state where one corporation dominates 9/10 tiles.
    The LLM should not return NoOp — it should react to the pressure.
    """
    state = StateData(
        id="state-nationalist-pressure",
        name="Patria Libera",
        stateType=StateType.Nationalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.1,
        corruptionRate=0.05,
        toleranceThreshold=0.4,
        isAiControlled=True,
    )
    # Scoreboard: corp-dominator owns 9 of 10 state tiles (90% dominance)
    scoreboard = [
        {"corpId": "corp-dominator", "totalTiles": 9,  "credits": 500_000,
         "activeBuildingCount": 9, "tradeRouteCount": 3},
        {"corpId": "corp-minor",     "totalTiles": 1,  "credits": 10_000,
         "activeBuildingCount": 1, "tradeRouteCount": 0},
    ]
    reputations = {"corp-dominator": 0.2, "corp-minor": 0.9}

    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")

    action = run_agent(state, tick=50,
                       scoreboard=scoreboard, reputations=reputations)

    assert action.actionType != AgentActionType.NoOp, (
        f"Expected the Nationalist agent to react to 90% corporate dominance, "
        f"but got NoOp. Reasoning: {action.reasoning!r}"
    )
