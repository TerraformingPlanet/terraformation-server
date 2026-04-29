from __future__ import annotations

import math
import random
import h3 as _h3
from noise import snoise3 as _snoise3

from .stellar import compute_tile_albedo, compute_tile_irradiance
from .ecology import seed_species_for_tile
from ..models import (
    DebugCoherenceOverride,
    GoldbergTileState,
    ProjectionDebugSummary,
    TerrainClass,
    TerrainType,
    WaterClassification,
)

# Bump this string whenever the tile generation algorithm changes.
# Bodies that were modified under a different version will have their
# tiles regenerated lazily on next access (mutations are preserved).
GENERATION_VERSION: str = "v8"


def _body_h3_resolution(radius_km: float) -> int:
    """Return the H3 resolution appropriate for a body's radius.
    Res 0 → 122 cells  (asteroids  < 500 km)
    Res 1 → 842 cells  (moons 500–2000 km)
    Res 2 → 5 882 cells (planets > 2000 km)
    """
    if radius_km < 500.0:
        return 0
    if radius_km < 2000.0:
        return 1
    return 2


def _tile_noise_h3(cell: str, seed: int, octave: int = 0) -> float:
    """Deterministic pseudo-random float [0,1] from H3 cell index string and seed.
    Used only for uncorrelated scatter values (Metal, TerrainClass, toxin…).
    NOT used for elevation — use _planet_height() for spatial coherence.

    H3 cell identity sits in the *upper* bits; lower 39 bits (res=2) are
    constant padding. Shift right 39 before mixing.
    """
    h_int = (int(cell, 16) >> 39) & 0x7FFFFFFF
    v = (h_int * 1619 + seed * 6271 + octave * 1013) & 0x7FFFFFFF
    v = ((v >> 13) ^ v) & 0x7FFFFFFF
    v = (v * (v * v * 60493 + 19990303) + 1376312589) & 0x7FFFFFFF
    return (v & 0xFFFF) / 65535.0


def _tile_noise(col: int, row: int, seed: int, octave: int = 0) -> float:
    """Fully deterministic pseudo-random float in [0, 1] from tile coordinates."""
    v = (col * 1619 + row * 31337 + seed * 6271 + octave * 1013) & 0x7FFFFFFF
    v = ((v >> 13) ^ v) & 0x7FFFFFFF
    v = (v * (v * v * 60493 + 19990303) + 1376312589) & 0x7FFFFFFF
    return (v & 0xFFFF) / 65535.0


