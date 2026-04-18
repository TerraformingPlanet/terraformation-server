from __future__ import annotations

import math

from .models import (
    DebugCoherenceOverride,
    GoldbergTileState,
    HexGridDebugSummary,
    HexStateModifier,
    InteriorZoneState,
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


# ── Goldberg / spherical body tile generation ─────────────────────────────────

def compute_goldberg_divisions(radius_km: float) -> int:
    """Mirror of GoldbergSphereGenerator.ComputeDivisions() in Unity.
    Returns N in [2, 15] such that 10·N²+2 ≈ the equivalent Mercator grid size.
    """
    _MAX_REF = 69911.0   # PlanetaryHexGrid.MaxReferenceRadiusKm
    _MIN_C, _MAX_C = 24.0, 96.0
    _MIN_R, _MAX_R = 12.0, 48.0
    norm = max(0.0, min(1.0, radius_km / _MAX_REF))
    cols = _MIN_C + (_MAX_C - _MIN_C) * norm
    rows = _MIN_R + (_MAX_R - _MIN_R) * norm
    n = round(math.sqrt(cols * rows / 10.0))
    return max(2, min(15, n))


def _goldberg_grid_dims(divisions: int) -> tuple[int, int]:
    """Return (cols, rows) for the lat/lon grid equivalent to a Goldberg sphere
    with the given number of subdivisions. tile_id = row * cols + col."""
    tile_approx = 10 * divisions * divisions + 2
    cols = max(6, round(math.sqrt(tile_approx * 2.0)))
    rows = max(3, cols // 2)
    return cols, rows


def _tile_noise(col: int, row: int, seed: int, octave: int = 0) -> float:
    """Fully deterministic pseudo-random float in [0, 1] from tile coordinates.
    Based on Jenkins-style bit mixing — stable across Python runs."""
    v = (col * 1619 + row * 31337 + seed * 6271 + octave * 1013) & 0x7FFFFFFF
    v = ((v >> 13) ^ v) & 0x7FFFFFFF
    v = (v * (v * v * 60493 + 19990303) + 1376312589) & 0x7FFFFFFF
    return (v & 0xFFFF) / 65535.0


def _assign_spherical_tile(
    col: int, row: int, cols: int, rows: int,
    coherence: DebugCoherenceOverride,
    water_level: float,
    seed: int,
) -> tuple[TerrainType, WaterClassification, TerrainClass, float, float, float]:
    """Return (terrain_type, water_class, terrain_class, water_ratio, temperature, toxin_level)."""
    lat_norm = row / max(1, rows - 1)           # 0 = south pole, 1 = north pole
    lat_factor = 1.0 - abs(lat_norm - 0.5) * 2.0  # 0 at poles, 1 at equator
    is_polar = lat_norm < 0.1 or lat_norm > 0.9

    noise_w = _tile_noise(col, row, seed, 0)
    noise_t = _tile_noise(col, row, seed, 1)
    noise_r = _tile_noise(col, row, seed, 2)
    noise_c = _tile_noise(col, row, seed, 3)

    if coherence == DebugCoherenceOverride.Ocean:
        base_water, eq_temp, pole_temp = 0.85, 18.0, -5.0
    elif coherence == DebugCoherenceOverride.Arid:
        base_water, eq_temp, pole_temp = 0.05, 40.0, 5.0
    elif coherence == DebugCoherenceOverride.Frozen:
        base_water, eq_temp, pole_temp = 0.20, -10.0, -45.0
    elif coherence == DebugCoherenceOverride.Coast:
        base_water, eq_temp, pole_temp = 0.50, 16.0, -12.0
    elif coherence == DebugCoherenceOverride.Basin:
        base_water, eq_temp, pole_temp = 0.40, 14.0, -15.0
    else:
        base_water, eq_temp, pole_temp = 0.35, 15.0, -20.0

    water_ratio = max(0.0, min(1.0, base_water + water_level + (noise_w - 0.5) * 0.30))
    temperature = pole_temp + (eq_temp - pole_temp) * lat_factor + (noise_t - 0.5) * 8.0
    toxin_level = max(0.0, noise_r * 0.08 - 0.05)

    # Water classification
    if is_polar and water_ratio > 0.12:
        water_class = WaterClassification.FrozenWater
    elif water_ratio > 0.75:
        water_class = WaterClassification.OpenOcean
    elif water_ratio > 0.48:
        water_class = WaterClassification.InlandWater
    elif water_ratio > 0.30:
        water_class = WaterClassification.Coast
    else:
        water_class = WaterClassification.Dry

    # Terrain type
    if temperature < -15.0 or (is_polar and water_ratio > 0.10):
        terrain_type = TerrainType.Glace
    elif toxin_level > 0.04:
        terrain_type = TerrainType.AtmosphereToxique
    elif water_ratio > 0.50:
        terrain_type = TerrainType.Eau
    elif water_ratio > 0.22 and temperature > 5.0 and noise_r > 0.55:
        terrain_type = TerrainType.Vegetation
    elif noise_r > 0.88:
        terrain_type = TerrainType.Metal
    else:
        terrain_type = TerrainType.Roche

    # Terrain class
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
    divisions: int,
    coherence_override: DebugCoherenceOverride,
    water_level: float,
    seed: int,
) -> list[GoldbergTileState]:
    """Generate the lat/lon tile grid for a spherical body.
    Each tile maps to one face of the equivalent Goldberg polyhedron via lat/lon proximity
    (same as GoldbergFaceColorizer in Unity).
    """
    cols, rows = _goldberg_grid_dims(divisions)
    tiles: list[GoldbergTileState] = []

    for row in range(rows):
        for col in range(cols):
            lat_norm = row / max(1, rows - 1)
            lon_norm = col / max(1, cols - 1)
            lat_deg = lat_norm * 180.0 - 90.0
            lon_deg = lon_norm * 360.0 - 180.0

            t_type, w_class, t_class, water_ratio, temperature, toxin_level = _assign_spherical_tile(
                col, row, cols, rows, coherence_override, water_level, seed
            )
            habitable = is_tile_habitable(t_type, temperature, water_ratio)

            tiles.append(GoldbergTileState(
                tileId=row * cols + col,
                latNorm=lat_norm,
                lonNorm=lon_norm,
                latDeg=lat_deg,
                lonDeg=lon_deg,
                terrainType=t_type,
                waterClassification=w_class,
                terrainClass=t_class,
                waterRatio=water_ratio,
                temperature=temperature,
                toxinLevel=toxin_level,
                isHabitable=habitable,
            ))

    return tiles


def is_tile_habitable(terrain_type: TerrainType, temperature: float, water_ratio: float) -> bool:
    if terrain_type == TerrainType.Vegetation:
        return True
    if terrain_type == TerrainType.Eau:
        return True
    return -10.0 <= temperature <= 50.0 and water_ratio >= 0.05


def summarize_spherical_tiles(tiles: list[GoldbergTileState], cols: int = 0, rows: int = 0) -> ProjectionDebugSummary:
    summary = ProjectionDebugSummary(cols=cols, rows=rows, totalCells=len(tiles))
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