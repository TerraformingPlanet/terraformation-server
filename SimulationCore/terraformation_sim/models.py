from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Literal
import colorsys

from pydantic import BaseModel, Field


def _corp_color_rgb(corp_id: str) -> tuple[float, float, float]:
    """Compute corporation color from ID (port of C# CorpColorFromId)."""
    if not corp_id:
        return (1.0, 1.0, 1.0)  # white
    hash_val = 17
    count = 0
    for char in corp_id:
        if char == '-':
            continue
        if count >= 8:
            break
        hash_val = hash_val * 31 + ord(char)
        count += 1
    hue = (hash_val & 0x7FFFFFFF) % 360 / 360.0
    # HSV to RGB: S=0.85, V=0.90
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.90)
    return (r, g, b)


# State color palette (port of C# _statePalette)
_STATE_PALETTE = [
    (0.20, 0.55, 0.85),  # bleu
    (0.86, 0.20, 0.22),  # rouge
    (0.18, 0.68, 0.32),  # vert
    (0.95, 0.75, 0.10),  # jaune
    (0.60, 0.20, 0.80),  # violet
    (1.00, 0.50, 0.10),  # orange
    (0.10, 0.70, 0.70),  # cyan
    (0.85, 0.30, 0.65),  # rose
    (0.40, 0.25, 0.12),  # marron
    (0.55, 0.75, 0.20),  # vert lime
]


def _state_color_rgb(state_id: str) -> tuple[float, float, float]:
    """Compute state color from ID (port of C# StateColorFromId)."""
    if not state_id:
        return _STATE_PALETTE[0]
    hash_val = 17
    count = 0
    for char in state_id:
        if char == '-':
            continue
        if count >= 8:
            break
        hash_val = hash_val * 31 + ord(char)
        count += 1
    idx = (hash_val & 0x7FFFFFFF) % len(_STATE_PALETTE)
    return _STATE_PALETTE[idx]


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
    ExpeditionLost = 12         # Phase 9.1 — expedition failed
    ExpeditionDelayed = 13      # Phase 9.1 — expedition delayed
    TradeRouteEstablished = 14  # Phase 9.1 — new trade route confirmed


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


# ── Corporation layer ──────────────────────────────────────────────────────────

# ── Market: social classes ────────────────────────────────────────────────────

class SocialClass(IntEnum):
    Poor   = 0
    Middle = 1
    Rich   = 2


class PopulationTier(BaseModel):
    socialClass: SocialClass = SocialClass.Poor
    count: int = 0
    avgIncome: float = 0.0  # Phase 9.6 — average income multiplier per person


class ClaimedTile(BaseModel):
    bodyId: str = ""
    tileId: str = ""
    population: list[PopulationTier] = Field(default_factory=list)


# ── Buildings ─────────────────────────────────────────────────────────────────

class BuildingType(IntEnum):
    Mine        = 0
    Farm        = 1
    EnergyPlant = 2
    Research    = 3
    Road        = 4
    SeaPort     = 5
    Spaceport   = 6


class ResourceType(IntEnum):
    Minerals       = 0
    Food           = 1
    Energy         = 2
    ResearchPoints = 3
    Waste          = 4
    Iron           = 5      # Phase 9.5
    Oxygen         = 6      # Phase 9.5
    Water          = 7      # Phase 9.5
    Tech           = 8      # Phase 9.5


# Production par tick pour chaque type de bâtiment (ResourceType → delta par tick)
BUILDING_CONFIGS: dict[BuildingType, dict[ResourceType, float]] = {
    BuildingType.Mine:        {ResourceType.Minerals: 2.0, ResourceType.Waste: 0.5},
    BuildingType.Farm:        {ResourceType.Food: 3.0},
    BuildingType.EnergyPlant: {ResourceType.Energy: 5.0, ResourceType.Waste: 1.0},
    BuildingType.Research:    {ResourceType.Energy: -1.0, ResourceType.ResearchPoints: 1.0},
    BuildingType.Road:        {},   # Phase 9.1 — infrastructure, no production
    BuildingType.SeaPort:     {},   # Phase 9.1
    BuildingType.Spaceport:   {},   # Phase 9.1
}

