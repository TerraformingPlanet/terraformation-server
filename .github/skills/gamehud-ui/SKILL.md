---
name: gamehud-ui
description: 'Use when implementing or refactoring the UI Toolkit HUD in GameHUDController.cs: TileInspector, BottomActionBar, EventFeed, LeftPanel, TopBar, building list, icon rendering. Trigger words: GameHUDController, GameHUD, RightPanel, building HUD, icon, TileInspector, BottomActionBar, EventFeed, dropdown, code-driven UI, tile inspector, badge, market panel, contract panel.'
argument-hint: 'Describe the HUD/UI task: e.g. "add building icons", "refactor TileInspector", "wire BottomActionBar tab"'
---

# GameHUD UI — Terraformation

## Architecture — Migration GameHUD → GameHUDController

Le HUD a migré de `GameHUD.cs` (uGUI Canvas code-driven) vers `GameHUDController.cs` (UI Toolkit).

**IMPORTANT** : `GameHUD.cs` est LEGACY. Son canvas uGUI est détruit au démarrage par `GameHUDController.Start()`.
Ne plus éditer `GameHUD.cs` pour les nouvelles features.

### Structure UI Toolkit actuelle

```
_root (VisualElement, position:Absolute, 100%×100%)
├── _topBar          — TopBar.uxml + TopBar.uss
├── _leftPanel       — LeftPanel.uxml + LeftPanel.uss  (vue Planète)
├── _tileInspector   — TileInspector.uxml + TileInspector.uss  (sélection tuile)
├── _eventFeed       — Panneau droit, construit en C# (position:Absolute right:0)
└── _bottomBar       — BottomActionBar.uxml + BottomActionBar.uss
```

### BottomActionBar — 5 tabs d'axe corp

| Tab | Nom | Couleur accent | Index |
|-----|-----|---------------|-------|
| 0 | TERRITOIRE | `--text-accent` (bleu) | 0 |
| 1 | CONSTRUCTION | `--construction-orange` | 1 |
| 2 | MARCHÉ | jaune | 2 |
| 3 | CONTRATS | vert | 3 |
| 4 | TERRAFORM | `--diplomacy-purple` | 4 |

Active tab class: `bottom-action-bar__tab--active`.
Visible uniquement en `ViewState.Planet`.

### TileInspector — sections gardées

Après nettoyage (sections migrées vers tabs), il ne reste que :
- Header (terrain + tileId + close)
- PROPRIÉTAIRE (badge, claim/unclaim)
- BÂTIMENTS (building-list-container)
- Status label

Les sections FILE DE CONSTRUCTION, MARCHÉ, CONTRATS, NATIONALISATION, ÉCOLOGIE ont été supprimées → elles vivront dans les panels contextuels des tabs.

## When to Use

- Editing `Game/Assets/Scripts/UI/GameHUDController.cs`
- Ajout/refactor de sections dans TileInspector, BottomActionBar, EventFeed, LeftPanel, TopBar
- Implémentation building, marché, contrats dans les panels de tabs
- Iconographie UI (Font Awesome, TMP font assets, TMP sprite assets)
- TMP dropdowns, labels, badge rows, building list rendering

## Files Involved

| File | Role |
|------|------|
| `Game/Assets/Scripts/UI/GameHUDController.cs` | **Contrôleur principal UI Toolkit (actif)** |
| `Game/Assets/Scripts/UI/GameHUD.cs` | Legacy uGUI — NE PAS ÉDITER |
| `Game/Assets/UI/Templates/*.uxml` | Templates UXML (TopBar, LeftPanel, TileInspector, BottomActionBar) |
| `Game/Assets/UI/Styles/*.uss` | Stylesheets USS (variables, base, TopBar, LeftPanel, TileInspector, BottomActionBar) |
| `Game/Assets/UI/Components/*.uxml` | Composants réutilisables (BuildingCard, ConstructionCard) |
| `Game/Assets/Scripts/UI/GameHUDBuildingIcons.cs` | UI-only mapping CorpBuildingType → label/icon/tint |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Mirror types |
| `Documentation/ROADMAP.md` | Feature progress |
| `Documentation/ARCHITECTURE.md` | Décisions techniques |

