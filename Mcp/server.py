"""
Terraformation Debug — FastMCP server
Wraps the Unity RuntimeDebugHttpServer (HTTP bridge on port 48621).

Transport:
  - stdio (default, Phase 0)        : MCP_TRANSPORT=stdio  (or unset)
  - HTTP  (Docker, Phase 2)         : MCP_TRANSPORT=http   MCP_PORT=8000
"""

import os
import time
import urllib.parse
from datetime import datetime

import httpx
from fastmcp import FastMCP

GAME_BRIDGE_URL: str = os.environ.get("GAME_BRIDGE_URL", "http://127.0.0.1:48621")
SIMULATION_SERVER_URL: str = os.environ.get("SIMULATION_SERVER_URL", "http://host.docker.internal:8080")

# Windows HttpListener validates the Host header against its registered prefix.
# When requests come from Docker via host.docker.internal, the Host header
# won't match the 127.0.0.1 prefix and HTTP.sys returns 400 before Unity sees it.
# Force Host to match the actual registered prefix.
_parsed_bridge = urllib.parse.urlparse(GAME_BRIDGE_URL)
_BRIDGE_HOST_HEADER = f"127.0.0.1:{_parsed_bridge.port}"
MCP_TRANSPORT: str = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_PORT: int = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP("terraformation-debug")


def _get(path: str, **params) -> dict:
    with httpx.Client(timeout=10) as client:
        response = client.get(
            f"{GAME_BRIDGE_URL}{path}",
            params=params or None,
            headers={"Host": _BRIDGE_HOST_HEADER},
        )
        response.raise_for_status()
        return response.json()


def _server_get(path: str, **params) -> dict:
    with httpx.Client(timeout=10) as client:
        response = client.get(f"{SIMULATION_SERVER_URL}{path}", params=params or None)
        response.raise_for_status()
        return response.json()


def _server_post(path: str, **params) -> dict:
    with httpx.Client(timeout=10) as client:
        response = client.post(f"{SIMULATION_SERVER_URL}{path}", params=params or None)
        response.raise_for_status()
        return response.json()


@mcp.tool
def get_view_state() -> dict:
    """
    Get the current Unity view state.
    Returns active view level (SolarSystem / Planet / Local), active planet name,
    current region coordinates, selected hex cell, and terraformation progress.

    NOTE — debug-client only.
    Requires Unity to be running in Play Mode (bridge on port 48621).
    The DedicatedServer has no knowledge of which view Unity is displaying;
    this tool can never be migrated to the simulation server.
    """
    return _get("/debug/state")


@mcp.tool
def get_projection_summary() -> dict:
    """
    Get the planetary projection summary.
    Returns the Mercator hex grid statistics, biome distribution and water coverage
    for the currently active planet.
    """
    return _server_get("/projection")


@mcp.tool
def get_projection_state() -> dict:
    """
    Get the structured projection snapshot contract.
    Returns ProjectionState, which is intended to stay compatible with the future
    dedicated simulation host API.
    """
    return _server_get("/projection")


@mcp.tool
def get_local_summary() -> dict:
    """
    Get the local hex region summary.
    Returns terrain, hydrology, biome stats and selected cell details for the
    currently loaded local region.
    """
    return _server_get("/region")


@mcp.tool
def get_region_state() -> dict:
    """
    Get the structured region snapshot contract.
    Returns RegionState, which is intended to stay compatible with the future
    dedicated simulation host API.
    """
    return _server_get("/region")


@mcp.tool
def get_world_state() -> dict:
    """
    Get the structured world snapshot contract.
    Returns WorldState built from the current Unity runtime.
    """
    return _server_get("/world")


@mcp.tool
def get_client_snapshot() -> dict:
    """
    Get the structured client snapshot contract.
    Returns ClientSnapshot for the current Unity runtime.
    """
    return _server_get("/world")


@mcp.tool
def get_last_simulation_event() -> dict:
    """
    Get the last server-side simulation event emitted by the dedicated runtime.
    Useful to inspect tick advancement, region loading, and command effects.
    """
    return _server_get("/events/last")


@mcp.tool
def get_server_action_definitions() -> dict:
    """
    Get the authoritative terraformation action definitions from the dedicated runtime.
    Returns duration and modifier metadata that should progressively replace duplicated
    client-side action configuration.
    """
    return {"actions": _server_get("/actions/definitions")}


@mcp.tool
def advance_simulation_tick(steps: int = 1) -> dict:
    """
    Advance the dedicated simulation runtime by one or more ticks.

    Args:
        steps: Number of ticks to advance.
    """
    return _server_post("/tick/advance", steps=steps)


@mcp.tool
def open_server_region(latitude: float, longitude: float) -> dict:
    """
    Open a region on the dedicated simulation runtime.

    Args:
        latitude: Normalized latitude in [0, 1].
        longitude: Normalized longitude in [0, 1].
    """
    return _server_post("/commands/open-region", latitude=latitude, longitude=longitude)


@mcp.tool
def get_atmospheric_state(latitude: float = 0.47, longitude: float = 0.18) -> dict:
    """
    Get the atmospheric state for a region (CO₂, O₂, pressure, temperature, habitability).
    Does not require Unity to be running — queries the dedicated simulation server directly.

    Args:
        latitude: Normalized latitude [0, 1].
        longitude: Normalized longitude [0, 1].
    """
    region = _server_post("/commands/open-region", latitude=latitude, longitude=longitude)
    return region.get("atmosphericState", {})


@mcp.tool
def get_generation_stats(
    coherence: int = 4,
    water_level: float = 0.71,
    seed: int = 1004,
    h3_resolution: int = 2,
    atmosphere_density: float = 0.7,
) -> dict:
    """
    Get dedicated-server generation quality metrics for one preset/profile.
    Useful for tuning projection generation without requiring Unity Play Mode.

    Args:
        coherence: DebugCoherenceOverride enum value. None_=0, Ocean=1, Arid=2, Frozen=3, Coast=4, Basin=5.
        water_level: Global water target in [0, 1].
        seed: Deterministic generation seed.
        h3_resolution: H3 resolution (0-2).
        atmosphere_density: Atmospheric retention factor in [0, 1].
    """
    return _server_get(
        "/debug/generation-stats",
        coherence=coherence,
        water_level=water_level,
        seed=seed,
        h3_resolution=h3_resolution,
        atmosphere_density=atmosphere_density,
    )