def _xyz_from_lat_lon(lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    """Convert lat/lon (degrees) to unit-sphere XYZ for snoise3.
    Y = polar axis so latitude gradient is along Y.
    """
    lat_r = math.radians(lat_deg)
    lon_r = math.radians(lon_deg)
    x = math.cos(lat_r) * math.cos(lon_r)
    y = math.sin(lat_r)
    z = math.cos(lat_r) * math.sin(lon_r)
    return x, y, z


def _snoise(x: float, y: float, z: float, scale: float, seed: int,
            octaves: int = 4, persistence: float = 0.5, lacunarity: float = 2.0) -> float:
    """Simplex noise helper — wraps snoise3 with scale and seed offset."""
    return _snoise3(
        x * scale + seed * 0.1,
        y * scale,
        z * scale,
        octaves=octaves,
        persistence=persistence,
        lacunarity=lacunarity,
    )


def _warp_position(x: float, y: float, z: float, warp_scale: float, warp_strength: float,
                   seed: int) -> tuple[float, float, float]:
    """Domain-warp the position to break up regular grid patterns."""
    wx = _snoise(x, y, z, warp_scale, seed + 1, octaves=2)
    wy = _snoise(y, z, x, warp_scale, seed + 2, octaves=2)
    wz = _snoise(z, x, y, warp_scale, seed + 3, octaves=2)
    return x + wx * warp_strength, y + wy * warp_strength, z + wz * warp_strength


def _planet_height(x: float, y: float, z: float, seed: int,
                   coherence: DebugCoherenceOverride) -> float:
    """Compute terrain elevation for a point on the unit sphere using Simplex noise.

    Returns a float in approximately [-0.6, +0.6].
    Continental masses are shaped by a low-frequency layer (continent_scale),
    local relief by a mid-frequency layer (detail_scale), and
    mountain ridges by the absolute value of a high-frequency layer.

    Parameters are tuned per DebugCoherenceOverride preset so that:
      - Ocean  → mostly below sea level (ocean planet)
      - Arid   → mostly above sea level (desert world)
      - Frozen → normal relief, temperature handles the ice
      - Coast  → Earth-like balance (~71% ocean)
      - Basin  → rougher terrain, more inland water basins
    """
    if coherence == DebugCoherenceOverride.Ocean:
        continent_scale, detail_scale, mountain_scale = 0.2, 1.2, 2.5
        warp_strength = 0.15
        w_continent, w_detail, w_mountain = 0.5, 0.35, 0.15
    elif coherence == DebugCoherenceOverride.Arid:
        continent_scale, detail_scale, mountain_scale = 0.4, 1.8, 3.5
        warp_strength = 0.30
        w_continent, w_detail, w_mountain = 0.6, 0.25, 0.15
    elif coherence == DebugCoherenceOverride.Frozen:
        continent_scale, detail_scale, mountain_scale = 0.3, 1.5, 3.0
        warp_strength = 0.15
        w_continent, w_detail, w_mountain = 0.6, 0.3, 0.1
    elif coherence == DebugCoherenceOverride.Basin:
        continent_scale, detail_scale, mountain_scale = 0.25, 2.0, 4.0
        warp_strength = 0.25
        w_continent, w_detail, w_mountain = 0.5, 0.35, 0.15
    else:  # Coast / None_ (Earth default)
        continent_scale, detail_scale, mountain_scale = 0.3, 1.5, 3.0
        warp_strength = 0.20
        w_continent, w_detail, w_mountain = 0.6, 0.3, 0.1

    wx, wy, wz = _warp_position(x, y, z, warp_scale=2.0, warp_strength=warp_strength, seed=seed)

    continent = _snoise(wx, wy, wz, continent_scale, seed)
    detail    = _snoise(wx, wy, wz, detail_scale,    seed + 100)
    mountain  = abs(_snoise(wx, wy, wz, mountain_scale, seed + 200))

    return continent * w_continent + detail * w_detail + mountain * w_mountain


def _assign_spherical_tile(
    lat_norm: float,
    lon_norm: float,
    cell: str,
    coherence: DebugCoherenceOverride,
    sea_level: float,
    seed: int,
    height: float,                    # pre-computed (smoothed) height — do NOT recompute
    atmosphere_density: float = 0.5,  # body's atmosphere density [0,1]; affects water retention
    terrain_defs: "dict[int, dict] | None" = None,  # loaded from terrain_type_defs table
) -> tuple[TerrainType, WaterClassification, TerrainClass, float, float, float]:
    """Return (terrain_type, water_class, terrain_class, water_ratio, temperature, toxin_level).

    height: smoothed pre-computed height from generate_spherical_tiles Pass 2.
    sea_level: water_level-th percentile of all tile heights (pre-computed).
    atmosphere_density: body's atmosphereDensity (affects water retention & biome threshold).
    Implements the MapGeneration_rule.md physical model:
      tempLocale = base + altitudePenalty + latitudePenalty + noise
      waterRatio *= atmosphere_factor * freeze_factor
      Biome tree: altitude > 0.85 → Roche; T < -20 → Glace; etc.
    """
    lat_deg = lat_norm * 180.0 - 90.0
    lon_deg = lon_norm * 360.0 - 180.0
    lat_factor = 1.0 - abs(lat_norm - 0.5) * 2.0  # 0 at poles, 1 at equator
    is_polar = lat_norm < 0.1 or lat_norm > 0.9

    # Uncorrelated scatter noise (hash-based) — used for Metal, TerrainClass, toxin
    noise_r = _tile_noise_h3(cell, seed, 2)
    noise_c = _tile_noise_h3(cell, seed, 3)

    x, y, z = _xyz_from_lat_lon(lat_deg, lon_deg)

    # ── Base temperature from coherence preset ──────────────────────────
    if coherence == DebugCoherenceOverride.Ocean:
        eq_temp, pole_temp = 20.0, -3.0
    elif coherence == DebugCoherenceOverride.Arid:
        eq_temp, pole_temp = 42.0, 8.0
    elif coherence == DebugCoherenceOverride.Frozen:
        eq_temp, pole_temp = -8.0, -50.0
    elif coherence == DebugCoherenceOverride.Coast:
        eq_temp, pole_temp = 16.0, -12.0
    elif coherence == DebugCoherenceOverride.Basin:
        eq_temp, pole_temp = 14.0, -15.0
    else:
        eq_temp, pole_temp = 15.0, -20.0

    # Altitude above sea level: normalize to [0, 1] (0.5 = practical max in snoise3 space)
    height_above_sea = max(0.0, height - sea_level)
    altitude_norm = min(1.0, height_above_sea / 0.5)
    is_mountain = altitude_norm > 0.70      # peaks ~85th percentile of land height
    is_water = height < sea_level
    is_coastal = (not is_water) and height_above_sea < 0.10

    # Temperature: latitude gradient + altitude penalty + noise.
    # Keep lowlands relatively mild and concentrate strong cooling on high relief,
    # otherwise Coast/Basin lose too much temperate land.
    temp_noise = _snoise(x, y, z, 2.0, seed + 50, octaves=2) * 4.0
    elevated_relief = max(0.0, altitude_norm - 0.20) / 0.80
    altitude_penalty = -60.0 * (elevated_relief ** 1.35)
    temperature = pole_temp + (eq_temp - pole_temp) * lat_factor + altitude_penalty + temp_noise

    # Toxin: rare, land-only; higher geological activity → more toxin (approximated by noise)
    toxin_level = max(0.0, noise_r * 0.08 - 0.05)

    # ── Humidity (snoise3, spatially coherent) ───────────────────────────
    humidity = (_snoise(x, y, z, 1.5, seed + 300, octaves=3) + 1.0) * 0.5  # [0, 1]

    # ── Load terrain thresholds (from DB defs if available, else hardcoded defaults) ──
    _d = terrain_defs or {}
    _veg = _d.get(4, {})
    import json as _json
    _veg_extra: dict = _json.loads(_veg.get("extra_params") or "{}") if isinstance(_veg.get("extra_params"), str) else {}
    _cold_base  = float(_veg.get("humidity_threshold") or 0.40)
    _cold_clamp = float(_veg.get("humidity_clamp_min") or 0.20)
    _temp_base  = float(_veg_extra.get("temperate_base", 0.54))
    _temp_clamp = float(_veg_extra.get("temperate_clamp", 0.26))
    _hot_base   = float(_veg_extra.get("hot_base", 0.58))
    _hot_clamp  = float(_veg_extra.get("hot_clamp", 0.35))
    _forest_hum    = float(_d.get(6, {}).get("humidity_threshold") or 0.62)
    _metal_noise   = float(_d.get(5, {}).get("noise_threshold") or 0.92)
    _ice_temp      = float(_d.get(1, {}).get("temperature_threshold") or -20.0)
    _ice_water_min = float(_d.get(1, {}).get("water_ratio_min") or 0.15)
    _toxin_thresh  = float(_d.get(2, {}).get("noise_threshold") or 0.04)

    cold_veg_threshold     = max(_cold_clamp, _cold_base - atmosphere_density * 0.16)
    temperate_veg_threshold = max(_temp_clamp, _temp_base - atmosphere_density * 0.20)
    hot_veg_threshold      = max(_hot_clamp,  _hot_base  - atmosphere_density * 0.12)

    # ── Water ratio — physical model ─────────────────────────────────────
    # Base from depth / coastal humidity
    if is_water:
        depth = max(sea_level - height, 0.0)
        water_ratio = min(1.0, 0.72 + depth / max(abs(sea_level) + 0.6, 0.01) * 0.28)
    elif is_coastal:
        water_ratio = 0.22 + humidity * 0.30
    else:
        accumulation_bonus = 0.0
        if noise_c > 0.50:
            accumulation_bonus = 0.14   # basin-like accumulation
        elif noise_c > 0.30:
            accumulation_bonus = 0.08   # channel-like accumulation
        elif noise_c > 0.15:
            accumulation_bonus = 0.04   # source-like moisture

        water_ratio = humidity * (0.08 + atmosphere_density * 0.22) + accumulation_bonus

    # Atmosphere density factor: thin atmo dries land strongly, but oceans should remain oceans.
    if is_water:
        atmo_factor = 0.85 + atmosphere_density * 0.15
    else:
        atmo_factor = 0.25 + atmosphere_density * 0.75
    water_ratio = min(1.0, water_ratio * atmo_factor)

    # Evaporation at extreme heat; below -20°C water stays as ice (terrain, not lost)
    if temperature > 80.0:
        evap = min(1.0, (temperature - 80.0) / 60.0)
        water_ratio = max(0.0, water_ratio * (1.0 - evap * 0.8))

    # ── Biome tree — MapGeneration_rule.md decision order ────────────────
    if is_mountain:
        terrain_type = TerrainType.Roche
    elif toxin_level > _toxin_thresh and not is_water:
        terrain_type = TerrainType.AtmosphereToxique
    elif is_water:
        terrain_type = TerrainType.Eau
    elif temperature < _ice_temp:
        terrain_type = TerrainType.Glace if water_ratio > _ice_water_min else TerrainType.Roche
    elif is_polar and height_above_sea < 0.50:
        terrain_type = TerrainType.Glace
    elif temperature < 10.0:
        # Cold zone: boreal forest possible in subarctic (not arctic/polar) if very humid
        if water_ratio > cold_veg_threshold:
            if (not is_polar) and humidity > _forest_hum:
                terrain_type = TerrainType.Foret
            else:
                terrain_type = TerrainType.Vegetation
        else:
            terrain_type = TerrainType.Roche
    elif temperature <= 50.0:
        if water_ratio > temperate_veg_threshold:
            # Dense humid temperate zones → Forest
            if humidity > _forest_hum:
                terrain_type = TerrainType.Foret
            else:
                terrain_type = TerrainType.Vegetation
        elif noise_r > _metal_noise:
            terrain_type = TerrainType.Metal
        else:
            terrain_type = TerrainType.Roche
    else:
        terrain_type = TerrainType.Vegetation if water_ratio > hot_veg_threshold else TerrainType.Roche

    # ── Water classification ─────────────────────────────────────────────
    if terrain_type == TerrainType.Glace:
        water_class = WaterClassification.FrozenWater
    elif water_ratio > 0.68:
        water_class = WaterClassification.OpenOcean
    elif water_ratio > 0.42:
        water_class = WaterClassification.InlandWater
    elif water_ratio > 0.25:
        water_class = WaterClassification.Coast
    else:
        water_class = WaterClassification.Dry

    # TerrainClass is refined later by the hydrology/topology pass.
    if noise_c > 0.82:
        terrain_class = TerrainClass.Ridge
    elif noise_c > 0.56:
        terrain_class = TerrainClass.Channel
    elif noise_c > 0.28:
        terrain_class = TerrainClass.Source
    else:
        terrain_class = TerrainClass.Slope

    return terrain_type, water_class, terrain_class, water_ratio, temperature, toxin_level, humidity


def _is_water_like_tile(tile: GoldbergTileState) -> bool:
    return (
        tile.terrainType in (TerrainType.Eau, TerrainType.Glace)
        or tile.waterRatio >= 0.52
        or tile.waterClassification in (
            WaterClassification.InlandWater,
            WaterClassification.OpenOcean,
            WaterClassification.FrozenWater,
        )
    )


def _find_water_components(
    tiles: list[GoldbergTileState],
) -> tuple[list[set[str]], set[str], dict[str, int]]:
    tile_by_id = {tile.tileId: tile for tile in tiles}
    water_ids = {tile.tileId for tile in tiles if _is_water_like_tile(tile)}
    components: list[set[str]] = []
    component_index: dict[str, int] = {}

    for tile_id in water_ids:
        if tile_id in component_index:
            continue
        stack = [tile_id]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            component_index[current] = len(components)
            tile = tile_by_id[current]
            for neighbor_id in tile.neighborIds:
                if neighbor_id in water_ids and neighbor_id not in component:
                    stack.append(neighbor_id)
        components.append(component)

    total = max(len(tiles), 1)
    ocean_component: set[str] = set()
    if components:
        largest = max(components, key=len)
        if len(largest) >= max(12, int(total * 0.04)):
            ocean_component = largest

    return components, ocean_component, component_index


def _apply_spherical_hydrology(
    tiles: list[GoldbergTileState],
    cell_heights: dict[str, float],
    sea_level: float,
) -> None:
    tile_by_id = {tile.tileId: tile for tile in tiles}
    _, ocean_component, _ = _find_water_components(tiles)

    downhill_target: dict[str, str] = {}
    upstream_count: dict[str, int] = {tile.tileId: 0 for tile in tiles}
    for tile in tiles:
        current_height = cell_heights[tile.tileId]
        lower_neighbors = [
            neighbor_id
            for neighbor_id in tile.neighborIds
            if neighbor_id in cell_heights and cell_heights[neighbor_id] + 0.01 < current_height
        ]
        if not lower_neighbors:
            continue
        target = min(lower_neighbors, key=lambda neighbor_id: cell_heights[neighbor_id])
        downhill_target[tile.tileId] = target
        upstream_count[target] += 1

    # Store downhill direction on each tile (used by river propagation at tick-time)
    for tile in tiles:
        if tile.tileId in downhill_target:
            tile.riverDirection = downhill_target[tile.tileId]

    for tile in tiles:
        current_height = cell_heights[tile.tileId]
        neighbors = [tile_by_id[neighbor_id] for neighbor_id in tile.neighborIds if neighbor_id in tile_by_id]
        neighbor_heights = [cell_heights[neighbor.tileId] for neighbor in neighbors]
        lower_neighbors = [neighbor for neighbor in neighbors if cell_heights[neighbor.tileId] + 0.01 < current_height]
        higher_neighbors = [neighbor for neighbor in neighbors if cell_heights[neighbor.tileId] > current_height + 0.01]
        adjacent_ocean = any(neighbor.tileId in ocean_component for neighbor in neighbors)
        adjacent_water = any(_is_water_like_tile(neighbor) for neighbor in neighbors)
        adjacent_land = any(not _is_water_like_tile(neighbor) for neighbor in neighbors)
        near_sea_level = abs(current_height - sea_level) < 0.045
        is_local_min = bool(neighbor_heights) and not lower_neighbors and bool(higher_neighbors)
        is_local_max = bool(neighbor_heights) and not higher_neighbors and bool(lower_neighbors)
        is_frozen_water = tile.temperature < -18.0 and (tile.waterRatio >= 0.14 or _is_water_like_tile(tile))
        is_ocean_water = tile.tileId in ocean_component
        is_basin_candidate = (
            not is_ocean_water
            and (
                (is_local_min and tile.waterRatio >= 0.10)
                or (not lower_neighbors and current_height <= sea_level + 0.07)
                or (
                    adjacent_water
                    and current_height <= sea_level + 0.055
                    and len(lower_neighbors) <= 1
                    and tile.waterRatio >= 0.18
                )
            )
        )
        is_actual_water_surface = tile.terrainType in (TerrainType.Eau, TerrainType.Glace)

        if is_basin_candidate:
            tile.terrainClass = TerrainClass.Basin
        elif is_local_max:
            tile.terrainClass = TerrainClass.Ridge
        elif lower_neighbors and upstream_count[tile.tileId] >= 2:
            tile.terrainClass = TerrainClass.Channel
        elif lower_neighbors and upstream_count[tile.tileId] == 0 and tile.waterRatio >= 0.12:
            tile.terrainClass = TerrainClass.Source
        else:
            tile.terrainClass = TerrainClass.Slope

        if is_frozen_water:
            tile.terrainType = TerrainType.Glace
            tile.waterClassification = WaterClassification.FrozenWater
            tile.waterRatio = max(tile.waterRatio, 0.18)
        elif is_ocean_water:
            tile.terrainType = TerrainType.Eau
            if adjacent_land or near_sea_level or tile.waterRatio < 0.58:
                tile.waterClassification = WaterClassification.Coast
                tile.waterRatio = max(tile.waterRatio, 0.28)
            else:
                tile.waterClassification = WaterClassification.OpenOcean
                tile.waterRatio = max(tile.waterRatio, 0.68)
        elif is_basin_candidate and (is_actual_water_surface or tile.waterRatio >= 0.22):
            tile.terrainType = TerrainType.Eau
            tile.waterClassification = WaterClassification.InlandWater
            tile.waterRatio = max(tile.waterRatio, 0.40)
        elif is_actual_water_surface and not is_ocean_water:
            tile.terrainType = TerrainType.Eau
            tile.waterClassification = WaterClassification.InlandWater
            tile.waterRatio = max(tile.waterRatio, 0.40)
        elif adjacent_ocean and tile.waterRatio >= 0.16:
            tile.waterClassification = WaterClassification.Coast
        elif adjacent_water and tile.waterRatio >= 0.22 and adjacent_land:
            tile.waterClassification = WaterClassification.Coast
        else:
            tile.waterClassification = WaterClassification.Dry

        tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)


