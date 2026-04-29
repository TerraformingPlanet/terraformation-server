# TileInspector — Structure UXML et champs C# (2026-04-29)

## Fichier UXML
`Game/Assets/UI/Templates/TileInspector.uxml`

## Structure complète

```
tile-inspector (VisualElement)
├── tile-inspector__header
│   ├── btn-territory-badge  (Button)   ← badge territoire cliquable
│   ├── tile-header-label    (Label)    ← tileId affiché
│   └── btn-close-inspector  (Button)   ← fermer l'inspecteur
│
├── territory-queue-section (VisualElement)  ← FILE DE CONSTRUCTION (fixe, au-dessus des tabs)
│   ├── queue-capital-row
│   │   ├── (Label "CAPITAL")
│   │   └── queue-corp-capital-label   (Label)  ← crédits corpo en ¤
│   ├── (Label "FILE DE CONSTRUCTION")
│   ├── queue-track [État]
│   │   ├── (Label "État")  class: queue-track__label--etat
│   │   ├── queue-track__bar-bg
│   │   │   └── queue-track-etat-fill      (VisualElement)  ← barre de progression
│   │   └── queue-track-etat-name          (Label)          ← nom du bâtiment
│   ├── queue-track [Investisseur]
│   │   ├── (Label "Investisseur")  class: queue-track__label--investor
│   │   ├── queue-track__bar-bg
│   │   │   └── queue-track-investor-fill  (VisualElement)  ← barre de progression
│   │   └── queue-track-investor-name      (Label)          ← nom du bâtiment
│   ├── queue-pending-container   (VisualElement)  ← items en attente territoire
│   ├── queue-corp-all-title      (Label)          ← "EN COURS — CORPORATION"
│   └── queue-corp-all-container  (VisualElement)  ← constructions InProgress corpo
│
├── tile-inspector__tabs
│   ├── tab-resume     (Button, active par défaut)
│   ├── tab-population (Button)
│   ├── tab-batiment   (Button)
│   ├── tab-marche     (Button)
│   └── tab-contrats   (Button)
│
└── inspector-scroll (ScrollView)
    ├── tab-content-resume     (VisualElement)
    │   ├── corp-list-container   (VisualElement)  ← liste des corporations sur la tuile
    │   ├── terrain-info-label    (Label)
    │   └── ecology-label         (Label)
    ├── tab-content-population (VisualElement)
    │   ├── pop-poor-label    (Label)
    │   ├── pop-middle-label  (Label)
    │   ├── pop-rich-label    (Label)
    │   ├── pop-total-label   (Label)
    │   ├── pop-summary-label (Label)
    │   └── territory-label   (Label)
    ├── tab-content-batiment   (VisualElement)
    │   └── building-list-container (VisualElement)
    ├── tab-content-marche     (VisualElement)
    └── tab-content-contrats   (VisualElement)
```

## Champs C# dans TileInspectorController.cs

```csharp
// Queue section
private VisualElement _queueSection;
private VisualElement _queuePendingContainer;
private VisualElement _queueCorpAllContainer;
private Label         _queueCorpAllTitle;
private Label         _queueCorpCapitalLabel;
private VisualElement _queueTrackEtatFill;
private VisualElement _queueTrackInvestorFill;
private Label         _queueTrackEtatName;
private Label         _queueTrackInvestorName;

// Tabs
private VisualElement _tabResume, _tabPopulation, _tabBatiment, _tabMarche, _tabContrats;
private VisualElement _contentResume, _contentPopulation, _contentBatiment, _contentMarche, _contentContrats;

// Data
private CorpItem[] _cachedCorpItems;  // corps fetchés, pour capital lookup
```

### Méthodes clés

| Méthode | Rôle |
|---------|------|
| `RefreshTerritoryQueue(corpId, bodyId, tileId)` | IEnumerator — 2 appels HTTP séquentiels |
| `RebuildQueueDisplay(queue, allCorpItems, corpCredits)` | Met à jour les tracks + pending + corp-all |
| `GetCachedCorpCredits(corpId)` | Lookup dans `_cachedCorpItems` |
| `OnTabSelected(index)` | Switche `display: none/flex` sur les tab-content-xxx |

### Logique tracks

```
isEBDeFortune = true  → track État actif, Investisseur à 0%
isEBDeFortune = false → track Investisseur actif, État à 0%
activeItem = premier ConstrItem avec status == 1 sur le territoire
progress = activeItem.ticksElapsed / activeItem.ticksRequired (clampé 0–1)
```

## CSS — Classes clés (TileInspector.uss)

| Classe | Description |
|--------|-------------|
| `.queue-track` | `flex-direction: row; align-items: center` |
| `.queue-track__label--etat` | `color: var(--queue-etat-color)` (orange) |
| `.queue-track__label--investor` | `color: var(--queue-investor-color)` (bleu) |
| `.queue-track__bar-fill` | `height: 100%; width: 0% → 100%; transition: width 0.4s` |
| `.queue-capital-value` | `color: var(--energy-yellow); font-weight: bold` |
| `.queue-sublabel` | `font-size: 9px; letter-spacing: 0.05em; color: var(--text-secondary)` |

## Tokens variables.uss liés à la queue

```css
--queue-etat-color:     rgb(255, 140,  0);  /* EB de fortune — orange */
--queue-investor-color: rgb(80,  160, 255); /* EB formel     — bleu  */
--construction-orange:  rgb(255, 140,  0);
--energy-yellow:        rgb(255, 215,  50);
```