@mcp.tool
def get_generation_noise_distribution(
    seed: int = 1004,
    octave: int = 10,
    h3_resolution: int = 2,
    buckets: int = 10,
) -> dict:
    """
    Inspect the distribution of the dedicated-server H3 scatter noise.
    Use this when generation thresholds behave oddly and you need to detect a biased hash/noise distribution.

    Args:
        seed: Generation seed.
        octave: Noise octave index.
        h3_resolution: H3 resolution (0-2).
        buckets: Histogram bucket count (2-50).
    """
    return _server_get(
        "/debug/noise-distribution",
        seed=seed,
        octave=octave,
        h3_resolution=h3_resolution,
        buckets=buckets,
    )


@mcp.tool
def queue_server_terraform_action(action_type: int, q: int | None = None, r: int | None = None) -> dict:
    """
    Queue a terraformation action on the dedicated simulation runtime.

    Args:
        action_type: TerraformAction enum value. Heat=0, Irrigate=1, Plant=2, Mine=3, Detoxify=4.
        q: Optional target cell q coordinate.
        r: Optional target cell r coordinate.
    """
    params = {"action_type": action_type}
    if q is not None and r is not None:
        params["q"] = q
        params["r"] = r
    return _server_post("/commands/queue-action", **params)


@mcp.tool
def apply_server_cell_delta(water_delta: float = 0.0,
                            temperature_delta: float = 0.0,
                            q: int | None = None,
                            r: int | None = None) -> dict:
    """
    Apply a bounded direct cell state change on the dedicated simulation runtime.

    Args:
        water_delta: Additive water delta for the target cell.
        temperature_delta: Additive temperature delta for the target cell.
        q: Optional target cell q coordinate.
        r: Optional target cell r coordinate.
    """
    params = {
        "water_delta": water_delta,
        "temperature_delta": temperature_delta,
    }
    if q is not None and r is not None:
        params["q"] = q
        params["r"] = r
    return _server_post("/commands/apply-cell-delta", **params)


@mcp.tool
def get_console_errors(max_entries: int = 20, minimum_severity: str = "Warning") -> dict:
    """
    Get recent Unity console logs filtered by severity.

    Args:
        max_entries: Maximum number of entries to return (default 20, max 200).
        minimum_severity: Minimum log level to include.
            Accepted values: Log, Warning, Error, Exception (default Warning).
    """
    return _get("/debug/console", maxEntries=max_entries, minimumSeverity=minimum_severity)


@mcp.tool
def take_screenshot(file_name: str = "", super_size: int = 1) -> dict:
    """
    Capture a screenshot of the Unity game view.

    Args:
        file_name: Output filename (empty = auto-generated timestamp).
        super_size: Resolution multiplier — 1 = native, 2 = 2x, 4 = 4x.
    """
    return _get("/debug/screenshot", fileName=file_name, superSize=super_size)


@mcp.tool
def launch_preset(preset_name: str) -> dict:
    """
    Launch a named debug scenario preset in Unity.
    Loads the corresponding CelestialBodyData, applies generation parameters
    and transitions the view to the Local level.

    Args:
        preset_name: Name of the preset (e.g. 'Coast', 'Desert', 'Arctic').
    """
    return _get("/debug/launch-preset", preset=preset_name)


@mcp.tool
def open_region(latitude: float, longitude: float) -> dict:
    """
    Navigate Unity to a specific planet region.
    Both coordinates are normalized in [0, 1] (0 = North/West, 1 = South/East).

    Args:
        latitude: Normalized latitude in [0, 1].
        longitude: Normalized longitude in [0, 1].
    """
    return _get("/debug/open-region", lat=latitude, lon=longitude)


# ---------------------------------------------------------------------------
# Helpers for composite tools
# ---------------------------------------------------------------------------

_PRESET_COORDINATES: dict[str, dict[str, float]] = {
    "ocean":  {"lat": 0.50, "lon": 0.50},
    "arid":   {"lat": 0.52, "lon": 0.52},
    "frozen": {"lat": 0.20, "lon": 0.50},
    "coast":  {"lat": 0.47, "lon": 0.18},
    "basin":  {"lat": 0.57, "lon": 0.58},
}

_GENERATION_PROFILES: dict[str, dict[str, float | int]] = {
    "Coast":  {"coherence": 4, "water_level": 0.71, "atmosphere_density": 0.70, "seed": 1004},
    "Ocean":  {"coherence": 1, "water_level": 0.85, "atmosphere_density": 0.65, "seed": 1011},
    "Arid":   {"coherence": 2, "water_level": 0.03, "atmosphere_density": 0.12, "seed": 1021},
    "Frozen": {"coherence": 3, "water_level": 0.35, "atmosphere_density": 0.30, "seed": 1031},
    "Basin":  {"coherence": 5, "water_level": 0.18, "atmosphere_density": 0.45, "seed": 1041},
}

_SMOKE_COMPARE_FIELDS_PROJ  = ["openOceanCells", "coastCells", "inlandWaterCells",
                                "frozenWaterCells", "dryCells",
                                "averageWaterRatio", "averageTemperature"]
_SMOKE_COMPARE_FIELDS_LOCAL = ["openOceanCells", "coastCells", "inlandWaterCells",
                                "frozenWaterCells", "dryCells", "basinCells",
                                "averageWaterRatio", "averageTemperature"]


def _build_smoke_projection_summary(gen_stats: dict) -> dict:
    """Convert generation-stats response to the projection summary shape used by _validate_smoke."""
    if "error" in gen_stats:
        return {"isValid": False, "error": gen_stats["error"], "summary": {}}
    water = gen_stats.get("water_classification", {})
    total = int(gen_stats.get("total_tiles", 0))

    def _cells(key: str) -> int:
        entry = water.get(key, {})
        return int(entry.get("count", 0)) if isinstance(entry, dict) else 0

    temp = gen_stats.get("temperature", {})
    water_ratio = gen_stats.get("water_ratio", {})
    summary = {
        "totalCells": total,
        "openOceanCells":    _cells("OpenOcean"),
        "coastCells":        _cells("Coast"),
        "inlandWaterCells":  _cells("InlandWater"),
        "frozenWaterCells":  _cells("FrozenWater"),
        "dryCells":          _cells("Dry"),
        "averageWaterRatio": float(water_ratio.get("avg", 0.0) if isinstance(water_ratio, dict) else 0.0),
        "averageTemperature": float(temp.get("avg", 0.0) if isinstance(temp, dict) else 0.0),
    }
    return {
        "isValid": True,
        "source": "generation-stats",
        "summary": summary,
    }