def _seed_water_sources(tiles: list[GoldbergTileState], seed: int) -> None:
    """Assign hasWaterSource and sourceCapacity probabilistically at generation time.

    Probabilities by altitude + terrainClass:
    - altitude > 0.5 AND TerrainClass.Ridge  → 75 %  (mountain peak)
    - altitude > 0.3 OR  TerrainClass.Ridge  → 40 %  (highland / crest)
    - other land tiles                        →  5 %
    - water / ocean tiles                     →  0 %  (no spring)

    sourceCapacity is scaled by altitude [0.5–3.0] m³/tick.
    """
    rng = random.Random(seed ^ 0xDEADBEEF)
    for tile in tiles:
        if tile.waterClassification in (
            WaterClassification.OpenOcean,
            WaterClassification.InlandWater,
            WaterClassification.FrozenWater,
        ):
            tile.hasWaterSource = False
            tile.sourceCapacity = None
            continue

        if tile.altitude > 0.5 and tile.terrainClass == TerrainClass.Ridge:
            prob = 0.75
        elif tile.altitude > 0.3 or tile.terrainClass == TerrainClass.Ridge:
            prob = 0.40
        else:
            prob = 0.05

        if rng.random() < prob:
            altitude_factor = max(0.1, tile.altitude)
            base_flow = rng.uniform(0.5, 3.0)
            tile.hasWaterSource = True
            tile.sourceCapacity = round(base_flow * altitude_factor, 3)


