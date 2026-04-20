---
name: terraformation-debug
description: 'Use when debugging Terraformation map generation, projection bugs, hydrology/biome issues, view flow transitions (ESC F9 F10), or validating preset scenarios. Trigger words: projection bug, biome distribution, hydrology, water cells, local region, preset debug, view flow, generation stats, smoke test, Coast Ocean Arid Frozen Basin preset, tile mismatch, coherence override, water level, region open, simulation tick.'
argument-hint: 'Describe the bug or scenario: e.g. "debug projection bug on Coast preset", "hydrology mismatch in Basin local region", "validate view flow transitions"'
---

# Terraformation Debug — MCP Workflow

## When to Use

- Biome / water distribution looks wrong on a preset
- Local region shows unexpected cell types (hydrology, river, biome)
- View transitions (SolarSystem → Planet → Local, ESC, F9, F10) are broken or lose state
- Need to validate a scenario before/after a code change
- Running generation quality checks or smoke tests
- Comparing two generation profiles or presets

## Tool Families

Two families of tools with different preconditions:

### `debug-client` — requires Unity Play Mode

Unity must be in **Play Mode**. Log `[RuntimeDebugHttpServer] Started on http://127.0.0.1:48621/` must be visible in the Unity console.

| Tool | Purpose |
|------|---------|
| `get_view_state` | Current view (SolarSystem/Planet/Local), active planet, region coords, selected hex |
| `launch_preset` | Load a named preset scenario (Coast, Ocean, Arid, Frozen, Basin) |
| `open_region` | Navigate Unity to a local region by lat/lon (normalized 0–1) |
| `get_console_errors` | Recent Unity console logs filtered by severity |
| `take_screenshot` | Capture the Unity game view |

### `simulation-server` — works without Unity Play Mode

Interrogates the DedicatedServer directly (`http://terraformation-dedicated-server:8080`).

| Tool | Purpose |
|------|---------|
| `get_projection_summary` | Biome/water distribution stats for the active planet |
| `get_projection_state` | Structured `ProjectionState` contract |
| `get_local_summary` | Terrain, hydrology, biome stats for the open local region |
| `get_region_state` | Structured `RegionState` contract |
| `get_world_state` / `get_client_snapshot` | Full world snapshot |
| `get_last_simulation_event` | Most recent simulation tick event |
| `get_server_action_definitions` | Available server actions |
| `get_generation_stats` | Generation statistics (simulation-server) |
| `get_generation_noise_distribution` | Noise distribution diagnostics |
| `debug_generation_stats` | Extended generation diagnostics |
| `debug_noise_distribution` | Noise distribution debug output |
| `get_atmospheric_state` | Atmosphere state for the active body |
| `get_tick_status` | Current tick status |
| `advance_simulation_tick` | Step the simulation forward one tick |
| `open_server_region` | Open a region on the dedicated server (without Unity) |
| `set_projection` | Change projection override + water level without full reset |
| `diagnose_hydrology_mismatch` | Spot hydrology classification drift |
| `run_full_validation_suite` | Full validation across all systems |
| `run_generation_quality_suite` | Generation quality checks |
| `run_body_tile_checks` | Tile integrity checks for a body |
| `compare_generation_profiles` | Diff two generation profiles |
| `compare_presets` | Diff two preset outputs |
| `run_preset_smoke_test` | Run the smoke test for a single preset |

## Available Presets

| Preset | Coherence override | Water level | Atmosphere |
|--------|-------------------|------------|------------|
| `Coast` | Coast (4) | 0.71 | 0.70 |
| `Ocean` | Ocean (1) | 0.85 | 0.65 |
| `Arid` | Arid (2) | 0.03 | 0.12 |
| `Frozen` | Frozen (3) | 0.35 | 0.30 |
| `Basin` | Basin (5) | 0.18 | 0.45 |

`set_projection` uses the same enum: `None_=0, Ocean=1, Arid=2, Frozen=3, Coast=4, Basin=5`.

