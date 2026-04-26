---
name: gamehud-ui
description: Use when implementing or refactoring the code-driven Unity HUD in GameHUD.cs: RightPanel tile inspector, building list/actions, market/contract sections, icon rendering, TMP dropdowns, badge rows, Font Awesome or TMP sprite integration. Trigger words: GameHUD, RightPanel, building HUD, icon, Font Awesome, TMP, dropdown, code-driven UI, tile inspector, badge, market panel, contract panel, GameHUDController, BuildRightPanel.
---

# GameHUD UI — Terraformation

## When to Use

- Editing `Game/Assets/Scripts/UI/GameHUD.cs`
- Ajout ou refactoring de sections HUD dans RightPanel ou DebugDrawer
- Implémentation UI pour buildings, market, contrats dans le HUD
- Intégration iconographie (Font Awesome, TMP font assets, TMP sprite assets)
- Modification TMP dropdowns, labels, badge rows, building list
- Toute tâche où les `CorpBuildingType` doivent s'afficher dans l'UI sans contaminer le data model

## Fichiers impliqués

| Fichier | Rôle |
|---------|------|
| `Game/Assets/Scripts/UI/GameHUD.cs` | HUD principal code-driven |
| `Game/Assets/Scripts/UI/GameHUDController.cs` | Contrôleur HUD (show/hide, init) |
| `Game/Assets/Scripts/UI/GameHUDBuildingIcons.cs` | Mapping UI-only : `CorpBuildingType` → label/icon/tint |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Types réseau miroirs |
| `Game/Assets/Scripts/Economy/BuildingData.cs` | ScriptableObject gameplay local |
| `Game/Assets/Resources/Fonts/` | Font assets TMP optionnels |

## Règles fondamentales

### 1. Séparer gameplay et présentation

- `CorpBuildingType`, `CorpBuilding`, `BuildingData` = types gameplay/data — ne pas y mettre de glyphs
- Glyphs, noms icônes, chemins font, couleurs = **UI-only** → dans `GameHUDBuildingIcons.cs`
- La logique gameplay ne doit jamais dépendre d'un glyph ou d'une chaîne d'affichage UI

### 2. Couche de mapping centralisée

Ne pas éparpiller des littéraux d'icônes dans `GameHUD.cs`.

Approche correcte — `GameHUDBuildingIcons.cs` :
```csharp
public static class GameHUDBuildingIcons
{
    public static string GetLabel(CorpBuildingType t) => t switch {
        CorpBuildingType.Mine => "Mine",
        CorpBuildingType.Factory => "Factory",
        _ => t.ToString()
    };
    public static string GetIcon(CorpBuildingType t) => t switch {
        CorpBuildingType.Mine => "\uf0e7",   // Font Awesome
        _ => "?"
    };
}
```

### 3. Toujours fournir un fallback

Si le font asset est manquant ou que TMP ne peut pas le charger :
- Le HUD doit quand même afficher quelque chose de lisible
- Fallback déterministe : `M`, `F`, `E`, `R`, `?`, etc.

### 4. Cohérence des helpers

Lors d'ajout d'élément UI dans `GameHUD.cs` :
- Réutiliser les helpers existants (`MakeLabel`, `MakeButton`, builders dropdown, row layouts)
- Alignement, spacing et couleurs cohérents avec le HUD existant

## Procédure recommandée

### Étape 1 — Lire le HUD avant toute modification

```
Unity_ManageScript(action=read, name=GameHUD)
Unity_ManageScript(action=read, name=GameHUDBuildingIcons)   # si existe
```

Identifier :
- les champs d'état
- le bloc construction dans `BuildRightPanel()`
- la méthode de refresh qui peuple la section
- les helpers UI en bas du fichier

### Étape 2 — Identifier la nature du changement

- Changement labels/icons/layout → modifications dans `GameHUD.cs` et fichiers mapping UI
- Nouveau champ serveur requis → utiliser aussi `simulation-contract-sync`
- Nouvelle mécanique gameplay → utiliser aussi `gameplay-tick-feature`

### Étape 3 — Mettre à jour le mapping d'icônes

1. Étendre `GameHUDBuildingIcons.cs`
2. Ajouter display name, token icône/unicode, fallback, tint
3. Conserver une entrée default sûre pour les types inconnus

### Étape 4 — Utiliser les helpers pour le rendu

Structure préférée pour les building rows :
- label icône
- label texte
- statut secondaire optionnel (ticks, workers, outputs)

### Étape 5 — Intégration TMP/font

Si utilisation d'une font dans `Assets/Resources/Fonts/` :
- Charger via `Resources.Load<Font>()`
- Créer `TMP_FontAsset` dynamiquement si besoin
- Logger un warning et fallback gracieux si le chargement échoue

### Étape 6 — Valider

```
Unity_ValidateScript(name=GameHUD, level=standard)
Unity_ValidateScript(name=GameHUDBuildingIcons, level=standard)
Unity_ReadConsole(Types=[Error], Count=10)
```

## Erreurs fréquentes

- Mettre des unicode Font Awesome directement dans les enums gameplay ou contracts
- Rendre `GameHUD.cs` dépendant de strings d'affichage comme identifiants
- Oublier le fallback texte si le font asset est absent
- N'afficher les icônes qu'au seul endroit (ex : building list) en oubliant le flow de construction
- Confondre icon HUD avec world-space rendering (tiles/globe) — ce sont deux tâches distinctes

## Checklist de validation

1. `GameHUD.cs` compile sans erreur
2. Le RightPanel reste lisible au runtime
3. Les building rows affichent icon + label + état, ou un fallback lisible
4. La section construction montre le bâtiment sélectionné avant l'action de build
5. Aucun type contract ou gameplay ne dépend des métadonnées d'icône