def summarize_spherical_hydrology(tiles: list[GoldbergTileState]) -> dict:
    components, ocean_component, _ = _find_water_components(tiles)
    water_tile_count = sum(1 for tile in tiles if _is_water_like_tile(tile))
    inland_components = [component for component in components if component != ocean_component]
    coast_tiles = [tile for tile in tiles if tile.waterClassification == WaterClassification.Coast]
    basin_tiles = [tile for tile in tiles if tile.terrainClass == TerrainClass.Basin]
    channel_tiles = [tile for tile in tiles if tile.terrainClass == TerrainClass.Channel]
    total = max(len(tiles), 1)
    return {
        "water_components": len(components),
        "largest_water_component_tiles": max((len(component) for component in components), default=0),
        "largest_water_component_pct": round(max((len(component) for component in components), default=0) / total * 100, 1),
        "ocean_connected_tiles": len(ocean_component),
        "ocean_connected_pct": round(len(ocean_component) / total * 100, 1),
        "enclosed_water_components": len(inland_components),
        "enclosed_water_tiles": sum(len(component) for component in inland_components),
        "enclosed_water_pct": round(sum(len(component) for component in inland_components) / total * 100, 1),
        "shoreline_tiles": len(coast_tiles),
        "shoreline_pct": round(len(coast_tiles) / total * 100, 1),
        "basin_floor_tiles": len(basin_tiles),
        "basin_floor_pct": round(len(basin_tiles) / total * 100, 1),
        "channel_tiles": len(channel_tiles),
        "channel_pct": round(len(channel_tiles) / total * 100, 1),
        "water_tile_pct": round(water_tile_count / total * 100, 1),
    }


