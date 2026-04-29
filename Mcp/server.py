"""
Terraformation Debug — FastMCP server
Wraps the Unity RuntimeDebugHttpServer (HTTP bridge on port 48621).

Transport:
  - stdio (default, Phase 0)        : MCP_TRANSPORT=stdio  (or unset)
  - HTTP  (Docker, Phase 2)         : MCP_TRANSPORT=http   MCP_PORT=8000
"""

import os
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


def _server_patch(path: str, **params) -> dict:
    with httpx.Client(timeout=10) as client:
        response = client.patch(f"{SIMULATION_SERVER_URL}{path}", params=params or None)
        response.raise_for_status()
        return response.json()


def _server_delete(path: str) -> dict:
    with httpx.Client(timeout=10) as client:
        response = client.delete(f"{SIMULATION_SERVER_URL}{path}")
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
def navigate_view(target: str) -> dict:
    """
    Navigate to a different view in Unity.
    Triggers a ViewManager transition and returns the new view state.

    Requires Unity to be running in Play Mode (bridge on port 48621).
    This tool can never be migrated to the simulation server.

    Args:
        target: View to navigate to. One of:
            - "galaxy"                 — top-level galaxy map
            - "solar_system"           — solar system orbit view
            - "toggle_planet_subview"  — toggle Globe ↔ Flat while in Planet view (no-op otherwise)
    """
    return _get("/debug/navigate", target=target)


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
def get_atmospheric_state(body_id: str = "", latitude: float = 0.47, longitude: float = 0.18) -> dict:
    """
    Get the atmospheric composition and equilibrium temperature for a body or region.

    When body_id is provided, returns the full AtmosphericComposition (gas list, pressure)
    and equilibrium temperature from GET /bodies/{body_id}/atmosphere.
    When body_id is empty, falls back to the legacy region-level AtmosphericState
    (CO₂, O₂, pressure, temperature, habitability) by opening the region at lat/lon.

    Args:
        body_id: UUID of the spherical body. Empty string = legacy region mode.
        latitude: Normalized latitude [0, 1] (used only in legacy mode).
        longitude: Normalized longitude [0, 1] (used only in legacy mode).
    """
    if body_id:
        return _server_get(f"/bodies/{body_id}/atmosphere")
    # Legacy: open region and return atmosphericState
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


# ---------------------------------------------------------------------------
# Sprint MCP-1 — Region cell inspection, hydrology, validation
# ---------------------------------------------------------------------------

@mcp.tool
def get_cell_detail(q: int, r: int) -> dict:
    """
    Get the full state of a specific hex cell in the active region by axial coordinates.
    Returns waterRatio, temperature, waterClassification, terrainType, terrainClass,
    flowAccumulation, isHabitable and all other SimulationCellState fields.

    Requires an active region (call open_server_region first).

    Args:
        q: Axial q coordinate of the cell.
        r: Axial r coordinate of the cell.
    """
    return _server_get("/debug/cell", q=q, r=r)


@mcp.tool
def get_hydrology_stats() -> dict:
    """
    Get hydrology distribution statistics for the current active region.
    Returns percentages per water classification (ocean, coast, inland, frozen, dry)
    and terrain class breakdown (basin, ridge, channel, source cells).

    Requires an active region (call open_server_region first).
    """
    return _server_get("/debug/hydrology")


@mcp.tool
def run_validation() -> dict:
    """
    Validate the coherence of the active region cells without opening Unity.
    Flags cells where waterClassification contradicts waterRatio or temperature:
    - OpenOcean but waterRatio < 0.60
    - FrozenWater but temperature > 0°C
    - Dry but waterRatio > 0.40

    Returns: passed (bool), issueCount, and a list of flagged cells with their rule name.

    Requires an active region (call open_server_region first).
    """
    return _server_get("/debug/validate")


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

_GENERATION_PROFILES: dict[str, dict[str, float | int]] = {
    "Coast":  {"coherence": 4, "water_level": 0.71, "atmosphere_density": 0.70, "seed": 1004},
    "Ocean":  {"coherence": 1, "water_level": 0.85, "atmosphere_density": 0.65, "seed": 1011},
    "Arid":   {"coherence": 2, "water_level": 0.03, "atmosphere_density": 0.12, "seed": 1021},
    "Frozen": {"coherence": 3, "water_level": 0.35, "atmosphere_density": 0.30, "seed": 1031},
    "Basin":  {"coherence": 5, "water_level": 0.18, "atmosphere_density": 0.45, "seed": 1041},
}

_SMOKE_COMPARE_FIELDS_PROJ = ["openOceanCells", "coastCells", "inlandWaterCells",
                              "frozenWaterCells", "dryCells",
                              "averageWaterRatio", "averageTemperature"]
# Generation-stats fields used for compare_presets diff (H3-native, no Unity)
_SMOKE_COMPARE_FIELDS_GEN = [
    "dryPct", "humidPct", "saturatedPct", "habitablePct",
    "coldPct", "hotPct", "vegetationPct", "openOceanPct",
    "frozenPct", "coastPct", "inlandPct", "basinPct", "temperatureAvg",
]


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
            _append_generation_check(
                checks, preset, "coast-temperate", row["temperatureAvg"] >= 0.0,
                f"Coast should have average temperature ≥ 0°C, got {row['temperatureAvg']:.1f}°C.")
        elif preset == "Ocean":
            _append_generation_check(
                checks, preset, "ocean-dominant", row["openOceanPct"] >= 45.0,
                f"Ocean should have at least 45% open ocean, got {row['openOceanPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "not-overdry", row["dryPct"] <= 25.0,
                f"Ocean should not be dry above 25%, got {row['dryPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "ocean-temperate", row["temperatureAvg"] >= 5.0,
                f"Ocean should have average temperature ≥ 5°C, got {row['temperatureAvg']:.1f}°C.")
        elif preset == "Arid":
            _append_generation_check(
                checks, preset, "dry-dominant", row["dryPct"] >= 60.0,
                f"Arid should have at least 60% dry tiles, got {row['dryPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "limited-vegetation", row["vegetationPct"] <= 15.0,
                f"Arid should keep vegetation under 15%, got {row['vegetationPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "arid-not-frozen", row["coldPct"] <= 50.0,
                f"Arid should not have more than 50% cold tiles, got {row['coldPct']:.1f}%.")
        elif preset == "Frozen":
            _append_generation_check(
                checks, preset, "cold-dominant", row["coldPct"] >= 40.0,
                f"Frozen should have at least 40% cold tiles, got {row['coldPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "ice-present", row["frozenPct"] >= 5.0,
                f"Frozen should have at least 5% frozen water, got {row['frozenPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "frozen-cold", row["temperatureAvg"] <= -10.0,
                f"Frozen should have average temperature ≤ -10°C, got {row['temperatureAvg']:.1f}°C.")
        elif preset == "Basin":
            _append_generation_check(
                checks, preset, "inland-water-present", row["inlandPct"] >= 5.0,
                f"Basin should have at least 5% inland water, got {row['inlandPct']:.1f}%.")
            _append_generation_check(
                checks, preset, "basin-shapes-present", row["basinPct"] >= 9.5,
                f"Basin should keep at least 9.5% terrainClass Basin, got {row['basinPct']:.1f}%.")

    failures = [check for check in checks if not check["passed"]]
    return {"passed": len(failures) == 0, "checks": checks, "failures": failures}


