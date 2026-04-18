"""
Legacy compatibility copy of the MCP server.

Source of truth has moved to `Mcp/server.py`.
Keep this file in sync only as a temporary bridge for older references.
"""

import os
import urllib.parse
import httpx
from fastmcp import FastMCP

GAME_BRIDGE_URL: str = os.environ.get("GAME_BRIDGE_URL", "http://127.0.0.1:48621")

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


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

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
    return _get("/debug/projection")


@mcp.tool
def get_local_summary() -> dict:
    """
    Get the local hex region summary.
    Returns terrain, hydrology, biome stats and selected cell details for the
    currently loaded local region.
    """
    return _get("/debug/local")


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


# ---------------------------------------------------------------------------
# Action tools
# ---------------------------------------------------------------------------

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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if MCP_TRANSPORT == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=MCP_PORT)
    else:
        mcp.run()
