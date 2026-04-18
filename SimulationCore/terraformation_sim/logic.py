from __future__ import annotations

import math
import h3 as _h3
from noise import snoise3 as _snoise3

# Bump this string whenever the tile generation algorithm changes.
# Bodies that were modified under a different version will have their
# tiles regenerated lazily on next access (mutations are preserved).
GENERATION_VERSION: str = "v7"

from .models import (
    AnyBodyState,
    AtmosphericState,
    DebugCoherenceOverride,
    GoldbergTileState,
    HexGridDebugSummary,
    HexStateModifier,
    InteriorZoneState,
    OrbitalParameters,
    PendingTerraformAction,
    ProjectionDebugSummary,
    RegionState,
    SimulationCellAddress,
    SimulationCellState,
    SimulationSoilState,
    SimulationVector2State,
    TerraformAction,
    TerraformActionDefinition,
    TerrainClass,
    TerrainType,
    WaterClassification,
    WorldLayer,
    ZoneType,
)


# ── Greenhouse constants (GameBalanced preset — from Per Aspera SDK ClimateConfig) ──
_CO2_EFF: float = 1.5
_H2O_EFF: float = 4.0
_MAX_WARMING_K: float = 80.0


def _greenhouse_delta(co2_ratio: float, h2o_factor: float = 0.01) -> float:
    """Extra temperature (Kelvin) from greenhouse effect. Logarithmic, capped."""
    co2_effect = _CO2_EFF * math.log(1.0 + co2_ratio * 100.0) * 5.0
    h2o_effect = _H2O_EFF * h2o_factor
    return min(co2_effect + h2o_effect, _MAX_WARMING_K)


def cell_habitability_score(cell: SimulationCellState) -> float:
    """Continuous habitability score [0..1] for a single cell (weighted multi-param)."""
    t = cell.temperature
    if t < -30.0 or t > 70.0:
        temp_score = 0.0
    elif -10.0 <= t <= 50.0:
        temp_score = 1.0 - abs(t - 15.0) / 35.0
    else:
        temp_score = max(0.0, 1.0 - abs(t - 15.0) / 45.0) * 0.3

    if cell.terrainType == TerrainType.Vegetation:
        water_score = 1.0
    elif cell.terrainType == TerrainType.Eau:
        water_score = min(1.0, cell.waterRatio / 0.3)
    else:
        water_score = cell.waterRatio

    veg_bonus = 1.0 if cell.terrainType == TerrainType.Vegetation else 0.0
    toxin_penalty = max(0.0, 1.0 - cell.toxinLevel * 3.0)

    return (temp_score * 0.35 + water_score * 0.25 + veg_bonus * 0.25 + toxin_penalty * 0.15)


def compute_atmospheric_state(cells: list[SimulationCellState]) -> AtmosphericState:
    """Aggregate cell states into a planetary AtmosphericState (SDK Per Aspera port)."""
    if not cells:
        return AtmosphericState()

    total = len(cells)
    avg_temp = sum(c.temperature for c in cells) / total
    avg_water = sum(c.waterRatio for c in cells) / total
    avg_toxin = sum(c.toxinLevel for c in cells) / total

    veg_fraction = sum(1 for c in cells if c.terrainType == TerrainType.Vegetation) / total
    water_fraction = sum(
        1 for c in cells
        if c.waterClassification in (
            WaterClassification.OpenOcean,
            WaterClassification.InlandWater,
            WaterClassification.Coast,
        )
    ) / total
    toxic_fraction = sum(1 for c in cells if c.terrainType == TerrainType.AtmosphereToxique) / total

    o2_ratio = min(0.21, veg_fraction * 0.5 + water_fraction * 0.05)
    co2_ratio = max(0.0004, toxic_fraction * 0.8 + avg_toxin * 0.3 - veg_fraction * 0.1)
    co2_ratio = min(0.96, co2_ratio)

    # kPa — Earth ≈ 101.3, Mars initial ≈ 0.6
    atmospheric_pressure = 0.6 + co2_ratio * 50.0 + o2_ratio * 40.0 + water_fraction * 10.0

    greenhouse_k = _greenhouse_delta(co2_ratio)
    effective_temp = avg_temp + greenhouse_k * 0.1

    habitability = sum(cell_habitability_score(c) for c in cells) / total

    return AtmosphericState(
        co2Ratio=round(co2_ratio, 6),
        o2Ratio=round(o2_ratio, 6),
        atmosphericPressure=round(atmospheric_pressure, 3),
        averageTemperature=round(effective_temp, 2),
        toxinRatio=round(avg_toxin, 4),
        habitabilityScore=round(habitability, 4),
    )