def _run_smoke_sequence(preset_name: str, capture_screenshot: bool) -> dict:
    """Execute the smoke sequence for one preset (Track 2 — Unity bridge).

    Validates launch, projection coherence, and console state.
    Local hex grid data (ActiveHexGrid / PlanetaryHexGrid) is excluded — that system
    is pre-H3 and not authoritative. Projection is validated via DedicatedServer
    generation-stats which is H3-native and preset-aware.
    open-region is excluded because ShowLocalView() triggers the old HexGrid, not H3.
    """
    data: dict = {
        "preset": preset_name,
        "ranAt": datetime.now().isoformat(timespec="seconds"),
    }
    data["stateBefore"]      = _safe_get("/debug/state")
    data["launchResult"]     = _safe_get("/debug/launch-preset", preset=preset_name)
    data["stateAfterLaunch"] = _safe_get("/debug/state")

    # Projection: DedicatedServer generation-stats (H3-native, preset-aware).
    # /debug/projection bridge endpoint is excluded — requires the Mercator sphere to
    # have been rendered (lazy-build) which never happens in automated runs.
    _key = next((k for k in _GENERATION_PROFILES if k.lower() == preset_name.lower()), "")
    _profile = _GENERATION_PROFILES.get(_key)
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

    data["console"] = _safe_get("/debug/console", maxEntries=20, minimumSeverity="Warning")
    if capture_screenshot:
        name = f"{preset_name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        data["screenshot"] = _safe_get("/debug/screenshot", fileName=name)
    return data


def _validate_smoke(preset_name: str, data: dict) -> dict:
    """Validate one preset's smoke sequence against H3-native criteria (Track 2).

    Checks:
    - state-before-response: bridge responds before launch
    - launch-preset-success: preset launches cleanly in Unity
    - unity-projection-override: Unity reports the correct coherenceOverride after launch
    - projection-valid / projection-has-summary: generation-stats returns H3 data
    - projection-*: per-preset terrain distribution checks (H3, DedicatedServer)
    - console-no-errors / console-no-warnings: no Unity errors/warnings after launch
    """
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

    # Unity must update its activeProjectionOverride to match the launched preset.
    state_after = data.get("stateAfterLaunch", {})
    unity_override = state_after.get("activeProjectionOverride", "")
    chk("unity-projection-override",
        unity_override.lower() == preset_name.lower(),
        f"Unity should report '{preset_name}' override after launch, got '{unity_override}'.")

    projection = data.get("projection", {})
    chk("projection-valid", projection.get("isValid") is True,
        "Projection must return valid H3 data (source: generation-stats).")
    proj_s = projection.get("summary", {})
    chk("projection-has-summary", bool(proj_s),
        "Projection must include a non-empty summary.")

    console = data.get("console", {})
    chk("console-no-errors",
        console.get("errorCount", 0) == 0 and console.get("exceptionCount", 0) == 0,
        "Console must not contain errors or exceptions.")
    chk("console-no-warnings", console.get("warningCount", 0) == 0,
        "Console should not contain warnings.", severity="warning")

    name_lower = preset_name.lower()
    if name_lower == "coast":
        chk("projection-coast-cells", proj_s.get("coastCells", 0) > 0,
            "Coast preset must produce coast cells in H3 projection.")
    elif name_lower == "basin":
        chk("projection-inland-water", proj_s.get("inlandWaterCells", 0) > 0,
            "Basin preset must produce inland water in H3 projection.")
    elif name_lower == "ocean":
        chk("projection-ocean-dominant",
            proj_s.get("openOceanCells", 0) > proj_s.get("dryCells", 0),
            "Ocean preset must be dominated by open ocean in H3 projection.")
    elif name_lower == "arid":
        chk("projection-dry-dominant",
            proj_s.get("dryCells", 0) > (proj_s.get("openOceanCells", 0)
                                         + proj_s.get("inlandWaterCells", 0)),
            "Arid preset must be mostly dry in H3 projection.")
    elif name_lower == "frozen":
        chk("projection-frozen-cells", proj_s.get("frozenWaterCells", 0) > 0,
            "Frozen preset must produce frozen water in H3 projection.")

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
    Run a smoke test for a named preset (Track 2 — requires Unity Play Mode).

    Sequence: launch_preset → check Unity override → validate H3 projection → check console.
    open-region and local hex grid data are excluded — those rely on the pre-H3
    PlanetaryHexGrid system. Projection is validated via DedicatedServer generation-stats.

    For purely server-side H3 validation without Unity, use run_generation_quality_suite.
    For both tracks together, use run_full_validation_suite.

    Args:
        preset_name: Preset name — 'Ocean', 'Arid', 'Frozen', 'Coast', or 'Basin'.
        capture_screenshot: Whether to capture a Unity screenshot at the end.

    Returns:
        dict with keys: preset, ranAt, stateBefore, launchResult, stateAfterLaunch,
        projection, console, (screenshot?), verdict { passed, failures, warnings, checks }.
    """
    data = _run_smoke_sequence(preset_name, capture_screenshot)
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
def run_full_validation_suite(h3_resolution: int = 2,
                              capture_screenshot: bool = False) -> dict:
    """
    Run both validation tracks across all 5 reference presets.

    Track 1 — DedicatedServer (H3 pur, no Unity required):
      generation-stats quality suite, temperature checks, hydrology checks.

    Track 2 — Unity bridge (requires Play Mode on port 48621):
      launch preset → check override → validate H3 projection → check console.
      open-region and local hex grid excluded (pre-H3 PlanetaryHexGrid system).

    Args:
        h3_resolution: H3 resolution for Track 1 generation stats (0-2).
        capture_screenshot: Whether to capture a screenshot per preset in Track 2.

    Returns:
        dict with `dedicated` (Track 1 verdict), `unity` (per-preset Track 2 verdicts),
        and `combined` { passed, failureCount }.
    """
    # Track 1 — DedicatedServer, H3-native, no Unity
    dedicated = run_generation_quality_suite(h3_resolution=h3_resolution)

    # Track 2 — Unity bridge, sequential (FastMCP is single-threaded)
    unity_results: list[dict] = []
    for preset_name in _GENERATION_PROFILES:
        data = _run_smoke_sequence(preset_name, capture_screenshot)
        verdict = _validate_smoke(preset_name, data)
        unity_results.append({
            "preset": preset_name,
            "ranAt": data.get("ranAt"),
            "verdict": verdict,
        })

    all_unity_passed = all(r["verdict"]["passed"] for r in unity_results)
    combined_passed = dedicated.get("passed", False) and all_unity_passed
    total_failures = (
        len(dedicated.get("failures", []))
        + sum(len(r["verdict"]["failures"]) for r in unity_results)
    )

    return {
        "h3Resolution": h3_resolution,
        "dedicated": dedicated,
        "unity": {
            "results": unity_results,
            "passed": all_unity_passed,
        },
        "combined": {
            "passed": combined_passed,
            "failureCount": total_failures,
        },
    }


@mcp.tool
def run_body_tile_checks(body_id: str, preset_name: str) -> dict:
    """
    Sample H3 surface tiles for a body and validate dominant terrain matches a preset.

    Reads authoritative tile data from the DedicatedServer. Does not require Unity.
    Useful after bootstrap to verify that bodies in the galaxy have the correct
    terrain distribution for their configured preset.

    Args:
        body_id: UUID of the spherical body (from /bodies or list_bodies MCP tool).
        preset_name: Expected preset — 'Ocean', 'Arid', 'Frozen', 'Coast', or 'Basin'.

    Returns:
        dict with dominant water classification, histogram, per-preset checks, passed/failures.
    """
    try:
        tiles = _server_get(f"/bodies/{body_id}/tiles", page=0, size=200)
    except Exception as exc:
        return {"error": str(exc), "bodyId": body_id, "preset": preset_name}

    if not isinstance(tiles, list) or not tiles:
        return {"error": "No tiles returned", "bodyId": body_id, "preset": preset_name}

    from collections import Counter
    water_counts: Counter = Counter(
        t.get("waterClassification", "Unknown") for t in tiles
    )
    total = len(tiles)
    histogram = {
        cls: {"count": cnt, "pct": round(cnt / total * 100, 1)}
        for cls, cnt in sorted(water_counts.items(), key=lambda x: -x[1])
    }
    dominant = water_counts.most_common(1)[0][0] if water_counts else "Unknown"

    # Threshold checks per preset
    _thresholds: dict[str, tuple[str, float, str]] = {
        "ocean":  ("OpenOcean",    40.0, "OpenOcean tiles should be ≥40% for Ocean"),
        "arid":   ("Dry",          50.0, "Dry tiles should be ≥50% for Arid"),
        "frozen": ("FrozenWater",   5.0, "FrozenWater tiles should be ≥5% for Frozen"),
        "coast":  ("Coast",         5.0, "Coast tiles should be ≥5% for Coast"),
        "basin":  ("InlandWater",   5.0, "InlandWater tiles should be ≥5% for Basin"),
    }
    checks: list[dict] = []
    threshold_entry = _thresholds.get(preset_name.lower())
    if threshold_entry:
        cls_name, threshold, msg = threshold_entry
        pct = histogram.get(cls_name, {}).get("pct", 0.0)
        passed = pct >= threshold
        checks.append({
            "check": f"{preset_name.lower()}-dominant-tiles",
            "passed": passed,
            "message": f"{msg}, got {pct:.1f}%.",
        })

    failures = [c for c in checks if not c["passed"]]
    return {
        "bodyId": body_id,
        "preset": preset_name,
        "tilesSampled": total,
        "dominant": dominant,
        "histogram": histogram,
        "checks": checks,
        "passed": len(failures) == 0,
        "failures": failures,
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
    Compare two presets: H3 generation quality diff (Track 1) + Unity smoke (Track 2).

    Track 1 compares generation-stats from the DedicatedServer (no Unity required).
    Track 2 runs Unity smoke sequences sequentially and validates launch + projection.
    local hex grid data is excluded — it relied on the pre-H3 PlanetaryHexGrid system.

    Args:
        preset_a: First preset name  ('Ocean', 'Arid', 'Frozen', 'Coast', 'Basin').
        preset_b: Second preset name ('Ocean', 'Arid', 'Frozen', 'Coast', 'Basin').
    """
    # Track 1: generation quality comparison (H3, no Unity)
    gen_compare = compare_generation_profiles(preset_a, preset_b)

    # Track 2: Unity smoke sequences
    data_a = _run_smoke_sequence(preset_a, False)
    data_b = _run_smoke_sequence(preset_b, False)

    proj_a = data_a.get("projection", {}).get("summary", {})
    proj_b = data_b.get("projection", {}).get("summary", {})

    def diff_field(key: str, a: dict, b: dict) -> dict:
        va, vb = a.get(key, 0), b.get(key, 0)
        return {"field": key, preset_a: va, preset_b: vb,
                "delta": round(vb - va, 4) if isinstance(vb, float) else vb - va}

    return {
        "presets": [preset_a, preset_b],
        "generationDiff": gen_compare.get("delta", []),
        "projectionDiff": [diff_field(k, proj_a, proj_b)
                           for k in _SMOKE_COMPARE_FIELDS_PROJ],
        "verdictA": _validate_smoke(preset_a, data_a),
        "verdictB": _validate_smoke(preset_b, data_b),
    }


