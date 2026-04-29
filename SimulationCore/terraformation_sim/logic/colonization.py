"""
colonization.py — Phase Colonisation Initiale Terre.

Pure functions: no side effects, no registry access, no `self`.
All mutations happen in runtime.py via _bootstrap_earth_colonization_locked().

Key responsibilities:
- Determine which tiles are terrestrial (claimable)
- Compute per-tile population factor from terrain + water type
- Seed PopulationTier list from a PopDistribution (parameterised — never hardcoded)
- Assign tiles to one of the 7 geographic continent zones by lat/lon
- Build TerritoryData objects via BFS flood-fill over neighbourIds
"""
from __future__ import annotations

from collections import deque
from uuid import uuid4

from ..models import (
    ClaimedTile,
    GoldbergTileState,
    PopDistribution,
    PopulationTier,
    SocialClass,
    STATE_PROFILES,
    TerritoryData,
    TerrainType,
    WaterClassification,
)

# ── Income defaults (imported rather than duplicated) ─────────────────────────
_INCOME_DEFAULTS: dict[SocialClass, float] = {
    SocialClass.Poor:   1.0,
    SocialClass.Middle: 4.0,
    SocialClass.Rich:   15.0,
}

# ── Population multipliers per terrain / water ────────────────────────────────

#: Terrain type → population multiplier relative to base
TERRAIN_POP_MULTIPLIERS: dict[TerrainType, float] = {
    TerrainType.Vegetation:         1.5,
    TerrainType.Metal:              0.8,
    TerrainType.Roche:              0.5,
    TerrainType.AtmosphereToxique:  0.1,
    TerrainType.Eau:                0.0,   # never claimable as terrestrial
    TerrainType.Glace:              0.0,   # excluded from colonisation
    TerrainType.Foret:              1.2,   # forest terrain bonus
}

#: Water classification → population multiplier (coastal bonus)
WATER_POP_MULTIPLIERS: dict[WaterClassification, float] = {
    WaterClassification.Coast:        1.5,
    WaterClassification.InlandWater:  1.2,
    WaterClassification.Dry:          1.0,
    WaterClassification.OpenOcean:    0.0,   # not terrestrial
    WaterClassification.FrozenWater:  0.0,   # excluded
}

# ── 7 geographic continent zones ─────────────────────────────────────────────
# Each zone is a (label, profile_key) pair assigned by banding on lat/lon.
# order matters: first match wins.
_CONTINENT_ZONES: list[tuple[str, float, float, float, float, str, str]] = [
    # (name, lat_min, lat_max, lon_min, lon_max, profile_key, state_name)
    # North America — lon extended to -180 to cover antimeridian Alaskan tiles
    ("NordAmerique",   15.0,  90.0, -180.0,  -30.0, "Standard",        "République Nordique"),
    # South America
    ("SudAmerique",   -60.0,  15.0, -100.0,  -30.0, "EnDeveloppement", "Union Sudaméricaine"),
    # Europe
    ("Europe",         35.0,  90.0,  -30.0,   40.0, "RicheUtopique",   "Fédération Européenne"),
    # Africa — lon extended to 60 to cover East Africa coast + Madagascar
    ("Afrique",        -40.0,  35.0,  -20.0,   60.0, "Pauvre",          "Confédération Africaine"),
    # Middle East (checked before Asie, first-match wins)
    ("MoyenOrient",    10.0,  45.0,   40.0,   75.0, "Autoritaire",     "Coalition du Désert"),
    # Oceania / Pacific — checked before Asie to get first-match priority
    ("Oceanie",        -55.0,  15.0,   90.0,  180.0, "EnDeveloppement", "Confédération Pacifique"),
    # Asia — lon starts at 40 to cover Western Siberia (lat 45–90, lon 40–60 gap)
    ("Asie",          -15.0,  90.0,   40.0,  180.0, "Standard",        "Alliance Asiatique"),
]

# Catchall — tiles that don't match any zone (e.g. antimeridian wrapping)
_FALLBACK_ZONE = ("Reste",  "Standard", "Territoires Libres")


# ── Public helpers ────────────────────────────────────────────────────────────

def is_terrestrial_tile(tile: GoldbergTileState) -> bool:
    """Return True if the tile can be colonised (not ocean, not polar ice)."""
    if tile.terrainType == TerrainType.Glace:
        return False
    if tile.waterClassification in (
        WaterClassification.OpenOcean,
        WaterClassification.FrozenWater,
    ):
        return False
    # Tiles classified Eau (river/lake surface) are non-terrestrial
    if tile.terrainType == TerrainType.Eau:
        return False
    return True


def tile_population_factor(tile: GoldbergTileState) -> float:
    """Return the combined terrain × water multiplier for a tile.

    Returns 0.0 for non-terrestrial tiles (ocean/ice).
    """
    terrain_m = TERRAIN_POP_MULTIPLIERS.get(tile.terrainType, 0.5)
    water_m   = WATER_POP_MULTIPLIERS.get(tile.waterClassification, 1.0)
    return terrain_m * water_m