# Workers required per social class, per building type (Phase 9.6)
EMPLOYMENT_CONFIGS: dict[BuildingType, dict[str, int]] = {
    BuildingType.Mine:        {"Poor": 50, "Middle": 10},
    BuildingType.Farm:        {"Poor": 30, "Middle": 5},
    BuildingType.EnergyPlant: {"Middle": 20, "Rich": 5},
    BuildingType.Research:    {"Middle": 10, "Rich": 15},
    BuildingType.Road:        {},
    BuildingType.SeaPort:     {},
    BuildingType.Spaceport:   {},
}


class BuildingData(BaseModel):
    id: str = ""
    buildingType: BuildingType = BuildingType.Mine
    tileId: str = ""
    bodyId: str = ""
    corpId: str = ""
    workerRatio: float = 1.0
    ticksActive: int = 0
    employmentSlots: dict[str, int] = Field(default_factory=dict)  # Phase 9.6 — keys = SocialClass.name
    level: int = 1  # Phase 12 — building level [1–5]: production × level, workers required × level


# ── Construction queue (Phase 10.5) ──────────────────────────────────────────

class ConstructionStatus(IntEnum):
    Pending    = 0  # waiting in queue
    InProgress = 1  # currently being built (first item only)
    Done       = 2  # completed this tick — transient, used internally


class ConstructionItem(BaseModel):
    id: str = ""                            # UUID
    buildingType: BuildingType = BuildingType.Mine
    tileId: str = ""
    bodyId: str = ""
    corpId: str = ""
    status: ConstructionStatus = ConstructionStatus.Pending
    ticksRemaining: int = 0                 # decremented each tick by constructionPts applied
    totalCostPts: int = 0                   # total construction points needed
    pointsAccumulated: int = 0              # accumulated so far


class TerritoryQueue(BaseModel):
    territoryId: str = ""                   # "{corpId}::{min_tileId}"
    corpId: str = ""
    bodyId: str = ""
    tileIds: list[str] = Field(default_factory=list)    # contiguous tile IDs in territory
    items: list[ConstructionItem] = Field(default_factory=list)
    constructionCapacity: float = 0.0       # sum of EB production this tick
    isEBDeFortune: bool = False             # true when capacity comes from an auto-spawned EB


# Building cost in construction points (Phase 10.5)
BUILDING_CONSTRUCTION_COST: dict[BuildingType, int] = {
    BuildingType.Mine:        50,
    BuildingType.Farm:        40,
    BuildingType.EnergyPlant: 90,
    BuildingType.Research:    90,
    BuildingType.Road:        20,
    BuildingType.SeaPort:     120,
    BuildingType.Spaceport:   240,
}

# Construction points produced per tick by an EB (formal vs de fortune)
EB_FORMAL_CAPACITY:   float = 30.0
EB_FORTUNE_CAPACITY:  float = 10.0
EB_FORTUNE_WOOD_COST: float = 2.0   # Wood units consumed per tick by EB de fortune


# ── Bot Corporations FSM (Phase 11.2) ───────────────────────────────────────

class CorpProfile(IntEnum):
    """Fixed strategic personality assigned at corporation creation (AI only)."""
    Economiste      = 0   # optimise production & marché
    Expansionniste  = 1   # claim agressif de tuiles
    Militariste     = 2   # cible les infrastructures adverses


class BotFSMState(IntEnum):
    """Current FSM state of an AI-controlled corporation."""
    Idle       = 0
    Expanding  = 1   # en train de claim des tuiles
    Building   = 2   # construction en cours prioritaire
    Trading    = 3   # optimisation marchés/contrats
    Raiding    = 4   # guerre économique vs corpo cible