def generate_spherical_tiles(
    h3_resolution: int,
    coherence_override: DebugCoherenceOverride,
    water_level: float,
    seed: int,
    atmosphere_density: float = 0.5,
    planet_irradiance_wm2: float = 0.0,
    terrain_defs: "dict[int, dict] | None" = None,
) -> list[GoldbergTileState]:
    """Generate tiles for a spherical body using H3 hexagonal hierarchical indexing.
    Each tile corresponds to one H3 cell at the given resolution (0, 1 or 2).
    Cells are sorted by H3 index string for a stable, reproducible ordering.
    neighborIds: up to 6 adjacent H3 cells (5 for the 12 pentagons per resolution).
    boundaryLatLons: 6 (lat, lon) vertex pairs for exact 3D projection in Unity.

    atmosphere_density: passed from SphericalBodyState.atmosphereDensity.
    Used in _assign_spherical_tile to scale water retention (thin atmo → drier tiles).

    Post-generation smoothing (2 passes) blends each tile's height with its
    neighbors' average to produce smoother coastlines and terrain transitions.
    The smoothed heights are forwarded to _assign_spherical_tile so terrain
    assignment actually benefits from the smoothing (fixing the old disconnect).
    """
    cells = sorted(_h3.uncompact_cells(_h3.get_res0_cells(), h3_resolution))

    # ── Pass 1: compute raw heights for smoothing ────────────────────────
    cell_heights: dict[str, float] = {}
    for cell in cells:
        lat, lng = _h3.cell_to_latlng(cell)
        x, y, z = _xyz_from_lat_lon(lat, lng)
        cell_heights[cell] = _planet_height(x, y, z, seed, coherence_override)

    # ── Percentile sea level: guarantees water_level fraction of tiles are ocean ──
    sorted_heights = sorted(cell_heights.values())
    sea_level_idx = min(int(water_level * len(sorted_heights)), len(sorted_heights) - 1)
    sea_level = sorted_heights[sea_level_idx]

    # ── Pass 2: smooth heights (2 iterations, len(neighbors) safe for pentagons) ──
    for _ in range(2):
        smoothed: dict[str, float] = {}
        for cell in cells:
            neighbors = sorted(set(_h3.grid_disk(cell, 1)) - {cell})
            neighbor_heights = [cell_heights[n] for n in neighbors if n in cell_heights]
            if neighbor_heights:
                avg = sum(neighbor_heights) / len(neighbor_heights)
                smoothed[cell] = cell_heights[cell] * 0.70 + avg * 0.30
            else:
                smoothed[cell] = cell_heights[cell]
        cell_heights = smoothed

    # ── Pass 3: assign terrain from smoothed heights ─────────────────────
    tiles: list[GoldbergTileState] = []
    for cell in cells:
        lat, lng = _h3.cell_to_latlng(cell)
        lat_norm = (lat + 90.0) / 180.0
        lon_norm = (lng + 180.0) / 360.0

        t_type, w_class, t_class, water_ratio, temperature, toxin_level, humidity = _assign_spherical_tile(
            lat_norm, lon_norm, cell, coherence_override, sea_level, seed,
            height=cell_heights[cell],
            atmosphere_density=atmosphere_density,
            terrain_defs=terrain_defs,
        )
        habitable = is_tile_habitable(t_type, temperature, water_ratio)

        # Physical fields: altitude, albedo, irradiance
        raw_height = cell_heights[cell]
        altitude = (raw_height - sea_level) / max(abs(raw_height - sea_level) + 1e-6, 0.3)
        altitude = max(-1.0, min(1.0, altitude))
        albedo = compute_tile_albedo(t_type, w_class)
        irradiance = compute_tile_irradiance(lat, planet_irradiance_wm2)

        neighbors = sorted(set(_h3.grid_disk(cell, 1)) - {cell})
        boundary = [[lat_v, lng_v] for lat_v, lng_v in _h3.cell_to_boundary(cell)]

        tiles.append(GoldbergTileState(
            tileId=cell,
            latNorm=lat_norm,
            lonNorm=lon_norm,
            latDeg=lat,
            lonDeg=lng,
            terrainType=t_type,
            waterClassification=w_class,
            terrainClass=t_class,
            waterRatio=water_ratio,
            temperature=temperature,
            toxinLevel=toxin_level,
            isHabitable=habitable,
            neighborIds=neighbors,
            boundaryLatLons=boundary,
            altitude=altitude,
            albedo=albedo,
            solarIrradiance=irradiance,
            humidity=humidity,
            species=seed_species_for_tile(t_type, w_class),
        ))

    _apply_spherical_hydrology(tiles, cell_heights, sea_level)
    _seed_water_sources(tiles, seed)

    return tiles