## Three Canonical Debug Loops

### Loop 1 — Projection bug

**Symptoms**: wrong biome distribution, water coverage off, tile color mismatch on planet view.

```
1. get_view_state                                   ← confirm starting state
2. launch_preset(preset_name="Coast")               ← or whichever preset
3. get_projection_summary                           ← check OpenOcean / Coast / InlandWater / Dry / FrozenWater
4. get_console_errors(minimum_severity="Warning")   ← look for generation warnings
5. take_screenshot(file_name="projection_coast")    ← capture visual
```

**Key metrics to verify** (`get_projection_summary`):
- `openOceanCells`, `coastCells`, `inlandWaterCells`, `dryCells`, `frozenWaterCells`
- Distributions should match the coherence archetype of the preset

**Reference scripts**: `PlanetaryHexGrid`, `PlanetSphere`, `PlanetTextureGenerator`, `MapRegion`

---

### Loop 2 — Hydrology / local region bug

**Symptoms**: wrong cell water type in local view, river/lake logic broken, biome mismatch, HUD cell values inconsistent.

```
1. launch_preset(preset_name="Basin")               ← or whichever preset
2. open_region(latitude=0.57, longitude=0.58)       ← representative coordinates
3. get_local_summary                                ← terrain, hydrology, biome stats + selected cell
4. get_console_errors(minimum_severity="Warning")
5. take_screenshot(file_name="local_basin")
```

**Diagnostic escalation**: if `get_local_summary` is insufficient → call `diagnose_hydrology_mismatch`

**Reference scripts**: `WaterSystem`, `HydrologySystem`, `WaterClassificationSystem`, `RiverSystem`, `BiomeSystem`

---

### Loop 3 — View flow bug

**Symptoms**: ESC / F9 / F10 transitions broken, state lost between views, override or water level not preserved.

```
1. get_view_state                                   ← baseline
2. launch_preset(preset_name="Ocean")
3. get_view_state                                   ← confirm Planet view active
4. open_region(latitude=0.50, longitude=0.50)
5. get_view_state                                   ← confirm Local view active
6. [manual ESC in Unity]
7. get_view_state                                   ← confirm return to Planet view
```

**Reference scripts**: `ViewManager`, `TestLaunchMenu`, `DebugHydrologyPanel`, `TerraformHUD`

---

## Mandatory Artifacts

Collect and retain these for every debug session:

1. `get_view_state` — before and after any significant transition
2. `get_projection_summary` or `get_projection_state`
3. `get_local_summary` or `get_region_state` (if a region was opened)
4. `get_console_errors`
5. `take_screenshot` (if visual rendering is part of the diagnosis)

## Advanced Diagnostics

For deeper investigation after the canonical loops:

| Goal | Tool |
|------|------|
| Hydrology classification drift | `diagnose_hydrology_mismatch` |
| Full system validation pass | `run_full_validation_suite` |
| Generation quality regression | `run_generation_quality_suite` |
| Tile integrity check | `run_body_tile_checks` |
| Before/after code change comparison | `compare_generation_profiles` or `compare_presets` |
| Noise distribution anomaly | `debug_noise_distribution` / `get_generation_noise_distribution` |
| Change projection without reset | `set_projection(projection_override=4, water_level=0.71)` |
| Step tick manually | `advance_simulation_tick` |
| Atmosphere state | `get_atmospheric_state` |

## Debug Protocol Rules (from AI_DEBUG_WORKFLOW.md)

1. **One clear question per session** — "what is the OpenOcean % for Coast preset?" not "make it look better"
2. **Read state before acting** — always `get_view_state` first if Unity is in Play Mode
3. **One functional zone at a time** — do not modify multiple subsystems in a single session
4. **Validate after change** — re-run the relevant debug loop after any code modification
5. **Simulation-server tools first** when Unity is not in Play Mode — they are always available and authoritative for data