class CorporationData(BaseModel):
    id: str = ""
    name: str = ""
    credits: float = 0.0
    # claimedTiles is an internal runtime field — excluded from API serialization.
    # Corps no longer "own" tiles; population / building-tile tracking is an
    # implementation detail migrated progressively to StateData.
    claimedTiles: list[ClaimedTile] = Field(default_factory=list, exclude=True)
    score: float = 0.0
    isAI: bool = False
    buildings: list[BuildingData] = Field(default_factory=list)
    resources: dict[str, float] = Field(default_factory=dict)
    globalReputation: float = 0.0    # Phase 7.5 — score public visible par tous
    # Phase 11.2 — FSM bot fields (ignored for human players)
    profile: CorpProfile = CorpProfile.Economiste
    fsmState: BotFSMState = BotFSMState.Idle
    fsmThresholds: dict = Field(default_factory=dict)  # overrides for CORP_FSM_DEFAULTS
    # Color fields (computed from id)
    colorR: float = 0.0
    colorG: float = 0.0
    colorB: float = 0.0


# ── Market layer (Phase 7.3) ──────────────────────────────────────────────────

class ResourceListing(BaseModel):
    resourceType: ResourceType = ResourceType.Food
    price: float = 1.0
    supply: float = 0.0
    demand: float = 0.0
    priceVelocity: float = 0.0                                      # Phase 9.4 — fractional price change per tick
    priceHistory: list[float] = Field(default_factory=list)         # Phase 9.4 — last 10 prices


class LocalMarketState(BaseModel):
    territoryId: str = ""                                           # "{ownerEntityId}::{min_tile_id}"
    ownerEntityId: str = ""                                         # corp_id or state_id
    tileIds: list[str] = Field(default_factory=list)                # H3 tile IDs in this territory
    listings: list[ResourceListing] = Field(default_factory=list)
    taxRate: float = 0.0                                            # placeholder — État branché Phase 7.5
    connectivity: float = 1.0                                       # [0,1] — 1.0 normal, <1 partiellement isolé
    tickComputed: int = 0


class GlobalMarketState(BaseModel):
    """Phase 9.5 — Aggregated market state across all territories in a system."""
    systemId: str = ""                                              # e.g. "sol"
    listings: list[ResourceListing] = Field(default_factory=list)   # Aggregated across all local markets
    tick: int = 0                                                    # tick when computed
    marketCount: int = 0                                             # number of local markets aggregated


# ── Contract layer (Phase 7.4) ────────────────────────────────────────────────

class ContractStatus(IntEnum):
    Proposed  = 0
    Active    = 1
    Completed = 2
    Broken    = 3
    Expired   = 4


class ContractVisibility(IntEnum):
    Public  = 0
    Private = 1


class ContractData(BaseModel):
    id: str = ""
    status: ContractStatus = ContractStatus.Proposed
    visibility: ContractVisibility = ContractVisibility.Private
    # Parties
    proposerId: str = ""
    targetId: str = ""          # Private: corp this was sent to
    acceptorId: str = ""        # filled when accepted / bidder confirmed
    candidates: list[str] = Field(default_factory=list)  # corp IDs who bid (Public)
    # Delivery
    resourceType: ResourceType = ResourceType.Food
    resourceAmount: float = 0.0
    deliveredAmount: float = 0.0
    # Finance
    rewardCredits: float = 0.0
    penaltyCredits: float = 0.0
    knowledgeBonus: float = 0.0  # ResearchPoints credited to acceptor on completion
    # Timing
    durationTicks: int = 0      # 0 = open-ended
    startTick: int = 0
    expiresAtTick: int = 0
    # Bidding window (Public)
    biddingWindowTicks: int = 5
    biddingCloseTick: int = 0
    tickCreated: int = 0


# ── State & Reputation layer (Phase 7.5) ────────────────────────────────────

