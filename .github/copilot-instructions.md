# Instructions Copilot — Terraformation

## Projet

Jeu de simulation / colonisation spatiale tick-based, multijoueur asynchrone.
Deux dépôts Git dans ce workspace :
- `e:\terraformation\` → backend (Python SimulationCore, DedicatedServer FastAPI, MCP FastMCP)
- `e:\terraformation\Game\` → client Unity 6 LTS 3D URP (son propre `.git`)

## Protocole de navigation — avant toute implémentation

1. **Roadmap Service live** → `Set-PhaseComplete.ps1 -List` ou `GET http://localhost:8001/phases?status=pending` — liste les phases actives depuis la DB (source de vérité état). Puis **[Documentation/ROADMAP.md](Documentation/ROADMAP.md)** pour le détail des critères de sortie.
2. **[Documentation/description_jeu/Description_du_jeu.md](Documentation/description_jeu/Description_du_jeu.md) §lié** — source de vérité design (lien en tête de chaque phase du ROADMAP)
3. **[Documentation/ARCHITECTURE.md](Documentation/ARCHITECTURE.md)** — contraintes de stack, décisions prises
4. **[Documentation/REPOSITORY_STRUCTURE.md](Documentation/REPOSITORY_STRUCTURE.md)** — où placer les fichiers

## Agents spécialisés — routing prioritaire

Préférer un agent spécialisé avant d'implémenter directement :

| Tâche | Agent | Skills associés |
|---|---|---|
| Python : models, runtime, logic, endpoints, MCP | `@SimCore Dev` | `simulation-contract-sync`, `gameplay-tick-feature`, `dedicated-server-endpoint` |
| C# Unity : scripts, HUD, contrats, scènes | `@Unity Dev` | `unity-mcp`, `gamehud-ui`, `simulation-contract-sync` |
| Design tokens, USS, DESIGN.md, UX/UI visuel | `@Design & UX` | `design-md`, `gamehud-ui` |
| Tests, smoke, benchmark LLM, assertions ROADMAP | `@Test & CI` | `unit-tests`, `smoke-test-ci` |
| Agent LLM États IA + Corp FSM (Phase 8.5 / 11.2) | `@LLM Agent Entity` | `llm-agent-entity` |
| Documentation, ROADMAP, Description_du_jeu | `@Doc Terraformation` | `roadmap-phase-complete`, `game-design-ref` |

Références conditionnelles :
- Tâche touche un contrat Python ↔ C# → [Documentation/SIMULATION_CONTRACTS.md](Documentation/SIMULATION_CONTRACTS.md) + skill `simulation-contract-sync`
- Tâche touche un tool MCP ou endpoint DedicatedServer → [Documentation/MCP_TOOLS_ARCHITECTURE.md](Documentation/MCP_TOOLS_ARCHITECTURE.md) + skill `dedicated-server-endpoint`
- Debug visuel Unity → [Documentation/AI_DEBUG_WORKFLOW.md](Documentation/AI_DEBUG_WORKFLOW.md) + skill `terraformation-debug`
- Opération Unity MCP (scripts, scènes, assets) → skill `unity-mcp`
- UI/HUD code-driven Unity (`GameHUD`, RightPanel, icônes bâtiments, TMP, dropdowns, badges) → skill `gamehud-ui`
- Tokens design, `DESIGN.md`, USS variables, palette couleurs, typographie HUD → skill `design-md` + agent `@Design & UX`
- Nouvelle mécanique gameplay cross-couche → skill `gameplay-tick-feature`
- Validation génération post-changement → skill `smoke-test-ci`
- Question de design / mécanique de jeu (États, réputation, contrats, bâtiments, marchés, IA) → skill `game-design-ref`
- Cocher une phase / marquer une tâche terminée → Roadmap Service (`http://localhost:8001`) + skill `roadmap-phase-complete`

## Stack technique actuelle

| Couche | Technologie | Dossier |
|--------|------------|---------|
| Simulation | Python / Pydantic | `SimulationCore/terraformation_sim/` |
| API serveur | FastAPI / uvicorn | `DedicatedServer/app/server.py` |
| MCP | FastMCP 3.x (streamable-http :8000) | `Mcp/server.py` |
| Client | Unity 6 LTS 3D URP C# | `Game/Assets/Scripts/` |
| Grille | H3 géospatial (res=1/2) | côté serveur Python |
| Persistance | PostgreSQL + SQLAlchemy Core | `SimulationCore/terraformation_sim/persistence.py` |
| Roadmap | FastAPI + SQLite (port 8001) | `Roadmap/` — `python Roadmap/run.py` |
| Réseau client | Mirror Networking | Phase 10 (pas encore implémenté) |

## Délégation vers Cline (LLM local)

Quand l'utilisateur demande un plan à déléguer à Cline, produire obligatoirement ce format — Cline le lit via `/from-copilot` :

```markdown
## Contexte
- Fichiers impliqués : [liste avec chemins complets]
- État actuel : [ce qui existe, ce qui manque]

## Objectif
[Description en 2-3 phrases de ce qui doit être produit]

## Tâches
1. [action atomique — fichier cible]
2. [action atomique — fichier cible]
...

## Contraintes
- [règles spécifiques à cette tâche]

## Validation
- [commande ou vérification manuelle pour confirmer que c'est bon]
```

Modèles recommandés pour Cline :
- Code (Python/C#/USS) → `Gemma4-A4B-NoThink`
- Tâche complexe multi-fichiers → `qwen3.5-sonnet-30b`
- Simple / atomique → `Gemma4-A4B-NoThink`

Backend LLM local : `http://192.168.5.213:41200/v1`

---

## Règles de contribution doc

- Nouvelle mécanique → `Documentation/description_jeu/Description_du_jeu.md` (source de vérité design)
- Nouvelle tâche → `Documentation/ROADMAP.md` avec lien vers la section correspondante de `Description_du_jeu.md`
- Décision technique → `Documentation/ARCHITECTURE.md`
- Phase terminée → **utiliser `Set-PhaseComplete.ps1` + skill `roadmap-phase-complete`** (jamais à la main)
- Nouveau contrat Python ↔ C# → `Documentation/SIMULATION_CONTRACTS.md`
- Nouveau tool MCP → `Documentation/MCP_TOOLS_ARCHITECTURE.md`
- **Phase implémentée → créer `SimulationCore/tests/assertions/test_<phase_id_underscored>.py`** (template : `_template.py`) et lier via `assertion_script` dans la phase Roadmap. Vérifier `roadmap_test_all()` avant de compléter.
