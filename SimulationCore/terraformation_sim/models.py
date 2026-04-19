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
    ThermalEquilibrium = 9      # Temperature stable ±2K over 10 ticks
    HabitabilityThreshold = 10  # habitabilityScore crosses 0.25 / 0.50 / 0.75 / 1.0
    AtmosphereFormed = 11       # atmosphericPressure > 10 kPa for the first time


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


class AtmosphericState(BaseModel):
    """Aggregated atmospheric state for a region, derived from cell states."""
    co2Ratio: float = 0.0004           # CO₂ fraction [0..1] — Earth ≈ 0.0004
    o2Ratio: float = 0.0               # O₂ fraction [0..1] — Earth ≈ 0.21
    atmosphericPressure: float = 0.6   # kPa — Mars initial ≈ 0.6, Earth ≈ 101.3
    averageTemperature: float = -60.0  # °C — Mars initial ≈ -60°C
    toxinRatio: float = 0.0            # Toxin fraction [0..1]
    habitabilityScore: float = 0.0     # Weighted habitability score [0..1]


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
    atmosphericState: AtmosphericState = Field(default_factory=AtmosphericState)
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


class RouteStatus(IntEnum):
    Hidden = 0
    Known = 1


class TravelStatus(IntEnum):
    InTransit = 0
    Arrived = 1
    Cancelled = 2


class ZoneType(IntEnum):
    Cave = 0
    NaturalCavern = 1
    Building = 2
    Underground = 3
    Ship = 4
    Station = 5


# ── Atmospheric composition ───────────────────────────────────────────────────

class AtmosphericGas(BaseModel):
    """One gas species in a planetary atmosphere.
    greenhouseCoeff is game-balanced: CO₂=1.0, CH₄=28.0, H₂O=0.5, N₂=0.0, O₂=0.0.
    molarMass in g/mol (informational, used for future pressure / gravity calculations).
    """
    name: str = ""
    fraction: float = 0.0          # volume fraction [0..1]
    greenhouseCoeff: float = 0.0   # relative greenhouse warming factor
    molarMass: float = 28.0        # g/mol


class AtmosphericComposition(BaseModel):
    """Full atmospheric composition for a spherical body.
    gases is the list of tracked gas species; unlisted species are assumed trace.
    totalPressureKpa is the reference surface pressure.
    """
    gases: list[AtmosphericGas] = Field(default_factory=list)
    totalPressureKpa: float = 0.0  # kPa — Earth≈101.3, Mars≈0.6, vacuum=0.0

    def fraction_of(self, name: str) -> float:
        """Return the volume fraction of a gas by name, 0.0 if absent."""
        for g in self.gases:
            if g.name.upper() == name.upper():
                return g.fraction
        return 0.0

    def set_fraction(self, name: str, new_fraction: float) -> None:
        """Update a gas fraction in place (clamps to [0, 1])."""
        new_fraction = max(0.0, min(1.0, new_fraction))
        for g in self.gases:
            if g.name.upper() == name.upper():
                g.fraction = new_fraction
                return


# Reference preset atmospheres (used by bootstrap_sol and tests)
ATMOSPHERE_PRESETS: dict[str, AtmosphericComposition] = {
    "earth": AtmosphericComposition(
        totalPressureKpa=101.3,
        gases=[
            AtmosphericGas(name="N2",  fraction=0.780, greenhouseCoeff=0.0,  molarMass=28.0),
            AtmosphericGas(name="O2",  fraction=0.210, greenhouseCoeff=0.0,  molarMass=32.0),
            AtmosphericGas(name="CO2", fraction=0.000420, greenhouseCoeff=1.0,  molarMass=44.0),
            AtmosphericGas(name="CH4", fraction=0.0000018, greenhouseCoeff=28.0, molarMass=16.0),
            AtmosphericGas(name="H2O", fraction=0.010, greenhouseCoeff=0.5,  molarMass=18.0),
        ],
    ),
    "mars": AtmosphericComposition(
        totalPressureKpa=0.6,
        gases=[
            AtmosphericGas(name="CO2", fraction=0.953, greenhouseCoeff=1.0, molarMass=44.0),
            AtmosphericGas(name="N2",  fraction=0.027, greenhouseCoeff=0.0, molarMass=28.0),
            AtmosphericGas(name="O2",  fraction=0.001, greenhouseCoeff=0.0, molarMass=32.0),
        ],
    ),
    "venus": AtmosphericComposition(
        totalPressureKpa=9200.0,
        gases=[
            AtmosphericGas(name="CO2", fraction=0.965, greenhouseCoeff=1.0, molarMass=44.0),
            AtmosphericGas(name="N2",  fraction=0.035, greenhouseCoeff=0.0, molarMass=28.0),
        ],
    ),
    "vacuum": AtmosphericComposition(totalPressureKpa=0.0, gases=[]),
}


