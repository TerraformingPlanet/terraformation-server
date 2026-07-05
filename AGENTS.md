# AGENTS.md — terraformation-server

> Point d'entrée pour tout agent IA (Codex, Claude Code, Copilot, Cline).
> Vision globale du projet et carte des repos : repo privé `TerraformingPlanet/docs`.

## Vue d'ensemble

Simulation autoritaire de terraformation planétaire. **Le serveur est la source de
vérité du monde** ; les clients (Unity aujourd'hui, mod Satisfactory demain) ne font
que du rendu et n'envoient que des intentions.

| Sous-projet | Rôle | Techno |
|---|---|---|
| `SimulationCore/` | Règles du monde : génération Goldberg/H3, hydrologie, biomes, colonisation, marché | Python pur (Pydantic), zéro dépendance moteur |
| `DedicatedServer/` | Host autoritaire :8080 — tick, commandes, WebSocket JWT, persistance PostgreSQL | FastAPI |
| `Mcp/` | Tools IA/debug :8000 (façade, jamais le moteur métier) | FastMCP 3.x, Docker |
| `Roadmap/` | Service de queue de tâches :8001 | FastAPI + SQLite |

## Démarrage rapide

```bash
docker compose up -d                      # stack canonique : DedicatedServer + MCP
curl http://localhost:8080/health         # santé + tickCount
cd SimulationCore && python -m pytest tests/   # tests du cœur métier
```

## Documents canoniques (à lire avant de coder)

- `Documentation/ARCHITECTURE.md` — décisions structurantes, invariants, routes HTTP
- `Documentation/SIMULATION_CONTRACTS.md` — **source de vérité des contrats
  Python ↔ clients** (C# Unity, demain C++ UE). Ne jamais dupliquer : lier.
- `Documentation/REPOSITORY_STRUCTURE.md` — découpage monorepo
- `Documentation/ROADMAP.md`, `Documentation/CHANGELOG.md`

## Skills (procédures réutilisables)

Localisation canonique : **`.github/skills/<nom>/SKILL.md`**.
`.cline/skills/` et `.claude/skills/` sont des miroirs synchronisés (skill `sync-skills`).
Exemples : `dedicated-server-endpoint` (ajouter une route), `simulation-contract-sync`
(synchro modèles Python ↔ contrats clients), `unit-tests`, `smoke-test-ci`.

## Règles non négociables

1. Aucune logique métier nouvelle dans les clients — elle naît dans `SimulationCore/`.
2. Invariants `logic/generation.py` : `_compute_sea_level_altitude()` retourne
   **4 valeurs** ; `_set_tile_water_classification()` est une fonction **pure, sans
   récursion** ; `StateRepository._load_galaxy_rows()` reste concrète (pas
   `@abstractmethod`).
3. `ws_broadcast()` est appelé depuis le thread tick synchrone → toujours passer par
   `asyncio.run_coroutine_threadsafe(..., _main_event_loop)`.
4. Ne pas retirer l'override du header `Host: 127.0.0.1:48621` dans `Mcp/server.py`
   (contrainte HTTP.sys Windows).
5. H3 est un détail d'implémentation interne — le gameplay ne référence que les
   niveaux de tuiles 0→N.

## Écosystème TerraformingPlanet

- `satisfactory-terraform-mod` — mod Satisfactory (SML/UE 5.3.2-CSS), futur client
  principal. Son intégration passera par de nouveaux endpoints (ex. rapport de
  production → deltas de terraformation).
- `Game-unity-terra` — client Unity, dashboard de référence pendant la transition ;
  sa géométrie Goldberg est la spec du portage UE.
- `docs` (privé) — plan d'architecture global (phases 0–4), guides, legacy Per Aspera.
