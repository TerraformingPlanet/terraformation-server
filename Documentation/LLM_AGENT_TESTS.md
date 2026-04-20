# LLM Agent — Tests & Intégration (Phase 8.5)

> Source de vérité pour la stratégie de test de l'agent LLM qui pilote les États IA.
> Complémente [ARCHITECTURE.md](ARCHITECTURE.md) et le skill `llm-agent-entity`.

---

## Structure des fichiers de test

```
SimulationCore/tests/
  conftest.py                      # fixtures partagées + marks pytest
  test_phase85_agent_models.py     # M1 — modèles Pydantic AgentAction/Memory (5 tests, venv local)
  test_phase85_agent_logic.py      # logique pure logic/agent.py sans LLM (10 tests, venv local)
  test_phase85_agent_llm.py        # appels LLM réels @pytest.mark.llm (6 tests, Docker)
  test_phase85_agent_scenarios.py  # scénarios runtime + LLM (4 tests, Docker)
```

---

## Marks pytest

| Mark | Condition de skip | Où tourner |
|------|------------------|-----------|
| _(aucun)_ | Jamais skippé | Venv local ou Docker |
| `llm` | `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` absents | Docker (besoin de `h3`/`noise`) |
| `scenario` | idem | Docker |

**Règle** : les tests `llm` et `scenario` ont besoin des extensions C (`h3`, `noise`) disponibles uniquement dans le conteneur Docker `terraformation-dedicated-server`.

---

## Variables d'environnement LLM

| Variable | Valeur de prod | Valeur fast-test |
|----------|---------------|-----------------|
| `LLM_BASE_URL` | `https://ai.prv.jerem.ovh/openai` | idem |
| `LLM_API_KEY` | `sk-...` (depuis OpenWebUI Settings → API Keys) | idem |
| `LLM_MODEL` | `Qwen3.6-35B-A3B-MXFP4_MOE` | `gemma-4-E4B-it-Q5_K_M` |
| `LLM_MODE` | `tools` | `json` (plus compatible petits modèles) |
| `AGENT_TICK_INTERVAL` | `10` | — |

**Important** : `LLM_BASE_URL` ne doit **pas** se terminer par `/v1` — OpenWebUI route correctement
avec `/openai`. Exemple : `https://ai.prv.jerem.ovh/openai` ✓

---

## Commandes

### Tests rapides (CI sans réseau, venv local)

```powershell
cd e:\terraformation\SimulationCore
e:\terraformation\.venv\Scripts\python.exe -m pytest tests/ -m "not llm and not scenario" -v
# ≈ 55 tests, < 10 s
```

### Tests LLM dans Docker

```powershell
# 1. Copier les tests mis à jour dans le conteneur
docker exec terraformation-dedicated-server rm -rf /app/SimulationCore/tests
docker cp e:\terraformation\SimulationCore\tests terraformation-dedicated-server:/app/SimulationCore/tests

# 2. Lancer LLM + scenario uniquement
docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -m "llm or scenario" -v
# 10 tests, ≈ 2 minutes (latence réseau LLM)

# 3. Tous les tests dans le conteneur
docker exec -w /app/SimulationCore terraformation-dedicated-server python -m pytest tests/ -v
# 66 tests
```

> **Piège `docker cp`** : si le dossier `/app/SimulationCore/tests` existe déjà,
> `docker cp src/tests dst/` crée `dst/tests/tests`. Toujours `rm -rf` avant.

---

## Fixtures clés (`conftest.py`)

### `llm_env` (session-scoped)
Skipped si les env vars LLM sont absentes. Retourne `{base_url, api_key, model}`.

### `fast_model` (session-scoped)
Surcharge `model` avec `gemma-4-E4B-it-Q5_K_M` (Always-On 4B, latence ~5s).
Utiliser dans les tests LLM pour ne pas toucher le modèle de prod.

```python
def test_mon_test_llm(fast_model, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", fast_model["base_url"])
    monkeypatch.setenv("LLM_API_KEY",  fast_model["api_key"])
    monkeypatch.setenv("LLM_MODEL",    fast_model["model"])
    monkeypatch.setenv("LLM_MODE",     "json")
    ...
```

