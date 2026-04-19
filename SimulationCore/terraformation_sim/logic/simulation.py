from __future__ import annotations

from .stellar import _greenhouse_delta
from ..models import (
    AtmosphericState,
    HexGridDebugSummary,
    HexStateModifier,
    PendingTerraformAction,
    RegionState,
    SimulationCellAddress,
    SimulationCellState,
    SimulationSoilState,
    TerraformAction,
    TerraformActionDefinition,
    TerrainClass,
    TerrainType,
    WaterClassification,
)


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
