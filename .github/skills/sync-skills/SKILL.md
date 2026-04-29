---
name: sync-skills
description: Use when updating, creating, or synchronizing Cline skills for the Terraformation project. Trigger words: update skill, create skill, sync skills, mettre à jour le skill, nouveau skill, SKILL.md, .github/skills, .cline/skills, sync-skills, maintenir les skills, skill obsolète.
---

# Sync Skills — Terraformation

## Règle fondamentale

**Source de vérité : `.github\skills\`**  
**Destination consommée par Cline : `.cline\skills\`**

Ne jamais éditer directement `.cline\skills\*\SKILL.md`. Toujours éditer `.github\skills\*\SKILL.md`, puis synchroniser.

## Quand utiliser ce skill

- Un skill existant est obsolète (architecture changée, fichiers renommés, nouveaux champs)
- Un nouveau domaine apparaît et mérite son propre skill
- Après une grosse feature (HUD, endpoint, contrat Python/C#, mécanique tick)
- Avant de déléguer une tâche complexe à Cline

## Procédure — Mettre à jour un skill existant

### 1. Lire le skill actuel
```
read_file("e:\terraformation\.github\skills\<nom>\SKILL.md")
```

### 2. Identifier ce qui est obsolète
Points à vérifier :
- Noms de fichiers changés (ex: `GameHUD.cs` → sous-contrôleurs `HUD/*.cs`)
- Nouvelles sections UXML/USS ajoutées
- Nouveaux modèles Pydantic / structs C# dans `SimulationContracts.cs`
- Nouveaux endpoints `DedicatedServer/app/server.py`
- Nouvelles mécaniques tick dans `logic/`

### 3. Éditer le fichier source
```
replace_string_in_file("e:\terraformation\.github\skills\<nom>\SKILL.md", ...)
```

### 4. Synchroniser vers .cline\skills
```powershell
cd e:\terraformation
.\Tools\Sync-ClineSkills.ps1
```

Résultat attendu :
```
  [+] <nom>  → copié
  [=] autres → inchangés
Sync terminé : 1 skill(s) mis à jour, N déjà à jour.
```

## Procédure — Créer un nouveau skill

### 1. Créer le dossier et SKILL.md dans `.github\skills`
```
create_file("e:\terraformation\.github\skills\<nom>\SKILL.md", content)
```

Structure minimale :
```markdown
---
name: <nom>          # doit correspondre EXACTEMENT au nom du dossier
description: Action verbe + quand utiliser + mots déclencheurs. Max 1024 chars.
argument-hint: 'Indication pour l'utilisateur sur ce qu'il doit fournir'
---

# Titre du skill

## When to Use
(liste de cas)

## Files Involved
(table fichier → rôle)

## Procedure
(étapes numérotées)

## Common Mistakes
(liste)
```

### 2. Synchroniser
```powershell
.\Tools\Sync-ClineSkills.ps1
```

## Référence script complète

→ [docs/script-reference.md](docs/script-reference.md)

## Skills existants — référence rapide

| Skill | Domaine |
|-------|---------|
| `gamehud-ui` | UI Toolkit HUD : TileInspector, BottomActionBar, UXML/USS, sous-contrôleurs |
| `simulation-contract-sync` | Modèles Pydantic Python ↔ structs C# SimulationContracts.cs |
| `unity-mcp` | Opérations Unity Editor via MCP (scripts, scènes, assets) |
| `dedicated-server-endpoint` | Nouveaux endpoints FastAPI + tools MCP |
| `gameplay-tick-feature` | Mécaniques tick : bâtiments, marché, contrats, ressources |
| `smoke-test-ci` | Smoke test génération, comparaison baseline, CI |
| `unit-tests` | Tests pytest SimulationCore (models, runtime, tick) |
| `terraformation-debug` | Debug génération carte, projection, hydrology, biomes |
| `roadmap-phase-complete` | Cocher une phase / CHANGELOG / Set-PhaseComplete |
| `game-design-ref` | Questions design : États, réputation, contrats, marchés, IA |
| `design-md` | Tokens design DESIGN.md, USS variables, palette |
| `llm-agent-entity` | Agent LLM IA États (logic/agent.py, corp_fsm.py) |

## Validation

Après sync, vérifier :
```powershell
Get-ChildItem e:\terraformation\.cline\skills -Recurse -Filter SKILL.md | Select-Object FullName
```

Comparer avec :
```powershell
Get-ChildItem e:\terraformation\.github\skills -Recurse -Filter SKILL.md | Select-Object FullName
```

Les deux listes doivent être identiques.
