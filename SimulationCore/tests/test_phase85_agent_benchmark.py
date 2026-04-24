"""
test_phase85_agent_benchmark.py — Comparaison multi-modèles de l'agent LLM (Phase 8.5).

Chaque test tourne sur chaque modèle listé dans LLM_BENCHMARK_MODELS.
À la fin, pytest affiche un tableau récapitulatif ✅/❌ + latence.

Configuration :
    export LLM_BENCHMARK_MODELS=gemma4,Qwen3.6,qwen3.5-sonnet-30b
    pytest tests/test_phase85_agent_benchmark.py -m llm_benchmark -v

Sans la variable, seul gemma4 est testé.

Scénarios agent (décision d'état) :
    json_parse        — Le modèle répond un JSON valide (test de base)
    tools_call        — Le modèle utilise le bon outil d'action d'état
    stable_noop       — État stable → NoOp ou SetTolerance attendu
    nationalist_react — État sous pression → NE DOIT PAS retourner NoOp
    capitalist_crisis — État en crise → ProposeContract ou SetTolerance attendu

Scénarios MCP gameplay (sélection d'outil MCP) :
    mcp_advance_tick    — "Avancer de 5 ticks" → advance_simulation_tick(steps=5)
    mcp_world_inspect   — "Voir l'état du monde" → get_world_state
    mcp_irrigate_cell   — "Cellule sèche en (2,-1)" → queue_server_terraform_action(Irrigate,q,r)
    mcp_open_region     — "Ouvrir région lat=0.85 lon=0.32" → open_server_region
    mcp_coherence_check — "Vérifier cohérence après ouverture" → run_validation
"""
import sys
import time
from pathlib import Path

import pytest

# ── Imports ────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent))

from terraformation_sim.models import AgentAction, AgentActionType, StateData, StateType  # noqa: E402
from terraformation_sim.logic.agent import (  # noqa: E402
    AGENT_TOOLS_SCHEMA,
    build_system_prompt,
    build_state_context,
    call_llm_json,
    call_llm_tools,
    run_agent,
    _ACTION_TYPE_MAP,
)

# ── Scénarios ─────────────────────────────────────────────────────────────────

def _state_stable() -> StateData:
    return StateData(
        id="bench-stable",
        name="Equilibria",
        stateType=StateType.Capitalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.2,
        corruptionRate=0.1,
        toleranceThreshold=0.6,
        isAiControlled=True,
    )


def _state_nationalist_pressure() -> StateData:
    return StateData(
        id="bench-nationalist",
        name="Patria Libera",
        stateType=StateType.Nationalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.1,
        corruptionRate=0.05,
        toleranceThreshold=0.4,
        isAiControlled=True,
    )


