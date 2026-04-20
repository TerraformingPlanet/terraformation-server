# Skill — llm-agent-entity

## Quand utiliser ce skill

Quand on ajoute, modifie ou debug l'agent LLM qui pilote les États IA dans Terraformation (Phase 8.5+).

Triggers : `agent LLM`, `isAiControlled`, `run_agent_for_state`, `logic/agent.py`, `AgentAction`, `AgentMemory`, `LLM_BASE_URL`, `LLM_MODE`.

---

## Architecture en 4 couches

```
OpenWebUI LLM  (VPN Tailscale)
      ↕  HTTPS  OpenAI-compatible API
logic/agent.py  (fonctions pures, sans état)
      ↕  appel synchrone
runtime.py  _run_agent_for_state_bg()  (thread daemon)
      ↕  HTTP
DedicatedServer /game/agent/*  (FastAPI)
      ↕
Mcp/server.py  get_agent_context / run_agent_for_state / get_agent_memory
```

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `SimulationCore/terraformation_sim/logic/agent.py` | Fonctions pures : `build_system_prompt`, `build_state_context`, `call_llm_json`, `call_llm_tools`, `parse_action_from_json`, `parse_action_from_tool_call`, `run_agent` |
| `SimulationCore/terraformation_sim/models.py` | Modèles : `AgentActionType`, `AgentAction`, `AgentMemory`, `StateData.isAiControlled` |
| `SimulationCore/terraformation_sim/runtime.py` | Intégration : `run_agent_for_state()`, `_run_agent_for_state_bg()`, `_apply_agent_action_locked()`, `_update_agent_memory_locked()`, `get_agent_context()`, `get_agent_memory()`, hook tick |
| `DedicatedServer/app/server.py` | Endpoints : `GET /game/agent/context/{id}`, `POST /game/agent/run/{id}`, `GET /game/agent/memory/{id}` |
| `Mcp/server.py` | Tools MCP : `get_agent_context`, `run_agent_for_state`, `get_agent_memory` |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Miroirs C# : `AgentActionType`, `AgentAction`, `AgentMemory` |
| `.env.example` | Template de configuration LLM |

---

## Variables d'environnement

```
LLM_BASE_URL=https://ai.prv.jerem.ovh/openai   # pas de slash final, pas de /v1
LLM_MODEL=Qwen3.6-35B-A3B-MXFP4_MOE
LLM_API_KEY=sk-...                              # générer depuis OpenWebUI Settings → API Keys
LLM_MODE=tools                                  # "json" | "tools"
AGENT_TICK_INTERVAL=10                          # ticks entre chaque cycle agent
```

Modèle de dev/test rapide (Always-On 4B) : `gemma-4-E4B-it-Q5_K_M`

---

## Modes LLM

| Mode | Mécanisme | Compatibilité | Usage |
|------|-----------|---------------|-------|
| `tools` | function-calling natif OpenAI | Qwen3, modèles function-calling | Prod |
| `json` | `response_format={"type":"json_object"}` | Tous modèles | Fallback / dev |

Schema attendu en mode `json` :
```json
{"action": "SetTolerance", "params": {"newThreshold": 0.4}, "reasoning": "..."}
```

---

## Règles d'implémentation

1. **Tout appel LLM se fait HORS du lock runtime** (`self._lock`) pour éviter de bloquer le tick loop.
2. **Les actions agent sont appliquées DANS le lock** via `_apply_agent_action_locked()`.
3. **L'agent ne s'active que pour les states avec `isAiControlled = True`**.
4. **L'agent est non-bloquant** : spawn d'un thread daemon par état IA par cycle.
5. **La mémoire est in-process** (non persistée) — elle se réinitialise à chaque `bootstrap_sol()`.
6. **Fallback NoOp systématique** : toute erreur LLM / parsing → `AgentAction(entityId=id)` sans crash.

---

## Actions disponibles

| Action | Effet |
|--------|-------|
| `NoOp` | Rien |
| `SetTolerance` | Modifie `toleranceThreshold` de l'état (0..1) |
| `TriggerNationalization` | Lance un processus de nationalisation contre une corpo |
| `ProposeContract` | Propose un contrat à une corpo (MVP: enregistré mais pas encore dispatché) |

---

## Protocole d'ajout d'une nouvelle action

1. Ajouter la valeur dans `AgentActionType(IntEnum)` dans `models.py`
2. Mettre à jour la valeur correspondante dans l'enum C# `AgentActionType` dans `SimulationContracts.cs`
3. Ajouter l'entrée dans `AGENT_TOOLS_SCHEMA` dans `logic/agent.py`
4. Ajouter le dispatch dans `_apply_agent_action_locked()` dans `runtime.py`
5. Mettre à jour `SIMULATION_CONTRACTS.md` + ce skill