def is_cell_habitable(cell: SimulationCellState | None) -> bool:
    if cell is None:
        return False

    if cell.terrainType == TerrainType.Vegetation:
        return True

    if cell.terrainType == TerrainType.Eau:
        return True

    return -10.0 <= cell.temperature <= 50.0 and cell.waterRatio >= 0.05


def compute_habitability_progress(cells: list[SimulationCellState]) -> float:
    if not cells:
        return 0.0

    habitable_count = sum(1 for cell in cells if is_cell_habitable(cell))
    return habitable_count / len(cells)


def apply_region_progress(region: RegionState, cells: list[SimulationCellState]) -> RegionState:
    region.terraformationProgress = compute_habitability_progress(cells)
    region.cells = [cell.model_copy(deep=True) for cell in cells]
    if region.hasSelectedCell and cells:
        selected_address = region.selectedCell.address
        matched_cell = next(
            (cell for cell in cells if cell.address.q == selected_address.q and cell.address.r == selected_address.r),
            None,
        )
        region.selectedCell = matched_cell if matched_cell is not None else cells[0]
    region.summary = summarize_region_cells(cells)
    return region


def summarize_region_cells(cells: list[SimulationCellState]) -> HexGridDebugSummary:
    summary = HexGridDebugSummary(totalCells=len(cells))
    if not cells:
        return summary

    total_water = 0.0
    total_temperature = 0.0

    for cell in cells:
        total_water += cell.waterRatio
        total_temperature += cell.temperature
        summary.maxFlowAccumulation = max(summary.maxFlowAccumulation, cell.flowAccumulation)

        if cell.waterClassification == WaterClassification.OpenOcean:
            summary.openOceanCells += 1
        elif cell.waterClassification == WaterClassification.InlandWater:
            summary.inlandWaterCells += 1
        elif cell.waterClassification == WaterClassification.Coast:
            summary.coastCells += 1
        elif cell.waterClassification == WaterClassification.FrozenWater:
            summary.frozenWaterCells += 1
        else:
            summary.dryCells += 1

        if cell.terrainClass == TerrainClass.Ridge:
            summary.ridgeCells += 1
        elif cell.terrainClass == TerrainClass.Basin:
            summary.basinCells += 1
        elif cell.terrainClass == TerrainClass.Channel:
            summary.channelCells += 1
        elif cell.terrainClass == TerrainClass.Source:
            summary.sourceCells += 1

        if cell.hasRiver:
            summary.riverCells += 1
        if cell.hasDownstream:
            summary.downstreamCells += 1
        if cell.hasOverflowOutlet:
            summary.overflowCells += 1

        if cell.terrainType == TerrainType.Roche:
            summary.rockTerrainCells += 1
        elif cell.terrainType == TerrainType.Glace:
            summary.iceTerrainCells += 1
        elif cell.terrainType == TerrainType.AtmosphereToxique:
            summary.toxicTerrainCells += 1
        elif cell.terrainType == TerrainType.Eau:
            summary.waterTerrainCells += 1
        elif cell.terrainType == TerrainType.Vegetation:
            summary.vegetationTerrainCells += 1
        elif cell.terrainType == TerrainType.Metal:
            summary.metalTerrainCells += 1

    summary.averageWaterRatio = total_water / len(cells)
    summary.averageTemperature = total_temperature / len(cells)
    return summary


def terraform_action_definitions() -> dict[TerraformAction, TerraformActionDefinition]:
    return {
        TerraformAction.Heat: TerraformActionDefinition(
            actionType=TerraformAction.Heat,
            displayName="Heat",
            durationTicks=3,
            modifier=HexStateModifier(tempDelta=8.0),
        ),
        TerraformAction.Irrigate: TerraformActionDefinition(
            actionType=TerraformAction.Irrigate,
            displayName="Irrigate",
            durationTicks=5,
            modifier=HexStateModifier(waterDelta=0.15, hardnessDelta=-0.05),
        ),
        TerraformAction.Plant: TerraformActionDefinition(
            actionType=TerraformAction.Plant,
            displayName="Plant",
            durationTicks=10,
            modifier=HexStateModifier(organicDelta=0.08),
        ),
        TerraformAction.Mine: TerraformActionDefinition(
            actionType=TerraformAction.Mine,
            displayName="Mine",
            durationTicks=1,
            modifier=HexStateModifier(mineralDelta=-0.10, hardnessDelta=-0.05),
        ),
        TerraformAction.Detoxify: TerraformActionDefinition(
            actionType=TerraformAction.Detoxify,
            displayName="Detoxify",
            durationTicks=4,
            modifier=HexStateModifier(toxinDelta=-0.20),
        ),
    }