class GlobalWindPattern(BaseModel):
    """Simplified planetary wind pattern (MVP — Hadley cells deferred to later sprint).
    dominantWindDeg: direction FROM which the prevailing wind blows, in degrees [0, 360).
    windIntensity: normalised strength [0, 1]. 0=calm, 1=storm-force.
    Local windVector in SimulationCellState is derived from this at region-open time.
    """
    dominantWindDeg: float = 270.0  # westerlies (wind from west)
    windIntensity: float = 0.3      # moderate


class GoldbergTileState(BaseModel):
    """One tile on a spherical body surface — H3 hexagonal hierarchical cell.
    tileId is the H3 cell index string (e.g. '8928308280fffff').
    neighborIds lists up to 6 adjacent H3 cells (5 for the 12 pentagons at icosahedron vertices).
    boundaryLatLons provides the 6 (lat, lon) vertex pairs of the hexagon boundary for exact
    3D projection in Unity (replacing nearest-neighbour lat/lon approximation).
    childZoneIds lists any interior zones accessible from this tile (caves, buildings…).

    Physical fields added for terraformation simulation:
    - altitude: height relative to sea level, normalised [-1, 1] (negative = submarine).
    - albedo: surface reflectivity [0=absorb all, 1=reflect all].
    - solarIrradiance: effective W/m² received at this tile (cos-latitude weighted).
    - vegetationDensity: fraction of tile covered by vegetation [0, 1].
    - wildlifeDensity: relative density of surface fauna [0, 1].
    - atmosphereDeltaCo2/O2: per-tick gas delta produced/consumed by this tile's occupants;
      aggregated into SphericalBodyState.atmosphere by advance_tick().
    """
    tileId: str = ""
    neighborIds: list[str] = Field(default_factory=list)
    boundaryLatLons: list[list[float]] = Field(default_factory=list)
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
    # ── Physical simulation fields ──────────────────────────────────────────
    altitude: float = 0.0           # normalised height relative to sea level [-1, 1]
    albedo: float = 0.15            # surface albedo [0, 1]
    solarIrradiance: float = 0.0    # W/m² at tile surface
    vegetationDensity: float = 0.0  # [0, 1]
    wildlifeDensity: float = 0.0    # [0, 1] — species breakdown in sprint E
    atmosphereDeltaCo2: float = 0.0 # CO₂ volume fraction delta per tick (from buildings/plants)
    atmosphereDeltaO2: float = 0.0  # O₂ volume fraction delta per tick


# Ticks required to travel 1 light-year along a stellar route (baseline, modifier=1.0)
TICKS_PER_LIGHT_YEAR: int = 100


class OrbitalParameters(BaseModel):
    """Keplerian-like orbital parameters for a body orbiting its parent.
    None on BodyBase means the body is the system root (star / black hole).
    Position at tick T: angle = initialPhaseDeg + 360 * (T / periodTicks)
    """
    semiMajorAxisAU: float = 1.0      # orbit radius in Astronomical Units
    eccentricity: float = 0.0          # 0 = circle, 0.9 = highly elliptical
    inclinationDeg: float = 0.0        # tilt relative to system ecliptic
    initialPhaseDeg: float = 0.0       # angle at tick 0 (degrees)
    periodTicks: int = 365             # ticks for one full revolution


class BodyBase(BaseModel):
    """Base contract for every body tracked by the simulation host.
    Subclasses override surfaceType with a Literal to act as the discriminator.
    parentId links moons to their parent planet, zones to their parent body,
    and secondary stars to the primary star of a multi-star system.
    orbitalParams=None means this body is the root of its system (no orbit).
    """
    bodyId: str = ""
    bodyType: BodyType = BodyType.Planet
    name: str = ""
    parentId: str | None = None
    seed: int = 0
    surfaceType: str = "goldberg"
    isDiscovered: bool = True
    isColonized: bool = False
    # Galaxy layer
    systemId: str = ""                           # UUID of the SolarSystemState that owns this body
    spectralType: str = ""                       # e.g. "G2V", "M5Ve", "BH", "" for non-stars
    orbitalParams: OrbitalParameters | None = None  # None = system root


