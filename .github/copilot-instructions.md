# Instructions Copilot — Terraformation

## Projet

Jeu de simulation / colonisation spatiale tick-based, multijoueur asynchrone.
Deux dépôts Git dans ce workspace :
- `e:\terraformation\` → backend (Python SimulationCore, DedicatedServer FastAPI, MCP FastMCP)
- `e:\terraformation\Game\` → client Unity 6 LTS 3D URP (son propre `.git`)

## Protocole de navigation — avant toute implémentation

1. **[Documentation/ROADMAP.md](Documentation/ROADMAP.md)** — identifier la tâche active + critères de sortie
2. **GDD.md §lié** (lien `> Design de référence` en tête de chaque phase du ROADMAP)
3. **[Documentation/ARCHITECTURE.md](Documentation/ARCHITECTURE.md)** — contraintes de stack, décisions prises
4. **[Documentation/REPOSITORY_STRUCTURE.md](Documentation/REPOSITORY_STRUCTURE.md)** — où placer les fichiers

Références conditionnelles :
- Tâche touche un contrat Python ↔ C# → [Documentation/SIMULATION_CONTRACTS.md](Documentation/SIMULATION_CONTRACTS.md)
- Tâche touche un tool MCP → [Documentation/MCP_TOOLS_ARCHITECTURE.md](Documentation/MCP_TOOLS_ARCHITECTURE.md)
- Debug visuel Unity → [Documentation/AI_DEBUG_WORKFLOW.md](Documentation/AI_DEBUG_WORKFLOW.md)

## Stack technique actuelle

| Couche | Technologie | Dossier |
|--------|------------|---------|
| Simulation | Python / Pydantic | `SimulationCore/terraformation_sim/` |
| API serveur | FastAPI / uvicorn | `DedicatedServer/app/server.py` |
| MCP | FastMCP 3.x (streamable-http :8000) | `Mcp/server.py` |
| Client | Unity 6 LTS 3D URP C# | `Game/Assets/Scripts/` |
| Grille | H3 géospatial (res=1/2) | côté serveur Python |
| Persistance | PostgreSQL + SQLAlchemy Core | `SimulationCore/terraformation_sim/persistence.py` |
| Réseau client | Mirror Networking | Phase 10 (pas encore implémenté) |

## Règles de contribution doc

- Nouvelle mécanique → `Documentation/GDD.md`
- Nouvelle tâche → `Documentation/ROADMAP.md` avec lien vers `GDD.md §X`
- Décision technique → `Documentation/ARCHITECTURE.md`
- Phase terminée → `[ ]` → `[x]` dans ROADMAP, puis déplacer vers `Documentation/CHANGELOG.md`
- Nouveau contrat Python ↔ C# → `Documentation/SIMULATION_CONTRACTS.md`
- Nouveau tool MCP → `Documentation/MCP_TOOLS_ARCHITECTURE.md`