def is_tile_habitable(terrain_type: TerrainType, temperature: float, water_ratio: float) -> bool:
    if terrain_type == TerrainType.Vegetation:
        return True
    if terrain_type == TerrainType.Foret:
        return True
    if terrain_type == TerrainType.Eau:
        return True
    return -10.0 <= temperature <= 50.0 and water_ratio >= 0.05


def summarize_spherical_tiles(tiles: list[GoldbergTileState]) -> ProjectionDebugSummary:
    """Build a ProjectionDebugSummary from H3 tile list.
    cols/rows are 0 (not meaningful for H3 — use totalCells instead)."""
    summary = ProjectionDebugSummary(cols=0, rows=0, totalCells=len(tiles))
    if not tiles:
        return summary
    total_water = 0.0
    total_temp = 0.0
    for t in tiles:
        total_water += t.waterRatio
        total_temp += t.temperature
        if t.waterClassification == WaterClassification.OpenOcean:
            summary.openOceanCells += 1
        elif t.waterClassification == WaterClassification.InlandWater:
            summary.inlandWaterCells += 1
        elif t.waterClassification == WaterClassification.Coast:
            summary.coastCells += 1
        elif t.waterClassification == WaterClassification.FrozenWater:
            summary.frozenWaterCells += 1
        else:
            summary.dryCells += 1
        if t.terrainType == TerrainType.Roche:
            summary.rockTerrainCells += 1
        elif t.terrainType == TerrainType.Glace:
            summary.iceTerrainCells += 1
        elif t.terrainType == TerrainType.AtmosphereToxique:
            summary.toxicTerrainCells += 1
        elif t.terrainType == TerrainType.Eau:
            summary.waterTerrainCells += 1
        elif t.terrainType == TerrainType.Vegetation:
            summary.vegetationTerrainCells += 1
        elif t.terrainType == TerrainType.Metal:
            summary.metalTerrainCells += 1
    summary.averageWaterRatio = total_water / len(tiles)
    summary.averageTemperature = total_temp / len(tiles)
    return summary