def _safe_get(path: str, **params) -> dict:
    try:
        return _get(path, **params)
    except Exception as exc:
        return {"error": str(exc), "success": False}


def _safe_server_get(path: str, **params) -> dict:
    try:
        return _server_get(path, **params)
    except Exception as exc:
        return {"error": str(exc), "success": False}


def _metric_pct(stats_map: dict, key: str) -> float:
    entry = stats_map.get(key, {}) if isinstance(stats_map, dict) else {}
    value = entry.get("pct", 0.0) if isinstance(entry, dict) else 0.0
    return float(value or 0.0)


def _build_generation_quality_row(preset_name: str, stats: dict) -> dict:
    terrain = stats.get("terrain", {})
    water = stats.get("water_classification", {})
    terrain_class = stats.get("terrain_class", {})
    quality = stats.get("quality", {})
    temperature = stats.get("temperature", {})
    params = stats.get("params", {})

    return {
        "preset": preset_name,
        "seed": params.get("seed"),
        "atmosphereDensity": params.get("atmosphere_density"),
        "waterLevel": params.get("water_level"),
        "dryPct": float(quality.get("dry_pct", 0.0)),
        "humidPct": float(quality.get("humid_pct", 0.0)),
        "saturatedPct": float(quality.get("saturated_pct", 0.0)),
        "habitablePct": float(quality.get("habitable_pct", 0.0)),
        "coldPct": float(quality.get("cold_pct", 0.0)),
        "hotPct": float(quality.get("hot_pct", 0.0)),
        "vegetationPct": _metric_pct(terrain, "Vegetation"),
        "openOceanPct": _metric_pct(water, "OpenOcean"),
        "frozenPct": _metric_pct(water, "FrozenWater"),
        "coastPct": _metric_pct(water, "Coast"),
        "inlandPct": _metric_pct(water, "InlandWater"),
        "basinPct": _metric_pct(terrain_class, "Basin"),
        "temperatureAvg": float(temperature.get("avg", 0.0)),
    }


def _append_generation_check(checks: list[dict], preset: str, name: str,
                             passed: bool, message: str) -> None:
    checks.append({
        "preset": preset,
        "check": name,
        "passed": passed,
        "message": message,
    })


def _evaluate_generation_quality(results: list[dict]) -> dict:
    checks: list[dict] = []
    for row in results:
        preset = row["preset"]
        if preset == "Coast":
            _append_generation_check(
                checks, preset, "coast-band-present", row["coastPct"] >= 5.0,
                f"Coast should keep at least 5% coastal tiles, got {row['coastPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "vegetation-present", row["vegetationPct"] >= 5.0,
                f"Coast should keep at least 5% vegetation, got {row['vegetationPct']:.1f}%.")
        elif preset == "Ocean":
            _append_generation_check(
                checks, preset, "ocean-dominant", row["openOceanPct"] >= 45.0,
                f"Ocean should have at least 45% open ocean, got {row['openOceanPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "not-overdry", row["dryPct"] <= 25.0,
                f"Ocean should not be dry above 25%, got {row['dryPct']:.1f}%.")
        elif preset == "Arid":
            _append_generation_check(
                checks, preset, "dry-dominant", row["dryPct"] >= 60.0,
                f"Arid should have at least 60% dry tiles, got {row['dryPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "limited-vegetation", row["vegetationPct"] <= 15.0,
                f"Arid should keep vegetation under 15%, got {row['vegetationPct']:.1f}%.")
        elif preset == "Frozen":
            _append_generation_check(
                checks, preset, "cold-dominant", row["coldPct"] >= 40.0,
                f"Frozen should have at least 40% cold tiles, got {row['coldPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "ice-present", row["frozenPct"] >= 5.0,
                f"Frozen should have at least 5% frozen water, got {row['frozenPct']:.1f}%.")
        elif preset == "Basin":
            _append_generation_check(
                checks, preset, "inland-water-present", row["inlandPct"] >= 5.0,
                f"Basin should have at least 5% inland water, got {row['inlandPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "basin-shapes-present", row["basinPct"] >= 9.5,
                f"Basin should keep at least 9.5% terrainClass Basin, got {row['basinPct']:.1f}%.")

    failures = [check for check in checks if not check["passed"]]
    return {"passed": len(failures) == 0, "checks": checks, "failures": failures}


def _run_smoke_sequence(preset_name: str, lat: float, lon: float,
                        capture_screenshot: bool) -> dict:
    """Execute the standard smoke sequence for one preset and return raw data."""
    data: dict = {
        "preset": preset_name,
        "latitude": lat,
        "longitude": lon,
        "ranAt": datetime.now().isoformat(timespec="seconds"),
    }
    data["stateBefore"]   = _safe_get("/debug/state")
    data["launchResult"]  = _safe_get("/debug/launch-preset", preset=preset_name)
    data["stateAfterLaunch"] = _safe_get("/debug/state")
    # Projection: use DedicatedServer generation-stats with preset-specific params.
    # The bridge /debug/projection requires the Mercator sphere to have been rendered
    # at least once (lazy-build), which doesn't happen during automated smoke tests.
    # The default /projection endpoint always returns the fixed Earth planet — not
    # useful for preset-specific checks.  generation-stats is preset-aware.
    _profile = _GENERATION_PROFILES.get(
        next((k for k in _GENERATION_PROFILES if k.lower() == preset_name.lower()), ""),
        None,
    )
    if _profile is not None:
        _gen_stats = _safe_server_get(
            "/debug/generation-stats",
            coherence=_profile["coherence"],
            water_level=_profile["water_level"],
            atmosphere_density=_profile["atmosphere_density"],
            seed=_profile["seed"],
        )
        data["projection"] = _build_smoke_projection_summary(_gen_stats)
    else:
        data["projection"] = {"isValid": False, "error": f"No profile for preset '{preset_name}'"}
    data["openRegion"]    = _safe_get("/debug/open-region", lat=lat, lon=lon)
    # Use the Unity bridge for local data — the DedicatedServer /region returns
    # a fixed default region that is not updated when a preset is launched in Unity.
    _bridge_local = _safe_get("/debug/local")
    # Remap bridge response shape (gridSummary) to the expected shape (summary)
    # so _validate_smoke field access stays consistent.
    if "gridSummary" in _bridge_local and "summary" not in _bridge_local:
        _bridge_local["summary"] = _bridge_local.pop("gridSummary")
    data["local"]         = _bridge_local
    data["console"]       = _safe_get("/debug/console",
                                      maxEntries=20, minimumSeverity="Warning")
    if capture_screenshot:
        name = f"{preset_name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        data["screenshot"] = _safe_get("/debug/screenshot", fileName=name)
    return data


