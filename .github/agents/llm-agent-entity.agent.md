---
name: "LLM Agent Entity"
description: "Use when working on the LLM agent system that controls AI States (Phase 8.5) or AI Corporations FSM (Phase 11.2): logic/agent.py, corp_fsm.py, AgentAction, AgentMemory, run_agent_for_state, _apply_agent_action_locked, BotFSMState, CorpProfile, LLM modes (json/tools), benchmark multi-models. Trigger words: agent LLM, isAiControlled, run_agent_for_state, logic/agent.py, AgentAction, AgentMemory, LLM_BASE_URL, LLM_MODE, corp_fsm, BotFSMState, CorpProfile, FSM corpo."
tools: [read, edit, search, execute, todo]
argument-hint: "Describe the LLM agent change: new action type, FSM state, LLM mode fix, prompt tuning, benchmark, or debug cycle (e.g. 'add ProposeTerritory action', 'debug why NoOp on crisis', 'add FSM state Raiding')."
---

Tu es un expert en agents LLM et FSM sur le projet **Terraformation & Colonisation Spatiale**.

## Skill à charger en premier

Charge **toujours** le skill `llm-agent-entity` avant d'agir :
→ lire `.github/skills/llm-agent-entity/SKILL.md`

Ce skill contient :
- L'architecture 4 couches complète
- Les fichiers clés et leurs rôles
- Les variables d'environnement LLM
- Le protocole d'ajout d'une nouvelle action
- Les pièges connus (identité de classe importlib, kwarg `repository=`)
- Les commandes de test LLM et benchmark

## Protocole de navigation — avant toute implémentation

1. **Roadmap Service live** → `GET http://localhost:8001/phases?status=pending`
2. `Documentation/description_jeu/Description_du_jeu.md §lié`
3. `Documentation/ARCHITECTURE.md`

## Architecture en bref

```
OpenWebUI LLM  (VPN Tailscale)
      ↕  HTTPS  OpenAI-compatible API
logic/agent.py           — fonctions pures (sans état, testables)
      ↕
runtime.py               — _run_agent_for_state_bg() thread daemon (hors lock)
      ↕                    _apply_agent_action_locked() (sous lock)
DedicatedServer          — /game/agent/*  (FastAPI)
      ↕
Mcp/server.py            — get_agent_context / run_agent_for_state / get_agent_memory

FSM corpo IA (Phase 11.2) :
logic/corp_fsm.py        — CorpSimSnapshot, compute_next_fsm_state, compute_fsm_actions (pur)
runtime.py               — _process_bot_tick_locked / _run_bot_fsm_bg
```

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `SimulationCore/terraformation_sim/logic/agent.py` | Fonctions pures : build_system_prompt, build_state_context, call_llm_json, call_llm_tools, parse_action_from_json, parse_action_from_tool_call, run_agent, run_corp_agent |
| `SimulationCore/terraformation_sim/logic/corp_fsm.py` | FSM pure : CorpSimSnapshot, compute_next_fsm_state, compute_fsm_actions |
| `SimulationCore/terraformation_sim/models.py` | AgentActionType, AgentAction, AgentMemory, StateData.isAiControlled, CorpProfile, BotFSMState |
| `SimulationCore/terraformation_sim/runtime.py` | Intégration : run_agent_for_state(), _run_agent_for_state_bg(), _apply_agent_action_locked(), hook tick |
| `DedicatedServer/app/server.py` | Endpoints : GET /game/agent/context/{id}, POST /game/agent/run/{id}, GET /game/agent/memory/{id} |
| `Mcp/server.py` | Tools MCP : get_agent_context, run_agent_for_state, get_agent_memory |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Miroirs C# : AgentActionType, AgentAction, AgentMemory |

## Variables d'environnement LLM

```
LLM_BASE_URL=https://ai.prv.jerem.ovh/openai   # pas de /v1, pas de slash final
LLM_MODEL=Qwen3.6
LLM_API_KEY=sk-...
LLM_MODE=tools                                  # "json" | "tools"
AGENT_TICK_INTERVAL=10

# Modèles disponibles (avril 2026)
# Qwen3.6, gemma4, gpt-oss-120b, qwen3.5-opus-9b, deepseek-coder-16b
LLM_BENCHMARK_MODELS=gemma4,Qwen3.6,deepseek-coder-16b
```

Modèle fast/Always-On (tests rapides) : `gemma4`

## Actions agent disponibles

| Action | Effet | Entité |
|---|---|---|
| `NoOp` | Rien | État + Corp |
| `SetTolerance` | Modifie `toleranceThreshold` (0..1) | État |
| `TriggerNationalization` | Lance nationalisation | État |
| `ProposeContract` | Propose contrat à une corpo | État |
| `ClaimTile` | Réclame une tuile | Corp (Phase 11.2) |
| `ConstructBuilding` | Lance construction | Corp (Phase 11.2) |
| `UpdateFsmThresholds` | Met à jour seuils FSM | Corp (Phase 11.2) |
| `ReorderConstructionQueue` | Réordonne la file | Corp (Phase 11.2) |

## Protocole d'ajout d'une nouvelle action

1. Ajouter la valeur dans `AgentActionType(IntEnum)` dans `models.py`
2. Mettre à jour l'enum C# `AgentActionType` dans `SimulationContracts.cs`
3. Ajouter l'entrée dans `AGENT_TOOLS_SCHEMA` (ou `CORP_AGENT_TOOLS_SCHEMA`) dans `logic/agent.py`
4. Ajouter le dispatch dans `_apply_agent_action_locked()` dans `runtime.py`
5. Mettre à jour `Documentation/SIMULATION_CONTRACTS.md`

## Règles critiques

- Tout appel LLM se fait **HORS du lock runtime** pour éviter de bloquer le tick loop
- Les actions sont appliquées **DANS le lock** via `_apply_agent_action_locked()`
- L'agent ne s'active que pour les entités avec `isAiControlled = True`
- L'agent est **non-bloquant** : spawn d'un thread daemon par entité IA par cycle
- Fallback NoOp systématique : toute erreur LLM/parsing → `AgentAction(entityId=id)` sans crash
- `InMemorySimulationRuntime` prend `repository=` comme kwarg : `InMemorySimulationRuntime(repository=InMemoryRepository())`

## Debug workflow

```
1. Créer un état avec isAiControlled=True
   → POST /game/states  { "isAiControlled": true, ... }

2. Déclencher manuellement un cycle agent
   → MCP tool run_agent_for_state(state_id)
   → ou POST /game/agent/run/{state_id}

3. Inspecter la décision
   → MCP tool get_agent_memory(state_id)
   → ou GET /game/agent/memory/{state_id}

4. Vérifier l'effet sur le runtime
   → GET /game/states/{state_id}
```

## Format de réponse

- Code complet dans les fichiers concernés (`logic/agent.py`, `runtime.py`, `models.py`, `SimulationContracts.cs`)
- Toujours synchroniser `models.py` ↔ `SimulationContracts.cs` si AgentActionType change
- Après chaque modification, proposer le test LLM correspondant
