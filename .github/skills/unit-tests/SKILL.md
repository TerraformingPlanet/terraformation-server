---
name: unit-tests
description: 'Use when writing or running Python unit tests for SimulationCore: model round-trips, runtime logic, tick loop, expedition/trade-route lifecycle. No Docker or server required. Trigger words: test, unit test, pytest, round-trip, test_phase, Test-Phase, validate model, test runtime, test tick.'
argument-hint: 'Describe what to test: e.g. "add tests for TradeRoute round-trip", "test launch_expedition validates port presence", "run Phase 9 model tests"'
---

# Unit Tests — SimulationCore (sans Docker)

## Philosophie

- **Aucun Docker ni serveur requis** — les tests utilisent uniquement le venv local
- **Chargement direct de `models.py`** via `importlib.util.spec_from_file_location` pour éviter
  les dépendances transitives (`h3`, `noise`) du package `__init__.py`
- **Tests runtime** instancient directement `InMemorySimulationRuntime` + `InMemoryRepository`
- Durée cible : **< 5 secondes** par fichier de test

## Structure

```
SimulationCore/
  tests/
    conftest.py                          # fixtures partagées + marks pytest (llm, scenario)
    test_phase85_agent_models.py         # Phase 8.5 M1 — modèles AgentAction/Memory/StateData (5 tests)
    test_phase85_agent_logic.py          # Phase 8.5 — logique pure agent.py, sans LLM (10 tests)
    test_phase85_agent_llm.py            # Phase 8.5 — appels LLM réels @pytest.mark.llm (6 tests)
    test_phase85_agent_scenarios.py      # Phase 8.5 — scénarios runtime+LLM (4 tests, 2 mocked + 2 LLM)
    test_phase8_events.py                # Phase 8 — événements gameplay (8 tests)
    test_phase9_models.py                # Phase 9.1 — TradeRoute, ExpeditionUnit, enums (12 tests)
    test_phase9_runtime.py               # Phase 9.2 — runtime launch_expedition (8 tests)
    test_phase94_market.py               # Phase 9.4 — priceVelocity + sparkline (4 tests)
    test_phase95_global_market.py        # Phase 9.5 — GlobalMarketState + compute_global_market (4 tests)
    test_phase95_resources.py            # Phase 9.5 — ResourceType + ResourceListing (4 tests)
    # Tout nouveau test_phase*.py est auto-découvert par Invoke-PhaseValidation.ps1
```

## Fichiers et scripts

| Fichier | Rôle |
|---------|------|
| `SimulationCore/tests/conftest.py` | Fixtures `llm_env`, `fast_model` + marks `llm` / `scenario` |
| `SimulationCore/tests/test_phase85_agent_models.py` | Tests modèles Phase 8.5 M1 |
| `SimulationCore/tests/test_phase85_agent_logic.py` | Tests logique pure `logic/agent.py` |
| `SimulationCore/tests/test_phase85_agent_llm.py` | Tests LLM réels (skipés si env absent) |
| `SimulationCore/tests/test_phase85_agent_scenarios.py` | Scénarios bout-en-bout runtime + LLM |
| `SimulationCore/tests/test_phase9_models.py` | Tests modèles Phase 9.1 |
| `SimulationCore/tests/test_phase9_runtime.py` | Tests runtime Phase 9.2 |
| `SimulationCore/tests/test_phase94_market.py` | Tests marché Phase 9.4 |
| `Tools/Invoke-PhaseValidation.ps1` | **Validation globale de fin de phase** (auto-découvre tous les tests) |

## Tests LLM — stratégie (Phase 8.5+)

### Marks pytest

| Mark | Condition de skip | Usage |
|------|------------------|-------|
| `llm` | `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` absents | Tests d'intégration LLM purs |
| `scenario` | idem | Scénarios runtime + LLM bout-en-bout |

### Fixture `fast_model`

Retourne un dict `{base_url, api_key, model}` avec le modèle Always-On 4B (`gemma-4-E4B-it-Q5_K_M`) — rapide, sans toucher `LLM_MODEL` de production.

