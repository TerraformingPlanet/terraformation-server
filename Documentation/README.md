# Documentation — Terraformation

Index d'entrée pour le projet. Commence ici si tu découvres le dépôt.

---

## Démarrage rapide — agent IA

> **Si tu démarres une session de travail :**
>
> 1. **[ROADMAP.md](ROADMAP.md)** — identifie la tâche active (tableau récapitulatif en bas du fichier)
> 2. **[GDD.md §lié](GDD.md)** — design intent de la mécanique à implémenter (lien `> Design de référence` en tête de chaque phase)
> 3. **[ARCHITECTURE.md](ARCHITECTURE.md)** — contraintes de stack et décisions techniques
> 4. **[REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md)** — où placer les fichiers, conventions de nommage
>
> → Détail de ce protocole dans [ROADMAP.md — section Navigation](ROADMAP.md#navigation--agents-ia)

---

## Ordre de lecture recommandé

| # | Fichier | Intention |
|---|---------|-----------|
| 1 | [GDD.md](GDD.md) | **Document de design unique** — vision, concept, systèmes de jeu (vues, tuiles, corporations, marchés, contrats, États, IA) |
| 2 | [ARCHITECTURE.md](ARCHITECTURE.md) | Stack technique, décisions d'architecture, structure cible des couches |
| 3 | [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | Découpage monorepo en sous-projets (`Game/`, `Mcp/`, `DedicatedServer/`, `SimulationCore/`) |
| 4 | [ROADMAP.md](ROADMAP.md) | **Backlog actif uniquement** — phases et sprints en cours ou à venir |
| 5 | [CHANGELOG.md](CHANGELOG.md) | Historique des phases complétées (Phase 0 → 6.9) |

---

## Référence technique

| Fichier | Intention |
|---------|-----------|
| [SIMULATION_CONTRACTS.md](SIMULATION_CONTRACTS.md) | Convention de synchronisation des contrats Python ↔ C# (`models.py` ↔ `SimulationContracts.cs`) |
| [BODY_HIERARCHY.md](BODY_HIERARCHY.md) | Architecture des corps célestes côté serveur Python — modèles, génération de tuiles, zones intérieures, endpoints REST |
| [MCP_TOOLS_ARCHITECTURE.md](MCP_TOOLS_ARCHITECTURE.md) | Architecture des tools MCP, endpoints HTTP, bridge Unity, état par tool |
| [AI_DEBUG_WORKFLOW.md](AI_DEBUG_WORKFLOW.md) | Workflow AI/debug : comment utiliser Copilot pour débugger sans improviser |
| [TEST_PRESETS_CHECKLIST.md](TEST_PRESETS_CHECKLIST.md) | Checklist de validation pour les presets Ocean, Arid, Frozen, Coast, Basin |
| [MapGeneration_rule.md](MapGeneration_rule.md) | Règles de génération de carte et de cohérence projection → local |

---

## Design du jeu (notes de travail)

| Dossier | Intention |
|---------|-----------|
| [description_jeu/Description_du_jeu.md](description_jeu/Description_du_jeu.md) | Premier brouillon de description du jeu (source du GDD) |
| [description_jeu/questions/](description_jeu/questions/) | Notes de design par thème : contrats, marchés, bâtiments, tour de jeu, IA, tuiles — base de travail ayant alimenté le GDD |

---

## Plans de migration

| Fichier | Intention |
|---------|-----------|
| [SERVER_MIGRATION_PLAN.md](SERVER_MIGRATION_PLAN.md) | Plan de migration vers le serveur dédié autoritaire |
| [UNITY_AI_ASSISTANT_MCP_PLAN.md](UNITY_AI_ASSISTANT_MCP_PLAN.md) | Plan initial MCP (historique — voir MCP_TOOLS_ARCHITECTURE.md pour l'état actuel) |

---

## Doc externe MCP (FastMCP)

| Dossier | Intention |
|---------|-----------|
| [mcp/README.md](mcp/README.md) | Patterns FastMCP utilisés dans ce projet + liens vers la doc officielle |

---

## Archive

| Dossier | Intention |
|---------|-----------|
| [Archive/](Archive/) | Notes de recherche, scratchpads et documents fusionnés — pas de documentation active |

---

## Règles de contribution

- **Nouvelles décisions d'architecture** → `ARCHITECTURE.md` (section "Décisions d'Architecture")
- **Nouveau type de contrat partagé Python ↔ C#** → `SIMULATION_CONTRACTS.md` (mettre à jour les deux colonnes)
- **Nouvelle mécanique de jeu** → `GDD.md` section correspondante
- **Nouvelle tâche / phase** → `ROADMAP.md` avec lien vers la section GDD concernée
- **Nouveau tool MCP** → `MCP_TOOLS_ARCHITECTURE.md`
- **Phase terminée** → déplacer de `ROADMAP.md` vers `CHANGELOG.md`
- **Doc spécifique à une brique** → `{Brique}/README.md` (co-localisé avec le code, pas ici)