# ---------------------------------------------------------------------------
# Sprint MCP-2 — Region validation pipeline (server-only, no Unity needed)
# ---------------------------------------------------------------------------

@mcp.tool
def set_projection(preset_name: str) -> dict:
    """
    Set the active server projection to a named preset.
    Configures coherence override and water level so that subsequent open_server_region
    calls return cells matching the preset biome.

    This is the server-side equivalent of launching a preset in Unity.
    Does not require Unity Play Mode.

    Args:
        preset_name: One of 'Ocean', 'Arid', 'Frozen', 'Coast', 'Basin'.
    """
    key = next((k for k in _GENERATION_PROFILES if k.lower() == preset_name.lower()), None)
    if key is None:
        return {"error": f"Unknown preset '{preset_name}'. Valid: {list(_GENERATION_PROFILES)}"}
    profile = _GENERATION_PROFILES[key]
    return _server_post(
        "/commands/set-projection",
        projection_override=profile["coherence"],
        water_level=profile["water_level"],
    )


@mcp.tool
def run_region_validation_suite(latitude: float = 0.47, longitude: float = 0.18) -> dict:
    """
    Server-only region validation pipeline across all 5 reference presets.
    Does NOT require Unity Play Mode.

    For each preset:
      1. set-projection (coherence + water_level)
      2. open-region at (latitude, longitude)
      3. GET /debug/hydrology  → water distribution
      4. GET /debug/validate   → coherence checks
      5. GET /debug/cell (0,0) → sample cell detail
      6. atmospheric state from region

    Returns per-preset results + global passed/failureCount.

    Args:
        latitude:  Normalized latitude [0, 1] to sample (default 0.47 = mid-latitude).
        longitude: Normalized longitude [0, 1] to sample (default 0.18).
    """
    preset_results: list[dict] = []
    failures_total = 0

    for preset_name, profile in _GENERATION_PROFILES.items():
        row: dict = {"preset": preset_name}

        # 1. Set projection
        try:
            _server_post(
                "/commands/set-projection",
                projection_override=profile["coherence"],
                water_level=profile["water_level"],
            )
        except Exception as exc:
            row["error"] = f"set-projection failed: {exc}"
            preset_results.append(row)
            failures_total += 1
            continue

        # 2. Open region
        try:
            region = _server_post("/commands/open-region", latitude=latitude, longitude=longitude)
            row["cellCount"] = len(region.get("cells", []))
            atm = region.get("atmosphericState", {})
            row["atmosphericState"] = {
                "habitabilityScore": atm.get("habitabilityScore", 0.0),
                "o2Ratio":           atm.get("o2Ratio", 0.0),
                "pressure":          atm.get("atmosphericPressure", 0.0),
                "avgTemp":           atm.get("averageTemperature", 0.0),
            }
        except Exception as exc:
            row["error"] = f"open-region failed: {exc}"
            preset_results.append(row)
            failures_total += 1
            continue

        # 3. Hydrology
        try:
            row["hydrology"] = _server_get("/debug/hydrology")
        except Exception as exc:
            row["hydrology"] = {"error": str(exc)}

        # 4. Validation
        try:
            val = _server_get("/debug/validate")
            row["validation"] = {
                "passed":     val.get("passed", False),
                "issueCount": val.get("issueCount", 0),
                "totalCells": val.get("totalCells", 0),
                "issues":     val.get("issues", []),
            }
            if not val.get("passed", True):
                failures_total += val.get("issueCount", 0)
        except Exception as exc:
            row["validation"] = {"error": str(exc)}

        # 5. Sample cell (0, 0)
        try:
            cell = _server_get("/debug/cell", q=0, r=0)
            row["sampleCell"] = {
                "q": cell.get("address", {}).get("q", 0),
                "r": cell.get("address", {}).get("r", 0),
                "waterRatio":          round(cell.get("waterRatio", 0.0), 3),
                "temperature":         round(cell.get("temperature", 0.0), 1),
                "waterClassification": cell.get("waterClassification", "?"),
                "terrainType":         cell.get("terrainType", "?"),
            }
        except Exception:
            row["sampleCell"] = None

        preset_results.append(row)

    all_passed = all(
        r.get("validation", {}).get("passed", True)
        and "error" not in r
        for r in preset_results
    )

    return {
        "latitude":     latitude,
        "longitude":    longitude,
        "presets":      preset_results,
        "passed":       all_passed,
        "failureCount": failures_total,
    }


