from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TerrainType(IntEnum):
    Roche = 0
    Glace = 1
    AtmosphereToxique = 2
    Eau = 3
    Vegetation = 4
    Metal = 5


class TerrainClass(IntEnum):
    Slope = 0
    Ridge = 1
    Basin = 2
    Channel = 3
    Source = 4


class WaterClassification(IntEnum):
    Dry = 0
    Coast = 1
    InlandWater = 2
    OpenOcean = 3
    FrozenWater = 4


class WorldLayer(IntEnum):
    Underground = 0
    OceanFloor = 1
    Ocean = 2
    Surface = 3
    Atmosphere = 4
    Space = 5


class TerraformAction(IntEnum):
    Heat = 0
    Irrigate = 1
    Plant = 2
    Mine = 3
    Detoxify = 4


class DebugCoherenceOverride(IntEnum):
    None_ = 0
    Ocean = 1
    Arid = 2
    Frozen = 3
    Coast = 4
    Basin = 5


class SimulationCommandType(IntEnum):
    None_ = 0
    LoadProjection = 1
    OpenRegion = 2
    QueueTerraformAction = 3
    ApplyDirectCellDelta = 4
    PauseTick = 5
    ResumeTick = 6
    CaptureSnapshot = 7


class SimulationEventType(IntEnum):
    None_ = 0
    ProjectionLoaded = 1
    RegionLoaded = 2
    ActionQueued = 3
    ActionRejected = 4
    CellUpdated = 5
    TickAdvanced = 6
    SnapshotCaptured = 7
    Error = 8


class SimulationVector2State(BaseModel):
    x: float = 0.0
    y: float = 0.0


class SimulationCoordinates(BaseModel):
    latitude: float = 0.0
    longitude: float = 0.0


class SimulationCellAddress(BaseModel):
    q: int = 0
    r: int = 0


class SimulationSoilState(BaseModel):
    rockHardness: float = 0.0
    organicContent: float = 0.0
    porosity: float = 0.0
    mineralDensity: float = 0.0
    toxicSoil: bool = False
    thermalConductivity: float = 0.0


class HexStateModifier(BaseModel):
    tempDelta: float = 0.0
    waterDelta: float = 0.0
    toxinDelta: float = 0.0
    organicDelta: float = 0.0
    hardnessDelta: float = 0.0
    mineralDelta: float = 0.0


class TerraformActionDefinition(BaseModel):
    actionType: TerraformAction
    displayName: str = "Action"
    durationTicks: int = 1
    modifier: HexStateModifier = Field(default_factory=HexStateModifier)


class SimulationActionCatalog(BaseModel):
    actions: list[TerraformActionDefinition] = Field(default_factory=list)


class PendingTerraformAction(BaseModel):
    cell: SimulationCellAddress = Field(default_factory=lambda: SimulationCellAddress(q=0, r=0))
    actionType: TerraformAction = TerraformAction.Heat
    ticksRemaining: int = 1


class SimulationCellState(BaseModel):
    address: SimulationCellAddress = Field(default_factory=SimulationCellAddress)
    terrainName: str = ""
    terrainType: TerrainType = TerrainType.Roche
    layer: WorldLayer = WorldLayer.Surface
    altitude: float = 0.0
    temperature: float = 0.0
    waterRatio: float = 0.0
    toxinLevel: float = 0.0
    windVector: SimulationVector2State = Field(default_factory=SimulationVector2State)
    windSpeed: float = 0.0
    rainShadow: bool = False
    hasRiver: bool = False
    flowAccumulation: int = 0
    terrainClass: TerrainClass = TerrainClass.Slope
    waterClassification: WaterClassification = WaterClassification.Dry
    hasDownstream: bool = False
    downstream: SimulationCellAddress = Field(default_factory=SimulationCellAddress)
    hasOverflowOutlet: bool = False
    overflowOutlet: SimulationCellAddress = Field(default_factory=SimulationCellAddress)
    soil: SimulationSoilState = Field(default_factory=SimulationSoilState)