def _state_capitalist_crisis() -> StateData:
    # toleranceThreshold=0.7 (permissive) + high corruption/bureaucracy → model MUST tighten
    # With 0.3 (already strict), models reason "I'm already strict → NoOp" which is wrong.
    return StateData(
        id="bench-crisis",
        name="Bankograd",
        stateType=StateType.Capitalist,
        tileIds=[f"t{i}" for i in range(10)],
        bureaucracy=0.6,
        corruptionRate=0.5,
        toleranceThreshold=0.7,
        isAiControlled=True,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_json_parse(benchmark_model, bench_recorder):
    """Le modèle retourne un JSON valide avec la clé 'ok'."""
    messages = [
        {"role": "system", "content": "Reply ONLY with a JSON object containing key 'ok' set to true."},
        {"role": "user",   "content": "Go."},
    ]
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = call_llm_json(
            messages,
            llm_url=benchmark_model["base_url"],
            model=benchmark_model["model"],
            api_key=benchmark_model["api_key"],
            temperature=0.0,
        )
        passed = isinstance(result, dict) and len(result) > 0
        detail = str(result)[:80]
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("json_parse", passed, latency, detail, max_latency_s=20.0)
    assert passed, f"[{benchmark_model['_name']}] json_parse failed — {detail}"


_FAST_TIER_MODELS = {"gemma4"}  # modèles trop petits pour le function calling


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_tools_call(benchmark_model, bench_recorder):
    """Le modèle appelle le bon tool depuis le schéma d'actions (tools API, sans JSON schema dans le prompt)."""
    if benchmark_model["_name"] in _FAST_TIER_MODELS:
        pytest.skip(f"{benchmark_model['_name']} is a FAST-tier model — function calling not supported")
    state = _state_stable()
    # Prompt neutre sans instruction JSON — le test valide le tools API pur
    messages = [
        {"role": "system", "content": (
            "You are an AI agent managing a state in a strategy game. "
            "Use the available tools to decide what action to take this tick."
        )},
        {"role": "user", "content": build_state_context(state, tick=1)},
    ]
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = call_llm_tools(
            messages,
            AGENT_TOOLS_SCHEMA,
            llm_url=benchmark_model["base_url"],
            model=benchmark_model["model"],
            api_key=benchmark_model["api_key"],
            temperature=0.1,  # 0.0 cause des freezes sur les grands modèles (26B+)
        )
        passed = "name" in result and result["name"] in _ACTION_TYPE_MAP
        detail = f"tool={result.get('name','?')}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("tools_call", passed, latency, detail, max_latency_s=20.0)
    assert passed, f"[{benchmark_model['_name']}] tools_call failed — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_stable_noop(benchmark_model, bench_recorder, monkeypatch):
    """
    État stable → le modèle doit choisir NoOp ou SetTolerance (réponse conservatrice).
    Un ProposeContract ou TriggerNationalization sur état sain = erreur de jugement.
    """
    state = _state_stable()
    monkeypatch.setenv("LLM_BASE_URL", benchmark_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  benchmark_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    benchmark_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")
    monkeypatch.delenv("LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("LLM_MODEL_DEEP", raising=False)

    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        action = run_agent(state, tick=5)
        conservative = {AgentActionType.NoOp, AgentActionType.SetTolerance}
        passed = action.actionType in conservative
        detail = f"action={action.actionType.name}, reasoning={action.reasoning[:60]!r}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("stable_noop", passed, latency, detail, max_latency_s=30.0)
    assert passed, f"[{benchmark_model['_name']}] stable_noop: expected NoOp/SetTolerance — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_nationalist_react(benchmark_model, bench_recorder, monkeypatch):
    """
    État nationaliste sous forte pression corpo (90% dominance simulée via scoreboard).
    Le modèle NE DOIT PAS retourner NoOp — il doit réagir.
    """
    state = _state_nationalist_pressure()
    # Scoreboard explicite : mega-corp occupe 9/10 tuiles = 90% > tolerance 0.4
    scoreboard_90pct = [
        {"corpId": "mega-corp",  "totalTiles": 9, "credits": 500_000,
         "activeBuildingCount": 8, "tradeRouteCount": 3},
        {"corpId": "small-corp", "totalTiles": 1, "credits": 2_000,
         "activeBuildingCount": 1, "tradeRouteCount": 0},
    ]
    monkeypatch.setenv("LLM_BASE_URL", benchmark_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  benchmark_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    benchmark_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")
    monkeypatch.delenv("LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("LLM_MODEL_DEEP", raising=False)

    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        action = run_agent(state, tick=10, scoreboard=scoreboard_90pct)
    except Exception as exc:
        detail = str(exc)[:80]
        bench_recorder("nationalist_react", False, time.perf_counter() - t0, detail, max_latency_s=120.0)
        pytest.fail(f"[{benchmark_model['_name']}] nationalist_react error — {detail}")

    latency = time.perf_counter() - t0
    passed = action.actionType != AgentActionType.NoOp
    detail = f"action={action.actionType.name}, reasoning={action.reasoning[:60]!r}"
    bench_recorder("nationalist_react", passed, latency, detail, max_latency_s=120.0)
    assert passed, f"[{benchmark_model['_name']}] nationalist_react: should NOT return NoOp — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_capitalist_crisis(benchmark_model, bench_recorder, monkeypatch):
    """
    État capitaliste en crise (bureaucratie 0.6, corruption 0.5, seuil bas 0.3).
    Réponse pertinente = ProposeContract ou SetTolerance. NoOp = mauvais jugement.
    """
    state = _state_capitalist_crisis()
    monkeypatch.setenv("LLM_BASE_URL", benchmark_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  benchmark_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    benchmark_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")
    monkeypatch.delenv("LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("LLM_MODEL_DEEP", raising=False)

    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        action = run_agent(state, tick=20)
        expected = {AgentActionType.ProposeContract, AgentActionType.SetTolerance}
        passed = action.actionType in expected
        detail = f"action={action.actionType.name}, reasoning={action.reasoning[:60]!r}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("capitalist_crisis", passed, latency, detail, max_latency_s=120.0)
    assert passed, f"[{benchmark_model['_name']}] capitalist_crisis: expected ProposeContract/SetTolerance — {detail}"


# ═══════════════════════════════════════════════════════════════════════════════
# Scénarios MCP gameplay — le modèle doit choisir le bon outil MCP du serveur
# ═══════════════════════════════════════════════════════════════════════════════

# Schéma OpenAI des outils MCP gameplay (miroir des tools réels de Mcp/server.py)
_MCP_GAMEPLAY_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "advance_simulation_tick",
            "description": "Advance the dedicated simulation by N ticks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {"type": "integer", "description": "Number of ticks to advance (default 1)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_world_state",
            "description": "Get the full authoritative world snapshot from the simulation server.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_server_region",
            "description": "Open and load a region of the planet at the given normalized coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude":  {"type": "number", "description": "Normalized latitude [0, 1]."},
                    "longitude": {"type": "number", "description": "Normalized longitude [0, 1]."},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "queue_server_terraform_action",
            "description": (
                "Queue a terraformation action on the simulation. "
                "TerraformAction enum: Heat=0, Irrigate=1, Plant=2, Mine=3, Detoxify=4."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_type": {"type": "integer", "description": "TerraformAction enum value."},
                    "q": {"type": "integer", "description": "Axial q coordinate of target cell."},
                    "r": {"type": "integer", "description": "Axial r coordinate of target cell."},
                },
                "required": ["action_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_validation",
            "description": (
                "Validate region coherence: flags cells where waterClassification contradicts "
                "waterRatio or temperature. Requires an active region."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hydrology_stats",
            "description": "Get hydrology distribution statistics (ocean%, coast%, dry%, frozen%) for the active region.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_simulation_event",
            "description": "Retrieve the last event emitted by the simulation runtime (tick advance, region load, etc.).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

_MCP_SYSTEM = (
    "You are an AI assistant controlling the Terraformation simulation server. "
    "You have access to a set of tools to interact with the simulation. "
    "For each user request, call EXACTLY ONE tool with the correct arguments. "
    "Do not explain — just call the tool."
)


def _mcp_tool_call(model_cfg: dict, user_prompt: str) -> dict:
    """Helper: ask the LLM to pick a tool from _MCP_GAMEPLAY_TOOLS and return the raw tool call dict."""
    messages = [
        {"role": "system", "content": _MCP_SYSTEM},
        {"role": "user",   "content": user_prompt},
    ]
    return call_llm_tools(
        messages,
        _MCP_GAMEPLAY_TOOLS,
        llm_url=model_cfg["base_url"],
        model=model_cfg["model"],
        api_key=model_cfg["api_key"],
    )


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_mcp_advance_tick(benchmark_model, bench_recorder):
    """
    L'utilisateur veut avancer de 5 ticks.
    → doit appeler advance_simulation_tick avec steps proche de 5.
    """
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = _mcp_tool_call(benchmark_model, "Advance the simulation by 5 ticks.")
        name   = result.get("name", "")
        args   = result.get("arguments", {})
        # steps doit être fourni et proche de 5 (tolérance ±1 pour les modèles créatifs)
        steps  = args.get("steps", None)
        passed = (name == "advance_simulation_tick") and (steps is not None) and (4 <= int(steps) <= 6)
        detail = f"name={name}, args={args}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("mcp_advance_tick", passed, latency, detail, max_latency_s=25.0)
    assert passed, f"[{benchmark_model['_name']}] mcp_advance_tick failed — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_mcp_world_inspect(benchmark_model, bench_recorder):
    """
    L'utilisateur veut voir l'état du monde.
    → doit appeler get_world_state (ou get_last_simulation_event).
    """
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = _mcp_tool_call(benchmark_model, "Show me the current state of the world simulation.")
        name   = result.get("name", "")
        passed = name in {"get_world_state", "get_client_snapshot", "get_last_simulation_event"}
        detail = f"name={name}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("mcp_world_inspect", passed, latency, detail, max_latency_s=25.0)
    assert passed, f"[{benchmark_model['_name']}] mcp_world_inspect failed — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_mcp_irrigate_cell(benchmark_model, bench_recorder):
    """
    Cellule sèche en (q=2, r=-1) — irriguer.
    → queue_server_terraform_action(action_type=1 [Irrigate], q=2, r=-1)
    """
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = _mcp_tool_call(
            benchmark_model,
            "Cell at axial coordinates q=2, r=-1 is classified as Dry despite having residual water. "
            "Apply an irrigation terraform action on it.",
        )
        name = result.get("name", "")
        args = result.get("arguments", {})
        passed = (
            name == "queue_server_terraform_action"
            and args.get("action_type") == 1   # Irrigate
            and args.get("q") == 2
            and args.get("r") == -1
        )
        detail = f"name={name}, args={args}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("mcp_irrigate_cell", passed, latency, detail, max_latency_s=25.0)
    assert passed, f"[{benchmark_model['_name']}] mcp_irrigate_cell failed — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_mcp_open_region(benchmark_model, bench_recorder):
    """
    Ouvrir la région polaire nord à lat=0.85, lon=0.32.
    → open_server_region(latitude=0.85, longitude=0.32)
    """
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = _mcp_tool_call(
            benchmark_model,
            "Open and load the region at normalized latitude 0.85, longitude 0.32.",
        )
        name = result.get("name", "")
        args = result.get("arguments", {})
        # Tolérance 0.02 pour les arrondis de flottants
        lat_ok = abs(float(args.get("latitude",  0)) - 0.85) < 0.02
        lon_ok = abs(float(args.get("longitude", 0)) - 0.32) < 0.02
        passed = (name == "open_server_region") and lat_ok and lon_ok
        detail = f"name={name}, args={args}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("mcp_open_region", passed, latency, detail, max_latency_s=25.0)
    assert passed, f"[{benchmark_model['_name']}] mcp_open_region failed — {detail}"


@pytest.mark.llm_benchmark
@pytest.mark.llm
def test_bench_mcp_coherence_check(benchmark_model, bench_recorder):
    """
    Après ouverture d'une région, vérifier la cohérence des cellules.
    → run_validation (ou get_hydrology_stats — acceptable aussi)
    """
    t0 = time.perf_counter()
    passed = False
    detail = ""
    try:
        result = _mcp_tool_call(
            benchmark_model,
            "I just opened a region. Check that all cells have coherent water classification "
            "relative to their actual water ratio and temperature.",
        )
        name   = result.get("name", "")
        passed = name in {"run_validation", "get_hydrology_stats"}
        detail = f"name={name}"
    except Exception as exc:
        detail = str(exc)[:80]
    latency = time.perf_counter() - t0

    bench_recorder("mcp_coherence_check", passed, latency, detail, max_latency_s=25.0)
    assert passed, f"[{benchmark_model['_name']}] mcp_coherence_check failed — {detail}"