def seed_tile_population(
    tile: GoldbergTileState,
    base: int,
    dist: PopDistribution,
) -> list[PopulationTier]:
    """Build a PopulationTier list for a tile.

    The distribution is parameterised via `dist` so it can vary across
    states, events, or tick pressure — never hardcoded.

    Returns an empty list if the computed total rounds to 0.
    """
    factor = tile_population_factor(tile)
    total = max(0, round(base * factor))
    if total == 0:
        return []

    n_poor   = round(total * dist.poor)
    n_rich   = max(1, round(total * dist.rich))
    n_middle = max(0, total - n_poor - n_rich)

    tiers: list[PopulationTier] = []
    if n_poor > 0:
        tiers.append(PopulationTier(
            socialClass=SocialClass.Poor,
            count=n_poor,
            avgIncome=_INCOME_DEFAULTS[SocialClass.Poor],
        ))
    if n_middle > 0:
        tiers.append(PopulationTier(
            socialClass=SocialClass.Middle,
            count=n_middle,
            avgIncome=_INCOME_DEFAULTS[SocialClass.Middle],
        ))
    if n_rich > 0:
        tiers.append(PopulationTier(
            socialClass=SocialClass.Rich,
            count=n_rich,
            avgIncome=_INCOME_DEFAULTS[SocialClass.Rich],
        ))
    return tiers


def assign_tile_to_continent(lat_deg: float, lon_deg: float) -> tuple[str, str, str]:
    """Return (zone_key, profile_key, state_name) for a (lat, lon) coordinate.

    Uses a banded lookup table — fast O(N) where N=7 zones.
    Returns the fallback zone if no zone matches.
    """
    for name, lat_min, lat_max, lon_min, lon_max, profile_key, state_name in _CONTINENT_ZONES:
        if lat_min <= lat_deg <= lat_max and lon_min <= lon_deg <= lon_max:
            return name, profile_key, state_name
    return _FALLBACK_ZONE


def build_territories_from_tiles(
    tiles: list[GoldbergTileState],
    body_id: str,
    population_base: int = 500,
) -> tuple[list[TerritoryData], dict[str, str]]:
    """Build TerritoryData objects from terrestrial tiles using BFS flood-fill.

    Each tile is assigned to a continent zone first. Within each zone,
    connected components are identified via BFS over neighborIds. Each
    connected component becomes one TerritoryData.

    Returns:
        territories: list of TerritoryData (one per connected component)
        tile_to_zone: dict[tile_id → zone_key] (for state assignment)
    """
    # Build lookup: tile_id → tile
    tile_map: dict[str, GoldbergTileState] = {t.tileId: t for t in tiles}

    # Filter terrestrial tiles
    terrestrial_ids: set[str] = {
        t.tileId for t in tiles if is_terrestrial_tile(t)
    }

    # Assign each tile to a continent zone
    tile_to_zone: dict[str, str] = {}
    zone_profile: dict[str, str] = {}    # zone_key → profile_key
    zone_state_name: dict[str, str] = {} # zone_key → state_name
    for tid in terrestrial_ids:
        t = tile_map[tid]
        zone_key, profile_key, state_name = assign_tile_to_continent(t.latDeg, t.lonDeg)
        tile_to_zone[tid] = zone_key
        zone_profile[zone_key] = profile_key
        zone_state_name[zone_key] = state_name

    # BFS flood-fill per zone to find contiguous components
    visited: set[str] = set()
    territories: list[TerritoryData] = []

    # Sort for determinism
    for zone_key in sorted(zone_profile.keys()):
        zone_tiles = {tid for tid, z in tile_to_zone.items() if z == zone_key}
        profile_key = zone_profile[zone_key]
        state_name  = zone_state_name[zone_key]
        component_idx = 0

        for start_tid in sorted(zone_tiles):
            if start_tid in visited:
                continue
            # BFS
            component: list[str] = []
            queue: deque[str] = deque([start_tid])
            visited.add(start_tid)
            while queue:
                current = queue.popleft()
                component.append(current)
                current_tile = tile_map.get(current)
                if current_tile is None:
                    continue
                for nb in current_tile.neighborIds:
                    if nb in zone_tiles and nb not in visited:
                        visited.add(nb)
                        queue.append(nb)

            component_idx += 1
            t_id = str(uuid4())
            # Name: zone name + component index if more than 1 component
            t_name = state_name if component_idx == 1 else f"{state_name} (Région {component_idx})"
            territories.append(TerritoryData(
                id=t_id,
                name=t_name,
                stateId="",       # filled in runtime after StateData creation
                bodyId=body_id,
                tileIds=component,
                populationBase=population_base,
                profileKey=profile_key,
            ))

    return territories, tile_to_zone
