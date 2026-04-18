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


@mcp.tool
def get_view_state() -> dict:
    """
    Get the current Unity view state.
    Returns active view level (SolarSystem / Planet / Local), active planet name,
    current region coordinates, selected hex cell, and terraformation progress.
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

_SMOKE_COMPARE_FIELDS_PROJ  = ["openOceanCells", "coastCells", "inlandWaterCells",
                                "frozenWaterCells", "dryCells",
                                "averageWaterRatio", "averageTemperature"]
_SMOKE_COMPARE_FIELDS_LOCAL = ["openOceanCells", "coastCells", "inlandWaterCells",
                                "frozenWaterCells", "dryCells", "basinCells",
                                "averageWaterRatio", "averageTemperature"]


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
    data["projection"]    = _safe_server_get("/projection")
    data["openRegion"]    = _safe_get("/debug/open-region", lat=lat, lon=lon)
    data["local"]         = _safe_server_get("/region")
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
def get_body_tile(body_id: str, tile_id: int) -> dict:
    """
    Get a single surface tile by its stable tile_id (= row * cols + col).
    Also lists child zone IDs if any interior zones are accessible from this tile.

    Args:
        body_id: UUID of the spherical body.
        tile_id: Integer tile identifier.
    """
    return _server_get(f"/bodies/{body_id}/tiles/{tile_id}")


@mcp.tool
def apply_body_tile_delta(
    body_id: str,
    tile_id: int,
    water_delta: float = 0.0,
    temperature_delta: float = 0.0,
) -> dict:
    """
    Apply additive water and/or temperature deltas to a surface tile.
    water_delta and temperature_delta are clamped or bounded server-side.

    Args:
        body_id: UUID of the spherical body.
        tile_id: Target tile identifier.
        water_delta: Additive water delta (positive = add water).
        temperature_delta: Additive temperature delta in °C.
    """
    return _server_post(
        f"/bodies/{body_id}/tiles/{tile_id}/delta",
        water_delta=water_delta,
        temperature_delta=temperature_delta,
    )


@mcp.tool
def terraform_body_tile(body_id: str, tile_id: int, action_type: int) -> dict:
    """
    Apply a terraform action on a surface tile of a spherical body.
    The action modifier (Heat/Irrigate/Plant/Mine/Detoxify) is applied immediately.

    Args:
        body_id: UUID of the spherical body.
        tile_id: Target tile identifier.
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
    parent_tile_id: int | None = None,
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
        parent_tile_id: Tile on the parent body where the entrance is (optional).
        seed: Random seed for generation (optional, auto-generated if omitted).
    """
    params = {"zone_type": zone_type, "cols": cols, "rows": rows}
    if parent_tile_id is not None:
        params["parent_tile_id"] = parent_tile_id
    if seed is not None:
        params["seed"] = seed
    return _server_post(f"/bodies/{body_id}/zones", **params)


if __name__ == "__main__":
    if MCP_TRANSPORT == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=MCP_PORT)
    else:
        mcp.run()