class SimulationWeatherState(BaseModel):
    prevailingWindDirection: SimulationVector2State = Field(default_factory=SimulationVector2State)
    prevailingWindSpeed: float = 0.0
    precipitationRate: float = 0.0
    temperatureOffset: float = 0.0
    seasonalModifier: float = 0.0


class SimulationCoherenceState(BaseModel):
    dominantTerrainType: TerrainType = TerrainType.Roche
    projectedWaterRatio: float = 0.0
    oceanicity: float = 0.0
    deserticity: float = 0.0
    frigidity: float = 0.0
    isExtremeOcean: bool = False
    isExtremeArid: bool = False
    isExtremeFrozen: bool = False


class ProjectionDebugSummary(BaseModel):
    cols: int = 0
    rows: int = 0
    totalCells: int = 0
    dryCells: int = 0
    coastCells: int = 0
    inlandWaterCells: int = 0
    openOceanCells: int = 0
    frozenWaterCells: int = 0
    rockTerrainCells: int = 0
    iceTerrainCells: int = 0
    toxicTerrainCells: int = 0
    waterTerrainCells: int = 0
    vegetationTerrainCells: int = 0
    metalTerrainCells: int = 0
    averageWaterRatio: float = 0.0
    averageTemperature: float = 0.0


class HexGridDebugSummary(BaseModel):
    totalCells: int = 0
    dryCells: int = 0
    coastCells: int = 0
    inlandWaterCells: int = 0
    openOceanCells: int = 0
    frozenWaterCells: int = 0
    ridgeCells: int = 0
    basinCells: int = 0
    channelCells: int = 0
    sourceCells: int = 0
    riverCells: int = 0
    downstreamCells: int = 0
    overflowCells: int = 0
    rockTerrainCells: int = 0
    iceTerrainCells: int = 0
    toxicTerrainCells: int = 0
    waterTerrainCells: int = 0
    vegetationTerrainCells: int = 0
    metalTerrainCells: int = 0
    averageWaterRatio: float = 0.0
    averageTemperature: float = 0.0
    maxFlowAccumulation: int = 0


class ProjectionState(BaseModel):
    isValid: bool = False
    planetName: str = ""
    projectionOverride: DebugCoherenceOverride = DebugCoherenceOverride.None_
    projectionWaterLevel: float = 0.0
    summary: ProjectionDebugSummary = Field(default_factory=ProjectionDebugSummary)


class RegionState(BaseModel):
    isValid: bool = False
    seed: int = 0
    planetName: str = ""
    coordinates: SimulationCoordinates = Field(default_factory=SimulationCoordinates)
    terraformationProgress: float = 0.0
    weather: SimulationWeatherState = Field(default_factory=SimulationWeatherState)
    coherence: SimulationCoherenceState = Field(default_factory=SimulationCoherenceState)
    summary: HexGridDebugSummary = Field(default_factory=HexGridDebugSummary)
    hasSelectedCell: bool = False
    selectedCell: SimulationCellState = Field(default_factory=SimulationCellState)
    cells: list[SimulationCellState] = Field(default_factory=list)


class WorldState(BaseModel):
    isValid: bool = False
    tickCount: int = 0
    tickRunning: bool = False
    activePlanetName: str = ""
    projectionOverride: DebugCoherenceOverride = DebugCoherenceOverride.None_
    projectionWaterLevel: float = 0.0
    hasProjection: bool = False
    projection: ProjectionState = Field(default_factory=ProjectionState)
    hasRegion: bool = False
    region: RegionState = Field(default_factory=RegionState)


class ClientSnapshot(BaseModel):
    isValid: bool = False
    currentView: str = "Unavailable"
    activePlanetName: str = ""
    tickCount: int = 0
    tickRunning: bool = False
    terraformationProgress: float = 0.0
    hasProjection: bool = False
    projection: ProjectionState = Field(default_factory=ProjectionState)
    hasRegion: bool = False
    region: RegionState = Field(default_factory=RegionState)