@mcp.tool
def diagnose_hydrology_mismatch(preset_name: str) -> dict:
    """
    Diagnose hydrology coherence for a given preset using H3 generation-stats.

    Launches the preset in Unity, then compares two generation-stats views:
    full-planet (H3 res=2, global) vs regional (H3 res=0, coarse approximation).
    Both use the preset's authoritative DedicatedServer profile.

    Note: true macro→micro comparison (global projection vs local hex tile) is
    deferred to Sprint B when local H3 tile sampling replaces the old PlanetaryHexGrid.

    Args:
        preset_name: Preset name — 'Ocean', 'Arid', 'Frozen', 'Coast', or 'Basin'.

    Returns:
        dict with projectionRatios (res=2), coarseRatios (res=0), mismatches, insights.
    """
    _key = next((k for k in _GENERATION_PROFILES if k.lower() == preset_name.lower()), "")
    _profile = _GENERATION_PROFILES.get(_key)
    if _profile is None:
        return {"error": f"No profile for preset '{preset_name}'", "preset": preset_name}

    launch = _safe_get("/debug/launch-preset", preset=preset_name)

    # Full-planet projection (H3 res=2, 5882 tiles)
    proj_stats = _safe_server_get(
        "/debug/generation-stats",
        coherence=_profile["coherence"],
        water_level=_profile["water_level"],
        atmosphere_density=_profile["atmosphere_density"],
        seed=_profile["seed"],
        h3_resolution=2,
    )
    # Coarse view (H3 res=0, 122 tiles) — approximates macro-level tile distribution
    coarse_stats = _safe_server_get(
        "/debug/generation-stats",
        coherence=_profile["coherence"],
        water_level=_profile["water_level"],
        atmosphere_density=_profile["atmosphere_density"],
        seed=_profile["seed"],
        h3_resolution=0,
    )

    def _ratios(stats: dict) -> dict:
        wc = stats.get("water_classification", {})
        total = max(stats.get("total_tiles", 1), 1)
        def _r(key: str) -> float:
            entry = wc.get(key, {})
            return int(entry.get("count", 0)) / total if isinstance(entry, dict) else 0.0
        temp = stats.get("temperature", {})
        wr   = stats.get("water_ratio", {})
        return {
            "ocean":  round(_r("OpenOcean"),    3),
            "coast":  round(_r("Coast"),         3),
            "dry":    round(_r("Dry"),           3),
            "frozen": round(_r("FrozenWater"),   3),
            "inland": round(_r("InlandWater"),   3),
            "averageWaterRatio":  round(float(wr.get("avg",  0.0) if isinstance(wr,   dict) else 0.0), 3),
            "averageTemperature": round(float(temp.get("avg",0.0) if isinstance(temp, dict) else 0.0), 1),
        }

    proj_r   = _ratios(proj_stats)
    coarse_r = _ratios(coarse_stats)

    proj_s = proj_r
    loc_s  = coarse_r

    proj_total = max(proj_s.get("totalCells", 1), 1)
    loc_total  = max(loc_s.get("totalCells", 1), 1)

    proj_ocean_r  = proj_s["ocean"]
    proj_coast_r  = proj_s["coast"]
    proj_dry_r    = proj_s["dry"]
    proj_frozen_r = proj_s["frozen"]

    loc_ocean_r  = loc_s["ocean"]
    loc_coast_r  = loc_s["coast"]
    loc_dry_r    = loc_s["dry"]
    loc_frozen_r = loc_s["frozen"]
    loc_water_r  = loc_s["averageWaterRatio"]
    loc_temp     = loc_s["averageTemperature"]

    mismatches: list[str] = []
    insights:   list[str] = []

    # Ocean projection → expect high local water
    if proj_ocean_r > 0.5:
        if loc_water_r < 0.35:
            mismatches.append(
                f"Projection {proj_ocean_r:.0%} ocean but coarse averageWaterRatio={loc_water_r:.2f} (expected ≥0.35).")
        elif loc_dry_r > 0.5:
            mismatches.append(
                f"Projection {proj_ocean_r:.0%} ocean but coarse is {loc_dry_r:.0%} dry cells.")
        else:
            insights.append(
                f"Ocean projection ({proj_ocean_r:.0%}) coherent with coarse water ({loc_water_r:.2f}).")

    # Arid projection → expect low local water
    if proj_dry_r > 0.5:
        if loc_water_r > 0.4:
            mismatches.append(
                f"Projection {proj_dry_r:.0%} dry but coarse averageWaterRatio={loc_water_r:.2f} (expected ≤0.4).")
        elif (loc_ocean_r + loc_s.get("inland", 0.0)) > 0.3:
            mismatches.append(
                f"Projection is arid but coarse ocean+inland water = "
                f"{loc_ocean_r + loc_s.get('inland', 0.0):.0%}.")
        else:
            insights.append(
                f"Arid projection ({proj_dry_r:.0%} dry) coherent with coarse ({loc_dry_r:.0%} dry).")

    # Frozen projection → expect frozen cells or cold temp
    if proj_frozen_r > 0.1:
        if loc_frozen_r == 0 and loc_temp > 0:
            mismatches.append(
                f"Projection has {proj_frozen_r:.0%} frozen cells but coarse has none "
                f"and averageTemperature={loc_temp:.1f}°C > 0.")
        else:
            insights.append(
                f"Frozen projection ({proj_frozen_r:.0%}) coherent with coarse "
                f"(frozen={loc_frozen_r:.0%}, avgTemp={loc_temp:.1f}°C).")

    # Coast projection → expect coast cells in coarse view
    if proj_coast_r > 0.1:
        if loc_coast_r == 0:
            mismatches.append(
                f"Projection has {proj_coast_r:.0%} coast cells but coarse has none.")
        else:
            insights.append(
                f"Coast projection ({proj_coast_r:.0%}) coherent with coarse coast ({loc_coast_r:.0%}).")

    return {
        "preset": preset_name,
        "launchSuccess": launch.get("success", False),
        "note": "coarseRatios uses H3 res=0 (122 tiles) as macro approximation. "
                "True local H3 comparison deferred to Sprint B.",
        "projectionRatios": proj_r,
        "coarseRatios": coarse_r,
        "mismatches": mismatches,
        "insights":   insights,
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
def get_tile_ecology(body_id: str, tile_id: str) -> dict:
    """
    Get the list of species populations on a surface tile.
    Returns species id, density (0-1), temperature/O2 tolerances, and growth rate.
    Does not require Unity. Wraps GET /bodies/{body_id}/tiles/{tile_id}/ecology.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string.
    """
    return {"species": _server_get(f"/bodies/{body_id}/tiles/{tile_id}/ecology")}


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
def patch_atmosphere(
    body_id: str,
    gas: str,
    fraction_delta: float,
) -> dict:
    """
    Apply an additive CO₂/O₂/N₂/CH₄/H₂O fraction delta to a planet's atmosphere.
    The gas must already exist in the body's gas list (use get_atmospheric_state first).
    fraction_delta is clamped server-side so the result stays in [0, 1].

    Args:
        body_id: UUID of the spherical body.
        gas: Gas name ("CO2", "O2", "N2", "H2O", "CH4", … — case-insensitive).
        fraction_delta: Signed fraction delta to apply (e.g. 0.01 adds 1 %).
    """
    return _server_patch(f"/bodies/{body_id}/atmosphere", gas=gas, fraction_delta=fraction_delta)


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
# Debug — Tile & overlay inspection tools
# ---------------------------------------------------------------------------

@mcp.tool
def get_body_tiles_lod(body_id: str, h3_resolution: int = 3, page: int = 0, size: int = 200) -> dict:
    """
    Return tiles at a given H3 resolution for LOD debug purposes.
    Same data source as FetchAndColorizeHiLod (res=3) in PlanetSphereGoldberg.
    Use to verify that the right tiles + terrain types are served before Unity renders them.
    Does not require Unity. Wraps GET /bodies/{body_id}/tiles/lod.

    Args:
        body_id: UUID of the spherical body.
        h3_resolution: H3 resolution — 0=122 tiles, 1=842, 2=5882, 3=41162.
        page: Page index (0-based, default 0).
        size: Tiles per page (1–10000, default 200).
    """
    return {"tiles": _server_get(f"/bodies/{body_id}/tiles/lod", h3_resolution=h3_resolution, page=page, size=size)}


@mcp.tool
def get_tile_state(body_id: str, tile_id: str) -> dict:
    """
    Return the State and Territory owning a specific tile, or null if unowned.
    Useful to verify state overlay correctness — matches the data FetchStateOverlay uses for borders.
    Does not require Unity. Wraps GET /bodies/{body_id}/tiles/{tile_id}/state.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string (e.g. "820007fffffffff").
    """
    return _server_get(f"/bodies/{body_id}/tiles/{tile_id}/state")


@mcp.tool
def get_body_state_tile_colors(body_id: str) -> dict:
    """
    Return the raw tile→state color mapping for a planet body.
    This is exactly the data returned to PlanetSphereGoldberg.FetchStateOverlay.
    Use to debug missing/wrong state colors on the globe without needing Unity.
    Does not require Unity. Wraps GET /game/bodies/{body_id}/state-tile-colors.

    Args:
        body_id: UUID of the spherical body.
    """
    items = _server_get(f"/game/bodies/{body_id}/state-tile-colors")
    return {
        "bodyId": body_id,
        "count": len(items) if isinstance(items, list) else 0,
        "items": items,
    }


@mcp.tool
def get_cell_detail(q: int = 0, r: int = 0) -> dict:
    """
    Get the detailed state of a local hex cell by axial coordinates.
    Returns waterRatio, temperature, waterClassification, terrainType, and biome.
    Use to validate local region generation or debug specific cells after open_server_region.
    Does not require Unity. Wraps GET /debug/cell.

    Args:
        q: Axial Q coordinate of the cell (default 0).
        r: Axial R coordinate of the cell (default 0).
    """
    return _server_get("/debug/cell", q=q, r=r)


@mcp.tool
def debug_tile_overlay(body_id: str, tile_id: str) -> dict:
    """
    Composite debug tool: returns tile data + state/territory ownership + direct neighbors in one call.
    Use when a tile looks wrong in the globe overlay (wrong color, missing border, wrong terrain).
    Does not require Unity.

    Args:
        body_id: UUID of the spherical body.
        tile_id: H3 cell index string (e.g. "820007fffffffff").
    """
    tile       = _safe_server_get(f"/bodies/{body_id}/tiles/{tile_id}")
    ownership  = _safe_server_get(f"/bodies/{body_id}/tiles/{tile_id}/state")
    neighbors_raw = _safe_server_get(f"/bodies/{body_id}/tiles/{tile_id}/neighbors")

    neighbors = []
    if isinstance(neighbors_raw, list):
        neighbors = [
            {
                "tileId":              t.get("tileId"),
                "terrainType":         t.get("terrainType"),
                "waterClassification": t.get("waterClassification"),
            }
            for t in neighbors_raw
        ]

    return {
        "bodyId": body_id,
        "tileId": tile_id,
        "tile": {
            "terrainType":         tile.get("terrainType"),
            "waterClassification": tile.get("waterClassification"),
            "waterRatio":          tile.get("waterRatio"),
            "temperature":         tile.get("temperature"),
            "isHabitable":         tile.get("isHabitable"),
        },
        "stateOwnership": {
            "state":     ownership.get("state"),
            "territory": ownership.get("territory"),
        },
        "neighbors": neighbors,
    }


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
def bootstrap() -> dict:
    """
    Bootstrap the Sol solar system: 8 planets + key moons, Earth as active planet.
    Wipes all existing bodies and galaxy state first.
    Earth has waterLevel=0.71 (Coast coherence, seed=1004).
    """
    return _server_post("/commands/bootstrap")


# ── Sprint MCP-3: Gameplay / Corporation tools ─────────────────────────────


@mcp.tool
def get_tick_state() -> dict:
    """
    Get the current simulation tick state.
    Returns tickCount, tickRunning, tickIntervalSeconds, and autoResume flag.
    Does not require Unity. Wraps GET /tick/status on the DedicatedServer.
    """
    return _server_get("/tick/status")


@mcp.tool
def get_planet_overview(body_id: str) -> dict:
    """
    Get a composite overview of a spherical body.
    Returns body metadata (type, radius, atmosphere density, equilibrium temperature)
    plus tile distribution percentages (ocean, coast, inland, frozen, dry, habitable).

    Args:
        body_id: UUID of the body (from GET /bodies or get_galaxy_overview).
    """
    body = _server_get(f"/bodies/{body_id}")
    tiles = _server_get(f"/bodies/{body_id}/tiles", page=0, size=200)

    total = len(tiles) if isinstance(tiles, list) else 0
    dist: dict[str, int] = {}
    habitable = 0
    if total > 0:
        for tile in tiles:
            wc = tile.get("waterClassification", "Dry")
            dist[wc] = dist.get(wc, 0) + 1
            if tile.get("isHabitable", False):
                habitable += 1

    def _pct(key: str) -> float:
        return round(dist.get(key, 0) / total * 100, 1) if total > 0 else 0.0

    atm = body.get("atmosphere", {})
    return {
        "bodyId": body_id,
        "name": body.get("name", ""),
        "bodyType": body.get("bodyType", ""),
        "radiusKm": body.get("radiusKm", 0.0),
        "equilibriumTemperature": body.get("equilibriumTemperature", 0.0),
        "atmospherePressureKpa": atm.get("totalPressureKpa", 0.0),
        "tileCount": total,
        "tileDistribution": {
            "openOceanPct":   _pct("OpenOcean"),
            "coastPct":       _pct("Coast"),
            "inlandWaterPct": _pct("InlandWater"),
            "frozenWaterPct": _pct("FrozenWater"),
            "dryPct":         _pct("Dry"),
            "habitablePct":   round(habitable / total * 100, 1) if total > 0 else 0.0,
        },
    }


@mcp.tool
def get_corporations_list() -> dict:
    """
    List all registered corporations.
    Returns each corporation's id, name, credits, hex count, score, and AI flag.
    """
    corps = _server_get("/game/corporations")
    return {
        "corporations": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "credits": c.get("credits"),
                "hexCount": len(c.get("claimedTiles", [])),
                "score": c.get("score"),
                "isAI": c.get("isAI"),
            }
            for c in (corps if isinstance(corps, list) else [])
        ]
    }


