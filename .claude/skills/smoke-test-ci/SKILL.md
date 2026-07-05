---
name: smoke-test-ci
description: 'Use when validating generation quality after a code change, running the smoke test pipeline, comparing a candidate build to the baseline, or updating the smoke baseline. Trigger words: smoke test, regression, generation quality, baseline, compare runs, thresholds, generation-smoke.json, Invoke-DedicatedServerGenerationSmoke, compare_generation_runs, CI, generation regression, coastal cells, ocean distribution, preset validation.'
argument-hint: 'Describe the validation context: e.g. "validate after modifying CoherenceValidationSystem", "run smoke on current build and compare to baseline", "update baseline after intentional change"'
---

# Smoke Test CI — Generation Quality Validation

## When to Use

- After any change to `SimulationCore/terraformation_sim/logic.py` or `logic/`
- After changing generation parameters, coherence overrides, or water level thresholds
- After modifying `CoherenceValidationSystem`, `WaterSystem`, or `HydrologySystem` (C# side)
- Before merging a change that touches map generation
- To confirm a candidate build does not drift from the versioned baseline

## Files

| File | Role |
|------|------|
| `Tools/Invoke-DedicatedServerGenerationSmoke.ps1` | Run smoke against local server; produces `generation-smoke.json` |
| `Tools/Test-GenerationQuality.ps1` | Inner quality suite script (called by above) |
| `DedicatedServer/app/compare_generation_runs.py` | Diff two smoke runs; checks violation against thresholds |
| `DedicatedServer/config/generation-smoke-baseline.v8.json` | **Versioned baseline** — do not overwrite without validation |
| `DedicatedServer/config/generation-smoke-thresholds.v8.json` | Allowed delta per field per preset |
| `Artifacts/ci/generation-smoke.json` | Current run output (local) |
| `Artifacts/ci/generation-smoke.compare.local.json` | Comparison output (local) |

## Pipeline — 4 Steps

### Step 1 — Rebuild and run smoke

```powershell
# Option A — PowerShell (local dev)
.\Tools\Invoke-DedicatedServerGenerationSmoke.ps1 -BaseUrl http://127.0.0.1:8080

# Option B — Docker profile (no PowerShell dependency)
docker compose --profile smoke run --rm terraformation-generation-smoke > Artifacts/ci/generation-smoke.json
```

Output: `Artifacts/ci/generation-smoke.json`

The smoke script automatically rebuilds the dedicated server container unless `-SkipBuild` is passed.

### Step 2 — Compare to baseline

```powershell
python DedicatedServer/app/compare_generation_runs.py `
    DedicatedServer/config/generation-smoke-baseline.v8.json `
    Artifacts/ci/generation-smoke.json `
    --thresholds DedicatedServer/config/generation-smoke-thresholds.v8.json `
    --output Artifacts/ci/generation-smoke.compare.local.json
```

Also available as a VS Code task: `terraformation: compare smoke runs`

### Step 3 — Read the comparison report

The output JSON has:
- `"passed": true/false` — overall result
- `"violations": []` — list of fields that exceeded their threshold
- `"deltas": []` — all field deltas (baseline → candidate)

A passing run looks like: `"passed": true, "violations": []`

A failing run shows:
```json
{
  "preset": "Coast",
  "field": "coastPct",
  "baseline": 34.8,
  "candidate": 28.1,
  "delta": -6.7,
  "allowedAbsDelta": 5.0,
  "withinThreshold": false
}
```

### Step 4 — Interpret violations

| Field violated | Likely cause |
|---------------|-------------|
| `coastPct` | CoherenceValidationSystem, water level threshold change |
| `openOceanPct` | Ocean coherence override, water ratio logic |
| `frozenPct` | Temperature computation, Frozen coherence |
| `basinPct` | Hydrology connectivity, basin detection |
| `temperatureAvg` | Stellar/atmospheric chain (equilibrium temp) |
| `dryPct` | Arid coherence or classification threshold |

After diagnosing → fix the code → rerun from Step 1.

## Thresholds Reference

From `generation-smoke-thresholds.v8.json`:

| Field | Default max delta | Coast | Ocean | Frozen | Basin |
|-------|-------------------|-------|-------|--------|-------|
| `coastPct` | ±4.0% | ±5.0% | — | — | ±4.0% |
| `openOceanPct` | ±3.5% | ±5.0% | ±4.5% | — | — |
| `frozenPct` | ±3.5% | — | — | ±5.0% | — |
| `temperatureAvg` | ±2.0°C | — | — | ±3.0°C | — |
| `basinPct` | ±3.0% | — | — | — | ±4.0% |
| `inlandPct` | ±3.0% | — | — | — | ±4.0% |
| `dryPct` | ±2.5% | — | — | — | — |
| `habitablePct` | ±2.5% | — | — | — | — |

## CI Workflow (GitHub Actions)

The workflow `.github/workflows/generation-smoke.yml` runs automatically on push to `main`:
1. Builds the Docker stack
2. Runs `docker compose --profile smoke` → `Artifacts/ci/generation-smoke.json`
3. Compares with `generation-smoke-baseline.v8.json` using thresholds
4. Fails the job if violations exist
5. Uploads artifacts (smoke JSON, diff JSON, Docker logs on failure)

## Updating the Baseline

**Only update the baseline when the change is intentional and validated.**

```powershell
# After confirming the new output is correct:
Copy-Item Artifacts/ci/generation-smoke.json `
    DedicatedServer/config/generation-smoke-baseline.v8.json
```

Then commit `generation-smoke-baseline.v8.json` with a message explaining the intentional change.

**Never update the baseline to silence a failing smoke test without understanding the regression.**

## MCP Alternative (without rebuilding)

If the dedicated server is already running, use MCP tools instead of the full pipeline for a faster check:

```
run_generation_quality_suite      ← equivalent to Test-GenerationQuality.ps1
compare_generation_profiles       ← diff two profiles without a file
run_preset_smoke_test(preset_name="Coast")  ← single preset check
```

These tools do not require Unity and talk directly to the DedicatedServer.
