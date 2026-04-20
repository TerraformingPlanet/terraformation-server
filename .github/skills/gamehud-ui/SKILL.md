---
name: gamehud-ui
description: 'Use when implementing or refactoring the code-driven Unity HUD in GameHUD.cs: RightPanel tile inspector, building list/actions, market/contract sections, icon rendering, TMP dropdowns, badge rows, Font Awesome or TMP sprite integration. Trigger words: GameHUD, RightPanel, building HUD, icon, Font Awesome, TMP, dropdown, code-driven UI, tile inspector, badge, market panel, contract panel.'
argument-hint: 'Describe the HUD/UI task: e.g. "add building icons in GameHUD", "refactor RightPanel building list", "integrate TMP font or sprite icons for buildings"'
---

# GameHUD UI — Terraformation

## When to Use

- Editing `Game/Assets/Scripts/UI/GameHUD.cs`
- Adding or refactoring code-driven HUD sections in the RightPanel or DebugDrawer
- Implementing building, market, or contract UI in the HUD
- Integrating iconography for UI-only presentation (Font Awesome, TMP font assets, TMP sprite assets)
- Changing TMP dropdowns, labels, badge rows, or building list rendering
- Any task where gameplay building types must be displayed in UI without leaking presentation details into the data model

## Files Involved

| File | Role |
|------|------|
| `Game/Assets/Scripts/UI/GameHUD.cs` | Main code-driven HUD implementation |
| `Game/Assets/Scripts/UI/GameHUDBuildingIcons.cs` | UI-only mapping from `CorpBuildingType` to label/icon/tint |
| `Game/Assets/Scripts/Simulation/Contracts/SimulationContracts.cs` | Network mirror types (`CorpBuildingType`, `CorpBuilding`, etc.) |
| `Game/Assets/Scripts/Economy/BuildingData.cs` | Local gameplay ScriptableObject definitions |
| `Game/Assets/Resources/Fonts/` | Optional local UI font assets |
| `Documentation/ROADMAP.md` | Feature progress for Phase 7.x |
| `Documentation/ARCHITECTURE.md` | Technical decision when UI representation changes |
| `Documentation/CHANGELOG.md` | Completed implementation trace |

## Core Rules

### 1. Keep gameplay and presentation separate

- `CorpBuildingType`, `CorpBuilding`, and `BuildingData` remain gameplay/data types
- Glyphs, icon names, font asset paths, and colors are **UI-only** concerns
- Never make gameplay logic depend on a glyph or UI string

### 2. Use a central icon mapping layer

Do not scatter icon literals throughout `GameHUD.cs`.

Preferred approach:
- Create or update a single mapping file such as `GameHUDBuildingIcons.cs`
- Map `CorpBuildingType` to:
  - user-facing display name
  - icon token or unicode
  - fallback glyph/text
  - tint/color

### 3. Always provide a fallback

If using a font-based icon system:
- The HUD must still render something readable if the font is missing or TMP cannot create/load the font asset
- Fallback should be visible and deterministic (`M`, `F`, `E`, `R`, `?`, etc.)

### 4. Prefer code-driven UI consistency

When adding a new UI element in `GameHUD.cs`:
- Reuse the existing helper patterns (`MakeLabel`, `MakeButton`, dropdown builders, row layouts)
- Keep alignment, spacing, and colors consistent with the existing HUD
- Avoid creating hidden one-off layout code when a reusable helper is possible

### 5. Scope icon work to HUD unless explicitly asked otherwise

Font Awesome or TMP icon work is, by default:
- for HUD panels
- for dropdowns/lists/badges/buttons
- **not** for world-space rendering on tiles, globe overlays, or local scene props

If the user wants visible buildings on the map/globe/local scene, treat that as a separate rendering task.

## Recommended Procedure

### Step 1 — Read the current HUD section before editing

For any change, read the relevant `GameHUD.cs` region first:
- the state fields
- the panel construction block in `BuildRightPanel()`
- the refresh coroutine/method that populates the section
- the UI helpers at the bottom of the file

### Step 2 — Identify whether the change is data, UI, or both

- If only labels/icons/layout change: keep changes inside `GameHUD.cs` and UI mapping files
- If a new server field is required: stop and also use `simulation-contract-sync`
- If a new gameplay mechanic changes tick behavior: stop and also use `gameplay-tick-feature`

### Step 3 — Add/update the icon mapping

For building icons:
1. Extend `GameHUDBuildingIcons.cs`
2. Add display name, icon token/unicode, fallback, tint
3. Keep unknown types on a safe default entry

### Step 4 — Render through helpers, not ad hoc strings

Preferred rendering structure for building rows:
- icon label
- text label
- optional secondary status (ticks, workers, outputs)

Do not rely on one large multiline string if structured rows are feasible.

### Step 5 — Handle TMP/font integration safely

If using a font file in `Assets/Resources/Fonts/`:
- Load via `Resources.Load<Font>()`
- Create `TMP_FontAsset` dynamically when needed
- Preload needed glyphs when practical
- Log a warning and fall back gracefully if loading fails

If font integration proves unstable, switch to a `TMP Sprite Asset` without changing the mapping layer.

### Step 6 — Update documentation when the implementation changes project conventions

Update docs when relevant:
- `ROADMAP.md` — if a visible Phase 7.x UI feature is implemented
- `ARCHITECTURE.md` — if a new technical convention is introduced (e.g. icon mapping layer, local font assets, fallback policy)
- `CHANGELOG.md` — if the feature is complete enough to trace historically

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