def _validate_smoke(preset_name: str, data: dict) -> dict:
    """Port of PowerShell Test-SmokeResults.  Uses DedicatedServer summary field names."""
    checks: list[dict] = []

    def chk(name: str, passed: bool, message: str, severity: str = "error") -> None:
        checks.append({"name": name, "passed": passed,
                        "message": message, "severity": severity})

    chk("state-before-response",
        data.get("stateBefore") is not None and "error" not in data.get("stateBefore", {}),
        "State endpoint must respond before launch.")

    launch = data.get("launchResult", {})
    chk("launch-preset-success", launch.get("success") is True,
        "Preset must launch successfully.")

    projection = data.get("projection", {})
    chk("projection-valid", projection.get("isValid") is True,
        "Projection must return valid data.")
    proj_s = projection.get("summary", {})
    chk("projection-has-summary", bool(proj_s),
        "Projection must include a summary.")

    local = data.get("local", {})
    chk("local-valid", local.get("isValid") is True,
        "Local region must return valid data.")
    local_s = local.get("summary", {})
    chk("local-has-summary", bool(local_s),
        "Local region must include a summary.")

    console = data.get("console", {})
    chk("console-no-errors",
        console.get("errorCount", 0) == 0 and console.get("exceptionCount", 0) == 0,
        "Console must not contain errors or exceptions.")
    chk("console-no-warnings", console.get("warningCount", 0) == 0,
        "Console should not contain warnings.", severity="warning")

    name_lower = preset_name.lower()
    if name_lower == "coast":
        chk("projection-coast-cells", proj_s.get("coastCells", 0) > 0,
            "Coast preset must produce coast cells in projection.")
        chk("local-coast-cells", local_s.get("coastCells", 0) > 0,
            "Coast preset must produce coast cells locally.")
    elif name_lower == "basin":
        chk("projection-inland-water", proj_s.get("inlandWaterCells", 0) > 0,
            "Basin preset must produce inland water in projection.")
        chk("local-basin-or-water",
            local_s.get("basinCells", 0) > 0 or local_s.get("inlandWaterCells", 0) > 0,
            "Basin preset must produce basins or inland water locally.")
    elif name_lower == "ocean":
        chk("projection-ocean-dominant",
            proj_s.get("openOceanCells", 0) > proj_s.get("dryCells", 0),
            "Ocean preset must be dominated by ocean in projection.")
        chk("local-water-dominant", local_s.get("averageWaterRatio", 0.0) >= 0.45,
            "Ocean preset must maintain high water ratio locally (≥0.45).")
    elif name_lower == "arid":
        chk("projection-dry-dominant",
            proj_s.get("dryCells", 0) > (proj_s.get("openOceanCells", 0)
                                         + proj_s.get("inlandWaterCells", 0)),
            "Arid preset must be mostly dry in projection.")
        chk("local-dry-dominant",
            local_s.get("dryCells", 0) > (local_s.get("openOceanCells", 0)
                                           + local_s.get("inlandWaterCells", 0)
                                           + local_s.get("coastCells", 0)),
            "Arid preset must remain mostly dry locally.")
    elif name_lower == "frozen":
        chk("projection-frozen-cells", proj_s.get("frozenWaterCells", 0) > 0,
            "Frozen preset must produce frozen water in projection.")
        chk("local-frozen-or-cold",
            local_s.get("frozenWaterCells", 0) > 0
            or local_s.get("averageTemperature", 99.0) <= 0.0,
            "Frozen preset must produce frozen water or average temperature ≤ 0 locally.")

    failures = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    warnings  = [c for c in checks if not c["passed"] and c["severity"] == "warning"]
    return {"passed": len(failures) == 0,
            "failures": failures, "warnings": warnings, "checks": checks}


# ---------------------------------------------------------------------------
# Composite tools — Sprint 0 migration
# ---------------------------------------------------------------------------

@mcp.tool
def run_preset_smoke_test(preset_name: str, capture_screenshot: bool = False) -> dict:
    """
    Run a full smoke test sequence for a named preset.

    Executes: launch_preset → get_projection → open_region → get_local_summary →
    get_console_errors, then validates the results against per-preset criteria
    (port of Invoke-TerraformationDebugSmokeTest.ps1).

    Args:
        preset_name: Preset name — 'Ocean', 'Arid', 'Frozen', 'Coast', or 'Basin'.
        capture_screenshot: Whether to capture a Unity screenshot at the end.

    Returns:
        dict with keys: preset, ranAt, stateBefore, launchResult, projection, openRegion,
        local, console, (screenshot?), verdict { passed, failures, warnings, checks }.
    """
    coords = _PRESET_COORDINATES.get(preset_name.lower(), {"lat": 0.50, "lon": 0.50})
    data = _run_smoke_sequence(preset_name, coords["lat"], coords["lon"],
                               capture_screenshot)
    data["verdict"] = _validate_smoke(preset_name, data)
    return data


@mcp.tool
def run_generation_quality_suite(h3_resolution: int = 2) -> dict:
    """
    Run the dedicated-server generation quality suite across the 5 reference presets.
    This is the MCP equivalent of `Tools/Test-GenerationQuality.ps1` and does not require Unity.

    Args:
        h3_resolution: H3 resolution to test (0-2).

    Returns:
        dict with `passed`, per-preset `results`, and structured `checks` / `failures`.
    """
    results: list[dict] = []
    for preset_name, profile in _GENERATION_PROFILES.items():
        stats = _server_get(
            "/debug/generation-stats",
            coherence=profile["coherence"],
            water_level=profile["water_level"],
            atmosphere_density=profile["atmosphere_density"],
            seed=profile["seed"],
            h3_resolution=h3_resolution,
        )
        results.append(_build_generation_quality_row(preset_name, stats))

    verdict = _evaluate_generation_quality(results)
    return {
        "h3Resolution": h3_resolution,
        "profiles": _GENERATION_PROFILES,
        "results": results,
        **verdict,
    }