---

## Tests

### Fichiers de test Phase 8.5

| Fichier | Mark | Contenu |
|---------|------|---------|
| `tests/test_phase85_agent_models.py` | aucun | Modèles `AgentAction` / `AgentMemory` / `StateData.isAiControlled` — 5 tests, venv local |
| `tests/test_phase85_agent_logic.py` | aucun | Logique pure `logic/agent.py` (parse, prompt, build_context) — 10 tests, venv local |
| `tests/test_phase85_agent_llm.py` | `llm` | Appels LLM réels (skipés si env absent) — 6 tests |
| `tests/test_phase85_agent_scenarios.py` | `scenario` | Scénarios runtime + LLM bout-en-bout — 4 tests (2 mocked + 2 LLM réels) |

### Quels tests tournent où

| Environnement | Tests disponibles | Commande |
|---------------|-------------------|---------|
| Venv local (Windows) | `not llm and not scenario` | `python -m pytest tests/ -m "not llm and not scenario" -v` |
| Conteneur Docker | **tous** (C extensions disponibles) | `docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -m "llm or scenario" -v` |

Tests `llm` / `scenario` nécessitent `h3` + `noise` (C extensions) → **Docker obligatoire**.

### Piège : identité de classe entre modules (importlib vs import)

Quand un test charge `models.py` via `importlib` ET qu'un autre module l'importe via le package
(`from terraformation_sim.models import AgentAction`), les classes sont **différentes instances** → `isinstance()` échoue silencieusement.

**Solution** : utiliser `type(action).__name__ == "AgentAction"` au lieu de `isinstance(action, AgentAction)`.

```python
# ✗ Fragile si plusieurs modules ont chargé models.py différemment
assert isinstance(action, AgentAction)

# ✓ Robuste
assert type(action).__name__ == "AgentAction", f"Expected AgentAction, got {type(action)}"
```

### Fixture `rt` (scénarios runtime+LLM dans Docker)

La fixture `rt` dans `test_phase85_agent_scenarios.py` utilise des **imports directs de package** (pas importlib) car `noise` est disponible en Docker :

```python
@pytest.fixture(scope="module")
def rt():
    try:
        import noise  # noqa: F401
    except ImportError:
        pytest.skip("C extension 'noise' not installed — run in Docker")

    import terraformation_sim.runtime as _runtime_mod
    from terraformation_sim.persistence import InMemoryRepository
    from terraformation_sim.models import AgentAction, AgentActionType, StateType
    from terraformation_sim.runtime import InMemorySimulationRuntime

    return {
        "AgentAction": AgentAction,
        "AgentActionType": AgentActionType,
        "StateType": StateType,
        "InMemorySimulationRuntime": InMemorySimulationRuntime,
        "InMemoryRepository": InMemoryRepository,
        "runtime_mod": _runtime_mod,
    }
```

**Important** : `InMemorySimulationRuntime` prend `repository=` comme kwarg (3e arg) :
```python
runtime = InMemorySimulationRuntime(repository=InMemoryRepository())  # ✓
runtime = InMemorySimulationRuntime(InMemoryRepository())              # ✗ TypeError
```

### Lancer les tests LLM

```powershell
# Copier les tests dans le conteneur (puis lancer)
docker exec terraformation-dedicated-server rm -rf /app/SimulationCore/tests
docker cp e:\terraformation\SimulationCore\tests terraformation-dedicated-server:/app/SimulationCore/tests
docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -m "llm or scenario" -v

# Tous les tests dans le conteneur
docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -v
```

Pattern d'import legacy (sans dépendances C, venv local uniquement) :
```python
import sys, importlib.util
from pathlib import Path
_SIM = Path(__file__).parent.parent / "terraformation_sim"
spec = importlib.util.spec_from_file_location("terraformation_sim.models", _SIM / "models.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["terraformation_sim.models"] = mod
spec.loader.exec_module(mod)
```

---

## Debug workflow

1. Créer un état avec `isAiControlled=True` via `POST /game/states` (`isAiControlled: true`)
2. Appeler `run_agent_for_state` (MCP tool ou `POST /game/agent/run/{id}`) pour forcer un cycle
3. Inspecter la décision avec `get_agent_memory`
4. Vérifier l'effet sur le runtime via `GET /game/states/{id}`

Si le LLM n'est pas joignable : le tool `run_agent_for_state` retourne `AgentAction.NoOp` avec log WARNING côté serveur.
