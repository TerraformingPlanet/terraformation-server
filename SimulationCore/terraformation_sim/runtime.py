"""runtime.py — Thin orchestrator for InMemorySimulationRuntime.

All domain logic is delegated to mixin classes. This file owns:
  - __init__ (state initialisation)
  - stop / tick loop
  - Region/projection/world-state read-write
  - Admin registry endpoints
"""
from __future__ import annotations

import json
import math
import os
import random
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .logic.corp_fsm import CorpSimSnapshot

from .logic import (
    aggregate_tile_deltas,
    apply_modifier_to_cell,
    apply_natural_growth,
    apply_region_progress,
    can_apply_action,
    compute_atmospheric_state,
    compute_body_position_at_tick,
    compute_equilibrium_temperature,
    compute_planetary_irradiance,
    compute_tile_irradiance,
    generate_interior_cells,
    generate_spherical_tiles,
    GENERATION_VERSION,
    NATURAL_GROWTH_INTERVAL,
    process_pending_actions,
    queue_action,
    spectral_type_to_luminosity,
    summarize_region_cells,
    summarize_spherical_tiles,
    terraform_action_definitions,
    _body_h3_resolution,
)
from .models import (
    AgentAction,
    AgentActionType,
    AgentMemory,
    AnyBodyState,
    AtmosphericComposition,
    AtmosphericGas,
    ATMOSPHERE_PRESETS,
    AtmosphericState,
    BodyBase,
    BodyType,
    BuildingData,
    ClaimedTile,
    ConstructionItem,
    ConstructionStatus,
    ContractData,
    ContractStatus,
    ContractVisibility,
    CorpProfile,
    CorporationData,
    DebugCoherenceOverride,
    EcoMarketState,
    EcoStockListing,
    EventData,
    EventEffect,
    EventType,
    ExpeditionStatus,
    ExpeditionUnit,
    GalacticPosition,
    GlobalMarketState,
    HexGridDebugSummary,
    HexStateModifier,
    InteriorZoneState,
    LocalMarketState,
    NationalizationProcess,
    OrbitalParameters,
    PendingTerraformAction,
    PopDistribution,
    ProjectionDebugSummary,
    ProjectionState,
    RegionState,
    ReputationEvent,
    ReputationEventReason,
    ResourceListing,
    RouteStatus,
    ScoreboardEntry,
    SimulationCellAddress,
    SimulationCellState,
    SimulationCoherenceState,
    SimulationCoordinates,
    SimulationEvent,
    SimulationEventType,
    SimulationSoilState,
    SimulationVector2State,
    SimulationWeatherState,
    SolarSystemState,
    SpaceTravel,
    SphericalBodyState,
    STATE_PROFILES,
    StateData,
    StateProfile,
    StateType,
    StellarRoute,
    TICKS_PER_LIGHT_YEAR,
    TerraformAction,
    TerraformActionDefinition,
    TerritoryData,
    TerritoryQueue,
    TerrainClass,
    TerrainType,
    TileBioListing,
    TileBioMarketState,
    TradeRoute,
    TradeRouteActivityStatus,
    TradeRouteType,
    TravelStatus,
    WaterClassification,
    WorldLayer,
    WorldState,
    ZoneType,
    _corp_color_rgb,
    _state_color_rgb,
    BUILDING_CONSTRUCTION_COST,
    EB_FORMAL_CAPACITY,
    EB_FORTUNE_CAPACITY,
    SubHexFeatureDef,
)
from .registry import BUILDING_REGISTRY, RESOURCE_REGISTRY
from .persistence import CellMutation, InMemoryRepository, SavedState, StateRepository
from .logic.market import auto_init_tile_population  # re-exported for test compat

# Domain mixins
from .runtime_corps import CorpsMixin
from .runtime_contracts import ContractsMixin
from .runtime_states import StatesMixin
from .runtime_events import EventsMixin
from .runtime_agent import AgentMixin
from .runtime_expeditions import ExpeditionsMixin
from .runtime_market import MarketMixin
from .runtime_buildings import BuildingsMixin
from .runtime_bodies import BodiesMixin
from .runtime_galaxy import GalaxyMixin
from .runtime_bootstrap import BootstrapMixin
from .runtime_rivers import RiversMixin


# ── Module-level helpers ───────────────────────────────────────────────────────

def _hydrate_tiles_from_db(tile_rows: list[dict]) -> "list":
    """Reconstruct GoldbergTileState objects from normalised DB rows."""
    import json as _json
    import h3 as _h3
    from .models import GoldbergTileState, TerrainType, WaterClassification, TerrainClass, PopulationTier, SocialClass
    from .logic.generation import seed_species_for_tile

    tiles = []
    for row in tile_rows:
        tile_id = row["tile_id"]
        neighbors = sorted(set(_h3.grid_disk(tile_id, 1)) - {tile_id})
        boundary = [[lat_v, lng_v] for lat_v, lng_v in _h3.cell_to_boundary(tile_id)]
        t_type = TerrainType[row["terrain_type"]]
        w_class = WaterClassification[row["water_classification"]]
        t_class = TerrainClass[row["terrain_class"]]
        # Deserialize persisted population tiers
        try:
            pop_data = _json.loads(row.get("population_json") or "[]")
            population = [
                PopulationTier(
                    socialClass=SocialClass[p["socialClass"]],
                    count=p["count"],
                    avgIncome=p.get("avgIncome", 0.0),
                )
                for p in pop_data if p.get("count", 0) > 0
            ]
        except Exception:
            population = []
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
            population=population,
        ))
    return tiles


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