## Core Rules

### 1. Inline styles obligatoires pour les containers positionnés avec CloneTree

`CloneTree()` dans un container existant **n'applique pas** les `<Style src="...">` déclarés dans le UXML.
→ Toujours appliquer les styles de layout critiques en C# inline **après** le clone :

```csharp
_myPanel.style.position       = Position.Absolute;
_myPanel.style.right          = new StyleLength(0f);   // float f, pas int
_myPanel.style.flexDirection  = FlexDirection.Row;
// etc.
```

⚠️ Utiliser `0f` / `52f` pas `0` / `52` : `StyleLength(int)` est ambigu avec `StyleLength(StyleKeyword)`.

### 2. Préférer `Instantiate()` pour les templates racine

Pour les panels racine (TopBar, LeftPanel) : utiliser `template.Instantiate()` + `_root.Add()`.
Pour les templates clonés dans un container déjà positionné (BottomActionBar, TileInspector) : utiliser `asset.CloneTree(_root)` + forcer les styles inline.

### 3. GameHUD legacy — ne pas contourner la destruction

`GameHUDController.Start()` détruit `GameHUDCanvas` (enfant de GameHUD).
Si GameHUD ajoute un nouveau panel, il faut le détruire aussi dans GameHUDController.

### 4. Keep gameplay and presentation separate

- `CorpBuildingType`, `CorpBuilding`, et `BuildingData` restent des types gameplay
- Glyphs, icon names, font asset paths, colors sont **UI-only** → dans `GameHUDBuildingIcons.cs`

### 5. Always provide a fallback

Si un template UXML est null → fallback procédural C# (`BuildXxxProcedural()`).
Toujours loguer un warning si le template est manquant.

## Recommended Procedure

### Step 1 — Lire le contrôleur avant d'éditer

Lire la région concernée dans `GameHUDController.cs` :
- les champs runtime (`_xxx`)
- la méthode `BuildXxx()`
- la coroutine de refresh si elle existe
- `OnViewChanged()` pour la visibilité

### Step 2 — Identifier data vs UI vs les deux

- Si seulement labels/layout : rester dans `GameHUDController.cs` et USS
- Si nouveau champ serveur requis : aussi utiliser `simulation-contract-sync`
- Si nouvelle mécanique tick : aussi utiliser `gameplay-tick-feature`

### Step 3 — Appliquer les styles inline après CloneTree

Voir règle 1 ci-dessus. Ne pas oublier `flex-direction` si le container doit être `Row`.

### Step 4 — Rendre les entrées interactives avec Button, pas Label

Les listes d'événements ou d'items cliquables → `Button` avec `RegisterCallback<ClickEvent>`.
`Label` pour affichage pur, `Button` pour toute interaction.

### Step 5 — Mettre à jour la doc si changement de convention

- `ROADMAP.md` — si une feature visible est implémentée
- `ARCHITECTURE.md` — si une nouvelle convention technique est introduite
- `CHANGELOG.md` — si la feature est complète

## Common Mistakes

- Putting Font Awesome unicode directly in gameplay enums or contracts
- Making `GameHUD.cs` depend on building display strings as identifiers
- Forgetting fallback text when the font asset is missing
- Only showing icons in one place (e.g. building list) and forgetting the construction flow preview
- Treating HUD icon work as equivalent to world rendering for buildings
- Updating docs as if the gameplay changed, when only UI presentation changed

## Validation Checklist

1. `GameHUD.cs` compiles with zero errors
2. The RightPanel remains readable at runtime
3. Building rows show icon + label + state, or a readable fallback
4. The construction section shows the selected building clearly before build action
5. No contract or gameplay type depends on icon metadata
6. Docs are updated if the UI convention became part of the project workflow