### `rt` (module-scoped, dans `test_phase85_agent_scenarios.py`)
Charge le runtime complet via imports directs (pas importlib) après avoir vérifié que `noise` est disponible :

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

---

## Pièges connus

### 1. Identité de classe entre importlib et import direct

Quand `models.py` est chargé deux fois (une fois via `importlib`, une fois via le package),
`isinstance(action, AgentAction)` retourne `False` même si l'objet est bien une `AgentAction`.

```python
# ✗ Fragile
assert isinstance(action, AgentAction)

# ✓ Robuste
assert type(action).__name__ == "AgentAction", f"Expected AgentAction, got {type(action)}"
```

Ce cas se produit quand `test_phase85_agent_llm.py` (importlib) est collecté **avant**
`test_phase85_agent_scenarios.py` (import direct) dans la même session pytest.

### 2. `InMemorySimulationRuntime` : argument `repository` en kwarg

```python
# ✓ Correct
runtime = InMemorySimulationRuntime(repository=InMemoryRepository())

# ✗ TypeError — InMemoryRepository() passé comme 1er arg positionnel (tick_interval_seconds)
runtime = InMemorySimulationRuntime(InMemoryRepository())
```

### 3. Extraire toutes les classes depuis `rt` dans la fonction de test

Ne pas oublier d'extraire `AgentActionType` si on l'utilise dans le corps du test :

```python
def test_mon_scenario(rt, fast_model, monkeypatch):
    AgentAction     = rt["AgentAction"]
    AgentActionType = rt["AgentActionType"]   # ← NameError si oublié
    StateType       = rt["StateType"]
    ...
```

### 4. Chemins hardcodés dans les fichiers de test

Utiliser `Path(__file__).parent.parent` pour accéder à `terraformation_sim/` :

```python
from pathlib import Path
_SIM = Path(__file__).parent.parent / "terraformation_sim"
spec = importlib.util.spec_from_file_location("terraformation_sim.models", _SIM / "models.py")
```

Ne jamais hardcoder `r"e:\terraformation\..."` — ça casse dans le conteneur Docker.

---

## Mocker le LLM dans les scénarios

Pour les tests qui n'ont pas besoin d'un vrai LLM (tests de logique runtime) :

```python
from unittest.mock import patch

def test_scenario_mocked(rt):
    AgentAction     = rt["AgentAction"]
    AgentActionType = rt["AgentActionType"]
    runtime_mod     = rt["runtime_mod"]
    runtime = _fresh_runtime(rt)

    mocked_action = AgentAction(
        entityId="state-id",
        actionType=AgentActionType.SetTolerance,
        params={"newThreshold": 0.25},
    )
    with patch.object(runtime_mod, "_run_agent_llm", return_value=mocked_action):
        action = runtime.run_agent_for_state("state-id")
    
    assert type(action).__name__ == "AgentAction"
    assert action.actionType == AgentActionType.SetTolerance
```

---

## Ajouter un nouveau test LLM

1. **Test pur (logique sans LLM)** → `test_phase85_agent_logic.py`, mark _(aucun)_
2. **Test appel LLM** → `test_phase85_agent_llm.py`, `@pytest.mark.llm`, utiliser `fast_model`
3. **Scénario runtime + LLM** → `test_phase85_agent_scenarios.py`, `@pytest.mark.scenario`, fixture `rt`
4. Lancer localement les purs : `pytest tests/ -m "not llm and not scenario" -v`
5. Lancer dans Docker les LLM : voir commandes ci-dessus

---

## État des tests (Phase 8.5 terminée)

| Fichier | Tests | Statut |
|---------|-------|--------|
| `test_phase85_agent_models.py` | 5 | ✅ venv local |
| `test_phase85_agent_logic.py` | 10 | ✅ venv local |
| `test_phase85_agent_llm.py` | 6 | ✅ Docker (10 passes en 2 min) |
| `test_phase85_agent_scenarios.py` | 4 | ✅ Docker |
| **Total** | **25** | **10/10 llm+scenario en Docker** |