```python
def test_mon_test_llm(fast_model, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")
    ...
```

### Commandes

```powershell
# Rapide — tests purs seulement (CI sans réseau)
cd e:\terraformation\SimulationCore
e:\terraformation\.venv\Scripts\python.exe -m pytest tests/ -m "not llm and not scenario" -v

# Tests LLM uniquement
e:\terraformation\.venv\Scripts\python.exe -m pytest tests/ -m llm -v

# Scénarios runtime+LLM
e:\terraformation\.venv\Scripts\python.exe -m pytest tests/ -m scenario -v

# Tout (LLM auto-skippé si env absent)
e:\terraformation\.venv\Scripts\python.exe -m pytest tests/ -v
```

### Mocker le LLM dans les scénarios

```python
from unittest.mock import patch

def test_scenario(monkeypatch):
    mocked_action = AgentAction(entityId="s1", actionType=AgentActionType.SetTolerance,
                                 params={"newThreshold": 0.25})
    with patch.object(
        sys.modules["terraformation_sim.runtime"],
        "_run_agent_llm",
        return_value=mocked_action,
    ):
        action = runtime.run_agent_for_state("s1")
```

## Tests avec C extensions (Docker obligatoire)

Les tests `llm` et `scenario` nécessitent `h3` + `noise` (extensions C non disponibles dans le venv Windows).
Ils doivent être exécutés dans le conteneur `terraformation-dedicated-server`.

### Workflow Docker

```powershell
# 1. Copier les tests dans le conteneur (après chaque modification)
docker exec terraformation-dedicated-server rm -rf /app/SimulationCore/tests
docker cp e:\terraformation\SimulationCore\tests terraformation-dedicated-server:/app/SimulationCore/tests

# 2. Lancer LLM + scenario
docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -m "llm or scenario" -v

# 3. Lancer TOUS les tests dans le conteneur
docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -v
```

**Attention `docker cp`** : si le dossier cible existe déjà, `docker cp src/tests dst/` copie `tests` *dans* `dst/tests` → toujours faire le `rm -rf` avant.

### Piège : identité de classe entre modules (importlib vs import direct)

Quand un test charge `models.py` via `importlib` ET que `runtime.py` l'importe via le package,
les classes sont des **instances différentes** → `isinstance()` retourne `False` silencieusement.

```python
# ✗ Peut échouer si models.py chargé deux fois différemment
assert isinstance(action, AgentAction)

# ✓ Robuste dans tous les cas
assert type(action).__name__ == "AgentAction", f"Expected AgentAction, got {type(action)}"
```

### Fixture `rt` pour les scénarios runtime+LLM

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

Instancier le runtime dans les tests :
```python
def _fresh_runtime(rt):
    return rt["InMemorySimulationRuntime"](repository=rt["InMemoryRepository"]())
    # ↑ repository= en kwarg obligatoire (3e param positionnel → TypeError si passé sans nom)
```

Extraire TOUTES les classes utilisées dans la fonction de test :
```python
def test_mon_scenario(rt, fast_model, monkeypatch):
    AgentAction     = rt["AgentAction"]
    AgentActionType = rt["AgentActionType"]   # ← ne pas oublier si utilisé
    StateType       = rt["StateType"]
    ...
```

## Pattern : charger models.py sans __init__.py

```python
import importlib.util, sys
from pathlib import Path

_path = Path(__file__).parent.parent / "terraformation_sim" / "models.py"
_spec = importlib.util.spec_from_file_location("terraformation_sim.models", _path)
_models = importlib.util.module_from_spec(_spec)
sys.modules["terraformation_sim.models"] = _models
_spec.loader.exec_module(_models)

TradeRoute = _models.TradeRoute
```

## Pattern : charger runtime.py (dépend de models + persistence)

Pour les tests runtime, charger les 3 fichiers dans l'ordre :

