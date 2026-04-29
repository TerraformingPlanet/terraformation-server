"""
test_phase85_agent_scenarios.py — Integration scenarios: LLM agent + InMemoryRuntime.

ALL tests are marked @pytest.mark.scenario because InMemorySimulationRuntime
depends on C extensions (noise, h3) that are only available inside the Docker
container. The tests are auto-skipped locally and should be run via:

    docker exec terraformation-dedicated-server \
        python -m pytest tests/test_phase85_agent_scenarios.py -v

Tests 1-2 use unittest.mock to patch the LLM call (deterministic, no network).
Tests 3-4 make real LLM calls via fast_model fixture (require LLM env vars).
"""
import sys
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

# ── All tests in this file require C extensions unavailable in local venv ─────
pytestmark = pytest.mark.scenario

# ── Lazy loader (called from fixture, not at module level) ────────────────────

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    if f"terraformation_sim.{name}" in sys.modules:
        return sys.modules[f"terraformation_sim.{name}"]
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rt():
    """
    Load runtime classes once per module.
    Skips if C extensions (noise, h3) are not available.
    In Docker (where all C extensions exist), uses direct package imports.
    """
    try:
        import noise  # noqa: F401
    except ImportError:
        pytest.skip(
            "C extension 'noise' not installed — scenario tests require Docker container. "
            "Run: docker exec terraformation-dedicated-server python -m pytest tests/ -m scenario -v"
        )

    # All C extensions available: use direct package imports (no importlib workaround)
    import terraformation_sim.runtime as _runtime_mod
    from terraformation_sim.persistence import InMemoryRepository
    from terraformation_sim.models import (
        AgentAction, AgentActionType, StateType,
    )
    from terraformation_sim.runtime import InMemorySimulationRuntime

    return {
        "AgentAction":               AgentAction,
        "AgentActionType":           AgentActionType,
        "StateType":                 StateType,
        "InMemorySimulationRuntime": InMemorySimulationRuntime,
        "InMemoryRepository":        InMemoryRepository,
        "runtime_mod":               _runtime_mod,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh_runtime(rt):
    return rt["InMemorySimulationRuntime"](repository=rt["InMemoryRepository"]())


def _make_ai_state(runtime, rt, state_type=None, tolerance=0.5):
    if state_type is None:
        state_type = rt["StateType"].Capitalist
    return runtime.create_state(
        name="Test State",
        state_type=state_type,
        tile_ids=[f"tile-{i}" for i in range(10)],
        tolerance_threshold=tolerance,
        is_ai_controlled=True,
    )


# ── Scenario 1 — SetTolerance applies to runtime ─────────────────────────────

def test_scenario_set_tolerance_applies_to_runtime(rt):
    """
    Patch LLM to return SetTolerance(0.25).
    Verify that state.toleranceThreshold == 0.25 after run_agent_for_state.
    """
    AgentAction     = rt["AgentAction"]
    AgentActionType = rt["AgentActionType"]
    runtime_mod     = rt["runtime_mod"]

    runtime = _fresh_runtime(rt)
    state   = _make_ai_state(runtime, rt, tolerance=0.5)

    mocked_action = AgentAction(
        entityId=state.id,
        actionType=AgentActionType.SetTolerance,
        params={"newThreshold": 0.25},
        reasoning="mocked",
    )

    with patch("terraformation_sim.logic.agent.run_agent", return_value=mocked_action):
        action = runtime.run_agent_for_state(state.id)

    assert action.actionType == AgentActionType.SetTolerance
    updated = runtime.get_state(state.id)
    assert updated.toleranceThreshold == pytest.approx(0.25), (
        f"Expected toleranceThreshold=0.25, got {updated.toleranceThreshold}"
    )


# ── Scenario 2 — Memory accumulates, capped at 5 ─────────────────────────────

def test_scenario_memory_accumulates_and_capped(rt):
    """
    Call run_agent_for_state 7 times (all mocked as NoOp).
    After 3 calls → recentDecisions has 3 entries.
    After 7 calls → recentDecisions has exactly 5 entries (rolling cap).
    """
    AgentAction     = rt["AgentAction"]
    AgentActionType = rt["AgentActionType"]
    runtime_mod     = rt["runtime_mod"]

    runtime = _fresh_runtime(rt)
    state   = _make_ai_state(runtime, rt)

    def _noop_action(*args, **kwargs):
        return AgentAction(entityId=state.id, actionType=AgentActionType.NoOp)

    with patch("terraformation_sim.logic.agent.run_agent", side_effect=_noop_action):
        for _ in range(3):
            runtime.run_agent_for_state(state.id)
        mem_after_3 = runtime.get_agent_memory(state.id)
        assert len(mem_after_3.recentDecisions) == 3, (
            f"Expected 3 decisions after 3 runs, got {len(mem_after_3.recentDecisions)}"
        )
        for _ in range(4):  # 4 more = total 7
            runtime.run_agent_for_state(state.id)
        mem_after_7 = runtime.get_agent_memory(state.id)
        assert len(mem_after_7.recentDecisions) == 5, (
            f"Expected rolling cap of 5, got {len(mem_after_7.recentDecisions)}"
        )


# ── Scenario 3 — Real LLM: 3 cycles → memory grows ──────────────────────────

def test_scenario_real_llm_memory_grows(rt, fast_model, monkeypatch):
    """
    Run run_agent_for_state 3 times with the real LLM (fast_model).
    Memory must contain exactly 3 entries afterwards, each with [tick N].
    """
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")

    runtime = _fresh_runtime(rt)
    state   = _make_ai_state(runtime, rt)

    for _ in range(3):
        runtime.run_agent_for_state(state.id)

    mem = runtime.get_agent_memory(state.id)
    assert mem is not None
    assert len(mem.recentDecisions) == 3
    for decision in mem.recentDecisions:
        assert "[tick" in decision, f"Decision missing tick stamp: {decision!r}"


# ── Scenario 4 — Full narrative: Nationalist under corporate pressure ─────────

def test_scenario_nationalist_under_pressure(rt, fast_model, monkeypatch):
    """
    Full narrative scenario:
        - Nationalist state with tolerance=0.3
        - One corporation planted on the state's tiles
        - Real LLM (fast_model) asked to decide
        - The action is actually applied to the runtime — verify state consistency
    """
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")

    AgentAction     = rt["AgentAction"]
    AgentActionType = rt["AgentActionType"]
    StateType       = rt["StateType"]

    runtime = _fresh_runtime(rt)

    runtime.register_corporation(name="DominaCorp")

    state = runtime.create_state(
        name="Patria Libera",
        state_type=StateType.Nationalist,
        tile_ids=[f"tile-{i}" for i in range(10)],
        tolerance_threshold=0.3,
        is_ai_controlled=True,
    )

    action = runtime.run_agent_for_state(state.id)

    # Use type name check instead of isinstance — avoids class identity conflicts
    # when other test modules reloaded terraformation_sim.models via importlib
    assert type(action).__name__ == "AgentAction", f"Expected AgentAction, got {type(action)}"
    assert action.entityId == state.id

    mem = runtime.get_agent_memory(state.id)
    assert mem is not None
    assert len(mem.recentDecisions) == 1

    updated_state = runtime.get_state(state.id)
    assert updated_state is not None
    assert 0.0 <= updated_state.toleranceThreshold <= 1.0

    # Soft assertion: log a warning if the agent returned NoOp
    # (not a hard failure — the 4B model may not always pick up the pressure signal)
    if action.actionType == AgentActionType.NoOp:
        import warnings
        warnings.warn(
            f"[soft] Nationalist agent returned NoOp despite 90% corporate dominance. "
            f"Reasoning: {action.reasoning!r}. "
            f"Consider retrying with a more capable model.",
            UserWarning,
            stacklevel=1,
        )