def can_apply_action(cell: SimulationCellState | None, action: TerraformAction) -> bool:
    if cell is None:
        return False

    if action == TerraformAction.Plant:
        if cell.waterRatio < 0.1:
            return False
        if cell.temperature < -30.0:
            return False
    elif action == TerraformAction.Mine:
        if cell.soil.rockHardness < 0.05:
            return False

    return True


def apply_modifier_to_cell(cell: SimulationCellState, modifier: HexStateModifier) -> SimulationCellState:
    cell.temperature += modifier.tempDelta
    cell.waterRatio = max(0.0, min(1.0, cell.waterRatio + modifier.waterDelta))
    cell.toxinLevel = max(0.0, min(1.0, cell.toxinLevel + modifier.toxinDelta))
    cell.soil = SimulationSoilState(
        rockHardness=max(0.0, min(1.0, cell.soil.rockHardness + modifier.hardnessDelta)),
        organicContent=max(0.0, min(1.0, cell.soil.organicContent + modifier.organicDelta)),
        porosity=cell.soil.porosity,
        mineralDensity=max(0.0, min(1.0, cell.soil.mineralDensity + modifier.mineralDelta)),
        toxicSoil=cell.soil.toxicSoil if cell.toxinLevel > 0.0 else False,
        thermalConductivity=cell.soil.thermalConductivity,
    )

    if cell.toxinLevel <= 0.0:
        cell.soil.toxicSoil = False

    return cell


def queue_action(pending: list[PendingTerraformAction],
                 target_cell: SimulationCellAddress,
                 action: TerraformAction) -> PendingTerraformAction:
    definition = terraform_action_definitions()[action]
    entry = PendingTerraformAction(cell=target_cell, actionType=action, ticksRemaining=definition.durationTicks)
    pending.append(entry)
    return entry


def process_pending_actions(cells: list[SimulationCellState],
                            pending: list[PendingTerraformAction]) -> tuple[list[SimulationCellState], list[PendingTerraformAction]]:
    if not pending:
        return cells, pending

    definitions = terraform_action_definitions()
    cell_index = {(cell.address.q, cell.address.r): index for index, cell in enumerate(cells)}
    next_pending: list[PendingTerraformAction] = []

    for entry in pending:
        index = cell_index.get((entry.cell.q, entry.cell.r))
        if index is None:
            continue

        definition = definitions[entry.actionType]
        cells[index] = apply_modifier_to_cell(cells[index], definition.modifier)
        remaining = entry.ticksRemaining - 1
        if remaining > 0:
            next_pending.append(PendingTerraformAction(cell=entry.cell, actionType=entry.actionType, ticksRemaining=remaining))

    return cells, next_pending


# ── H3 hexagonal hierarchical tile generation ─────────────────────────────────

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
                   coherence: "DebugCoherenceOverride") -> float:
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
    cold_veg_threshold = max(0.20, 0.40 - atmosphere_density * 0.16)
    temperate_veg_threshold = max(0.26, 0.54 - atmosphere_density * 0.20)
    hot_veg_threshold = max(0.35, 0.58 - atmosphere_density * 0.12)

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

    if coherence == DebugCoherenceOverride.Basin and not is_water:
        water_ratio = min(1.0, water_ratio + 0.05 * (1.0 - altitude_norm))

    # Evaporation at extreme heat; below -20°C water stays as ice (terrain, not lost)
    if temperature > 80.0:
        evap = min(1.0, (temperature - 80.0) / 60.0)
        water_ratio = max(0.0, water_ratio * (1.0 - evap * 0.8))

    # ── Biome tree — MapGeneration_rule.md decision order ────────────────
    if is_mountain:
        # altitude > 0.70 normalized → rocky mountain peak
        terrain_type = TerrainType.Roche
    elif toxin_level > 0.04 and not is_water:
        terrain_type = TerrainType.AtmosphereToxique
    elif is_water:
        terrain_type = TerrainType.Eau
    elif temperature < -20.0:
        # Sub-freezing: ice if any water present, polar desert otherwise
        terrain_type = TerrainType.Glace if water_ratio > 0.15 else TerrainType.Roche
    elif is_polar and height_above_sea < 0.15:
        terrain_type = TerrainType.Glace
    elif temperature < 10.0:
        # Cold temperate: tundra vegetation needs high water
        terrain_type = TerrainType.Vegetation if water_ratio > cold_veg_threshold else TerrainType.Roche
    elif temperature <= 50.0:
        # Temperate warm (10–50°C): main biome band
        if water_ratio > temperate_veg_threshold:
            terrain_type = TerrainType.Vegetation   # forest / prairie
        elif noise_r > 0.92:
            terrain_type = TerrainType.Metal
        else:
            terrain_type = TerrainType.Roche         # semi-arid or arid
    else:
        # Hot (>50°C): tropical vegetation needs sustained moisture
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

    # ── Terrain class (scatter, hash-based) ──────────────────────────────
    if noise_c > 0.75:
        terrain_class = TerrainClass.Ridge
    elif noise_c > 0.50:
        terrain_class = TerrainClass.Basin
    elif noise_c > 0.30:
        terrain_class = TerrainClass.Channel
    elif noise_c > 0.15:
        terrain_class = TerrainClass.Source
    else:
        terrain_class = TerrainClass.Slope

    return terrain_type, water_class, terrain_class, water_ratio, temperature, toxin_level