@mcp.tool
def get_corporation_state(corporation_id: str) -> dict:
    """
    Get the full state of a single corporation.
    Returns id, name, credits, claimedTiles, score, and isAI.

    Args:
        corporation_id: The corporation's UUID.
    """
    return _server_get(f"/game/corporations/{corporation_id}")


@mcp.tool
def create_corporation(name: str, is_ai: bool = False) -> dict:
    """
    Register a new corporation with 1 000 starting credits.
    Admin/debug operation — gameplay territory claims must go through Mirror.

    Args:
        name: Display name of the corporation.
        is_ai: True if this corporation is controlled by an AI agent.
    """
    with httpx.Client(timeout=10) as client:
        response = client.post(
            f"{SIMULATION_SERVER_URL}/game/corporations",
            json={"name": name, "is_ai": is_ai},
        )
        response.raise_for_status()
        return response.json()


@mcp.tool
def get_market_state(corp_id: str) -> dict:
    """
    Get the local market state for a corporation (prices, supply, demand per resource).
    Does not require Unity in Play Mode.

    Args:
        corp_id: The corporation ID to query.
    """
    return _server_get(f"/game/market/{corp_id}")


# ── Contract tools (Phase 7.4) ────────────────────────────────────────────────

@mcp.tool
def list_contracts(corp_id: str = "") -> dict:
    """
    List contracts. If corp_id is provided, filter to contracts involving that corporation.
    Does not require Unity in Play Mode.

    Args:
        corp_id: Optional corporation ID to filter by. Leave empty for all contracts.
    """
    url = "/game/contracts"
    if corp_id:
        url += f"?corp_id={corp_id}"
    return _server_get(url)


