---
name: design-md
description: 'Use when editing Game/Assets/UI/Styles/DESIGN.md, adding or changing design tokens, syncing tokens to variables.uss, or validating the design system against the @google/design.md spec. Trigger words: DESIGN.md, design token, color token, USS sync, design system, typography token, spacing token, components token, design.md lint.'
argument-hint: 'Describe the design task: e.g. "add a new color token", "sync DESIGN.md tokens to variables.uss", "fix lint errors in DESIGN.md", "add a new component token"'
---

# Design System — Terraformation (`DESIGN.md`)

## When to Use

- Editing `Game/Assets/UI/Styles/DESIGN.md`
- Adding, renaming, or removing design tokens (colors, typography, spacing, shapes, components)
- Syncing `DESIGN.md` front-matter tokens → `Game/Assets/UI/Styles/variables.uss`
- Running or fixing linter errors from `@google/design.md`
- Creating a new USS variable that should originate from a token
- Updating the prose sections (Overview, Colors, Typography, etc.)

## Files Involved

| File | Role |
|------|------|
| `Game/Assets/UI/Styles/DESIGN.md` | Source of truth — design tokens + prose |
| `Game/Assets/UI/Styles/variables.uss` | USS variables derived from DESIGN.md tokens |
| `Game/Assets/UI/Styles/hud.uss` | HUD component styles, consumes `variables.uss` |
| `Game/Assets/UI/Templates/*.uxml` | UXML templates that reference USS variables |
| `Documentation/design.md/docs/spec.md` | `@google/design.md` format specification (local copy) |
| `Documentation/design.md/examples/` | Reference examples (atmospheric-glass, paws-and-paths, totality-festival) |

## `@google/design.md` Format Rules

### YAML Front Matter

The front matter block opens and closes with `---`. All token values must follow these types exactly — the linter rejects anything else.

**Colors** — hex only, `#rrggbb`, no `rgb()`, no `rgba()`, no named colors:
```yaml
colors:
  surface: "#0c0c12"
  primary: "#64b4ff"
  accent: "#ff9f40"
```

**Typography** — `fontWeight` must be a number (not a string like `"bold"`):
```yaml
typography:
  headline:
    fontFamily: "Rajdhani"
    fontSize: 18px
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Inter"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
```

**Spacing / Rounded** — Dimension = string with `px`, `em`, or `rem` suffix:
```yaml
spacing:
  xs: 4px
  sm: 8px
  md: 16px
rounded:
  sm: 4px
  md: 8px
```

**Components** — valid sub-token keys are: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, `width`. Do NOT use `borderColor` (not in spec):
```yaml
components:
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
```

**Token References** — use `{path.to.token}` syntax:
```yaml
components:
  tile-inspector:
    backgroundColor: "{colors.surface}"
    typography: "{typography.body}"
```

### Section Order (canonical)

1. Overview
2. Colors
3. Typography
4. Layout
5. Elevation & Depth *(optional)*
6. Shapes
7. Components
8. Do's and Don'ts

All section headings use `##`. An `#` H1 is optional (title only).

## Alpha Transparency Limitation

The `@google/design.md` spec does not support alpha in color tokens (no `rgba()`).  
For panel backgrounds that need transparency (e.g. `rgba(12,12,18,0.92)`):
- Store the **opaque base color** in the token: `"#0c0c12"`
- Apply the `opacity` or `-unity-background-image-tint-color` directly in USS
- Document this in the DESIGN.md prose (e.g. "Panel surfaces use 92% opacity applied in USS")

## Lint Command

```powershell
# Run from workspace root (Node.js required)
npx @google/design.md lint Game/Assets/UI/Styles/DESIGN.md

# Output JSON for CI
npx @google/design.md lint Game/Assets/UI/Styles/DESIGN.md --output json > Artifacts/ci/design-lint.json
```

Lint result fields: `{ "errors": N, "warnings": N, "infos": N }`.  
Target: **0 errors, 0 warnings** before committing token changes.

## Syncing Tokens to USS

After editing `DESIGN.md`, update `variables.uss` manually — there is no auto-export step yet.  
Convention: every token in `colors.*` maps to a CSS variable `--color-<token-name>`.

```css
/* variables.uss — generated from DESIGN.md tokens */
:root {
    --color-surface: #0c0c12;
    --color-primary: #64b4ff;
    --color-accent: #ff9f40;
    --color-on-surface: #dcdcdc;

    --font-size-headline: 18px;
    --font-weight-headline: 700;

    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;

    --rounded-sm: 4px;
    --rounded-md: 8px;
}
```

Then in `hud.uss` and templates:
```css
.panel {
    background-color: var(--color-surface);
    border-radius: var(--rounded-md);
}
```

## Recommended Procedure

### Step 1 — Read current DESIGN.md front matter before editing

```
read_file("Game/Assets/UI/Styles/DESIGN.md")
```

Identify existing token names to avoid duplicates and follow the naming convention already in use.

### Step 2 — Edit tokens in front matter

- Colors: hex `#rrggbb` only
- `fontWeight`: bare number (`400`, `700`), not a string
- Dimensions: `px`, `em`, or `rem` suffix
- Token references: `{colors.token-name}` syntax

### Step 3 — Update prose to match token changes

Each section's prose should describe the tokens in human terms.  
Example: if adding `--color-danger`, add a bullet in the Colors prose section explaining its semantic role.

### Step 4 — Run the linter

```powershell
npx @google/design.md lint Game/Assets/UI/Styles/DESIGN.md
```

Fix all errors before proceeding. Warnings for unrecognized component sub-tokens must also be resolved.

### Step 5 — Sync variables.uss

Update `Game/Assets/UI/Styles/variables.uss` so every new/changed token has a matching CSS variable.

### Step 6 — Verify USS is referenced in UXML

Check that templates using the changed variables compile without missing references in Unity:
- Open Unity Console and check for USS parse errors
- Confirm visual appearance hasn't regressed (screenshot via MCP if needed)

## Common Mistakes

| Mistake | Fix |
|---|---|
| `rgb(100, 180, 255)` in YAML | Convert to hex: `"#64b4ff"` |
| `rgba(12,12,18,0.92)` in YAML | Use opaque hex `"#0c0c12"` + apply opacity in USS |
| `fontWeight: "bold"` | Use `fontWeight: 700` |
| `borderColor:` in components | Not a valid sub-token — use `backgroundColor` / `textColor` |
| Token added to DESIGN.md but not in variables.uss | Always sync both files together |
| USS variable added without a token | Token first in DESIGN.md, then USS variable |

## Reference Examples

Local examples in `Documentation/design.md/examples/`:
- `atmospheric-glass/` — dark glassmorphism palette, close to Terraformation style
- `paws-and-paths/` — light mobile design, useful for typography token patterns
- `totality-festival/` — event brand, useful for accent color + component tokens

Full spec: `Documentation/design.md/docs/spec.md`