```python
import importlib.util, sys
from pathlib import Path

SIM_DIR = Path(__file__).parent.parent / "terraformation_sim"

def _load(name, rel_path):
    p = SIM_DIR / rel_path
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod

_models      = _load("models",      "models.py")
_persistence = _load("persistence", "persistence.py")
_runtime     = _load("runtime",     "runtime.py")

InMemorySimulationRuntime = _runtime.InMemorySimulationRuntime
InMemoryRepository        = _persistence.InMemoryRepository
```

## Pattern : test round-trip JSON

```python
def _roundtrip(model_instance):
    cls = type(model_instance)
    raw = model_instance.model_dump_json()
    return cls.model_validate_json(raw)
```

## Pattern : test tick-based

```python
repo    = InMemoryRepository()
runtime = InMemorySimulationRuntime(repo)

# Bootstrap minimal sans génération complète
runtime._tick = 0
runtime._expeditions["exp-001"] = ExpeditionUnit(
    id="exp-001", ownerCorpId="corp-a",
    fromPortTileId="tile-a", toPortTileId="tile-b",
    bodyId="body-mars", routeType=TradeRouteType.Land,
    ticksRemaining=2, totalTicks=2,
)

# Avancer 2 ticks
runtime._process_expedition_tick_locked()
assert "exp-001" in runtime._expeditions  # encore InTransit
runtime._tick += 1
runtime._process_expedition_tick_locked()
# ticksRemaining = 0 → Success → TradeRoute créée
assert any(r.ownerCorpId == "corp-a" for r in runtime._trade_routes.values())
```

## Checklist après ajout d'un nouveau modèle

1. Ajouter cas `test_*_defaults()` — vérifie les valeurs par défaut
2. Ajouter cas `test_*_roundtrip()` — sérialisation JSON → désérialisation
3. Ajouter cas `test_*_enum_values()` — vérifie chaque valeur d'enum
4. Pour les modèles liés à la logique tick → ajouter un cas dans `test_phase9_runtime.py`
5. Lancer `.\Tools\Test-Phase9Models.ps1` avant de passer à l'étape suivante

## Lancer les tests

```powershell
# RECOMMANDÉ — validation globale de fin de phase (auto-découvre tous les test_*.py)
cd e:\terraformation
.\Tools\Invoke-PhaseValidation.ps1

# Isolé — un seul fichier de test
.\Tools\Invoke-PhaseValidation.ps1 -Filter "phase9"

# Syntaxe models.py uniquement
& .\venv\Scripts\python.exe -m py_compile SimulationCore/terraformation_sim/models.py

# Smoke test génération (Docker requis)
.\Tools\Invoke-DedicatedServerGenerationSmoke.ps1 -BaseUrl http://127.0.0.1:8080 -SkipBuild
```

## Validation Unity (après les tests Python)

Si des fichiers C# ont été modifiés dans le cycle, appeler via l'agent MCP :

```
Unity_ValidateScript('Assets/Scripts/Simulation/Contracts/SimulationContracts.cs')
Unity_ValidateScript('Assets/Scripts/UI/GameHUD.cs')              # si modifié
Unity_ValidateScript('Assets/Scripts/UI/GameHUDBuildingIcons.cs') # si modifié
```

**Règle** : marquer la phase `[x]` dans ROADMAP uniquement après 0 erreur Python ET 0 erreur C#.

## Quand renforcer les tests

| Événement | Action |
|-----------|--------|
| Nouveau modèle Pydantic | `test_*_defaults` + `test_*_roundtrip` |
| Nouveau enum | `test_*_enum_values` |
| Nouvelle logique runtime | `test_phase9_runtime.py` cas tick-based |
| Nouveau endpoint FastAPI | Test manuel via MCP tool ou curl |
| Régression génération | Mettre à jour baseline `generation-smoke-baseline.v*.json` |
| Nouvelle action agent | `test_phase85_agent_logic.py` (parse pure) + `test_phase85_agent_scenarios.py` (mocked) |
| Nouveau mode LLM | `test_phase85_agent_llm.py` cas `run_agent_*_mode` |