@mcp.tool
def list_public_contracts() -> dict:
    """
    List all open public contracts currently available for bidding.
    Does not require Unity in Play Mode.
    """
    return _server_get("/game/contracts/public")


@mcp.tool
def propose_contract(
    proposer_id: str,
    resource_type: str,
    resource_amount: float,
    reward_credits: float,
    penalty_credits: float = 0.0,
    duration_ticks: int = 0,
    visibility: str = "Private",
    target_id: str = "",
    bidding_window_ticks: int = 5,
    knowledge_bonus: float = 0.0,
) -> dict:
    """
    Propose a new resource-delivery contract.
    Does not require Unity in Play Mode.

    Args:
        proposer_id: The corporation proposing the contract.
        resource_type: Resource name (e.g. 'Food', 'Metal').
        resource_amount: Total amount to deliver.
        reward_credits: Credits paid to acceptor on completion.
        penalty_credits: Credits deducted on breach (default 0).
        duration_ticks: Max ticks to fulfil (0 = unlimited).
        visibility: 'Private' (directed) or 'Public' (open bidding).
        target_id: Target corp ID for private contracts.
        bidding_window_ticks: Ticks the bidding window stays open (default 5).
        knowledge_bonus: Research points bonus on completion (default 0).
    """
    return _server_post("/game/contracts", {
        "proposerId":         proposer_id,
        "resourceType":       resource_type,
        "resourceAmount":     resource_amount,
        "rewardCredits":      reward_credits,
        "penaltyCredits":     penalty_credits,
        "durationTicks":      duration_ticks,
        "visibility":         visibility,
        "targetId":           target_id,
        "biddingWindowTicks": bidding_window_ticks,
        "knowledgeBonus":     knowledge_bonus,
    })


@mcp.tool
def bid_on_contract(contract_id: str, bidder_id: str) -> dict:
    """
    Submit a bid on a public contract.
    Does not require Unity in Play Mode.

    Args:
        contract_id: The contract to bid on.
        bidder_id: The corporation placing the bid.
    """
    return _server_post(f"/game/contracts/{contract_id}/bid", {"bidderId": bidder_id})


@mcp.tool
def confirm_bidder(contract_id: str, proposer_id: str, bidder_id: str) -> dict:
    """
    Proposer confirms a candidate bidder to activate a public contract.
    Does not require Unity in Play Mode.

    Args:
        contract_id: The contract to activate.
        proposer_id: The proposing corporation (must match contract).
        bidder_id: The chosen bidder to activate the contract with.
    """
    return _server_post(f"/game/contracts/{contract_id}/confirm", {
        "proposerId": proposer_id,
        "bidderId":   bidder_id,
    })


@mcp.tool
def accept_contract(contract_id: str, acceptor_id: str) -> dict:
    """
    Accept a private contract directed at the given corporation.
    Does not require Unity in Play Mode.

    Args:
        contract_id: The contract to accept.
        acceptor_id: The corporation accepting (must be the targetId).
    """
    return _server_post(f"/game/contracts/{contract_id}/accept", {"acceptorId": acceptor_id})


@mcp.tool
def break_contract(contract_id: str, corp_id: str) -> dict:
    """
    Break an active contract. Penalty credits are deducted from the breaching corporation.
    Does not require Unity in Play Mode.

    Args:
        contract_id: The contract to break.
        corp_id: The corporation breaking the contract.
    """
    return _server_post(f"/game/contracts/{contract_id}/break", {"corpId": corp_id})


# ── Phase 7.5 — States & Reputation ──────────────────────────────────────────