# Attenuation factor per route type (mirrors _EXPEDITION_CONFIG in logic/expeditions.py)
_EXPEDITION_CONFIG_ATTENUATION: dict[str, float] = {
    "Land":     0.7,
    "Maritime": 0.8,
    "Orbital":  0.9,
}


# Biome mutation tick interval (every 5 ticks)
BIOME_TICK_INTERVAL = 5

# ── Orchestrator ───────────────────────────────────────────────────────────────

class InMemorySimulationRuntime(
    CorpsMixin,
    ContractsMixin,
    StatesMixin,
    EventsMixin,
    AgentMixin,
    ExpeditionsMixin,
    MarketMixin,
    BuildingsMixin,
    BodiesMixin,
    GalaxyMixin,
    BootstrapMixin,
    RiversMixin,
):
    """Thin orchestrator: owns state, tick loop, region/projection, and admin registry.

    All domain logic lives in the mixin classes above.
    """

    def __init__(
        self,
        tick_interval_seconds: float = 5.0,
        auto_resume: bool = False,
        repository: StateRepository | None = None,
    ) -> None:
        self._tick_interval_seconds = max(0.1, tick_interval_seconds)
        self._speed_multiplier = 1
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._tick_running = auto_resume
        self._tick_count = 0
        self._world_state = WorldState()
        self._region_cells: list[SimulationCellState] = []
        self._pending_actions: list[PendingTerraformAction] = []
        self._last_event = SimulationEvent(
            eventId=str(uuid4()),
            type=SimulationEventType.SnapshotCaptured,
            message="Runtime initialized",
        )
        # Body registry
        self._bodies: dict[str, AnyBodyState] = {}
        self._active_body_id: str = ""
        # Galaxy registry
        self._solar_systems: dict[str, SolarSystemState] = {}
        self._stellar_routes: dict[str, StellarRoute] = {}
        self._space_travels: dict[str, SpaceTravel] = {}
        self._repo: StateRepository = repository or InMemoryRepository()
        # LOD tile cache
        self._lod_tile_cache: dict = {}
        # Region mutation cache
        self._region_mutations: dict[str, dict[tuple[int, int], tuple[float, float]]] = {}
        # Corporation registry (Phase 7.1)
        self._corporations: dict[str, CorporationData] = {}
        self._tile_ownership: dict[str, dict[str, str]] = {}
        # Building registry (Phase 7.2)
        self._buildings: dict[str, BuildingData] = {}
        # Market registry (Phase 7.3)
        self._markets: dict[str, LocalMarketState] = {}
        # Eco-market registry (Phase 11.6)
        self._eco_markets: dict[str, EcoMarketState] = {}
        # Biome transition rules cache (Phase biome mutation)
        self._biome_rules_cache: list | None = None
        self._eco_extractions: dict[str, dict[str, float]] = {}
        # Bio-market per-tile history (Phase 11.6b)
        self._bio_tile_history: dict[str, dict[str, list[float]]] = {}
        # Contract registry (Phase 7.4)
        self._contracts: dict[str, ContractData] = {}
        # State & Reputation registries (Phase 7.5)
        self._states: dict[str, StateData] = {}
        self._reputations: dict[tuple[str, str], float] = {}
        self._nationalizations: dict[str, NationalizationProcess] = {}
        # Gameplay event log (Phase 8)
        self._game_events: list[EventData] = []
        self._event_rng: random.Random = random.Random()
        # Agent LLM memories (Phase 8.5)
        self._agent_memories: dict[str, AgentMemory] = {}
        # GM Narrative state (Phase 11.3)
        self._gm_cooldown_tick: int = 0
        self._gm_last_lever: str = ""
        # Terrain type definitions cache
        self._terrain_type_defs: dict[int, dict] = {}
        # Trade Routes & Expedition registry (Phase 9.2)
        self._trade_routes: dict[str, TradeRoute] = {}
        self._expeditions: dict[str, ExpeditionUnit] = {}
        self._expedition_rng: random.Random = random.Random()
        # Construction queue registry (Phase 10.5)
        self._construction_queues: dict[str, TerritoryQueue] = {}
        # Territory registry (Phase Colonisation)
        self._territories: dict[str, TerritoryData] = {}
        self._territory_tile_index: dict[str, str] = {}
        # WebSocket broadcast callback (Phase 10)
        self._ws_broadcast_callback: "Callable[[dict], None] | None" = None
        # Atmospheric event tracking (Phase 3)
        self._last_habitability_bucket: int = -1
        self._atmosphere_formed_fired: bool = False
        self._prev_avg_temp: float = 0.0
        self._temp_stable_ticks: int = 0
        # River arrival ticks index: body_id → {tile_id → tick_when_river_arrived}
        self._river_arrival_ticks: dict[str, dict[str, int]] = {}

        saved = self._repo.load()
        if saved.has_data:
            self._hydrate_from_saved(saved)
            # SERVER_AUTO_RESUME force le tick même si la sauvegarde l'avait arrêté
            if auto_resume:
                self._tick_running = True
                self._world_state.tickRunning = True
        else:
            self.bootstrap()
        self._thread = threading.Thread(target=self._tick_loop, name="SimulationRuntime", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def set_ws_broadcast_callback(self, callback: "Callable[[dict], None]") -> None:
        """Register a sync callable called every tick with the broadcast payload (Phase 10)."""
        with self._lock:
            self._ws_broadcast_callback = callback

    def health(self) -> dict:
        """Return a basic health/status dict for the /health endpoint."""
        with self._lock:
            return {
                "status": "ok",
                "tickCount": self._tick_count,
                "tickRunning": self._tick_running,
                "tickIntervalSeconds": self._tick_interval_seconds,
                "activePlanetName": self._world_state.activePlanetName,
                "hasProjection": self._world_state.hasProjection,
                "hasRegion": self._world_state.hasRegion,
            }

    # ── Tick loop ──────────────────────────────────────────────────────────────

    def _tick_loop(self) -> None:
        while not self._stop_event.wait(self._tick_interval_seconds):
            with self._lock:
                if self._tick_running:
                    self._advance_tick_locked()

    def _advance_tick_locked(self) -> None:
        self._tick_count += 1
        self._world_state.tickCount = self._tick_count
        self._world_state.tickRunning = self._tick_running

        if self._world_state.hasRegion:
            region = self._world_state.region
            self._region_cells, self._pending_actions = process_pending_actions(
                self._region_cells, self._pending_actions
            )
            if self._region_cells:
                co2 = region.atmosphericState.co2Ratio if region.atmosphericState.co2Ratio > 0 else 0.0004
                greenhouse_k = co2 * 150.0 * 0.005
                for index, cell in enumerate(self._region_cells):
                    cell.temperature += 0.04 if index % 3 == 0 else 0.01
                    cell.temperature += greenhouse_k
                    cell.waterRatio = _clamp01(cell.waterRatio + (0.004 if index % 4 == 0 else 0.001))
                    cell.flowAccumulation = min(999, cell.flowAccumulation + (1 if index == 0 else 0))
                    self._region_cells[index] = cell

            if region.hasSelectedCell and self._region_cells:
                cell = self._region_cells[0]
                cell.temperature += 0.08
                cell.waterRatio = _clamp01(cell.waterRatio + 0.003)
                cell.flowAccumulation = min(999, cell.flowAccumulation + 1)
                self._region_cells[0] = cell

            region = apply_region_progress(region, self._region_cells)
            region.atmosphericState = compute_atmospheric_state(self._region_cells)
            self._world_state.region = region

            self._last_event = self._check_climate_events(region) or SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.TickAdvanced,
                tickCount=self._tick_count,
                message="Tick advanced",
                hasRegion=True,
                coordinates=region.coordinates,
            )
        else:
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.TickAdvanced,
                tickCount=self._tick_count,
                message="Tick advanced",
                hasRegion=False,
            )

        # Domain tick processors (delegated to mixins)
        self._process_building_production()
        self._process_construction_tick_locked()
        self._process_market_tick_locked()
        self._process_expedition_tick_locked()
        self._process_contract_tick_locked()
        self._process_reputation_tick_locked()
        self._process_event_tick_locked()
        self._process_ecology_tick_locked()
        self._process_eco_market_tick_locked()
        self._process_bot_tick_locked()
        self._process_biome_tick_locked()
        self._process_river_tick_locked()
        self._tick_natural_growth_locked()

        # World agent cycle (Phase 11.1)
        agent_interval = int(os.environ.get("WORLD_AGENT_TICK_INTERVAL",
                                            os.environ.get("AGENT_TICK_INTERVAL", "10")))
        if self._tick_count % agent_interval == 0:
            threading.Thread(
                target=self.run_world_agent_cycle,
                args=("periodic",),
                daemon=True,
                name="world-agent-cycle",
            ).start()

        # Persist every 10 ticks
        if self._tick_count % 10 == 0:
            self._repo.save_world_state(self._world_state, self._tick_interval_seconds)
            for corp in self._corporations.values():
                self._repo.save_corporation(corp)
            for market in self._markets.values():
                self._repo.save_market(market)
            for queue in self._construction_queues.values():
                self._repo.save_construction_queue(queue)
            for exp in self._expeditions.values():
                self._repo.save_expedition(exp)

        # Space travel arrivals
        for travel in list(self._space_travels.values()):
            if travel.status == TravelStatus.InTransit and self._tick_count >= travel.arrivalTick:
                travel.status = TravelStatus.Arrived
                self._repo.save_space_travel(travel)

        # WebSocket broadcast (Phase 10)
        if self._ws_broadcast_callback is not None:
            try:
                self._ws_broadcast_callback({"type": "tick_advanced", "tick": self._tick_count})
            except Exception:
                pass

    def _check_climate_events(self, region: "RegionState") -> "SimulationEvent | None":
        """Emit climate threshold events (Phase 3 — ported from SDK ClimateEvents)."""
        atm = region.atmosphericState

        if not self._atmosphere_formed_fired and atm.atmosphericPressure > 10.0:
            self._atmosphere_formed_fired = True
            return SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.AtmosphereFormed,
                tickCount=self._tick_count,
                message=f"Atmosphere formed — pressure {atm.atmosphericPressure:.1f} kPa",
                hasRegion=True,
                coordinates=region.coordinates,
            )

        score = atm.habitabilityScore
        bucket = 0 if score < 0.25 else (1 if score < 0.50 else (2 if score < 0.75 else (3 if score < 1.0 else 4)))
        if bucket != self._last_habitability_bucket and self._last_habitability_bucket >= 0:
            self._last_habitability_bucket = bucket
            threshold = [0.25, 0.50, 0.75, 1.0][min(bucket, 3)]
            return SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.HabitabilityThreshold,
                tickCount=self._tick_count,
                message=f"Habitability crossed {threshold * 100:.0f}% — score {score:.3f}",
                hasRegion=True,
                coordinates=region.coordinates,
            )
        if self._last_habitability_bucket < 0:
            self._last_habitability_bucket = bucket

        avg_temp = atm.averageTemperature
        if abs(avg_temp - self._prev_avg_temp) < 0.5:
            self._temp_stable_ticks += 1
        else:
            self._temp_stable_ticks = 0
        self._prev_avg_temp = avg_temp
        if self._temp_stable_ticks == 10:
            return SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ThermalEquilibrium,
                tickCount=self._tick_count,
                message=f"Thermal equilibrium reached — avg {avg_temp:.1f}°C",
                hasRegion=True,
                coordinates=region.coordinates,
            )

        return None

    # ── Biome mutation processor ───────────────────────────────────────────────

    def _process_biome_tick_locked(self) -> None:
        """Apply biome transitions every BIOME_TICK_INTERVAL ticks."""
        if self._tick_count % BIOME_TICK_INTERVAL != 0:
            return

        # Get active body tiles
        if not self._active_body_id:
            return
        tiles = self._repo.load_tiles(self._active_body_id)
        if not tiles:
            return

        # Evaluate biome transitions
        from .logic.mutations import evaluate_biome_transitions
        from .models import GoldbergTileState
        tile_models = [GoldbergTileState.model_validate(t) if isinstance(t, dict) else t for t in tiles]
        rules = self._get_biome_rules_cached()
        mutations = evaluate_biome_transitions(tile_models, rules)

        # Apply mutations to DB
        for tile_id, new_terrain_type in mutations:
            self._repo.update_tile_fields(
                self._active_body_id, tile_id, terrain_type=new_terrain_type.name
            )

    # ── Projection & region ────────────────────────────────────────────────────

    def _tick_natural_growth_locked(self) -> None:
        """Apply natural population growth to all terrestrial tiles every NATURAL_GROWTH_INTERVAL ticks.

        1 tick = 1 day  →  NATURAL_GROWTH_INTERVAL = 270 ticks ≈ 9 months.
        food_per_capita is estimated from the state that owns the tile; defaults to 0.5
        when no state resource data is available (no starvation, no abundance).
        Operates on every loaded SphericalBodyState so future planets work automatically.
        Lock must be held.
        """
        if self._tick_count % NATURAL_GROWTH_INTERVAL != 0:
            return

        for body in self._bodies.values():
            if not body.tiles:
                continue
            # Build a fast state→food lookup: total food / total population in that state
            state_food: dict[str, float] = {}
            for state in self._states.values():
                # Sum corp resources that fall within this state's tiles
                food = 0.0
                for corp in self._corporations.values():
                    for ct in corp.claimedTiles:
                        if ct.tileId in state.tileIds:
                            food += corp.resources.get("Food", 0.0)
                            break
                state_food[state.id] = food

            updated_tiles: list = []
            for tile in body.tiles:
                if not tile.population:
                    updated_tiles.append(tile)
                    continue
                # Find the owning state (if any) for food_per_capita
                state_id = getattr(tile, "stateId", "") or ""
                food = state_food.get(state_id, 0.0)
                total_pop = sum(t.count for t in tile.population)
                food_per_capita = min(1.0, food / max(1, total_pop))
                updated_tiles.append(apply_natural_growth(tile, food_per_capita))

            body.tiles = updated_tiles

    def _build_projection_state(
        self,
        planet_name: str,
        projection_override: DebugCoherenceOverride,
        projection_water_level: float,
    ) -> ProjectionState:
        base_water = _clamp01(0.52 + projection_water_level)
        summary = ProjectionDebugSummary(
            cols=48, rows=24, totalCells=1152,
            dryCells=312, coastCells=184, inlandWaterCells=98,
            openOceanCells=402, frozenWaterCells=34,
            rockTerrainCells=328, iceTerrainCells=52,
            toxicTerrainCells=24, waterTerrainCells=488,
            vegetationTerrainCells=210, metalTerrainCells=50,
            averageWaterRatio=base_water, averageTemperature=12.4,
        )
        return ProjectionState(
            isValid=True,
            planetName=planet_name,
            projectionOverride=projection_override,
            projectionWaterLevel=projection_water_level,
            summary=summary,
        )

    def _build_region_state(
        self,
        planet_name: str,
        coordinates: SimulationCoordinates,
        tick_count: int,
    ) -> RegionState:
        latitude_bias = math.cos(coordinates.latitude * math.pi)
        longitude_bias = math.sin(coordinates.longitude * math.pi)
        projected_water_ratio = _clamp01(0.45 + latitude_bias * 0.15 + longitude_bias * 0.1)
        deserticity = _clamp01(0.55 - projected_water_ratio * 0.6)
        oceanicity = _clamp01(projected_water_ratio * 0.95)
        frigidity = _clamp01(0.15 + (1.0 - abs(coordinates.latitude - 0.5) * 2.0) * 0.1)
        average_temperature = 18.0 - abs(coordinates.latitude - 0.5) * 42.0 + tick_count * 0.03
        terraformation_progress = _clamp01(0.14 + tick_count * 0.0025)

        selected_cell = SimulationCellState(
            address=SimulationCellAddress(q=3, r=-1),
            terrainName="Coastal Shelf" if projected_water_ratio > 0.48 else "Dry Basin",
            terrainType=TerrainType.Eau if projected_water_ratio > 0.5 else TerrainType.Roche,
            layer=WorldLayer.Surface,
            altitude=0.42,
            temperature=average_temperature + 1.2,
            waterRatio=_clamp01(projected_water_ratio + 0.08),
            toxinLevel=0.04,
            windVector=SimulationVector2State(x=0.8, y=0.2),
            windSpeed=0.34,
            rainShadow=False,
            hasRiver=projected_water_ratio > 0.42,
            flowAccumulation=8 + tick_count,
            terrainClass=TerrainClass.Channel if projected_water_ratio > 0.42 else TerrainClass.Basin,
            waterClassification=WaterClassification.Coast if projected_water_ratio > 0.5 else WaterClassification.InlandWater,
            hasDownstream=True,
            downstream=SimulationCellAddress(q=4, r=-1),
            hasOverflowOutlet=True,
            overflowOutlet=SimulationCellAddress(q=5, r=0),
            soil=SimulationSoilState(
                rockHardness=0.46, organicContent=0.32, porosity=0.52,
                mineralDensity=0.41, toxicSoil=False, thermalConductivity=0.28,
            ),
        )

        self._region_cells = self._build_region_cells(selected_cell, projected_water_ratio, average_temperature)
        self._pending_actions = []

        summary = HexGridDebugSummary(
            totalCells=91, dryCells=24, coastCells=14, inlandWaterCells=11,
            openOceanCells=16, frozenWaterCells=2, ridgeCells=10, basinCells=13,
            channelCells=15, sourceCells=4, riverCells=9, downstreamCells=18,
            overflowCells=3, rockTerrainCells=28, iceTerrainCells=3,
            toxicTerrainCells=2, waterTerrainCells=30, vegetationTerrainCells=22,
            metalTerrainCells=6, averageWaterRatio=projected_water_ratio,
            averageTemperature=average_temperature,
            maxFlowAccumulation=max(
                (cell.flowAccumulation for cell in self._region_cells),
                default=selected_cell.flowAccumulation,
            ),
        )

        region = RegionState(
            isValid=True,
            seed=42042,
            planetName=planet_name,
            coordinates=coordinates,
            terraformationProgress=terraformation_progress,
            weather=SimulationWeatherState(
                prevailingWindDirection=SimulationVector2State(x=0.8, y=0.2),
                prevailingWindSpeed=0.34,
                precipitationRate=_clamp01(projected_water_ratio + 0.12),
                temperatureOffset=-4.0 + latitude_bias * 6.0,
                seasonalModifier=0.18,
            ),
            coherence=SimulationCoherenceState(
                dominantTerrainType=TerrainType.Eau if projected_water_ratio > 0.5 else TerrainType.Roche,
                projectedWaterRatio=projected_water_ratio,
                oceanicity=oceanicity,
                deserticity=deserticity,
                frigidity=frigidity,
                isExtremeOcean=projected_water_ratio > 0.85,
                isExtremeArid=projected_water_ratio < 0.08,
                isExtremeFrozen=average_temperature < -15.0,
            ),
            summary=summary,
            hasSelectedCell=True,
            selectedCell=selected_cell,
        )
        region = apply_region_progress(region, self._region_cells)
        region.atmosphericState = compute_atmospheric_state(self._region_cells)
        return region

    def _build_region_cells(
        self,
        selected_cell: SimulationCellState,
        projected_water_ratio: float,
        average_temperature: float,
    ) -> list[SimulationCellState]:
        cells = [selected_cell.model_copy(deep=True)]
        for index in range(1, 24):
            dryness = index / 24.0
            water_ratio = _clamp01(projected_water_ratio + 0.18 - dryness * 0.28)
            temperature = average_temperature + 3.0 - dryness * 9.0
            terrain_type = (
                TerrainType.Vegetation if water_ratio > 0.42 and temperature > 4.0
                else (TerrainType.Eau if water_ratio > 0.58 else TerrainType.Roche)
            )
            water_classification = (
                WaterClassification.OpenOcean if water_ratio > 0.8
                else (WaterClassification.Coast if water_ratio > 0.45 else WaterClassification.Dry)
            )
            cells.append(SimulationCellState(
                address=SimulationCellAddress(q=index % 6, r=-(index // 6)),
                terrainName=(
                    "Vegetated Shelf" if terrain_type == TerrainType.Vegetation
                    else ("Water Shelf" if terrain_type == TerrainType.Eau else "Rock Shelf")
                ),
                terrainType=terrain_type,
                layer=WorldLayer.Surface,
                altitude=_clamp01(0.25 + dryness * 0.45),
                temperature=temperature,
                waterRatio=water_ratio,
                toxinLevel=0.02 if index % 7 else 0.08,
                windVector=SimulationVector2State(x=0.8, y=0.2),
                windSpeed=0.24 + dryness * 0.18,
                rainShadow=index % 5 == 0,
                hasRiver=water_ratio > 0.48 and index % 3 == 0,
                flowAccumulation=2 + index,
                terrainClass=TerrainClass.Channel if water_ratio > 0.4 else TerrainClass.Ridge,
                waterClassification=water_classification,
                hasDownstream=index % 4 != 0,
                downstream=SimulationCellAddress(q=(index + 1) % 6, r=-((index + 1) // 6)),
                hasOverflowOutlet=index % 6 == 0,
                overflowOutlet=SimulationCellAddress(q=(index + 2) % 6, r=-((index + 2) // 6)),
                soil=SimulationSoilState(
                    rockHardness=_clamp01(0.3 + dryness * 0.4),
                    organicContent=_clamp01(0.5 - dryness * 0.35),
                    porosity=_clamp01(0.58 - dryness * 0.18),
                    mineralDensity=_clamp01(0.22 + dryness * 0.4),
                    toxicSoil=index % 11 == 0,
                    thermalConductivity=_clamp01(0.18 + dryness * 0.2),
                ),
            ))
        return cells

    # ── World state / projection public API ───────────────────────────────────

    def world_state(self) -> WorldState:
        with self._lock:
            return self._world_state.model_copy(deep=True)

    def projection_state(self) -> ProjectionState:
        with self._lock:
            return self._world_state.projection.model_copy(deep=True)

    def region_state(self) -> RegionState:
        with self._lock:
            return self._world_state.region.model_copy(deep=True)

    def last_event(self) -> SimulationEvent:
        with self._lock:
            return self._last_event.model_copy(deep=True)

    def tick_status(self) -> dict:
        with self._lock:
            return {
                "tickCount": self._tick_count,
                "tickRunning": self._tick_running,
                "tickIntervalSeconds": self._tick_interval_seconds,
                "speedMultiplier": self._speed_multiplier,
            }

    def set_projection(
        self,
        projection_override: DebugCoherenceOverride,
        water_level: float,
    ) -> WorldState:
        with self._lock:
            planet_name = self._world_state.activePlanetName or "Astra-Prime"
            water_level = max(0.0, min(1.0, water_level))
            projection = self._build_projection_state(planet_name, projection_override, water_level)
            self._world_state.projection = projection
            self._world_state.hasProjection = True
            self._world_state.projectionOverride = projection_override
            self._world_state.projectionWaterLevel = water_level
            if self._active_body_id and self._active_body_id in self._bodies:
                body = self._bodies[self._active_body_id]
                if isinstance(body, SphericalBodyState):
                    body.projectionOverride = projection_override
                    body.waterLevel = water_level
                    body.tiles = []
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ProjectionLoaded,
                tickCount=self._tick_count,
                message=f"Projection changed to {projection_override.name}, waterLevel={water_level:.2f}",
                hasRegion=self._world_state.hasRegion,
                coordinates=self._world_state.region.coordinates if self._world_state.hasRegion else SimulationCoordinates(),
            )
            self._repo.save_world_state(self._world_state, self._tick_interval_seconds)
            if self._active_body_id and self._active_body_id in self._bodies:
                self._repo.save_body(self._bodies[self._active_body_id])
            return self._world_state.model_copy(deep=True)

    def action_definitions(self) -> list[TerraformActionDefinition]:
        with self._lock:
            definitions = terraform_action_definitions()
            return [definitions[action].model_copy(deep=True) for action in sorted(definitions.keys(), key=int)]

    def open_region(self, latitude: float, longitude: float) -> RegionState:
        with self._lock:
            coordinates = SimulationCoordinates(
                latitude=_clamp01(latitude), longitude=_clamp01(longitude)
            )
            region = self._build_region_state(
                self._world_state.activePlanetName or "Astra-Prime", coordinates, self._tick_count
            )
            region_key = f"{coordinates.latitude:.3f},{coordinates.longitude:.3f}"
            pending = self._region_mutations.get(region_key)
            if pending:
                for i, cell in enumerate(self._region_cells):
                    k = (cell.address.q, cell.address.r)
                    if k in pending:
                        w_delta, t_delta = pending[k]
                        self._region_cells[i] = apply_modifier_to_cell(
                            cell, HexStateModifier(waterDelta=w_delta, tempDelta=t_delta)
                        )
                region = apply_region_progress(region, self._region_cells)
                region.atmosphericState = compute_atmospheric_state(self._region_cells)
            self._world_state.hasRegion = True
            self._world_state.region = region
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.RegionLoaded,
                tickCount=self._tick_count,
                message="Region opened",
                hasRegion=True,
                coordinates=coordinates,
            )
            self._repo.save_world_state(self._world_state, self._tick_interval_seconds)
            return region.model_copy(deep=True)

    def resume(self) -> WorldState:
        with self._lock:
            self._tick_running = True
            self._world_state.tickRunning = True
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.TickAdvanced,
                tickCount=self._tick_count,
                message="Tick resumed",
            )
            return self._world_state.model_copy(deep=True)

    def pause(self) -> WorldState:
        with self._lock:
            self._tick_running = False
            self._world_state.tickRunning = False
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.TickAdvanced,
                tickCount=self._tick_count,
                message="Tick paused",
            )
            return self._world_state.model_copy(deep=True)

    def set_tick_speed(self, multiplier: int) -> dict:
        BASE_INTERVAL = 5.0
        valid_multipliers = {1, 2, 10, 50, 100}
        if multiplier not in valid_multipliers:
            raise ValueError(f"Invalid multiplier {multiplier}, must be one of {valid_multipliers}")
        with self._lock:
            self._speed_multiplier = multiplier
            self._tick_interval_seconds = max(0.1, BASE_INTERVAL / multiplier)
            return self.tick_status()

    def advance_tick(self, steps: int = 1) -> WorldState:
        with self._lock:
            for _ in range(max(1, steps)):
                self._advance_tick_locked()
            return self._world_state.model_copy(deep=True)

    def queue_terraform_action(
        self, action: TerraformAction, cell: SimulationCellAddress | None = None
    ) -> WorldState:
        with self._lock:
            if not self._region_cells:
                self._last_event = SimulationEvent(
                    eventId=str(uuid4()),
                    type=SimulationEventType.ActionRejected,
                    tickCount=self._tick_count,
                    message="No active region",
                )
                return self._world_state.model_copy(deep=True)

            target = cell or self._region_cells[0].address
            target_cell = next(
                (c for c in self._region_cells if c.address.q == target.q and c.address.r == target.r),
                None,
            )
            if not can_apply_action(target_cell, action):
                self._last_event = SimulationEvent(
                    eventId=str(uuid4()),
                    type=SimulationEventType.ActionRejected,
                    tickCount=self._tick_count,
                    message=f"Action {action.name} rejected",
                    hasCell=True,
                    cell=target,
                )
                return self._world_state.model_copy(deep=True)

            queue_action(self._pending_actions, target, action)
            if self._pending_actions:
                self._repo.save_pending_action(self._pending_actions[-1])
            if target_cell is not None:
                self._world_state.region.hasSelectedCell = True
                self._world_state.region.selectedCell = target_cell.model_copy(deep=True)
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ActionQueued,
                tickCount=self._tick_count,
                message=f"Action {action.name} queued",
                hasCell=True,
                cell=target,
            )
            return self._world_state.model_copy(deep=True)

    def apply_direct_cell_delta(
        self,
        water_delta: float = 0.0,
        temperature_delta: float = 0.0,
        cell: SimulationCellAddress | None = None,
    ) -> WorldState:
        with self._lock:
            if not self._region_cells:
                return self._world_state.model_copy(deep=True)

            target = cell or self._region_cells[0].address
            for index, current in enumerate(self._region_cells):
                if current.address.q == target.q and current.address.r == target.r:
                    self._region_cells[index] = apply_modifier_to_cell(
                        current,
                        HexStateModifier(tempDelta=temperature_delta, waterDelta=water_delta),
                    )
                    self._world_state.region.hasSelectedCell = True
                    self._world_state.region.selectedCell = self._region_cells[index].model_copy(deep=True)
                    break

            self._world_state.region = apply_region_progress(self._world_state.region, self._region_cells)
            if self._world_state.hasRegion and (water_delta != 0.0 or temperature_delta != 0.0):
                region_key = f"{self._world_state.region.coordinates.latitude:.3f},{self._world_state.region.coordinates.longitude:.3f}"
                k = (target.q, target.r)
                existing_w, existing_t = self._region_mutations.get(region_key, {}).get(k, (0.0, 0.0))
                new_w = existing_w + water_delta
                new_t = existing_t + temperature_delta
                self._region_mutations.setdefault(region_key, {})[k] = (new_w, new_t)
                self._repo.upsert_cell_mutation(
                    region_key,
                    CellMutation(
                        cell_q=target.q, cell_r=target.r,
                        cell_json=json.dumps({"wd": new_w, "td": new_t}),
                    ),
                )
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.CellUpdated,
                tickCount=self._tick_count,
                message="Cell updated directly",
                hasCell=True,
                cell=target,
            )
            return self._world_state.model_copy(deep=True)

    # ── Region debug helpers ───────────────────────────────────────────────────

    def get_region_cell(self, q: int, r: int) -> "SimulationCellState | None":
        with self._lock:
            return next(
                (c.model_copy(deep=True) for c in self._region_cells if c.address.q == q and c.address.r == r),
                None,
            )

    def get_region_hydrology(self) -> dict:
        with self._lock:
            if not self._region_cells:
                return {"error": "no active region", "cells": 0}
            summary = summarize_region_cells(self._region_cells)
            total = summary.totalCells or 1
            return {
                "cells": total,
                "openOceanPct":   round(summary.openOceanCells / total * 100, 1),
                "coastPct":       round(summary.coastCells / total * 100, 1),
                "inlandWaterPct": round(summary.inlandWaterCells / total * 100, 1),
                "frozenWaterPct": round(summary.frozenWaterCells / total * 100, 1),
                "dryPct":         round(summary.dryCells / total * 100, 1),
                "riverCells":     summary.riverCells,
                "basinCells":     summary.basinCells,
                "channelCells":   summary.channelCells,
                "ridgeCells":     summary.ridgeCells,
                "sourceCells":    summary.sourceCells,
                "overflowCells":  summary.overflowCells,
                "maxFlowAccumulation": summary.maxFlowAccumulation,
            }

    def get_region_validation(self) -> dict:
        with self._lock:
            if not self._region_cells:
                return {"error": "no active region", "passed": True, "issues": []}
            issues: list[dict] = []
            for cell in self._region_cells:
                q, r = cell.address.q, cell.address.r
                wc = cell.waterClassification
                wr = round(cell.waterRatio, 3)
                temp = round(cell.temperature, 1)
                if wc == WaterClassification.OpenOcean and wr < 0.60:
                    issues.append({"q": q, "r": r, "rule": "ocean-low-water",
                                   "detail": f"OpenOcean but waterRatio={wr}"})
                if wc == WaterClassification.FrozenWater and temp > 0.0:
                    issues.append({"q": q, "r": r, "rule": "frozen-too-warm",
                                   "detail": f"FrozenWater but temperature={temp}°C"})
                if wc == WaterClassification.Dry and wr > 0.45:
                    issues.append({"q": q, "r": r, "rule": "dry-high-water",
                                   "detail": f"Dry but waterRatio={wr}"})
            return {
                "passed": len(issues) == 0,
                "totalCells": len(self._region_cells),
                "issueCount": len(issues),
                "issues": issues,
            }

    # ── Admin registry methods ─────────────────────────────────────────────────

    def list_resources(self) -> list[dict]:
        with self._lock:
            return [r.model_dump() for r in RESOURCE_REGISTRY.approved.values()]

    def list_pending_resources(self) -> list[dict]:
        with self._lock:
            return [r.model_dump() for r in RESOURCE_REGISTRY.pending.values()]

    def propose_resource(self, resource_def: dict) -> str:
        with self._lock:
            return RESOURCE_REGISTRY.propose(resource_def)

    def approve_resource(self, resource_id: str) -> None:
        with self._lock:
            RESOURCE_REGISTRY.approve(resource_id)

    def reject_resource(self, resource_id: str) -> None:
        with self._lock:
            RESOURCE_REGISTRY.reject(resource_id)

    def list_buildings(self) -> list[dict]:
        """Return all approved buildings from the registry (admin, no args)."""
        with self._lock:
            return [b.model_dump() for b in BUILDING_REGISTRY.approved.values()]

    def list_pending_buildings(self) -> list[dict]:
        with self._lock:
            return [b.model_dump() for b in BUILDING_REGISTRY.pending.values()]

    def propose_building(self, building_def: dict) -> str:
        with self._lock:
            return BUILDING_REGISTRY.propose(building_def)

    def approve_building(self, building_id: str) -> None:
        with self._lock:
            BUILDING_REGISTRY.approve(building_id)

    def reject_building(self, building_id: str) -> None:
        with self._lock:
            BUILDING_REGISTRY.reject(building_id)

    # ── Catalog — Biome Transition Rules ─────────────────────────────────

    def _get_biome_rules_cached(self) -> "list[BiomeTransitionRule]":
        """Lazy-load biome transition rules with caching."""
        if self._biome_rules_cache is None:
            from .logic.mutations import rules_from_db_rows
            rows = self._repo.load_biome_transition_rules()
            self._biome_rules_cache = rules_from_db_rows(rows)
        return self._biome_rules_cache

    def list_biome_transition_rules(self) -> "list[BiomeTransitionRule]":
        from .logic.mutations import rules_from_db_rows
        rows = self._repo.load_biome_transition_rules()
        return rules_from_db_rows(rows)

    def get_biome_transition_rule(self, rule_id: int) -> "BiomeTransitionRule | None":
        rules = self.list_biome_transition_rules()
        for r in rules:
            if r.rule_id == rule_id:
                return r
        return None

    def upsert_biome_transition_rule(self, rule: "BiomeTransitionRule") -> "BiomeTransitionRule":
        import json
        self._repo.upsert_biome_transition_rule({
            "rule_id": rule.rule_id,
            "name": rule.name,
            "target_terrain_type_id": int(rule.target_terrain_type),
            "from_terrain_type_ids": json.dumps([int(t) for t in rule.from_terrain_types]),
            "priority": rule.priority,
            "is_enabled": rule.is_enabled,
            "temperature_min": rule.temperature_min,
            "temperature_max": rule.temperature_max,
            "humidity_min": rule.humidity_min,
            "humidity_max": rule.humidity_max,
            "vegetation_min": rule.vegetation_min,
            "vegetation_max": rule.vegetation_max,
            "tree_count_min": rule.tree_count_min,
            "tree_count_max": rule.tree_count_max,
            "has_river": rule.has_river,
            "has_lake": rule.has_lake,
            "water_ratio_min": rule.water_ratio_min,
            "water_ratio_max": rule.water_ratio_max,
            "toxin_min": rule.toxin_min,
            "toxin_max": rule.toxin_max,
            "description": rule.description,
        })
        self._biome_rules_cache = None  # Invalidate cache
        return rule

    def delete_biome_transition_rule(self, rule_id: int) -> None:
        self._repo.delete_biome_transition_rule(rule_id)
        self._biome_rules_cache = None  # Invalidate cache

    # ── Catalog — Sub-hex Feature Definitions ───────────────────────────────

    def list_sub_hex_features(self) -> list[dict]:
        return self._repo.load_sub_hex_features()

    def upsert_sub_hex_feature(self, feature: "SubHexFeatureDef") -> dict:
        row = {
            "feature_id": feature.id,
            "name": feature.name,
            "label_fr": feature.labelFr,
            "description": feature.description,
            "bonus_building_types": json.dumps(feature.bonusBuildingTypes),
            "is_enabled": feature.isEnabled,
        }
        self._repo.upsert_sub_hex_feature(row)
        return row

    def delete_sub_hex_feature(self, feature_id: int) -> None:
        self._repo.delete_sub_hex_feature(feature_id)

    # ── Catalog — Terrain Type Defs ─────────────────────────────────────

    def list_terrain_type_defs(self) -> list[dict]:
        return self._repo.load_terrain_type_defs()

    def update_terrain_type_def(self, terrain_type_id: int, **kwargs) -> "dict | None":
        defs = self._repo.load_terrain_type_defs()
        row = next((d for d in defs if d["terrain_type_id"] == terrain_type_id), None)
        if row is None:
            return None
        self._repo.update_terrain_type_def(terrain_type_id, **kwargs)
        row.update(kwargs)
        return row


# Backward-compat alias
SimulationRuntime = InMemorySimulationRuntime