@mcp.tool
def compare_generation_profiles(profile_a: str, profile_b: str,
                                h3_resolution: int = 2) -> dict:
    """
    Compare two dedicated-server generation profiles without involving Unity.

    Args:
        profile_a: First profile name. One of Coast, Ocean, Arid, Frozen, Basin.
        profile_b: Second profile name. One of Coast, Ocean, Arid, Frozen, Basin.
        h3_resolution: H3 resolution to test (0-2).

    Returns:
        dict with the two profile result rows and a field-by-field delta.
    """
    key_a = next((name for name in _GENERATION_PROFILES if name.lower() == profile_a.lower()), None)
    key_b = next((name for name in _GENERATION_PROFILES if name.lower() == profile_b.lower()), None)
    if key_a is None:
        raise ValueError(f"Unknown generation profile: {profile_a}")
    if key_b is None:
        raise ValueError(f"Unknown generation profile: {profile_b}")

    def build_row(profile_name: str) -> dict:
        profile = _GENERATION_PROFILES[profile_name]
        stats = _server_get(
            "/debug/generation-stats",
            coherence=profile["coherence"],
            water_level=profile["water_level"],
            atmosphere_density=profile["atmosphere_density"],
            seed=profile["seed"],
            h3_resolution=h3_resolution,
        )
        return _build_generation_quality_row(profile_name, stats)

    row_a = build_row(key_a)
    row_b = build_row(key_b)
    fields = [
        "dryPct", "humidPct", "saturatedPct", "habitablePct",
        "coldPct", "hotPct", "vegetationPct", "openOceanPct",
        "frozenPct", "coastPct", "inlandPct", "basinPct", "temperatureAvg",
    ]

    return {
        "profiles": [key_a, key_b],
        "h3Resolution": h3_resolution,
        "resultA": row_a,
        "resultB": row_b,
        "delta": [
            {
                "field": field,
                key_a: row_a[field],
                key_b: row_b[field],
                "delta": round(float(row_b[field]) - float(row_a[field]), 3),
            }
            for field in fields
        ],
    }


@mcp.tool
def compare_presets(preset_a: str, preset_b: str) -> dict:
    """
    Run smoke sequences for two presets and compare their projection and local stats.

    Runs preset_a, then preset_b sequentially (each resets Unity state).
    Returns a field-by-field diff for projection and local summaries, plus
    individual verdicts for each preset.

    Args:
        preset_a: First preset name  ('Ocean', 'Arid', 'Frozen', 'Coast', 'Basin').
        preset_b: Second preset name ('Ocean', 'Arid', 'Frozen', 'Coast', 'Basin').
    """
    coords_a = _PRESET_COORDINATES.get(preset_a.lower(), {"lat": 0.50, "lon": 0.50})
    coords_b = _PRESET_COORDINATES.get(preset_b.lower(), {"lat": 0.50, "lon": 0.50})

    data_a = _run_smoke_sequence(preset_a, coords_a["lat"], coords_a["lon"], False)
    data_b = _run_smoke_sequence(preset_b, coords_b["lat"], coords_b["lon"], False)

    proj_a = data_a.get("projection", {}).get("summary", {})
    proj_b = data_b.get("projection", {}).get("summary", {})
    loc_a  = data_a.get("local", {}).get("summary", {})
    loc_b  = data_b.get("local", {}).get("summary", {})

    def diff_field(key: str, a: dict, b: dict) -> dict:
        va, vb = a.get(key, 0), b.get(key, 0)
        return {"field": key, preset_a: va, preset_b: vb,
                "delta": round(vb - va, 4) if isinstance(vb, float) else vb - va}

    return {
        "presets": [preset_a, preset_b],
        "projectionDiff": [diff_field(k, proj_a, proj_b)
                           for k in _SMOKE_COMPARE_FIELDS_PROJ],
        "localDiff":      [diff_field(k, loc_a, loc_b)
                           for k in _SMOKE_COMPARE_FIELDS_LOCAL],
        "verdictA": _validate_smoke(preset_a, data_a),
        "verdictB": _validate_smoke(preset_b, data_b),
    }