def _hydrate_tiles_from_db(tile_rows: list[dict]) -> list[GoldbergTileState]:
    """Reconstruct GoldbergTileState objects from normalised DB rows.

    neighborIds and boundaryLatLons are recomputed from H3 (deterministic).
    species are re-seeded from terrain/water classification (deterministic).
    """
    tiles: list[GoldbergTileState] = []
    for row in tile_rows:
        tile_id = row["tile_id"]
        neighbors = sorted(set(_h3.grid_disk(tile_id, 1)) - {tile_id})
        boundary = [[lat_v, lng_v] for lat_v, lng_v in _h3.cell_to_boundary(tile_id)]
        t_type = TerrainType[row["terrain_type"]]
        w_class = WaterClassification[row["water_classification"]]
        t_class = TerrainClass[row["terrain_class"]]
        tiles.append(GoldbergTileState(
            tileId=tile_id,
            latNorm=row["lat_norm"],
            lonNorm=row["lon_norm"],
            latDeg=row["lat_deg"],
            lonDeg=row["lon_deg"],
            terrainType=t_type,
            waterClassification=w_class,
            terrainClass=t_class,
            waterRatio=row["water_ratio"],
            temperature=row["temperature"],
            humidity=row["humidity"],
            toxinLevel=row["toxin_level"],
            isHabitable=bool(row["is_habitable"]),
            neighborIds=neighbors,
            boundaryLatLons=boundary,
            altitude=row["altitude"],
            albedo=row["albedo"],
            solarIrradiance=row["solar_irradiance"],
            species=seed_species_for_tile(t_type, w_class),
        ))
    return tiles