@mcp.tool
def create_state(
    name: str,
    state_type: int = 0,
    tile_ids: list[str] | None = None,
    bureaucracy: float = 0.1,
    corruption_rate: float = 0.1,
    tolerance_threshold: float = 0.5,
) -> dict:
    """
    Register a new in-game State on the server.
    Does not require Unity in Play Mode.

    Args:
        name: Display name of the State.
        state_type: 0=Capitalist (high tolerance), 1=Nationalist (low tolerance).
        tile_ids: H3 tile IDs that belong to this State's territory.
        bureaucracy: 0..1 — multiplier on nationalisation delay.
        corruption_rate: 0..1 — reduces delay, enables bribery.
        tolerance_threshold: Tolerance score above which nationalisation triggers.
    """
    return _server_post("/game/states", {
        "name": name,
        "stateType": state_type,
        "tileIds": tile_ids or [],
        "bureaucracy": bureaucracy,
        "corruptionRate": corruption_rate,
        "toleranceThreshold": tolerance_threshold,
    })


@mcp.tool
def list_states() -> dict:
    """
    Return all registered States.
    Does not require Unity in Play Mode.
    """
    return _server_get("/game/states")


@mcp.tool
def get_planet_states(body_id: str) -> dict:
    """
    Return a compact summary of all nation-States and their territories for a given planet body.
    Shows: state name, profile, territory count, total tile count, and each territory's name + tile count.
    Use this to quickly verify that countries have been generated on a planet after bootstrap.
    Does not require Unity in Play Mode.

    Args:
        body_id: UUID of the SphericalBody (e.g. Earth). Use get_body_overview or list_bodies to find it.
    """
    return _server_get(f"/game/bodies/{body_id}/states-summary")


@mcp.tool
def get_state(state_id: str) -> dict:
    """
    Return a single State by ID.
    Does not require Unity in Play Mode.

    Args:
        state_id: UUID of the State.
    """
    return _server_get(f"/game/states/{state_id}")


@mcp.tool
def list_territories(body_id: str = "") -> dict:
    """
    Return all territories on a given body. If body_id is empty, returns all territories.
    Does not require Unity in Play Mode.

    Args:
        body_id: UUID of the SphericalBody (e.g. Earth). Empty string = all bodies.
    """
    url = f"/game/territories?body_id={body_id}" if body_id else "/game/territories"
    return _server_get(url)


@mcp.tool
def get_territory(territory_id: str) -> dict:
    """
    Return a single Territory by ID.
    Does not require Unity in Play Mode.

    Args:
        territory_id: UUID of the Territory.
    """
    return _server_get(f"/game/territories/{territory_id}")


@mcp.tool
def get_reputation(source_id: str, target_id: str) -> dict:
    """
    Return the bilateral reputation score from source_id toward target_id.
    Does not require Unity in Play Mode.

    Args:
        source_id: Entity (State or corp) that observed the target's behaviour.
        target_id: Entity whose reputation is being queried.
    """
    return _server_get(f"/game/reputation/{source_id}/{target_id}")


@mcp.tool
def list_reputations(corp_id: str) -> dict:
    """
    Return all bilateral reputation scores where corp_id is the source observer.
    Does not require Unity in Play Mode.

    Args:
        corp_id: Corporation whose outgoing reputation map to query.
    """
    return _server_get(f"/game/reputation/{corp_id}")


@mcp.tool
def list_nationalizations(corp_id: str = "") -> dict:
    """
    Return nationalisation processes. Optionally filter by corporation.
    Does not require Unity in Play Mode.

    Args:
        corp_id: If provided, only return processes targeting this corporation.
    """
    url = "/game/nationalizations"
    if corp_id:
        url += f"?corp_id={corp_id}"
    return _server_get(url)


@mcp.tool
def corrupt_nationalization(process_id: str, corp_id: str, bribe_amount: float) -> dict:
    """
    Attempt to cancel a nationalisation process via bribery.
    Deducts bribe_amount from the corporation's credits.
    Does not require Unity in Play Mode.

    Args:
        process_id: UUID of the NationalizationProcess.
        corp_id: Corporation paying the bribe (must be the target corp).
        bribe_amount: Amount to spend. Must meet or exceed the computed cost.
    """
    return _server_post(f"/game/nationalizations/{process_id}/corrupt", {
        "corpId": corp_id,
        "bribeAmount": bribe_amount,
    })


@mcp.tool
def get_scoreboard() -> dict:
    """
    Return top 10 corporations sorted by composite score descending.
    Score = credits + tileCount*100 + globalReputation*50.
    Does not require Unity in Play Mode.
    """
    return _server_get("/game/leaderboard")


@mcp.tool
def list_game_events(limit: int = 20) -> dict:
    """
    Return the last simulation events (newest first, max 200).
    Includes EventType, effects (credits/resource delta), affected corp, and tick number.
    Does not require Unity in Play Mode. Wraps GET /game/events on the DedicatedServer.

    Args:
        limit: Number of events to return (default 20, max 200).
    """
    return _server_get("/game/events", limit=limit)


@mcp.tool
def get_global_market(system_id: str = "sol") -> dict:
    """
    Return the aggregated global market state for a solar system.
    Includes per-resource price, velocity, supply, demand, and price history.
    Does not require Unity in Play Mode. Wraps GET /game/global-market on the DedicatedServer.

    Args:
        system_id: Solar system identifier (default "sol").
    """
    return _server_get("/game/global-market", system_id=system_id)


# ── Phase 8.5 — Agent LLM context + manual trigger ───────────────────────────


@mcp.tool
def get_agent_context(state_id: str) -> dict:
    """
    Return the LLM context snapshot for a State entity (state data, scoreboard, recent events, agent memory).
    Useful to inspect what the agent "sees" before it decides.
    Does not require Unity in Play Mode. Wraps GET /game/agent/context/{state_id} on the DedicatedServer.

    Args:
        state_id: UUID of the State entity.
    """
    return _server_get(f"/game/agent/context/{state_id}")


@mcp.tool
def run_agent_for_state(state_id: str) -> dict:
    """
    Manually trigger one synchronous LLM agent cycle for a State entity and return the resulting AgentAction.
    This calls the LLM — may take several seconds.
    Does not require Unity in Play Mode. Wraps POST /game/agent/run/{state_id} on the DedicatedServer.

    Args:
        state_id: UUID of the State entity to run the agent for.
    """
    return _server_post(f"/game/agent/run/{state_id}")


# ── Phase 7.4 — MCP tools for market list and cancel nationalization ──────────


@mcp.tool
def list_market_states() -> dict:
    """
    Return all local market states for every corporation.
    Does not require Unity in Play Mode. Wraps GET /game/market on the DedicatedServer.
    """
    return _server_get("/game/market")


@mcp.tool
def cancel_nationalization_contract(process_id: str) -> dict:
    """
    Cancel a nationalization process by breaking the underlying contract.
    Does not require Unity in Play Mode. Wraps POST /game/nationalizations/{process_id}/cancel-contract on the DedicatedServer.

    Args:
        process_id: UUID of the NationalizationProcess to cancel.
    """
    return _server_post(f"/game/nationalizations/{process_id}/cancel-contract")


# ── Catalog — Biome Transition Rules ──────────────────────────────────────────