@mcp.tool
def diagnose_hydrology_mismatch(preset_name: str) -> dict:
    """
    Diagnose projection ↔ local hydrology mismatches for a given preset.

    Launches the preset, reads projection and local summaries, then compares
    dominant water classifications between the two to surface incoherences
    (e.g. ocean projection → dry local, frozen projection → warm local).

    Args:
        preset_name: Preset name — 'Ocean', 'Arid', 'Frozen', 'Coast', or 'Basin'.

    Returns:
        dict with projectionRatios, localRatios, mismatches list, insights list,
        and the raw coherence block from the region state.
    """
    coords = _PRESET_COORDINATES.get(preset_name.lower(), {"lat": 0.50, "lon": 0.50})

    launch     = _safe_get("/debug/launch-preset", preset=preset_name)
    projection = _safe_server_get("/projection")
    _safe_get("/debug/open-region", lat=coords["lat"], lon=coords["lon"])
    local      = _safe_server_get("/region")

    proj_s = projection.get("summary", {})
    loc_s  = local.get("summary", {})

    proj_total = max(proj_s.get("totalCells", 1), 1)
    loc_total  = max(loc_s.get("totalCells", 1), 1)

    proj_ocean_r  = proj_s.get("openOceanCells", 0) / proj_total
    proj_coast_r  = proj_s.get("coastCells",     0) / proj_total
    proj_dry_r    = proj_s.get("dryCells",        0) / proj_total
    proj_frozen_r = proj_s.get("frozenWaterCells",0) / proj_total

    loc_ocean_r   = loc_s.get("openOceanCells",  0) / loc_total
    loc_coast_r   = loc_s.get("coastCells",      0) / loc_total
    loc_dry_r     = loc_s.get("dryCells",        0) / loc_total
    loc_frozen_r  = loc_s.get("frozenWaterCells",0) / loc_total
    loc_water_r   = loc_s.get("averageWaterRatio", 0.0)
    loc_temp      = loc_s.get("averageTemperature", 0.0)

    mismatches: list[str] = []
    insights:   list[str] = []

    # Ocean projection → expect high local water
    if proj_ocean_r > 0.5:
        if loc_water_r < 0.35:
            mismatches.append(
                f"Projection {proj_ocean_r:.0%} ocean but local averageWaterRatio={loc_water_r:.2f} (expected ≥0.35).")
        elif loc_dry_r > 0.5:
            mismatches.append(
                f"Projection {proj_ocean_r:.0%} ocean but local is {loc_dry_r:.0%} dry cells.")
        else:
            insights.append(
                f"Ocean projection ({proj_ocean_r:.0%}) coherent with local water ({loc_water_r:.2f}).")

    # Arid projection → expect low local water
    if proj_dry_r > 0.5:
        if loc_water_r > 0.4:
            mismatches.append(
                f"Projection {proj_dry_r:.0%} dry but local averageWaterRatio={loc_water_r:.2f} (expected ≤0.4).")
        elif (loc_ocean_r + loc_s.get("inlandWaterCells", 0) / loc_total) > 0.3:
            mismatches.append(
                f"Projection is arid but local ocean+inland water = "
                f"{loc_ocean_r + loc_s.get('inlandWaterCells',0)/loc_total:.0%}.")
        else:
            insights.append(
                f"Arid projection ({proj_dry_r:.0%} dry) coherent with local ({loc_dry_r:.0%} dry).")

    # Frozen projection → expect frozen cells or cold temp
    if proj_frozen_r > 0.1:
        if loc_frozen_r == 0 and loc_temp > 0:
            mismatches.append(
                f"Projection has {proj_frozen_r:.0%} frozen cells but local has none "
                f"and averageTemperature={loc_temp:.1f}°C > 0.")
        else:
            insights.append(
                f"Frozen projection ({proj_frozen_r:.0%}) coherent with local "
                f"(frozenCells={loc_s.get('frozenWaterCells',0)}, avgTemp={loc_temp:.1f}°C).")

    # Coast projection → expect coast cells locally
    if proj_coast_r > 0.1:
        if loc_coast_r == 0:
            mismatches.append(
                f"Projection has {proj_coast_r:.0%} coast cells but local has none.")
        else:
            insights.append(
                f"Coast projection ({proj_coast_r:.0%}) coherent with local coast ({loc_coast_r:.0%}).")

    return {
        "preset": preset_name,
        "launchSuccess": launch.get("success", False),
        "projectionRatios": {
            "ocean":  round(proj_ocean_r,  3),
            "coast":  round(proj_coast_r,  3),
            "dry":    round(proj_dry_r,    3),
            "frozen": round(proj_frozen_r, 3),
        },
        "localRatios": {
            "ocean":              round(loc_ocean_r,  3),
            "coast":              round(loc_coast_r,  3),
            "dry":                round(loc_dry_r,    3),
            "frozen":             round(loc_frozen_r, 3),
            "averageWaterRatio":  round(loc_water_r,  3),
            "averageTemperature": round(loc_temp, 1),
        },
        "mismatches": mismatches,
        "insights":   insights,
        "coherence":  local.get("coherence", {}),
    }


# ---------------------------------------------------------------------------
# Tick + projection tools
# ---------------------------------------------------------------------------

@mcp.tool
def get_tick_status() -> dict:
    """
    Get the current tick status of the simulation server.
    Lightweight alternative to get_world_state — returns only tick info.

    Returns:
        dict with keys: tickCount, tickRunning, tickIntervalSeconds.
    """
    return _server_get("/tick/status")


@mcp.tool
def set_projection(projection_override: int = 0, water_level: float = 0.08) -> dict:
    """
    Change the active planet's projection override without resetting the full world state.
    Also invalidates the tile cache so GET /bodies/{id}/tiles will regenerate with the new override.

    Args:
        projection_override: DebugCoherenceOverride enum value.
            None_=0, Ocean=1, Arid=2, Frozen=3, Coast=4, Basin=5.
        water_level: Global water level (0.0–1.0, default 0.08).

    Returns:
        Updated WorldState.
    """
    return _server_post("/commands/set-projection", projection_override=projection_override, water_level=water_level)


# ---------------------------------------------------------------------------
# Body hierarchy tools
# ---------------------------------------------------------------------------

@mcp.tool
def list_bodies() -> dict:
    """
    List all registered bodies in the simulation: planets, moons, asteroids, interior zones.
    Returns metadata only — no tiles or cells.
    """
    return {"bodies": _server_get("/bodies")}


@mcp.tool
def get_body(body_id: str) -> dict:
    """
    Get metadata for a specific body (planet, moon, asteroid or interior zone).
    Returns the body without tiles/cells; use get_body_tiles or get_interior_zone for those.

    Args:
        body_id: UUID of the body.
    """
    return _server_get(f"/bodies/{body_id}")


@mcp.tool
def get_body_tiles(body_id: str, page: int = 0, size: int = 50) -> dict:
    """
    Get a paginated list of surface tiles for a spherical body (planet, moon, asteroid).
    Tiles carry terrain type, water classification, temperature, water ratio and habitability.

    Args:
        body_id: UUID of the spherical body.
        page: Page index (0-based).
        size: Tiles per page (1–200, default 50).
    """
    return {"tiles": _server_get(f"/bodies/{body_id}/tiles", page=page, size=size)}


@mcp.tool
def get_body_tile(body_id: str, tile_id: str) -> dict:
    """
    Get a single surface tile by its H3 cell index string (e.g. "820007fffffffff").
    Also lists child zone IDs if any interior zones are accessible from this tile.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string.
    """
    return _server_get(f"/bodies/{body_id}/tiles/{tile_id}")


@mcp.tool
def get_body_tile_at(body_id: str, lat: float, lon: float) -> dict:
    """
    Return the surface tile whose H3 cell contains the given latitude/longitude.

    Args:
        body_id: UUID of the spherical body.
        lat: Latitude in degrees (-90 to 90).
        lon: Longitude in degrees (-180 to 180).
    """
    return _server_get(f"/bodies/{body_id}/tiles/at", lat=lat, lon=lon)