class StateType(IntEnum):
    Capitalist  = 0
    Nationalist = 1
    Alien       = 2


# ── Population Distribution & State Profiles (Phase Colonisation) ─────────────

class PopDistribution(BaseModel):
    """Fractional distribution of population across social classes.
    Values should sum to 1.0. Passed explicitly to seeding functions so the
    distribution can evolve over time (events, policies, tick pressure).
    """
    poor: float = 0.40
    middle: float = 0.59
    rich: float = 0.01


class StateProfile(BaseModel):
    """Preset values for a StateData at bootstrap time.
    Using a named profile speeds up world generation and makes balance tweaks
    easy without touching individual StateData instances.
    """
    popDistribution: PopDistribution = Field(default_factory=PopDistribution)
    literacyRate: float = 0.75     # [0,1] — affects research output, agent efficiency
    taxRate: float = 0.25
    corruptionRate: float = 0.20
    bureaucracy: float = 0.30


STATE_PROFILES: dict[str, StateProfile] = {
    "Standard": StateProfile(
        popDistribution=PopDistribution(poor=0.40, middle=0.59, rich=0.01),
        literacyRate=0.75, taxRate=0.25, corruptionRate=0.20, bureaucracy=0.30,
    ),
    "RicheUtopique": StateProfile(
        popDistribution=PopDistribution(poor=0.01, middle=0.98, rich=0.01),
        literacyRate=1.00, taxRate=0.15, corruptionRate=0.00, bureaucracy=0.10,
    ),
    "EnDeveloppement": StateProfile(
        popDistribution=PopDistribution(poor=0.70, middle=0.28, rich=0.02),
        literacyRate=0.55, taxRate=0.30, corruptionRate=0.40, bureaucracy=0.50,
    ),
    "Pauvre": StateProfile(
        popDistribution=PopDistribution(poor=0.85, middle=0.14, rich=0.01),
        literacyRate=0.35, taxRate=0.35, corruptionRate=0.60, bureaucracy=0.70,
    ),
    "Autoritaire": StateProfile(
        popDistribution=PopDistribution(poor=0.60, middle=0.35, rich=0.05),
        literacyRate=0.65, taxRate=0.45, corruptionRate=0.50, bureaucracy=0.80,
    ),
}


# ── Territory layer (Phase Colonisation) ──────────────────────────────────────

class TerritoryData(BaseModel):
    """A contiguous group of tiles on a body surface owned by a StateData.
    tileIds are H3 cell id strings. The territory has a fixed bodyId so it can
    always be resolved back to its parent planet/moon without extra lookups.
    populationBase is the reference size used when seeding new tiles added to
    this territory after the initial bootstrap.
    """
    id: str = ""
    name: str = ""
    stateId: str = ""
    bodyId: str = ""
    tileIds: list[str] = Field(default_factory=list)
    populationBase: int = 500
    profileKey: str = "Standard"  # key into STATE_PROFILES


class StateData(BaseModel):
    id: str = ""
    name: str = ""
    stateType: StateType = StateType.Capitalist
    tileIds: list[str] = Field(default_factory=list)
    territoryIds: list[str] = Field(default_factory=list)  # Phase Colonisation
    bureaucracy: float = 0.1       # 0..1 — délai multiplicateur sur décisions
    corruptionRate: float = 0.1    # 0..1 — réduit le délai de nationalisation ET modifie l'efficacité de l'État
    toleranceThreshold: float = 0.5  # seuil du score de tolérance au-delà duquel la nationalisation est déclenchée
    taxRate: float = 0.15          # Phase 7.5.1 — taux de taxe propagé aux marchés locaux couverts par cet État
    literacyRate: float = 0.75     # Phase Colonisation — [0,1] taux d'alphabétisation
    profileKey: str = "Standard"   # Phase Colonisation — clé du StateProfile utilisé au bootstrap
    isAiControlled: bool = False   # True → un agent LLM pilote cet état (Phase 8.5)
    # ── Vassal / soumission system ────────────────────────────────────────────
    isVassal: bool = False         # True → créé par une mission de colonisation corpo
    vassalCorpId: str | None = None  # corpo fondatrice (si isVassal=True) ou corpo dominante
    # loyalty[corpId] = [0..1] — score de loyauté bilatéral corpo→état
    # Monte via quêtes/contrats tenus/aide en crise, baisse via trahison/rupture
    loyalty: dict[str, float] = Field(default_factory=dict)