class SphericalBodyState(BodyBase):
    """Planet, Moon or Asteroid — spherical surface represented as a lat/lon tile grid.
    tiles is empty by default; populated on demand via GET /bodies/{id}/tiles.
    isModified is set True only when a player or agent performs a write action on this body
    (tile delta, terraform action, zone registration). Read-only access never sets this flag.
    generationVersion records which GENERATION_VERSION was active at time of first modification,
    so a future algo change can detect and re-generate stale bodies.

    Atmosphere & climate:
    - atmosphere: full gas composition + pressure. atmosphereDensity is kept as a
      convenience property for backward-compat with generation code (= pressure / 101.3).
    - equilibriumTemperature: planetary mean surface temperature (°C) computed from
      star luminosity, orbit, albedo and greenhouse effect. Updated each tick.
    - globalWindPattern: simplified planetary wind (MVP — Hadley cells in later sprint).
    - luminosityLsun: only meaningful for stars (bodyType==Star). Derived at bootstrap
      from spectralType + radiusKm. 0.0 for planets/moons.
    """
    surfaceType: Literal["goldberg"] = "goldberg"
    radiusKm: float = 6371.0
    h3Resolution: int = 2  # H3 resolution: 0=122 cells, 1=842 cells, 2=5882 cells
    tileCount: int = 0
    projectionOverride: DebugCoherenceOverride = DebugCoherenceOverride.None_
    waterLevel: float = 0.0
    isModified: bool = False
    generationVersion: str = ""
    summary: ProjectionDebugSummary = Field(default_factory=ProjectionDebugSummary)
    tiles: list[GoldbergTileState] = Field(default_factory=list)
    # ── Atmosphere & climate ────────────────────────────────────────────────
    atmosphere: AtmosphericComposition = Field(default_factory=lambda: AtmosphericComposition())
    equilibriumTemperature: float = -273.15   # °C — updated by compute_equilibrium_temperature
    globalWindPattern: GlobalWindPattern = Field(default_factory=GlobalWindPattern)
    luminosityLsun: float = 0.0               # L☉ — stars only

    @property
    def atmosphereDensity(self) -> float:  # type: ignore[override]
        """Backward-compat: normalised density [0, 1] ≈ totalPressureKpa / 101.3."""
        return min(1.0, self.atmosphere.totalPressureKpa / 101.3)


class InteriorZoneState(BodyBase):
    """Cave, building, ship or station — flat hex grid.
    Reuses SimulationCellState for cells (same contract as RegionState).
    parentTileId is the surface tile on the parent body where the entrance is located.
    Can be nested: a building inside a cave has its own parentId pointing to the cave zone.
    cells is empty by default; populated on demand via GET /bodies/{id}/cells.
    """
    surfaceType: Literal["hex_flat"] = "hex_flat"
    zoneType: ZoneType = ZoneType.Cave
    parentTileId: str | None = None  # H3 cell index of the surface tile entrance
    cols: int = 9
    rows: int = 9
    summary: HexGridDebugSummary = Field(default_factory=HexGridDebugSummary)
    cells: list[SimulationCellState] = Field(default_factory=list)


AnyBodyState = Annotated[
    SphericalBodyState | InteriorZoneState,
    Field(discriminator="surfaceType"),
]


# ── Galaxy layer ───────────────────────────────────────────────────────────────
# Sits above the body hierarchy: systems contain bodies, routes connect systems,
# and space travels move factions along routes.

class GalacticPosition(BaseModel):
    """3-D position in the galaxy, in light-years from an arbitrary origin."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class SolarSystemState(BaseModel):
    """A star system: one root body (star / black hole) plus all orbiting bodies.
    rootBodyId is the body at the gravitational centre (orbitalParams=None).
    bodyIds lists every body that belongs to this system (including root).
    """
    systemId: str = ""
    name: str = ""
    position: GalacticPosition = Field(default_factory=GalacticPosition)
    rootBodyId: str = ""          # body_id of the central star / black hole
    bodyIds: list[str] = Field(default_factory=list)
    isDiscovered: bool = True
    description: str = ""


class StellarRoute(BaseModel):
    """A travel corridor between two systems.
    Hidden by default — must be revealed via event / agent action before use.
    travelTimeModifier: <1 = shortcut (wormhole), >1 = hazard (black hole gravity).
    distanceLy is computed at creation time from the two system positions.
    """
    routeId: str = ""
    fromSystemId: str = ""
    toSystemId: str = ""
    distanceLy: float = 0.0
    travelTimeModifier: float = 1.0
    status: RouteStatus = RouteStatus.Hidden
    description: str = ""


class SpaceTravel(BaseModel):
    """An in-flight journey of a faction from one system to another.
    arrivalTick is computed at departure: tick + round(distanceLy * TICKS_PER_LIGHT_YEAR * modifier).
    """
    travelId: str = ""
    factionId: str = ""           # corporation / player / agent identifier
    fromSystemId: str = ""
    toSystemId: str = ""
    routeId: str = ""
    distanceLy: float = 0.0
    departedAtTick: int = 0
    arrivalTick: int = 0
    status: TravelStatus = TravelStatus.InTransit