@mcp.tool
def get_body_tile_neighbors(body_id: str, tile_id: str) -> dict:
    """
    Return the direct H3 neighbors (up to 6) of a surface tile.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string of the center tile.
    """
    return _server_get(f"/bodies/{body_id}/tiles/{tile_id}/neighbors")


@mcp.tool
def apply_body_tile_delta(
    body_id: str,
    tile_id: str,
    water_delta: float = 0.0,
    temperature_delta: float = 0.0,
) -> dict:
    """
    Apply additive water and/or temperature deltas to a surface tile.
    water_delta and temperature_delta are clamped or bounded server-side.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string of the target tile.
        water_delta: Additive water delta (positive = add water).
        temperature_delta: Additive temperature delta in °C.
    """
    return _server_post(
        f"/bodies/{body_id}/tiles/{tile_id}/delta",
        water_delta=water_delta,
        temperature_delta=temperature_delta,
    )


@mcp.tool
def terraform_body_tile(body_id: str, tile_id: str, action_type: int) -> dict:
    """
    Apply a terraform action on a surface tile of a spherical body.
    The action modifier (Heat/Irrigate/Plant/Mine/Detoxify) is applied immediately.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string of the target tile.
        action_type: TerraformAction enum value. Heat=0, Irrigate=1, Plant=2, Mine=3, Detoxify=4.
    """
    return _server_post(f"/bodies/{body_id}/tiles/{tile_id}/action", action_type=action_type)


@mcp.tool
def list_interior_zones(body_id: str) -> dict:
    """
    List all interior zones (caves, buildings, ships…) whose parent is the given body.
    Traverses the full body registry to find children.

    Args:
        body_id: UUID of the parent spherical body.
    """
    all_bodies = _server_get("/bodies").get("bodies", _server_get("/bodies"))
    if isinstance(all_bodies, dict):
        all_bodies = all_bodies.get("bodies", [])
    zones = [b for b in all_bodies if b.get("parentId") == body_id and b.get("surfaceType") == "hex_flat"]
    return {"parentBodyId": body_id, "zones": zones}


@mcp.tool
def get_interior_zone(zone_id: str) -> dict:
    """
    Get an interior zone with all its hex cells (cave, building, ship, station…).
    Cells use the same SimulationCellState contract as RegionState.cells.

    Args:
        zone_id: UUID of the interior zone.
    """
    zone = _server_get(f"/bodies/{zone_id}")
    cells = _server_get(f"/bodies/{zone_id}/cells", page=0, size=200)
    zone["cells"] = cells
    return zone


@mcp.tool
def register_interior_zone(
    body_id: str,
    zone_type: int = 0,
    cols: int = 9,
    rows: int = 9,
    parent_tile_id: str | None = None,
    seed: int | None = None,
) -> dict:
    """
    Create an interior zone attached to a surface tile of a spherical body.
    The hex cell grid is generated immediately and stored in the runtime.

    Args:
        body_id: UUID of the parent spherical body.
        zone_type: ZoneType enum value. Cave=0, NaturalCavern=1, Building=2, Underground=3, Ship=4, Station=5.
        cols: Hex grid width (3–64).
        rows: Hex grid height (3–64).
        parent_tile_id: H3 cell index string of the entrance tile (optional).
        seed: Random seed for generation (optional, auto-generated if omitted).
    """
    params = {"zone_type": zone_type, "cols": cols, "rows": rows}
    if parent_tile_id is not None:
        params["parent_tile_id"] = parent_tile_id
    if seed is not None:
        params["seed"] = seed
    return _server_post(f"/bodies/{body_id}/zones", **params)


# ---------------------------------------------------------------------------
# Galaxy layer MCP tools
# ---------------------------------------------------------------------------

@mcp.tool
def get_galaxy_overview() -> dict:
    """
    Get a high-level summary of the galaxy: number of systems, known/hidden routes, active travels.
    """
    return _server_get("/galaxy")


@mcp.tool
def list_solar_systems() -> dict:
    """
    List all solar systems in the galaxy with their galactic coordinates (light-years) and body IDs.
    """
    return {"systems": _server_get("/galaxy/systems")}


@mcp.tool
def get_solar_system(system_id: str) -> dict:
    """
    Get details for a specific solar system including its root body and all body IDs.

    Args:
        system_id: UUID of the solar system.
    """
    return _server_get(f"/galaxy/systems/{system_id}")


@mcp.tool
def create_solar_system(
    name: str,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    description: str = "",
) -> dict:
    """
    Create a new solar system at the given galactic position in light-years.

    Args:
        name: Human-readable name (e.g. "Kepler-442").
        x: Galactic X coordinate in light-years.
        y: Galactic Y coordinate in light-years.
        z: Galactic Z coordinate in light-years.
        description: Optional lore/description.
    """
    return _server_post("/galaxy/systems", name=name, x=x, y=y, z=z, description=description)


@mcp.tool
def add_body_to_system(
    system_id: str,
    name: str,
    body_type: int = 1,
    radius_km: float = 6371.0,
    water_level: float = 0.0,
    seed: int = 0,
    parent_body_id: str | None = None,
    orbital_semi_major_axis_au: float = 1.0,
    orbital_eccentricity: float = 0.0,
    orbital_inclination_deg: float = 0.0,
    orbital_initial_phase_deg: float = 0.0,
    orbital_period_ticks: int = 365,
    spectral_type: str = "",
    is_system_root: bool = False,
) -> dict:
    """
    Add a body (star, planet, moon, gas giant…) to an existing solar system with orbital parameters.

    Args:
        system_id: UUID of the target solar system.
        name: Name of the body.
        body_type: BodyType enum. Star=0, Planet=1, Moon=2, Asteroid=3, GasGiant=4, BlackHole=5.
        radius_km: Body radius in kilometres.
        water_level: Water coverage fraction (0–1). 0=arid, 1=ocean.
        seed: Terrain generation seed.
        parent_body_id: UUID of the parent body (star for planets, planet for moons). None = system root.
        orbital_semi_major_axis_au: Orbit radius in AU.
        orbital_eccentricity: Orbit eccentricity (0=circle, <1=ellipse).
        orbital_inclination_deg: Inclination relative to ecliptic in degrees.
        orbital_initial_phase_deg: Phase angle at tick 0 in degrees.
        orbital_period_ticks: Orbital period in simulation ticks.
        spectral_type: Stellar spectral type (e.g. "G2V", "M5Ve"). Empty for non-stars.
        is_system_root: If True, designates this body as the system root (no orbital params).
    """
    params: dict = {
        "name": name,
        "body_type": body_type,
        "radius_km": radius_km,
        "water_level": water_level,
        "seed": seed,
        "orbital_semi_major_axis_au": orbital_semi_major_axis_au,
        "orbital_eccentricity": orbital_eccentricity,
        "orbital_inclination_deg": orbital_inclination_deg,
        "orbital_initial_phase_deg": orbital_initial_phase_deg,
        "orbital_period_ticks": orbital_period_ticks,
        "spectral_type": spectral_type,
        "is_system_root": is_system_root,
    }
    if parent_body_id is not None:
        params["parent_body_id"] = parent_body_id
    return _server_post(f"/galaxy/systems/{system_id}/bodies", **params)


