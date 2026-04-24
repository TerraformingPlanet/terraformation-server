# Terraformation — Règles backend (SimulationCore · DedicatedServer · Mcp · Roadmap)

## Projet

Jeu de colonisation spatiale **tick-based multijoueur asynchrone**.

| Couche | Technologie | Port |
|--------|------------|------|
| Simulation (logique métier) | Python / Pydantic | — |
| API serveur dédié | FastAPI / uvicorn | 8080 |
| MCP tools | FastMCP 3.x (streamable-http) | 8000 |
| Persistance | PostgreSQL + SQLAlchemy Core | — |
| Roadmap | FastAPI + SQLite | 8001 |
| Client | Unity 6 LTS 3D URP (dépôt séparé `Game/`) | — |

---

## Avant toute implémentation

1. Lire `Documentation/ROADMAP.md` → identifier la phase et ses critères de sortie
2. Lire la section liée dans `Documentation/description_jeu/Description_du_jeu.md` (source de vérité design)
3. Lire `Documentation/ARCHITECTURE.md` → contraintes de stack et décisions prises
4. Lire `Documentation/REPOSITORY_STRUCTURE.md` → où placer les fichiers

Références conditionnelles :
- Changement touche un contrat Python ↔ C# → `Documentation/SIMULATION_CONTRACTS.md`
- Changement touche un endpoint ou tool MCP → `Documentation/MCP_TOOLS_ARCHITECTURE.md`
- Debug visuel Unity → `Documentation/AI_DEBUG_WORKFLOW.md`

---

## Règles de code

### SimulationCore
- `SimulationCore/terraformation_sim/` contient **toute** la logique métier (models, runtime, logic)
- `models.py` est la **source de vérité** de tous les contrats partagés Python ↔ C#
- Modifier un modèle Pydantic partagé → synchroniser **immédiatement** `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`

### DedicatedServer
- `DedicatedServer/app/server.py` : tous les endpoints FastAPI
- Ajouter un endpoint → lire `Documentation/MCP_TOOLS_ARCHITECTURE.md` d'abord

### Mcp
- `Mcp/server.py` : tous les tools FastMCP
- Contrainte Host header Windows HTTP.sys : `server.py` force `Host: 127.0.0.1:48621` sur les requêtes vers Unity — **ne pas retirer**

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `SimulationCore/terraformation_sim/models.py` | Tous les modèles Pydantic (source de vérité) |
| `SimulationCore/terraformation_sim/runtime.py` | Boucle tick + persistance write-through |
| `SimulationCore/terraformation_sim/logic/agent.py` | Agent LLM (`call_llm_json/tools`, `run_agent`) |
| `SimulationCore/terraformation_sim/logic/corp_fsm.py` | FSM corporations IA |
| `DedicatedServer/app/server.py` | Tous les endpoints FastAPI |
| `Mcp/server.py` | Tous les tools FastMCP |
| `SimulationCore/tests/conftest.py` | Fixtures pytest + benchmark store + early-abort (`ABORT_THRESHOLD=4`) |
| `SimulationCore/tests/benchmark_exclusions.json` | Modèles LLM blacklistés |

---

## Tests

- **Venv** : `e:\terraformation\.venv` — **JAMAIS `.venv-1`**
- Tests rapides (sans LLM, sans Docker) :
  ```
  e:\terraformation\.venv\Scripts\pytest.exe SimulationCore/tests/ -m "not llm and not scenario" -v
  ```
- Tests LLM : nécessitent `LLM_DIRECT_BASE_URL=http://192.168.5.213:41200/v1` dans `.env` + Docker actif
- Benchmark multi-modèles : `test_phase85_agent_benchmark.py -m llm_benchmark`
- Nouvelle phase implémentée → créer `SimulationCore/tests/assertions/test_<phase_id>.py` (template : `_template.py`)

---

## LLM config (agent IA in-game)

| Variable | Modèle | Usage |
|----------|--------|-------|
| `LLM_MODEL_FAST` | `gemma4` (4B) | Décisions simples, latence ~5s, always-on |
| `LLM_MODEL_DEEP` | `Gemma4-A4B-NoThink` (26B) | Agent État / Corp, benchmark 10/10, MCP 1-5s |
| `LLM_MODEL_REASON` | `qwen3.5-sonnet-30b` (30B) | Raisonnement / planification, benchmark 10/10 |

- Backend direct llama-swap : `http://192.168.5.213:41200/v1` (bypass OpenWebUI proxy, timeout proxy ~60s insuffisant pour les modèles Big à cold-start ~90s)
- `max_tokens=300` dans `call_llm_tools` (`agent.py`) — **ne pas retirer** (évite les freezes de génération)
- Modèles exclus (`benchmark_exclusions.json`) : `Gemma4-A4B-Think` (timeout systématique), `Llama-xLAM-2-8B-fc-r` (template FC propriétaire incompatible avec llama-swap tools API)
- Qwen3-8B/14B : tools_call ❌ (mode thinking interfère) — fix potentiel : `/no_think` dans system prompt
- Qwen3-32B : trop lent en interactif avec grand contexte (~13K tokens → >5min de prompt eval)

---

## Roadmap Service

- `http://localhost:8001` — source de vérité état des phases (`GET /phases?status=pending`)
- Marquer une phase terminée : `Set-PhaseComplete.ps1` **uniquement** (jamais à la main dans ROADMAP.md)

---

## Docker

- Stack complète : `docker compose up -d` (racine du dépôt)
- Rebuild serveur dédié : task VS Code "terraformation: rebuild dedicated server"
- Tests dans le container : `docker exec terraformation-dedicated-server python -m pytest SimulationCore/tests/ -v`
- Compose canonique : `docker-compose.yml` à la racine — les fichiers `Mcp/` et `DedicatedServer/` sont des wrappers locaux
