---
paths:
  - "Game/**"
---

# Terraformation — Règles Unity / UI Toolkit

S'active automatiquement dès qu'un fichier sous `Game/` est dans le contexte.

## Projet client

- Unity **6 LTS** 3D URP — C# uniquement
- Scripts : `Game/Assets/Scripts/`
- UI : Unity UI Toolkit (USS + UXML + code-driven via C#)
- **Aucune logique gameplay en C#** — tout passe par les endpoints DedicatedServer (port 8080)

---

## Design system

- Source de vérité des tokens : `Game/Assets/UI/Styles/variables.uss`
- Documentation design + règles de composition : `Game/Assets/UI/Styles/DESIGN.md`
- Composants de base (classes utilitaires) : `Game/Assets/UI/Styles/base.uss`
- **JAMAIS de valeur hardcodée** dans du CSS/USS — toujours `var(--token-name)`
- Ajouter un token → mettre à jour `variables.uss` **ET** `DESIGN.md` en même temps

### Tokens clés

| Catégorie | Exemples |
|-----------|---------|
| Fonds panneaux | `--panel-bg`, `--panel-bg-light`, `--topbar-bg` |
| Texte | `--text-primary`, `--text-secondary`, `--text-accent`, `--text-warning`, `--text-danger` |
| Boutons | `--btn-claim`, `--btn-unclaim`, `--btn-build`, `--btn-neutral` |
| Domaine | `--construction-orange`, `--energy-yellow`, `--eco-green`, `--research-blue` |
| Terrain | `--terrain-ocean` … `--terrain-volcano` |
| Typo | `--font-size-title` (14px), `--font-size-body` (12px), `--font-size-caption` (10px) |
| Géométrie | `--panel-radius` (6px), `--card-radius` (4px), `--gap-xs/sm/md/lg` |

---

## Composants USS existants

| Composant | Fichier | Largeur / position |
|-----------|---------|--------------------|
| `.top-bar` | `TopBar.uss` | 100% × 40px, absolute top |
| `.tile-inspector` | `TileInspector.uss` | 260px, absolute left, sous topbar |
| `.hud-panel` / `.hud-panel--light` | `base.uss` | flottant |
| `.hud-btn` + variantes `--claim/unclaim/build/danger` | `base.uss` | — |
| `.hud-label` + variantes `--title/secondary/accent/warning/danger` | `base.uss` | — |

---

## Conventions C#

- **PascalCase** : classes, méthodes, propriétés
- **camelCase** : variables locales, paramètres
- `FindAnyObjectByType<T>()` — **pas** `FindFirstObjectByType` (obsolète Unity 6)
- Pas de `GameObject.Find()` en dehors de l'initialisation
- Les scripts HUD code-driven centralisés dans `GameHUD.cs`

---

## Contrats Python ↔ C#

- Modèles Pydantic (Python) → `SimulationCore/terraformation_sim/models.py`
- Miroir C# → `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs`
- Modifier un côté → **synchroniser l'autre immédiatement**
- Référence : `Documentation/SIMULATION_CONTRACTS.md`

---

## Fichiers clés Unity

| Fichier | Rôle |
|---------|------|
| `Game/Assets/Scripts/GameHUD.cs` | HUD code-driven (RightPanel, TileInspector, TopBar) |
| `Game/Assets/Scripts/ViewManager.cs` | Transitions de vues (ESC, F9, F10) |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Contrats C# partagés |
| `Game/Assets/UI/Styles/variables.uss` | Tous les tokens CSS |
| `Game/Assets/UI/Styles/DESIGN.md` | Documentation design system |