@mcp.tool
def create_stellar_route(
    from_system_id: str,
    to_system_id: str,
    travel_time_modifier: float = 1.0,
    description: str = "",
    status: int = 0,
) -> dict:
    """
    Create a stellar route between two solar systems. Distance is auto-computed from positions.

    Args:
        from_system_id: UUID of the origin system.
        to_system_id: UUID of the destination system.
        travel_time_modifier: Multiplier applied to travel time (>1 = slower, <1 = faster).
        description: Optional narrative description of the route.
        status: RouteStatus. Hidden=0, Known=1. Default Hidden.
    """
    return _server_post(
        "/galaxy/routes",
        from_system_id=from_system_id,
        to_system_id=to_system_id,
        travel_time_modifier=travel_time_modifier,
        description=description,
        status=status,
    )


@mcp.tool
def list_stellar_routes(known_only: bool = False) -> dict:
    """
    List stellar routes. Optionally filter to only Known (revealed) routes.

    Args:
        known_only: If True, return only routes with status=Known.
    """
    return {"routes": _server_get("/galaxy/routes", known_only=known_only)}


@mcp.tool
def reveal_stellar_route(route_id: str) -> dict:
    """
    Reveal a hidden stellar route, making it available for space travel.

    Args:
        route_id: UUID of the stellar route to reveal.
    """
    return _server_post(f"/galaxy/routes/{route_id}/reveal")


@mcp.tool
def initiate_travel(
    from_system_id: str,
    to_system_id: str,
    route_id: str,
    faction_id: str = "",
) -> dict:
    """
    Start a space journey along a known stellar route. Arrival tick is computed automatically.

    Args:
        from_system_id: UUID of the departure system.
        to_system_id: UUID of the destination system.
        route_id: UUID of the stellar route to use (must be Known/revealed).
        faction_id: Optional faction identifier for the travelling party.
    """
    return _server_post(
        "/travel",
        from_system_id=from_system_id,
        to_system_id=to_system_id,
        route_id=route_id,
        faction_id=faction_id,
    )


@mcp.tool
def list_active_travels() -> dict:
    """
    List all space travels that are currently in-transit (status=InTransit).
    """
    return {"travels": _server_get("/travel")}


@mcp.tool
def get_travel_status(travel_id: str) -> dict:
    """
    Get the current status and details of a space travel.

    Args:
        travel_id: UUID of the space travel.
    """
    return _server_get(f"/travel/{travel_id}")


@mcp.tool
def cancel_travel(travel_id: str) -> dict:
    """
    Cancel an in-transit space travel. The journey is aborted immediately.

    Args:
        travel_id: UUID of the space travel to cancel.
    """
    return _server_post(f"/travel/{travel_id}/cancel")


@mcp.tool
def wipe_galaxy() -> dict:
    """
    DESTRUCTIVE — for testing and world-reset only.
    Deletes all galaxy bodies, solar systems, stellar routes and space travels,
    then re-runs the bootstrap (Sol + Alpha Terraformis, hidden route).
    Bodies belonging to the active WorldState (e.g. Astra-Prime) are preserved.
    Returns counts of deleted and recreated items.
    """
    return _server_post("/admin/wipe-galaxy")


@mcp.tool
def debug_generation_stats(
    coherence: int = 4,
    water_level: float = 0.71,
    seed: int = 1004,
    h3_resolution: int = 2,
) -> dict:
    """
    Generate planet tiles in-memory and return terrain distribution statistics.
    Never stored — pure read-only. Perfect for iterating on generation algorithms
    without needing Unity.

    Returns per-terrain-type counts and percentages, water/temperature stats.

    Args:
        coherence: DebugCoherenceOverride — None_=0, Ocean=1, Arid=2, Frozen=3, Coast=4, Basin=5.
        water_level: Sea-level threshold (0.0=all land, 1.0=all ocean). Earth≈0.71.
        seed: Random seed for tile noise.
        h3_resolution: H3 grid resolution — 0=122 tiles, 1=842 tiles, 2=5882 tiles.
    """
    return _server_get(
        "/debug/generation-stats",
        coherence=coherence,
        water_level=water_level,
        seed=seed,
        h3_resolution=h3_resolution,
    )


@mcp.tool
def debug_noise_distribution(
    seed: int = 1004,
    octave: int = 10,
    h3_resolution: int = 2,
    buckets: int = 10,
) -> dict:
    """
    Analyse the distribution of the internal _tile_noise_h3 function across all H3 cells.
    Useful to detect biases for a given seed/octave combination.
    Returns a histogram and the percentage of values below common water_level thresholds.

    Args:
        seed: Random seed.
        octave: Noise octave index (0–15).
        h3_resolution: H3 resolution — 0=122, 1=842, 2=5882 cells.
        buckets: Number of histogram bins (2–50).
    """
    return _server_get(
        "/debug/noise-distribution",
        seed=seed,
        octave=octave,
        h3_resolution=h3_resolution,
        buckets=buckets,
    )


@mcp.tool
def bootstrap_sol() -> dict:
    """
    Bootstrap the Sol solar system: 8 planets + key moons, Earth as active planet.
    Wipes all existing bodies and galaxy state first.
    Earth has waterLevel=0.71 (Coast coherence, seed=1004).
    """
    return _server_post("/commands/bootstrap-sol")


if __name__ == "__main__":
    if MCP_TRANSPORT == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=MCP_PORT)
    else:
        mcp.run()