def generate_spherical_tiles(
    h3_resolution: int,
    coherence_override: DebugCoherenceOverride,
    water_level: float,
    seed: int,
    atmosphere_density: float = 0.5,
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

        # Pass the smoothed height so terrain assignment uses the same elevation
        # that Unity will render — coastlines and altitude zones are now consistent.
        t_type, w_class, t_class, water_ratio, temperature, toxin_level = _assign_spherical_tile(
            lat_norm, lon_norm, cell, coherence_override, sea_level, seed,
            height=cell_heights[cell],
            atmosphere_density=atmosphere_density,
        )
        habitable = is_tile_habitable(t_type, temperature, water_ratio)

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
        ))

    return tiles


def is_tile_habitable(terrain_type: TerrainType, temperature: float, water_ratio: float) -> bool:
    if terrain_type == TerrainType.Vegetation:
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


# ── Interior zone cell generation ─────────────────────────────────────────────

def generate_interior_cells(cols: int, rows: int, zone_type: ZoneType, seed: int) -> list[SimulationCellState]:
    """Generate the hex cell grid for an interior zone (cave, building, ship…).
    Reuses SimulationCellState — same contract as RegionState.cells.
    """
    cells: list[SimulationCellState] = []
    layer = _zone_layer(zone_type)

    for row in range(rows):
        for col in range(cols):
            n0 = _tile_noise(col, row, seed, 0)
            n1 = _tile_noise(col, row, seed, 1)
            n2 = _tile_noise(col, row, seed, 2)

            terrain_type, water_class, t_class, water_ratio, temperature, toxin_level = _interior_terrain(
                zone_type, n0, n1, n2
            )
            cells.append(SimulationCellState(
                address=SimulationCellAddress(q=col, r=row),
                terrainName=_terrain_name(terrain_type, zone_type),
                terrainType=terrain_type,
                layer=layer,
                altitude=n0 * 0.4,
                temperature=temperature,
                waterRatio=water_ratio,
                toxinLevel=toxin_level,
                windVector=SimulationVector2State(x=0.0, y=0.0),
                windSpeed=0.0,
                rainShadow=True,
                hasRiver=False,
                flowAccumulation=0,
                terrainClass=t_class,
                waterClassification=water_class,
                soil=SimulationSoilState(
                    rockHardness=n0 * 0.8 + 0.1,
                    organicContent=0.0 if zone_type in (ZoneType.Ship, ZoneType.Station, ZoneType.Building) else n1 * 0.1,
                    porosity=n1 * 0.3,
                    mineralDensity=n2 * 0.5 + 0.1,
                    toxicSoil=toxin_level > 0.1,
                    thermalConductivity=0.4,
                ),
            ))
    return cells


def _zone_layer(zone_type: ZoneType) -> WorldLayer:
    if zone_type in (ZoneType.Cave, ZoneType.NaturalCavern, ZoneType.Underground):
        return WorldLayer.Underground
    if zone_type in (ZoneType.Ship, ZoneType.Station):
        return WorldLayer.Space
    return WorldLayer.Surface  # Building


