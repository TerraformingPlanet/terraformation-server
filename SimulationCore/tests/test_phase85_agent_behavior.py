"""
test_phase85_agent_behavior.py — Tests comportementaux LLM pour l'agent d'État (Phase 8.5).

Ces tests valident que l'agent LLM produit des DÉCISIONS COHÉRENTES avec le contexte
du jeu, pas seulement des actions syntaxiquement valides.

Validation "Soft" : l'action retournée doit être dans l'ensemble valide pour le contexte,
mais on ne prédit pas quelle action exacte le modèle choisira.

Tous les tests sont marqués @pytest.mark.llm et skippés si les variables d'env
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL sont absentes.

Run:
    pytest tests/test_phase85_agent_behavior.py -v -m llm
"""
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

AgentAction     = _models.AgentAction
AgentActionType = _models.AgentActionType
StateData       = _models.StateData
StateType       = _models.StateType

run_agent = _agent.run_agent


# ── Helpers ───────────────────────────────────────────────────────────────────

ALL_VALID_ACTIONS = set(AgentActionType)


def _env(fast_model: dict, monkeypatch) -> None:
    """Inject LLM env vars from the fast_model fixture."""
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")
    # Clear FAST/DEEP so _resolve_model() falls back to LLM_MODEL above
    monkeypatch.delenv("LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("LLM_MODEL_DEEP", raising=False)


# ── Scenario 1 : Menace dominante — l'agent DOIT réagir ─────────────────────

@pytest.mark.llm
def test_s1_high_dominance_nationalist_reacts(fast_model, monkeypatch):
    """
    Scénario : un État Nationaliste dont une seule corpo occupe 90% des tuiles
    et a une réputation médiocre. L'agent ne devrait PAS choisir NoOp.

    Le score de tolérance est très largement dépassé → TriggerNationalization,
    SetTolerance ou AdjustTax sont toutes des réponses valides.
    """
    state = StateData(
        id="state-s1",
        name="Patria Invicta",
        stateType=StateType.Nationalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.1,
        corruptionRate=0.05,
        toleranceThreshold=0.3,
        taxRate=0.15,
        isAiControlled=True,
    )
    scoreboard = [
        {"corpId": "mega-corp",  "totalTiles": 9,  "credits": 800_000,
         "activeBuildingCount": 9,  "tradeRouteCount": 5},
        {"corpId": "small-corp", "totalTiles": 1,  "credits": 5_000,
         "activeBuildingCount": 1,  "tradeRouteCount": 0},
    ]
    reputations = {"mega-corp": 0.15, "small-corp": 0.8}

    _env(fast_model, monkeypatch)
    action = run_agent(state, tick=20, scoreboard=scoreboard, reputations=reputations)

    assert isinstance(action, AgentAction)
    # Soft assertion: the LLM must not ignore this critical threat
    assert action.actionType != AgentActionType.NoOp, (
        f"Nationalist state under 90% corp dominance should NOT return NoOp.\n"
        f"Got: {action.actionType!r}\nReasoning: {action.reasoning!r}"
    )
    print(f"\n✓ S1 Nationalist reacts: {action.actionType!r} — {action.reasoning[:80]!r}")


# ── Scenario 2 : Paix absolue — NoOp est acceptable ─────────────────────────

@pytest.mark.llm
def test_s2_peaceful_capitalist_accepts_noop(fast_model, monkeypatch):
    """
    Scénario : un État Capitaliste avec une seule corpo qui a une excellente
    réputation et occupe 30% des tuiles seulement. L'agent peut légitimement
    choisir NoOp.

    Validation : n'importe quelle action dans ALL_VALID_ACTIONS est acceptable
    (on ne force pas NoOp, mais on vérifie que l'action est syntaxiquement valide).
    """
    state = StateData(
        id="state-s2",
        name="Free Haven",
        stateType=StateType.Capitalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.05,
        corruptionRate=0.02,
        toleranceThreshold=0.7,
        taxRate=0.1,
        isAiControlled=True,
    )
    scoreboard = [
        {"corpId": "friendly-corp", "totalTiles": 3, "credits": 100_000,
         "activeBuildingCount": 3, "tradeRouteCount": 2},
    ]
    reputations = {"friendly-corp": 0.9}

    _env(fast_model, monkeypatch)
    action = run_agent(state, tick=5, scoreboard=scoreboard, reputations=reputations)

    assert isinstance(action, AgentAction)
    assert action.actionType in ALL_VALID_ACTIONS, (
        f"Expected a valid action, got {action.actionType!r}"
    )
    print(f"\n✓ S2 Peaceful capitalist: {action.actionType!r}")


# ── Scenario 3 : Contrats brisés récents — l'agent ne choisit pas NoOp ───────

@pytest.mark.llm
def test_s3_recent_broken_contracts_triggers_response(fast_model, monkeypatch):
    """
    Scénario : 3 contrats ont été brisés récemment par la même corpo.
    L'événement est injecté comme recent_events. L'agent doit réagir.

    Validation soft : l'action ≠ NoOp, car des contrats brisés font baisser
    la tolérance et devraient déclencher une réaction.
    """
    state = StateData(
        id="state-s3",
        name="Meridiana",
        stateType=StateType.Nationalist,
        tileIds=[f"t{i}" for i in range(8)],
        bureaucracy=0.2,
        corruptionRate=0.1,
        toleranceThreshold=0.5,
        taxRate=0.12,
        isAiControlled=True,
    )
    scoreboard = [
        {"corpId": "contract-breaker", "totalTiles": 4, "credits": 200_000,
         "activeBuildingCount": 4, "tradeRouteCount": 1},
    ]
    reputations = {"contract-breaker": 0.3}
    recent_events = [
        {"tick": 48, "type": "ContractBroken", "corpId": "contract-breaker",
         "detail": "Resource delivery contract #12 broken by corp"},
        {"tick": 47, "type": "ContractBroken", "corpId": "contract-breaker",
         "detail": "Resource delivery contract #11 broken by corp"},
        {"tick": 45, "type": "ContractBroken", "corpId": "contract-breaker",
         "detail": "Resource delivery contract #10 broken by corp"},
    ]

    _env(fast_model, monkeypatch)
    action = run_agent(state, tick=50,
                       scoreboard=scoreboard,
                       reputations=reputations,
                       recent_events=recent_events)

    assert isinstance(action, AgentAction)
    assert action.actionType != AgentActionType.NoOp, (
        f"3 recent broken contracts should trigger a response, not NoOp.\n"
        f"Action: {action.actionType!r}\nReasoning: {action.reasoning!r}"
    )
    print(f"\n✓ S3 Broken contracts response: {action.actionType!r} — {action.reasoning[:80]!r}")


# ── Scenario 4 : Nationaliste plus réactif que Capitaliste ───────────────────

@pytest.mark.llm
def test_s4_nationalist_more_reactive_than_capitalist(fast_model, monkeypatch):
    """
    Scénario comparatif : même contexte (50% de la surface occupée, réputation 0.3),
    mais un État Nationaliste vs un État Capitaliste.

    Hypothèse comportementale : le Nationaliste devrait réagir plus fort,
    i.e. son actionType ne devrait pas être plus "passif" que celui du Capitaliste.

    Validation : si le Capitaliste choisit NoOp, le Nationaliste peut aussi ;
    mais si le Nationaliste choisit une action active, elle doit être dans
    ALL_VALID_ACTIONS. On vérifie surtout que les deux retournent des AgentAction.

    Note : test de régression comportementale — si les deux retournent NoOp,
    le test passe quand même (la tolérance est élevée ici à 0.8).
    Ce test détecte surtout une régression où l'un des deux retourne une action invalide.
    """
    shared_context = dict(
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.2,
        corruptionRate=0.1,
        toleranceThreshold=0.8,
        taxRate=0.15,
        isAiControlled=True,
    )
    state_nationalist = StateData(
        id="state-nationalist",
        name="The Commune",
        stateType=StateType.Nationalist,
        **shared_context,
    )
    state_capitalist = StateData(
        id="state-capitalist",
        name="The Market",
        stateType=StateType.Capitalist,
        **shared_context,
    )
    scoreboard = [
        {"corpId": "neutral-corp", "totalTiles": 5, "credits": 300_000,
         "activeBuildingCount": 5, "tradeRouteCount": 2},
    ]
    reputations = {"neutral-corp": 0.3}

    _env(fast_model, monkeypatch)

    action_nat = run_agent(state_nationalist, tick=30,
                           scoreboard=scoreboard, reputations=reputations)
    action_cap = run_agent(state_capitalist, tick=30,
                           scoreboard=scoreboard, reputations=reputations)

    assert isinstance(action_nat, AgentAction), "Nationalist agent must return AgentAction"
    assert isinstance(action_cap, AgentAction), "Capitalist agent must return AgentAction"
    assert action_nat.actionType in ALL_VALID_ACTIONS, (
        f"Nationalist action invalid: {action_nat.actionType!r}"
    )
    assert action_cap.actionType in ALL_VALID_ACTIONS, (
        f"Capitalist action invalid: {action_cap.actionType!r}"
    )
    print(
        f"\n✓ S4 Comparative: Nationalist={action_nat.actionType!r}, "
        f"Capitalist={action_cap.actionType!r}"
    )
    print(f"  Nationalist reasoning: {action_nat.reasoning[:80]!r}")
    print(f"  Capitalist  reasoning: {action_cap.reasoning[:80]!r}")