@mcp.tool
def list_biome_rules() -> dict:
    """
    List all biome transition rules from the catalog.
    Does not require Unity. Wraps GET /catalog/biome-rules on the DedicatedServer.
    """
    return _server_get("/catalog/biome-rules")


@mcp.tool
def get_biome_rule(rule_id: int) -> dict:
    """
    Get a single biome transition rule by ID.
    Does not require Unity. Wraps GET /catalog/biome-rules/{rule_id} on the DedicatedServer.

    Args:
        rule_id: Integer ID of the rule.
    """
    return _server_get(f"/catalog/biome-rules/{rule_id}")


@mcp.tool
def update_biome_rule(
    rule_id: int,
    name: str | None = None,
    target_terrain_type: int | None = None,
    from_terrain_types: list[int] | None = None,
    priority: int | None = None,
    is_enabled: bool | None = None,
    temperature_min: float | None = None,
    temperature_max: float | None = None,
    humidity_min: float | None = None,
    humidity_max: float | None = None,
    vegetation_min: float | None = None,
    vegetation_max: float | None = None,
    tree_count_min: float | None = None,
    tree_count_max: float | None = None,
    has_river: bool | None = None,
    has_lake: bool | None = None,
    water_ratio_min: float | None = None,
    water_ratio_max: float | None = None,
    toxin_min: float | None = None,
    toxin_max: float | None = None,
    description: str | None = None,
) -> dict:
    """
    Update fields of an existing biome transition rule.
    Only provided (non-None) fields are updated.
    Does not require Unity. Wraps PATCH /catalog/biome-rules/{rule_id} on the DedicatedServer.

    Args:
        rule_id: Integer ID of the rule to update.
        name: Display name of the rule.
        target_terrain_type: TerrainType int value (0=Roche,1=Glace,2=AtmosphereToxique,3=Eau,4=Vegetation,5=Metal,6=Foret,7=Desert,8=Jungle,9=ZoneHumide).
        from_terrain_types: List of source TerrainType int values (empty = any).
        priority: Higher priority rules are evaluated first.
        is_enabled: Whether the rule is active in the tick loop.
        temperature_min: Minimum tile temperature (°C) required.
        temperature_max: Maximum tile temperature (°C) required.
        humidity_min: Minimum humidity (0–100) required.
        humidity_max: Maximum humidity (0–100) required.
        vegetation_min: Minimum vegetation level required.
        vegetation_max: Maximum vegetation level required.
        tree_count_min: Minimum tree count required (Forêt threshold ≈ 2000).
        tree_count_max: Maximum tree count required.
        has_river: If True, tile must have a river; if False, must not.
        has_lake: If True, tile must have a lake; if False, must not.
        water_ratio_min: Minimum water ratio of neighboring tiles.
        water_ratio_max: Maximum water ratio of neighboring tiles.
        toxin_min: Minimum toxin level required.
        toxin_max: Maximum toxin level required.
        description: Human-readable description of the rule logic.
    """
    payload = {k: v for k, v in {
        "name": name, "target_terrain_type": target_terrain_type,
        "from_terrain_types": from_terrain_types, "priority": priority,
        "is_enabled": is_enabled, "temperature_min": temperature_min,
        "temperature_max": temperature_max, "humidity_min": humidity_min,
        "humidity_max": humidity_max, "vegetation_min": vegetation_min,
        "vegetation_max": vegetation_max, "tree_count_min": tree_count_min,
        "tree_count_max": tree_count_max, "has_river": has_river,
        "has_lake": has_lake, "water_ratio_min": water_ratio_min,
        "water_ratio_max": water_ratio_max, "toxin_min": toxin_min,
        "toxin_max": toxin_max, "description": description,
    }.items() if v is not None}
    return _server_post(f"/catalog/biome-rules/{rule_id}", **payload)


@mcp.tool
def create_biome_rule(
    rule_id: int,
    target_terrain_type: int,
    name: str = "",
    priority: int = 10,
    description: str = "",
) -> dict:
    """
    Create a new biome transition rule (or replace an existing one with the same rule_id).
    Use update_biome_rule afterwards to set specific conditions.
    Does not require Unity. Wraps POST /catalog/biome-rules on the DedicatedServer.

    Args:
        rule_id: Integer ID for the new rule (must be unique).
        target_terrain_type: TerrainType int value the tile should transition to.
        name: Display name of the rule.
        priority: Evaluation priority (higher = checked first).
        description: Human-readable description.
    """
    return _server_post("/catalog/biome-rules", rule_id=rule_id,
                        target_terrain_type=target_terrain_type,
                        name=name, priority=priority, description=description)


@mcp.tool
def delete_biome_rule(rule_id: int) -> dict:
    """
    Delete a biome transition rule from the catalog.
    Does not require Unity. Wraps DELETE /catalog/biome-rules/{rule_id} on the DedicatedServer.

    Args:
        rule_id: Integer ID of the rule to delete.
    """
    return _server_delete(f"/catalog/biome-rules/{rule_id}")


# ── Catalog — Terrain Type Defs ────────────────────────────────────────────────


@mcp.tool
def list_terrain_types() -> dict:
    """
    List all terrain type definitions from the catalog (label, color, thresholds).
    Does not require Unity. Wraps GET /catalog/terrain-types on the DedicatedServer.
    """
    return _server_get("/catalog/terrain-types")


@mcp.tool
def update_terrain_type(
    terrain_type_id: int,
    label_fr: str | None = None,
    color_hex: str | None = None,
    humidity_threshold: float | None = None,
    humidity_clamp_min: float | None = None,
    noise_threshold: float | None = None,
    temperature_threshold: float | None = None,
    water_ratio_min: float | None = None,
    spawn_weight: float | None = None,
    description: str | None = None,
    is_enabled: bool | None = None,
) -> dict:
    """
    Update display properties or generation thresholds of a terrain type.
    Does not require Unity. Wraps PATCH /catalog/terrain-types/{terrain_type_id} on the DedicatedServer.

    Args:
        terrain_type_id: TerrainType int value (0=Roche, 1=Glace, ..., 9=ZoneHumide).
        label_fr: French display name.
        color_hex: HTML hex color code (e.g. '#D4AA70').
        humidity_threshold: Generation humidity threshold.
        humidity_clamp_min: Minimum clamped humidity value.
        noise_threshold: Noise map threshold for this terrain.
        temperature_threshold: Generation temperature threshold.
        water_ratio_min: Minimum water ratio for generation.
        spawn_weight: Relative spawn weight for procedural generation.
        description: Human-readable description.
        is_enabled: Whether this terrain type is active in generation.
    """
    payload = {k: v for k, v in {
        "label_fr": label_fr, "color_hex": color_hex,
        "humidity_threshold": humidity_threshold, "humidity_clamp_min": humidity_clamp_min,
        "noise_threshold": noise_threshold, "temperature_threshold": temperature_threshold,
        "water_ratio_min": water_ratio_min, "spawn_weight": spawn_weight,
        "description": description, "is_enabled": is_enabled,
    }.items() if v is not None}
    return _server_post(f"/catalog/terrain-types/{terrain_type_id}", **payload)


if __name__ == "__main__":
    if MCP_TRANSPORT == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=MCP_PORT)
    else:
        mcp.run()