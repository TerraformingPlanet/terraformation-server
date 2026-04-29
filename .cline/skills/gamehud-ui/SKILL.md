---
name: gamehud-ui
description: 'Use when implementing or refactoring the UI Toolkit HUD in GameHUDController.cs: TileInspector, BottomActionBar, EventFeed, LeftPanel, TopBar, building list, icon rendering. Trigger words: GameHUDController, GameHUD, RightPanel, building HUD, icon, TileInspector, BottomActionBar, EventFeed, dropdown, code-driven UI, tile inspector, badge, market panel, contract panel.'
argument-hint: 'Describe the HUD/UI task: e.g. "add building icons", "refactor TileInspector", "wire BottomActionBar tab"'
---

# GameHUD UI — Terraformation

## Architecture — Orchestrateur + 7 Sous-Contrôleurs

Le HUD utilise `GameHUDController.cs` (UI Toolkit) comme **orchestrateur**.
`GameHUD.cs` (uGUI) a été **supprimé**.

`GameHUDController` délègue toute la logique métier à 7 sous-contrôleurs dans `Scripts/UI/HUD/` :

| Sous-contrôleur | Fichier | Responsabilité |
|---|---|---|
| `TopBarController` | `HUD/TopBarController.cs` | Barre haut : nom planète, tick, crédits, bouton vue |
| `LeftPanelController` | `HUD/LeftPanelController.cs` | Panneau gauche : progress, scoreboard, atmo |
| `TileInspectorController` | `HUD/TileInspectorController.cs` | Inspecteur tuile (header, propriétaire, bâtiments) |
| `EventFeedController` | `HUD/EventFeedController.cs` | Fil événements + journal actions |
| `DebugDrawerController` | `HUD/DebugDrawerController.cs` | Debug drawer corps/projection (F9) |
| `BottomActionBarController` | `HUD/BottomActionBarController.cs` | Barre bas, 5 tabs (Territoire/Construction/Marché/Contrats/Terraform) |
| `TimeControlsController` | `HUD/TimeControlsController.cs` | Contrôles vitesse tick, barre progression |

`GameHUDController` **garde en propre** uniquement :
- Le `_root` (`VisualElement`, Absolute 100%×100%) partagé avec tous les sous-contrôleurs
- Le **tooltip** (`BuildTooltip()`, `OnTileHoverReady/Cancelled`)
- L'**event-popup** (`BuildEventPopup()`, `ShowEventPopup()`, `HideEventPopup()`)
- Le câblage des events Unity scène (ViewManager, PlanetSphere, TerraformHUD, WebSocket)

### Structure _root

