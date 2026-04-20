"""
Test Phase 8.5 M1 — Agent LLM models.

Tests: AgentAction round-trip, AgentMemory defaults, AgentActionType values,
       isAiControlled flag in StateData.
"""
import sys, os, importlib.util

# Load models.py directly to avoid optional C extension deps (noise, h3, etc.)
_spec = importlib.util.spec_from_file_location(
    "terraformation_sim.models",
    os.path.join(os.path.dirname(__file__), "..", "terraformation_sim", "models.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["terraformation_sim.models"] = _mod
_spec.loader.exec_module(_mod)

AgentActionType = _mod.AgentActionType
AgentAction     = _mod.AgentAction
AgentMemory     = _mod.AgentMemory
StateData       = _mod.StateData
StateType       = _mod.StateType


def test_agent_action_type_values():
    """AgentActionType enum integer values must match the C# mirror."""
    assert AgentActionType.NoOp                   == 0
    assert AgentActionType.ProposeContract        == 1
    assert AgentActionType.SetTolerance           == 2
    assert AgentActionType.TriggerNationalization == 3


def test_agent_action_round_trip():
    """AgentAction round-trips through JSON without data loss."""
    action = AgentAction(
        entityId="state-001",
        actionType=AgentActionType.SetTolerance,
        params={"newThreshold": 0.65},
        reasoning="Corporations are growing too powerful.",
    )
    serialized = action.model_dump_json()
    restored   = AgentAction.model_validate_json(serialized)
    assert restored.entityId   == "state-001"
    assert restored.actionType == AgentActionType.SetTolerance
    assert restored.params     == {"newThreshold": 0.65}
    assert restored.reasoning  == "Corporations are growing too powerful."


def test_agent_memory_defaults():
    """AgentMemory initialises with correct defaults."""
    mem = AgentMemory(entityId="state-001")
    assert mem.entityType       == "state"
    assert mem.recentDecisions  == []
    assert mem.relationshipNotes == {}
    assert mem.lastTickActed    == 0


def test_state_data_is_ai_controlled_default_false():
    """StateData.isAiControlled defaults to False (opt-in flag)."""
    state = StateData(id="s1", name="Terra Prime", stateType=StateType.Capitalist)
    assert state.isAiControlled is False


def test_state_data_is_ai_controlled_can_be_true():
    """StateData.isAiControlled can be set to True."""
    state = StateData(id="s2", name="Nova Republica", isAiControlled=True)
    assert state.isAiControlled is True