class SimulationCommand(BaseModel):
    commandId: str = ""
    type: SimulationCommandType = SimulationCommandType.None_
    planetName: str = ""
    coordinates: SimulationCoordinates = Field(default_factory=SimulationCoordinates)
    cell: SimulationCellAddress = Field(default_factory=SimulationCellAddress)
    actionType: TerraformAction = TerraformAction.Heat
    waterDelta: float = 0.0
    temperatureDelta: float = 0.0


class SimulationEvent(BaseModel):
    eventId: str = ""
    type: SimulationEventType = SimulationEventType.None_
    tickCount: int = 0
    message: str = ""
    hasRegion: bool = False
    coordinates: SimulationCoordinates = Field(default_factory=SimulationCoordinates)
    hasCell: bool = False
    cell: SimulationCellAddress = Field(default_factory=SimulationCellAddress)


# ── Body hierarchy ─────────────────────────────────────────────────────────────
# Mirrors the Unity CelestialBody → OrbitalBody → Planet/Moon/Asteroid hierarchy
# plus InteriorZone for caves, buildings, ships (hex-flat view, no Goldberg surface).

class BodyType(IntEnum):
    Star = 0
    Planet = 1
    Moon = 2
    Asteroid = 3
    GasGiant = 4
    SpaceStation = 5


class ZoneType(IntEnum):
    Cave = 0
    NaturalCavern = 1
    Building = 2
    Underground = 3
    Ship = 4
    Station = 5


class GoldbergTileState(BaseModel):
    """One tile on the surface of a spherical body (planet, moon, asteroid).
    tile_id = row * cols + col — stable and reproducible from coordinates.
    childZoneIds lists any interior zones accessible from this tile (caves, buildings…).
    """
    tileId: int = 0
    latNorm: float = 0.0
    lonNorm: float = 0.0
    latDeg: float = 0.0
    lonDeg: float = 0.0
    terrainType: TerrainType = TerrainType.Roche
    waterClassification: WaterClassification = WaterClassification.Dry
    terrainClass: TerrainClass = TerrainClass.Slope
    waterRatio: float = 0.0
    temperature: float = 0.0
    toxinLevel: float = 0.0
    isHabitable: bool = False
    childZoneIds: list[str] = Field(default_factory=list)


class BodyBase(BaseModel):
    """Base contract for every body tracked by the simulation host.
    Subclasses override surfaceType with a Literal to act as the discriminator.
    parentId links moons to their parent planet, zones to their parent body.
    """
    bodyId: str = ""
    bodyType: BodyType = BodyType.Planet
    name: str = ""
    parentId: str | None = None
    seed: int = 0
    surfaceType: str = "goldberg"
    isDiscovered: bool = True
    isColonized: bool = False


class SphericalBodyState(BodyBase):
    """Planet, Moon or Asteroid — spherical surface represented as a lat/lon tile grid.
    tiles is empty by default; populated on demand via GET /bodies/{id}/tiles.
    """
    surfaceType: Literal["goldberg"] = "goldberg"
    radiusKm: float = 6371.0
    divisions: int = 5
    tileCount: int = 0
    atmosphereDensity: float = 0.0
    projectionOverride: DebugCoherenceOverride = DebugCoherenceOverride.None_
    waterLevel: float = 0.0
    summary: ProjectionDebugSummary = Field(default_factory=ProjectionDebugSummary)
    tiles: list[GoldbergTileState] = Field(default_factory=list)


class InteriorZoneState(BodyBase):
    """Cave, building, ship or station — flat hex grid.
    Reuses SimulationCellState for cells (same contract as RegionState).
    parentTileId is the surface tile on the parent body where the entrance is located.
    Can be nested: a building inside a cave has its own parentId pointing to the cave zone.
    cells is empty by default; populated on demand via GET /bodies/{id}/cells.
    """
    surfaceType: Literal["hex_flat"] = "hex_flat"
    zoneType: ZoneType = ZoneType.Cave
    parentTileId: int | None = None
    cols: int = 9
    rows: int = 9
    summary: HexGridDebugSummary = Field(default_factory=HexGridDebugSummary)
    cells: list[SimulationCellState] = Field(default_factory=list)


AnyBodyState = Annotated[
    SphericalBodyState | InteriorZoneState,
    Field(discriminator="surfaceType"),
]