```
_root (VisualElement, position:Absolute, 100%×100%)
├── TopBarController.Initialize(_root)        → TopBar.uxml + TopBar.uss
├── LeftPanelController.Initialize(_root)     → LeftPanel.uxml + LeftPanel.uss
├── TileInspectorController.Initialize(_root) → TileInspector.uxml + TileInspector.uss
├── EventFeedController.Initialize(_root)     → EventFeed.uxml + fallback procédural
├── DebugDrawerController.Initialize(_root)   → DebugDrawer.uxml + DebugDrawer.uss (F9)
├── BottomActionBarController.Initialize(_root) → BottomActionBar.uxml + BottomActionBar.uss
├── TimeControlsController.Initialize(_root)  → construit en C# inline
├── _tooltip    — hud-tooltip / hud-tooltip-label (Tooltip.uxml ou fallback)
└── _eventPopup — event-popup / title / body  (EventPopup.uxml ou fallback)
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

### TileInspector — structure actuelle (2026-04-29)

Le TileInspector (`TileInspector.uxml`) est divisé en :

1. **Header fixe** — badge territoire + tileId + bouton close
2. **Section FILE DE CONSTRUCTION** (fixe, avant les tabs) — `territory-queue-section`
   - Ligne capital : `queue-capital-row` → `queue-corp-capital-label` (crédits corpo en ¤)
   - Track **État** (`queue-track-etat-fill` + `queue-track-etat-name`) — EB de fortune (population), couleur `--queue-etat-color` (orange)
   - Track **Investisseur** (`queue-track-investor-fill` + `queue-track-investor-name`) — EB formel (corpo/joueur), couleur `--queue-investor-color` (bleu)
   - `queue-pending-container` — items en attente du territoire
   - `queue-corp-all-title` + `queue-corp-all-container` — toutes les constructions InProgress de la corporation
3. **Tabs** (Résumé / Population / Bâtiment / Marché / Contrats)
4. **ScrollView** body avec un `tab-content-xxx` par onglet

**Fichiers UXML/USS à éditer pour changer l'UI :**

| Fichier | Rôle |
|---------|------|
| `Game/Assets/UI/Templates/TileInspector.uxml` | Structure HTML-like du panneau tuile |
| `Game/Assets/UI/Templates/TopBar.uxml` | Barre haute |
| `Game/Assets/UI/Templates/LeftPanel.uxml` | Panneau gauche |
| `Game/Assets/UI/Templates/BottomActionBar.uxml` | Barre basse 5 tabs |
| `Game/Assets/UI/Templates/EventFeed.uxml` | Fil d'événements |
| `Game/Assets/UI/Templates/DebugDrawer.uxml` | Debug (F9) |
| `Game/Assets/UI/Styles/TileInspector.uss` | CSS du TileInspector |
| `Game/Assets/UI/Styles/variables.uss` | **Tokens de couleur/taille globaux** — modifier ici pour changer une couleur partout |
| `Game/Assets/UI/Styles/base.uss` | Styles de base partagés |

**Tokens pertinents dans `variables.uss` :**
- `--queue-etat-color` : couleur barre/label track État (orange)
- `--queue-investor-color` : couleur barre/label track Investisseur (bleu)
- `--construction-orange`, `--energy-yellow`, `--text-primary`, `--text-secondary`

**Contrôleur C# correspondant :** `Game/Assets/Scripts/UI/HUD/TileInspectorController.cs`
- Champs clés : `_queueTrackEtatFill`, `_queueTrackInvestorFill`, `_queueTrackEtatName`, `_queueTrackInvestorName`, `_queueCorpCapitalLabel`, `_queueCorpAllContainer`
- Méthode principale : `RebuildQueueDisplay(TerritoryQueueDto queue, ConstrItem[] allCorpItems, float corpCredits)`

## Référence détaillée

Pour la structure UXML complète, les champs C#, et les classes CSS :
→ [docs/tile-inspector-structure.md](docs/tile-inspector-structure.md)

## When to Use

- Editing `Game/Assets/Scripts/UI/GameHUDController.cs`
- Ajout/refactor de sections dans TileInspector, BottomActionBar, EventFeed, LeftPanel, TopBar
- Implémentation building, marché, contrats dans les panels de tabs
- Iconographie UI (Font Awesome, TMP font assets, TMP sprite assets)
- TMP dropdowns, labels, badge rows, building list rendering

## Files Involved

| File | Role |
|------|------|
| `Game/Assets/Scripts/UI/GameHUDController.cs` | **Orchestrateur HUD** — init sous-contrôleurs, tooltip, event-popup, events scène |
| `Game/Assets/Scripts/UI/HUD/TopBarController.cs` | Sous-contrôleur barre haute |
| `Game/Assets/Scripts/UI/HUD/LeftPanelController.cs` | Sous-contrôleur panneau gauche |
| `Game/Assets/Scripts/UI/HUD/TileInspectorController.cs` | Sous-contrôleur inspecteur tuile |
| `Game/Assets/Scripts/UI/HUD/EventFeedController.cs` | Sous-contrôleur fil événements |
| `Game/Assets/Scripts/UI/HUD/DebugDrawerController.cs` | Sous-contrôleur debug drawer (F9) |
| `Game/Assets/Scripts/UI/HUD/BottomActionBarController.cs` | Sous-contrôleur barre basse (5 tabs) |
| `Game/Assets/Scripts/UI/HUD/TimeControlsController.cs` | Sous-contrôleur contrôles tick |
| `Game/Assets/UI/Templates/*.uxml` | Templates UXML (TopBar, LeftPanel, TileInspector, BottomActionBar, EventFeed, DebugDrawer, Tooltip, EventPopup) |
| `Game/Assets/UI/Styles/*.uss` | Stylesheets USS (variables, base, TopBar, LeftPanel, TileInspector, BottomActionBar, DebugDrawer) |
| `Game/Assets/UI/Components/*.uxml` | Composants réutilisables (BuildingCard, ConstructionCard) |
| `Game/Assets/Scripts/UI/GameHUDBuildingIcons.cs` | UI-only mapping CorpBuildingType → label/icon/tint |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Mirror types |
| `Documentation/ROADMAP.md` | Feature progress |
| `Documentation/ARCHITECTURE.md` | Décisions techniques |

## Core Rules

### 0. Toujours travailler dans le bon sous-contrôleur

Avant d'éditer, identifier quel sous-contrôleur possède la feature :
- EventFeed (fil événements, onglets) → `EventFeedController.cs`
- Debug drawer (corps, projection) → `DebugDrawerController.cs`
- Tooltip / event-popup → rester dans `GameHUDController.cs`
- Tout ce qui est délégué via `Initialize(_root)` appartient au sous-contrôleur correspondant

Les sous-contrôleurs sont ajoutés sur le même `GameObject` que `GameHUDController` via `AddComponent<XxxController>()` dans `InitializeHUDControllers()`. Ils reçoivent la référence `_root` dans `Initialize(VisualElement root)`.

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

### 3. GameHUD.cs est supprimé — ne pas le recréer

`GameHUD.cs` a été supprimé. Ne pas recréer de fichier du même nom.
Toute nouvelle feature UI va dans un sous-contrôleur existant ou dans un nouveau `HUD/XxxController.cs`.

### 4. Keep gameplay and presentation separate

- `CorpBuildingType`, `CorpBuilding`, et `BuildingData` restent des types gameplay
- Glyphs, icon names, font asset paths, colors sont **UI-only** → dans `GameHUDBuildingIcons.cs`

### 5. Always provide a fallback

Si un template UXML est null → fallback procédural C# (`BuildXxxProcedural()`).
Toujours loguer un warning si le template est manquant.

## Recommended Procedure

### Step 1 — Identifier le bon fichier avant d'éditer

Déterminer quel fichier possède la feature :
1. Chercher le champ `_xxx` ou la méthode `BuildXxx()` dans les sous-contrôleurs (`HUD/`)
2. Si c'est tooltip ou event-popup → `GameHUDController.cs`
3. Lire la méthode `Initialize(VisualElement root)` du sous-contrôleur cible
4. Vérifier `OnViewChanged()` dans `GameHUDController.cs` pour la visibilité

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