def _interior_terrain(
    zone_type: ZoneType, n0: float, n1: float, n2: float
) -> tuple[TerrainType, WaterClassification, TerrainClass, float, float, float]:
    """Return (terrain_type, water_class, terrain_class, water_ratio, temperature, toxin_level)."""
    if zone_type in (ZoneType.Ship, ZoneType.Station):
        terrain_type = TerrainType.Metal if n0 > 0.15 else TerrainType.Roche
        water_ratio = max(0.0, n1 * 0.05 - 0.02)
        temperature = 18.0 + (n2 - 0.5) * 4.0
        toxin_level = 0.0
        water_class = WaterClassification.Dry
        t_class = TerrainClass.Slope
    elif zone_type == ZoneType.Building:
        terrain_type = TerrainType.Metal if n0 > 0.30 else TerrainType.Roche
        water_ratio = max(0.0, n1 * 0.08 - 0.03)
        temperature = 16.0 + (n2 - 0.5) * 6.0
        toxin_level = 0.0
        water_class = WaterClassification.Dry
        t_class = TerrainClass.Slope
    elif zone_type in (ZoneType.Cave, ZoneType.NaturalCavern):
        terrain_type = TerrainType.Roche if n0 > 0.35 else (TerrainType.Glace if n2 < 0.15 else TerrainType.Roche)
        water_ratio = max(0.0, n1 * 0.35 - 0.05)
        temperature = -5.0 + n2 * 15.0
        toxin_level = max(0.0, n0 * 0.12 - 0.06)
        water_class = WaterClassification.InlandWater if water_ratio > 0.3 else WaterClassification.Dry
        t_class = TerrainClass.Basin if n0 > 0.6 else TerrainClass.Slope
    else:  # Underground
        terrain_type = TerrainType.Roche if n0 > 0.2 else TerrainType.Metal
        water_ratio = max(0.0, n1 * 0.20 - 0.05)
        temperature = 8.0 + n2 * 12.0
        toxin_level = max(0.0, n0 * 0.08 - 0.04)
        water_class = WaterClassification.Dry
        t_class = TerrainClass.Ridge if n2 > 0.7 else TerrainClass.Slope

    return terrain_type, water_class, t_class, water_ratio, temperature, toxin_level


def _terrain_name(terrain_type: TerrainType, zone_type: ZoneType) -> str:
    prefix = {
        ZoneType.Cave: "Cave", ZoneType.NaturalCavern: "Cavern",
        ZoneType.Building: "Block", ZoneType.Underground: "Deep",
        ZoneType.Ship: "Hull", ZoneType.Station: "Deck",
    }.get(zone_type, "")
    suffix = {
        TerrainType.Roche: "Rock", TerrainType.Glace: "Ice",
        TerrainType.AtmosphereToxique: "Toxic", TerrainType.Eau: "Water",
        TerrainType.Vegetation: "Growth", TerrainType.Metal: "Metal",
    }.get(terrain_type, "Unknown")
    return f"{prefix} {suffix}".strip()


def compute_body_position_at_tick(
    body_id: str,
    tick: int,
    bodies: dict[str, "AnyBodyState"],
) -> dict[str, float]:
    """Return the position of a body relative to its system root in Astronomical Units.
    Recursively resolves parentId chains. Root body (orbitalParams=None) is at (0, 0, 0).
    Result dict: {"x": float, "y": float, "z": float} in AU.
    """
    body = bodies.get(body_id)
    if body is None:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    params: OrbitalParameters | None = body.orbitalParams  # type: ignore[attr-defined]

    if params is None:
        # This is the root — sits at the origin
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    # Compute parent position first (recursive)
    parent_pos = compute_body_position_at_tick(body.parentId, tick, bodies) if body.parentId else {"x": 0.0, "y": 0.0, "z": 0.0}

    # Kepler position: use simplified circular/elliptical in the ecliptic plane
    # true_anomaly ≈ mean_anomaly (low-eccentricity approximation, good for gameplay)
    mean_angle_deg = params.initialPhaseDeg + 360.0 * (tick / max(1, params.periodTicks))
    angle_rad = math.radians(mean_angle_deg)
    # Semi-latus rectum: r = a(1 - e²) / (1 + e*cosθ)
    a = params.semiMajorAxisAU
    e = params.eccentricity
    r = a * (1.0 - e * e) / (1.0 + e * math.cos(angle_rad))

    # Apply inclination around the X axis
    inc_rad = math.radians(params.inclinationDeg)
    x_orb = r * math.cos(angle_rad)
    y_orb = r * math.sin(angle_rad) * math.cos(inc_rad)
    z_orb = r * math.sin(angle_rad) * math.sin(inc_rad)

    return {
        "x": parent_pos["x"] + x_orb,
        "y": parent_pos["y"] + y_orb,
        "z": parent_pos["z"] + z_orb,
    }