class StateTileColorDto(BaseModel):
    """DTO for state tile colors returned by /game/bodies/{body_id}/state-tile-colors."""
    tileId: str = ""
    stateId: str = ""
    stateName: str = ""
    profileKey: str = ""
    colorR: float = 0.0
    colorG: float = 0.0
    colorB: float = 0.0


class OwnershipTileDto(BaseModel):
    """DTO for ownership tile colors returned by /bodies/{body_id}/ownership-tiles."""
    tileId: str = ""
    corpId: str = ""
    colorR: float = 0.0
    colorG: float = 0.0
    colorB: float = 0.0

class ReputationEventReason(IntEnum):
    ContractCompleted         = 0
    ContractBroken            = 1
    NationalizationTriggered  = 2
    NationalizationCancelled  = 3
    CorruptionDetected        = 4


class ReputationEvent(BaseModel):
    sourceId: str = ""        # entité qui cause l'événement (corp, État)
    targetId: str = ""        # entité dont la réputation évolue
    deltaGlobal: float = 0.0
    deltaBilateral: float = 0.0
    reason: ReputationEventReason = ReputationEventReason.ContractCompleted
    tick: int = 0


class NationalizationProcess(BaseModel):
    id: str = ""
    stateId: str = ""
    corpId: str = ""
    tileId: str = ""
    startTick: int = 0
    completionTick: int = 0
    cancelled: bool = False


class ScoreboardEntry(BaseModel):
    corpId: str = ""
    corpName: str = ""
    credits: float = 0.0
    tileCount: int = 0
    globalReputation: float = 0.0
    score: float = 0.0


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


# Reference preset atmospheres (used by bootstrap() and tests)
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


class SpeciesData(BaseModel):
    """One species population on a tile.
    density is the current population fraction [0, 1].
    marketOutput maps resource names to per-tick output multiplied by density.
    minVegetation is the required vegetation coverage for animal species.
    """
    speciesId: str = ""
    density: float = 0.0           # current population density [0, 1]
    minTemp: float = 0.0           # minimum viable temperature (°C)
    maxTemp: float = 50.0          # maximum viable temperature (°C)
    minO2: float = 0.0             # minimum viable O₂ fraction [0, 1]
    maxO2: float = 1.0             # maximum viable O₂ fraction [0, 1]
    growthRate: float = 0.01       # density increase per tick when conditions met
    marketOutput: dict[str, float] = Field(default_factory=dict)  # resource → per-tick base output
    minVegetation: float = 0.0     # required vegetation coverage (for animals)


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
    - species: list of active SpeciesData populations (replaces legacy vegetationDensity/wildlifeDensity).
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
    species: list[SpeciesData] = Field(default_factory=list)  # active species populations
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
    # ── Ecology (Phase 11.5) ────────────────────────────────────────────────
    ecologyResources: dict[str, float] = Field(default_factory=dict)  # aggregated species output per tick

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


# ── Trade routes & expeditions (Phase 9.1) ────────────────────────────────────

class TradeRouteType(IntEnum):
    Land     = 0
    Maritime = 1
    Orbital  = 2


class TradeRouteActivityStatus(IntEnum):
    Active    = 0
    Suspended = 1


class ExpeditionStatus(IntEnum):
    InTransit = 0
    Success   = 1
    Failed    = 2


class TradeRoute(BaseModel):
    id: str = ""
    routeType: TradeRouteType = TradeRouteType.Land
    fromTileId: str = ""
    toTileId: str = ""
    bodyId: str = ""
    pathTileIds: list[str] = Field(default_factory=list)
    ownerCorpId: str = ""
    knownByEntityIds: list[str] = Field(default_factory=list)
    status: TradeRouteActivityStatus = TradeRouteActivityStatus.Active
    baseEfficiency: float = 1.0
    currentEfficiency: float = 1.0
    portMalusFrom: float = 0.0
    portMalusTo: float = 0.0
    tickCreated: int = 0
    knowledgeTransferTicks: int = 0


class ExpeditionUnit(BaseModel):
    id: str = ""
    ownerCorpId: str = ""
    fromPortTileId: str = ""
    toPortTileId: str = ""
    bodyId: str = ""
    routeType: TradeRouteType = TradeRouteType.Land
    ticksRemaining: int = 0
    totalTicks: int = 0
    pathTileIds: list[str] = Field(default_factory=list)
    status: ExpeditionStatus = ExpeditionStatus.InTransit
    isPhantom: bool = False
    cargo: dict[str, float] = Field(default_factory=dict)  # Phase 9.6 — keys = ResourceType.name


# ── Gameplay Events (Phase 8) ─────────────────────────────────────────────────

# ── Agent LLM (Phase 8.5) ────────────────────────────────────────────────────────

class AgentActionType(IntEnum):
    """Actions an LLM/FSM agent can dispatch for a State or Corporation entity."""
    NoOp                  = 0
    ProposeContract       = 1
    SetTolerance          = 2
    TriggerNationalization = 3
    # Phase 11.2 — Corporation FSM actions
    ClaimTile             = 10
    ConstructBuilding     = 11
    UpdateFsmThresholds   = 12
    ReorderConstructionQueue = 13


class AgentAction(BaseModel):
    """Single decision returned by the LLM agent for an entity."""
    entityId:   str = ""
    actionType: AgentActionType = AgentActionType.NoOp
    params:     dict = Field(default_factory=dict)  # action-specific payload
    reasoning:  str = ""                           # LLM explanation (debug)


class AgentMemory(BaseModel):
    """Per-entity rolling memory kept in-process (not persisted in MVP)."""
    entityId:          str = ""
    entityType:        str = "state"                    # "state" | "corporation"
    recentDecisions:   list[str] = Field(default_factory=list)  # max 5 — chronological
    relationshipNotes: dict = Field(default_factory=dict)       # other_entity_id → note
    lastTickActed:     int = 0


# ── Gameplay Events (Phase 8) ─────────────────────────────────────────────────────

class EventType(IntEnum):
    """Narrative gameplay events — distinct from SimulationEventType (engine events)."""
    RencontreAlienne        = 0
    TempeteSolaire          = 1
    DecouverteMiniere       = 2
    CriseEconomique         = 3
    SabotageCorpo           = 4
    Rebellion               = 5
    MigrationPopulation     = 6
    DecouverteMegastructure = 7
    EmpireGalactique        = 8


class EventEffect(BaseModel):
    """Quantified side-effect attached to an EventData."""
    resourceType: str = ""          # ResourceType.name or "" when N/A
    resourceDelta: float = 0.0      # positive = gain, negative = loss
    creditsDelta: float = 0.0
    reputationDelta: float = 0.0    # applied to ownerCorpId reputation
    populationDelta: float = 0.0


class EventData(BaseModel):
    id: str = ""
    eventType: EventType = EventType.RencontreAlienne
    name: str = ""
    description: str = ""
    tick: int = 0
    affectedEntityId: str = ""      # corp_id, state_id, or tile_id
    affectedEntityType: str = ""    # "corporation" | "state" | "tile" | ""
    effect: EventEffect = Field(default_factory=EventEffect)
    isResolved: bool = False