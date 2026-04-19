from __future__ import annotations

import json
import math
import threading
from uuid import uuid4

from .logic import apply_modifier_to_cell, apply_region_progress, aggregate_tile_deltas, can_apply_action, compute_atmospheric_state, compute_body_position_at_tick, compute_equilibrium_temperature, compute_planetary_irradiance, compute_tile_irradiance, spectral_type_to_luminosity, _body_h3_resolution, generate_interior_cells, generate_spherical_tiles, GENERATION_VERSION, process_pending_actions, queue_action, summarize_region_cells, summarize_spherical_tiles, terraform_action_definitions
from .models import (
    AnyBodyState,
    AtmosphericComposition,
    AtmosphericGas,
    ATMOSPHERE_PRESETS,
    AtmosphericState,
    BodyBase,
    BodyType,
    DebugCoherenceOverride,
    GalacticPosition,
    HexGridDebugSummary,
    HexStateModifier,
    InteriorZoneState,
    OrbitalParameters,
    PendingTerraformAction,
    ProjectionDebugSummary,
    ProjectionState,
    RegionState,
    RouteStatus,
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
    StellarRoute,
    TerraformAction,
    TerraformActionDefinition,
    TerrainClass,
    TerrainType,
    TICKS_PER_LIGHT_YEAR,
    TravelStatus,
    WaterClassification,
    WorldLayer,
    WorldState,
    ZoneType,
    ClaimedTile,
    CorporationData,
    BuildingData,
    BuildingType,
    BUILDING_CONFIGS,
    ResourceType,
)
from .persistence import CellMutation, InMemoryRepository, SavedState, StateRepository, TileMutation


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class InMemorySimulationRuntime:
    def __init__(
        self,
        tick_interval_seconds: float = 5.0,
        auto_resume: bool = False,
        repository: StateRepository | None = None,
    ) -> None:
        self._tick_interval_seconds = max(0.1, tick_interval_seconds)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._tick_running = auto_resume
        self._tick_count = 0
        self._world_state = WorldState()
        self._region_cells: list[SimulationCellState] = []
        self._pending_actions: list[PendingTerraformAction] = []
        self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.SnapshotCaptured, message="Runtime initialized")
        # Body registry: body_id → SphericalBodyState | InteriorZoneState
        self._bodies: dict[str, AnyBodyState] = {}
        self._active_body_id: str = ""
        # Galaxy registry
        self._solar_systems: dict[str, SolarSystemState] = {}
        self._stellar_routes: dict[str, StellarRoute] = {}
        self._space_travels: dict[str, SpaceTravel] = {}
        self._repo: StateRepository = repository or InMemoryRepository()
        # LOD tile cache: (body_id, h3_resolution) → list[GoldbergTileState] (never persisted)
        self._lod_tile_cache: dict = {}
        # Region mutation cache: region_key → {(q, r): (water_delta, temp_delta)}
        # Replayed on every open_region() call so modifications survive region reloads.
        # Key format: f"{lat:.3f},{lon:.3f}" (granularity ~0.1° ≈ 10 km)
        self._region_mutations: dict[str, dict[tuple[int, int], tuple[float, float]]] = {}
        # Corporation registry (Phase 7.1)
        self._corporations: dict[str, CorporationData] = {}
        self._tile_ownership: dict[str, dict[str, str]] = {}  # body_id -> tile_id -> corp_id
        # Building registry (Phase 7.2)
        self._buildings: dict[str, BuildingData] = {}  # building_id -> BuildingData
        # Atmospheric event tracking (Phase 3 — SDK climate events)
        self._last_habitability_bucket: int = -1   # 0=<25% 1=<50% 2=<75% 3=100%
        self._atmosphere_formed_fired: bool = False
        self._prev_avg_temp: float = 0.0
        self._temp_stable_ticks: int = 0
        saved = self._repo.load()
        if saved.has_data:
            self._hydrate_from_saved(saved)
        else:
            self.bootstrap_demo()
        self._thread = threading.Thread(target=self._tick_loop, name="SimulationRuntime", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    # ── Corporation registry (Phase 7.1) ──────────────────────────────────

    def register_corporation(self, name: str, is_ai: bool = False) -> CorporationData:
        with self._lock:
            corp_id = str(uuid4())
            corp = CorporationData(id=corp_id, name=name, credits=1000.0, isAI=is_ai)
            self._corporations[corp_id] = corp
            return corp

    def list_corporations(self) -> list[CorporationData]:
        with self._lock:
            return list(self._corporations.values())

    def get_corporation(self, corp_id: str) -> CorporationData | None:
        with self._lock:
            return self._corporations.get(corp_id)

    def claim_tile(self, corp_id: str, body_id: str, tile_id: str) -> CorporationData:
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            existing = self._tile_ownership.get(body_id, {}).get(tile_id)
            if existing is not None:
                raise ValueError(f"Tile '{tile_id}' on body '{body_id}' is already claimed by '{existing}'")
            self._tile_ownership.setdefault(body_id, {})[tile_id] = corp_id
            corp.claimedTiles.append(ClaimedTile(bodyId=body_id, tileId=tile_id))
            return corp

    def unclaim_tile(self, corp_id: str, body_id: str, tile_id: str) -> CorporationData:
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            owner = self._tile_ownership.get(body_id, {}).get(tile_id)
            if owner != corp_id:
                raise ValueError(f"Tile '{tile_id}' on body '{body_id}' is not owned by '{corp_id}'")
            self._tile_ownership[body_id].pop(tile_id, None)
            corp.claimedTiles = [ct for ct in corp.claimedTiles
                                  if not (ct.bodyId == body_id and ct.tileId == tile_id)]
            return corp

    # ── Building registry (Phase 7.2) ──────────────────────────────────────────

    def construct_building(self, corp_id: str, body_id: str, tile_id: str, building_type: BuildingType) -> BuildingData:
        with self._lock:
            corp = self._corporations.get(corp_id)
            if corp is None:
                raise KeyError(f"Corporation '{corp_id}' not found")
            owner = self._tile_ownership.get(body_id, {}).get(tile_id)
            if owner != corp_id:
                raise ValueError(f"Tile '{tile_id}' on body '{body_id}' is not claimed by '{corp_id}'")
            # 1 bâtiment par type par tuile
            for b in self._buildings.values():
                if b.corpId == corp_id and b.bodyId == body_id and b.tileId == tile_id and b.buildingType == building_type:
                    raise ValueError(f"A {building_type.name} already exists on tile '{tile_id}'")
            building_id = str(uuid4())
            building = BuildingData(
                id=building_id,
                buildingType=building_type,
                tileId=tile_id,
                bodyId=body_id,
                corpId=corp_id,
            )
            self._buildings[building_id] = building
            corp.buildings.append(building)
            return building

    def demolish_building(self, corp_id: str, building_id: str) -> None:
        with self._lock:
            building = self._buildings.get(building_id)
            if building is None:
                raise KeyError(f"Building '{building_id}' not found")
            if building.corpId != corp_id:
                raise ValueError(f"Building '{building_id}' does not belong to '{corp_id}'")
            del self._buildings[building_id]
            corp = self._corporations.get(corp_id)
            if corp:
                corp.buildings = [b for b in corp.buildings if b.id != building_id]

    def list_buildings(self, corp_id: str) -> list[BuildingData]:
        with self._lock:
            return [b for b in self._buildings.values() if b.corpId == corp_id]

    def get_building(self, building_id: str) -> BuildingData | None:
        with self._lock:
            return self._buildings.get(building_id)

    def set_building_worker_ratio(self, corp_id: str, building_id: str, worker_ratio: float) -> BuildingData:
        with self._lock:
            building = self._buildings.get(building_id)
            if building is None:
                raise KeyError(f"Building '{building_id}' not found")
            if building.corpId != corp_id:
                raise ValueError(f"Building '{building_id}' does not belong to '{corp_id}'")
            building.workerRatio = max(0.0, min(1.0, worker_ratio))
            return building

    def _process_building_production(self) -> None:
        """Appelé à chaque tick — crédite les ressources de chaque corpo selon ses bâtiments actifs."""
        for building in self._buildings.values():
            corp = self._corporations.get(building.corpId)
            if corp is None:
                continue
            config = BUILDING_CONFIGS.get(building.buildingType, {})
            for resource_type, delta in config.items():
                key = resource_type.name
                corp.resources[key] = corp.resources.get(key, 0.0) + delta * building.workerRatio
            building.ticksActive += 1

    def health(self) -> dict:
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

    def bootstrap_demo(self,
                       planet_name: str = "Astra-Prime",
                       projection_override: DebugCoherenceOverride = DebugCoherenceOverride.Coast,
                       projection_water_level: float = 0.08) -> WorldState:
        with self._lock:
            projection = self._build_projection_state(planet_name, projection_override, projection_water_level)
            region = self._build_region_state(planet_name, SimulationCoordinates(latitude=0.47, longitude=0.18), self._tick_count)
            self._world_state = WorldState(
                isValid=True,
                tickCount=self._tick_count,
                tickRunning=self._tick_running,
                activePlanetName=planet_name,
                projectionOverride=projection_override,
                projectionWaterLevel=projection_water_level,
                hasProjection=True,
                projection=projection,
                hasRegion=True,
                region=region,
            )
            # Register the demo planet in the body registry
            self._register_spherical_body_locked(
                body_id=None,
                name=planet_name,
                body_type=BodyType.Planet,
                radius_km=6371.0,
                coherence_override=projection_override,
                water_level=projection_water_level,
                seed=42042,
            )
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ProjectionLoaded,
                tickCount=self._tick_count,
                message=f"Demo world bootstrapped for {planet_name}",
                hasRegion=True,
                coordinates=region.coordinates,
            )
            self._repo.save_world_state(self._world_state, self._tick_interval_seconds)
            for body in self._bodies.values():
                self._repo.save_body(body)
            self._bootstrap_galaxy_locked()
            return self._world_state.model_copy(deep=True)

    def bootstrap_sol(self) -> WorldState:
        """Bootstrap the Sol solar system as the player's home system.
        Wipes all existing bodies and galaxy state first.
        Earth is the active planet. All 8 planets + key moons are registered.
        Kepler-442 is created as a hidden distant system.
        """
        with self._lock:
            # ── Wipe existing state ───────────────────────────────────────
            for bid in list(self._bodies):
                self._repo.delete_tile_mutations(bid)
                self._repo.delete_body(bid)
            self._bodies = {}
            self._active_body_id = ""
            for sid in list(self._solar_systems):
                self._repo.delete_solar_system(sid)
            for rid in list(self._stellar_routes):
                self._repo.delete_stellar_route(rid)
            for tid in list(self._space_travels):
                self._repo.delete_space_travel(tid)
            self._solar_systems = {}
            self._stellar_routes = {}
            self._space_travels = {}
            self._region_mutations = {}  # wipe persisted region deltas (Sprint C)
            self._corporations = {}         # wipe corporation registry (Phase 7.1)
            self._tile_ownership = {}       # wipe tile ownership (Phase 7.1)
            self._buildings = {}            # wipe building registry (Phase 7.2)

            # ── Bootstrap Sol ───────────────────────────────────────
            earth_name = "Earth"
            earth_water = 0.71
            earth_override = DebugCoherenceOverride.Coast
            earth_seed = 1004

            projection = self._build_projection_state(earth_name, earth_override, earth_water)
            region = self._build_region_state(
                earth_name, SimulationCoordinates(latitude=0.47, longitude=0.18), self._tick_count
            )
            self._world_state = WorldState(
                isValid=True,
                tickCount=self._tick_count,
                tickRunning=self._tick_running,
                activePlanetName=earth_name,
                projectionOverride=earth_override,
                projectionWaterLevel=earth_water,
                hasProjection=True,
                projection=projection,
                hasRegion=True,
                region=region,
            )
            earth = self._register_spherical_body_locked(
                body_id=None,
                name=earth_name,
                body_type=BodyType.Planet,
                radius_km=6371.0,
                coherence_override=earth_override,
                water_level=earth_water,
                seed=earth_seed,
                atmosphere=ATMOSPHERE_PRESETS["earth"],
            )
            self._last_event = SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ProjectionLoaded,
                tickCount=self._tick_count,
                message="Sol system bootstrapped — playing as Earth colonist",
                hasRegion=True,
                coordinates=region.coordinates,
            )
            self._repo.save_world_state(self._world_state, self._tick_interval_seconds)
            for body in self._bodies.values():
                self._repo.save_body(body)
            self._bootstrap_sol_galaxy_locked(earth)
            return self._world_state.model_copy(deep=True)

    def _bootstrap_sol_galaxy_locked(self, active_earth: SphericalBodyState) -> None:
        """Create the Sol system (home) and Kepler-442 (hidden target) and link them.
        Lock must be held.
        """

        def _make_system(name: str, x: float, y: float, z: float) -> SolarSystemState:
            sid = str(uuid4())
            system = SolarSystemState(
                systemId=sid, name=name,
                position=GalacticPosition(x=x, y=y, z=z),
            )
            self._solar_systems[sid] = system
            self._repo.save_solar_system(system)
            return system

        def _add_star(system: SolarSystemState, name: str, radius_km: float,
                      spectral: str, seed: int) -> SphericalBodyState:
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=BodyType.Star,
                radius_km=radius_km, coherence_override=DebugCoherenceOverride.None_,
                water_level=0.0, seed=seed,
            )
            body.spectralType = spectral
            body.systemId = system.systemId
            if system.rootBodyId == "":
                system.rootBodyId = body.bodyId
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body

        def _add_body(
            system: SolarSystemState,
            name: str,
            body_type: BodyType,
            radius_km: float,
            water_level: float,
            seed: int,
            semi_major_au: float,
            period_ticks: int,
            parent_id: str | None = None,
            override: DebugCoherenceOverride | None = None,
            atmosphere_density: float | None = None,
            atmosphere: "AtmosphericComposition | None" = None,
        ) -> SphericalBodyState:
            if override is None:
                if water_level > 0.5:
                    override = DebugCoherenceOverride.Ocean
                elif water_level < 0.05:
                    override = DebugCoherenceOverride.Arid
                else:
                    override = DebugCoherenceOverride.Coast
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=body_type,
                radius_km=radius_km, coherence_override=override,
                water_level=water_level, seed=seed, parent_id=parent_id,
                atmosphere_density=atmosphere_density,
                atmosphere=atmosphere,
            )
            body.systemId = system.systemId
            body.orbitalParams = OrbitalParameters(
                semiMajorAxisAU=semi_major_au, eccentricity=0.0, periodTicks=period_ticks,
            )
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body

        # ── Système Sol (home) ────────────────────────────────────────────────
        sol = _make_system("Sol", 0.0, 0.0, 0.0)
        sun = _add_star(sol, "Sun", 695700.0, "G2V", 1001)

        # Lier la Terre déjà enregistrée au système Sol
        active_earth.systemId = sol.systemId
        active_earth.orbitalParams = OrbitalParameters(
            semiMajorAxisAU=1.0, eccentricity=0.017, periodTicks=365,
        )
        active_earth.parentId = sun.bodyId
        sol.bodyIds.append(active_earth.bodyId)
        self._repo.save_body(active_earth)
        self._repo.save_solar_system(sol)

        _add_body(sol, "Mercury", BodyType.Planet, 2440.0,  0.00, 1002, 0.387,  88,   sun.bodyId, atmosphere_density=0.00)
        _add_body(sol, "Venus",   BodyType.Planet, 6051.0,  0.00, 1003, 0.723,  225,  sun.bodyId, atmosphere=ATMOSPHERE_PRESETS["venus"])
        mars    = _add_body(sol, "Mars",    BodyType.Planet, 3390.0,  0.02, 1005, 1.524,  687,  sun.bodyId, atmosphere=ATMOSPHERE_PRESETS["mars"])

        # Lune de la Terre
        _add_body(sol, "Luna",    BodyType.Moon,   1737.0,  0.01, 2001, 0.00257, 27,  active_earth.bodyId, atmosphere_density=0.00)

        # Planètes extérieures
        jupiter = _add_body(sol, "Jupiter", BodyType.Planet, 69911.0, 0.00, 1006, 5.203,  4333,  sun.bodyId,
                            DebugCoherenceOverride.None_, atmosphere_density=0.90)
        saturn  = _add_body(sol, "Saturn",  BodyType.Planet, 58232.0, 0.00, 1007, 9.537,  10759, sun.bodyId,
                            DebugCoherenceOverride.None_, atmosphere_density=0.85)
        _add_body(sol, "Uranus",  BodyType.Planet, 25362.0, 0.00, 1008, 19.19,  30685, sun.bodyId,
                  DebugCoherenceOverride.Frozen, atmosphere_density=0.75)
        _add_body(sol, "Neptune", BodyType.Planet, 24622.0, 0.00, 1009, 30.07,  60190, sun.bodyId,
                  DebugCoherenceOverride.Frozen, atmosphere_density=0.75)

        # Lunes de Jupiter
        _add_body(sol, "Io",       BodyType.Moon, 1821.0, 0.00, 2002, 0.00282, 2,  jupiter.bodyId, atmosphere_density=0.05)
        _add_body(sol, "Europa",   BodyType.Moon, 1560.0, 0.70, 2003, 0.00449, 4,  jupiter.bodyId, atmosphere_density=0.02)
        _add_body(sol, "Ganymede", BodyType.Moon, 2634.0, 0.30, 2004, 0.00716, 7,  jupiter.bodyId, atmosphere_density=0.01)

        # Lune de Saturne
        _add_body(sol, "Titan",    BodyType.Moon, 2575.0, 0.10, 2005, 0.00817, 16, saturn.bodyId, atmosphere_density=0.95)

        # ── Système Kepler-442 (cible d'exploration cachée) ───────────────────
        kepler = _make_system("Kepler-442", 1200.0, 0.0, 0.0)
        kepler.isDiscovered = False
        self._repo.save_solar_system(kepler)
        kepler_star = _add_star(kepler, "Kepler-442", 513000.0, "K", 3001)
        _add_body(kepler, "Kepler-442b", BodyType.Planet, 7600.0, 0.55, 3002,
                  0.409, 112, kepler_star.bodyId, DebugCoherenceOverride.Ocean,
                  atmosphere=AtmosphericComposition(
                      totalPressureKpa=40.0,
                      gases=[
                          AtmosphericGas(name="N2",  fraction=0.70, greenhouseCoeff=0.0,  molarMass=28.0),
                          AtmosphericGas(name="CO2", fraction=0.15, greenhouseCoeff=1.0,  molarMass=44.0),
                          AtmosphericGas(name="H2O", fraction=0.05, greenhouseCoeff=0.5,  molarMass=18.0),
                          AtmosphericGas(name="O2",  fraction=0.10, greenhouseCoeff=0.0,  molarMass=32.0),
                      ],
                  ))

        # ── Compute luminosity and equilibrium temperature ─────────────────────
        # Pass 1: stars only (must complete before planets can reference their luminosity)
        for body in self._bodies.values():
            if isinstance(body, SphericalBodyState) and body.bodyType == BodyType.Star:
                body.luminosityLsun = spectral_type_to_luminosity(body.spectralType, body.radiusKm)
                self._repo.save_body(body)

        # Pass 2: planets and moons (stars are all resolved now)
        for body in self._bodies.values():
            if not isinstance(body, SphericalBodyState):
                continue
            if body.bodyType == BodyType.Star or body.orbitalParams is None:
                continue
            parent = self._bodies.get(body.parentId or "")
            if parent is None or not isinstance(parent, SphericalBodyState):
                continue
            if parent.bodyType == BodyType.Star:
                # Planet orbiting a star directly
                star_luminosity = parent.luminosityLsun
                star_au = body.orbitalParams.semiMajorAxisAU
            else:
                # Moon: use grandparent star + parent planet's star distance
                grandparent = self._bodies.get(parent.parentId or "")
                if grandparent is None or not isinstance(grandparent, SphericalBodyState) or grandparent.bodyType != BodyType.Star:
                    continue
                star_luminosity = grandparent.luminosityLsun
                star_au = parent.orbitalParams.semiMajorAxisAU if parent.orbitalParams else 0.0
            if star_luminosity > 0.0 and star_au > 0.0:
                irr = compute_planetary_irradiance(star_luminosity, star_au)
                body.equilibriumTemperature = compute_equilibrium_temperature(irr, body.atmosphere)
                self._repo.save_body(body)

        # Route cachée Sol → Kepler-442
        self._create_stellar_route_locked(
            from_system_id=sol.systemId,
            to_system_id=kepler.systemId,
            travel_time_modifier=1.0,
            description="Signal interstellaire capté depuis l'orbite de Mars.",
        )
        _ = mars  # référencé pour future utilisation

    def _hydrate_from_saved(self, saved: SavedState) -> None:
        """Restore runtime state from a SavedState loaded from the repository."""
        self._tick_count = saved.tick_count
        self._tick_running = saved.tick_running
        self._tick_interval_seconds = max(0.1, saved.tick_interval_seconds)

        # Re-hydrate bodies from JSON (tiles regenerated lazily)
        for body_json in saved.bodies_json:
            data = json.loads(body_json)
            surface_type = data.get("surfaceType", "goldberg")
            if surface_type == "goldberg":
                body = SphericalBodyState.model_validate(data)
            else:
                body = InteriorZoneState.model_validate(data)
            self._bodies[body.bodyId] = body
            if not self._active_body_id or body.bodyType == BodyType.Planet:
                self._active_body_id = body.bodyId

        # Apply tile mutations to in-memory bodies
        for body_id, mutations in saved.tile_mutations.items():
            body = self._bodies.get(body_id)
            if body is None or not isinstance(body, SphericalBodyState):
                continue
            # If algo changed since last modification, discard cached tiles so they
            # regenerate lazily on next access (mutations are re-applied on top)
            if body.isModified and body.generationVersion != GENERATION_VERSION:
                import logging
                logging.getLogger(__name__).warning(
                    "Body %s was modified under generation version %r but current is %r — "
                    "tiles will regenerate on next access",
                    body_id, body.generationVersion, GENERATION_VERSION,
                )
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile_by_id = {t.tileId: t for t in body.tiles}
            for m in mutations:
                tile = tile_by_id.get(m.tile_id)
                if tile is not None:
                    tile.waterRatio = m.water_ratio
                    tile.temperature = m.temperature
                    tile.toxinLevel = m.toxin_level

        # Rebuild projection and region from saved parameters
        active_name = saved.active_planet_name or "Astra-Prime"
        override = DebugCoherenceOverride(saved.projection_override)
        projection = self._build_projection_state(active_name, override, saved.projection_water_level)
        coords = SimulationCoordinates(latitude=saved.region_lat, longitude=saved.region_lon)
        region = self._build_region_state(active_name, coords, self._tick_count) if saved.has_region else RegionState()

        self._world_state = WorldState(
            isValid=True,
            tickCount=self._tick_count,
            tickRunning=self._tick_running,
            activePlanetName=active_name,
            projectionOverride=override,
            projectionWaterLevel=saved.projection_water_level,
            hasProjection=True,
            projection=projection,
            hasRegion=saved.has_region,
            region=region,
        )

        # Re-hydrate pending actions
        from .models import PendingTerraformAction
        for action_json in saved.pending_actions_json:
            try:
                self._pending_actions.append(PendingTerraformAction.model_validate_json(action_json))
            except Exception:
                pass

        # Re-hydrate galaxy layer
        for system_json in saved.systems_json:
            try:
                system = SolarSystemState.model_validate_json(system_json)
                self._solar_systems[system.systemId] = system
            except Exception:
                pass

        for route_json in saved.routes_json:
            try:
                route = StellarRoute.model_validate_json(route_json)
                self._stellar_routes[route.routeId] = route
            except Exception:
                pass

        for travel_json in saved.travels_json:
            try:
                travel = SpaceTravel.model_validate_json(travel_json)
                self._space_travels[travel.travelId] = travel
            except Exception:
                pass

        # If no galaxy data yet (first run with new tables), seed the bootstrap systems
        if not self._solar_systems:
            self._bootstrap_galaxy_locked()

        self._last_event = SimulationEvent(
            eventId=str(uuid4()),
            type=SimulationEventType.SnapshotCaptured,
            message=f"State restored from persistence (tick={self._tick_count})",
        )

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
            }

    def set_projection(
        self,
        projection_override: DebugCoherenceOverride,
        water_level: float,
    ) -> WorldState:
        """Change the active projection override without resetting the full world state.
        Clears the active body's tile cache so tiles are regenerated on next access.
        """
        with self._lock:
            planet_name = self._world_state.activePlanetName or "Astra-Prime"
            water_level = max(0.0, min(1.0, water_level))
            projection = self._build_projection_state(planet_name, projection_override, water_level)
            self._world_state.projection = projection
            self._world_state.hasProjection = True
            self._world_state.projectionOverride = projection_override
            self._world_state.projectionWaterLevel = water_level
            # Update active body and invalidate tile cache
            if self._active_body_id and self._active_body_id in self._bodies:
                body = self._bodies[self._active_body_id]
                if isinstance(body, SphericalBodyState):
                    body.projectionOverride = projection_override
                    body.waterLevel = water_level
                    body.tiles = []  # force regeneration on next access
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
            coordinates = SimulationCoordinates(latitude=_clamp01(latitude), longitude=_clamp01(longitude))
            region = self._build_region_state(self._world_state.activePlanetName or "Astra-Prime", coordinates, self._tick_count)
            # Replay persisted mutations so modifications survive region reloads (Sprint C)
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
            self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.TickAdvanced, tickCount=self._tick_count, message="Tick resumed")
            return self._world_state.model_copy(deep=True)

    def pause(self) -> WorldState:
        with self._lock:
            self._tick_running = False
            self._world_state.tickRunning = False
            self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.TickAdvanced, tickCount=self._tick_count, message="Tick paused")
            return self._world_state.model_copy(deep=True)

    def advance_tick(self, steps: int = 1) -> WorldState:
        with self._lock:
            for _ in range(max(1, steps)):
                self._advance_tick_locked()
            return self._world_state.model_copy(deep=True)

    def queue_terraform_action(self, action: TerraformAction, cell: SimulationCellAddress | None = None) -> WorldState:
        with self._lock:
            if not self._region_cells:
                self._last_event = SimulationEvent(eventId=str(uuid4()), type=SimulationEventType.ActionRejected, tickCount=self._tick_count, message="No active region")
                return self._world_state.model_copy(deep=True)

            target = cell or self._region_cells[0].address
            target_cell = next((current for current in self._region_cells if current.address.q == target.q and current.address.r == target.r), None)
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
            # persist the newly added action
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

    def apply_direct_cell_delta(self,
                                water_delta: float = 0.0,
                                temperature_delta: float = 0.0,
                                cell: SimulationCellAddress | None = None) -> WorldState:
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
            # Persist delta so it survives region reloads (Sprint C)
            if self._world_state.hasRegion and (water_delta != 0.0 or temperature_delta != 0.0):
                region_key = f"{self._world_state.region.coordinates.latitude:.3f},{self._world_state.region.coordinates.longitude:.3f}"
                k = (target.q, target.r)
                existing_w, existing_t = self._region_mutations.get(region_key, {}).get(k, (0.0, 0.0))
                self._region_mutations.setdefault(region_key, {})[k] = (
                    existing_w + water_delta, existing_t + temperature_delta
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

    # ── Sprint MCP-1 — Region debug helpers ─────────────────────────────────

    def get_region_cell(self, q: int, r: int) -> "SimulationCellState | None":
        """Return the cell at axial coordinates (q, r) in the current region, or None."""
        with self._lock:
            return next(
                (c.model_copy(deep=True) for c in self._region_cells if c.address.q == q and c.address.r == r),
                None,
            )

    def get_region_hydrology(self) -> dict:
        """Return hydrology summary for the current region cells."""
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
        """Validate coherence of the current region cells.

        Returns a list of issues (incoherent cells) and a summary score.
        A cell is flagged if its waterClassification contradicts its waterRatio:
        - OpenOcean but waterRatio < 0.60
        - FrozenWater but temperature > 0°C
        - Dry but waterRatio > 0.45  (matches actual Dry classification boundary)
        """
        with self._lock:
            if not self._region_cells:
                return {"error": "no active region", "passed": True, "issues": []}
            issues: list[dict] = []
            for cell in self._region_cells:
                q, r = cell.address.q, cell.address.r
                wc = cell.waterClassification
                wr = round(cell.waterRatio, 3)
                temp = round(cell.temperature, 1)
                from .models import WaterClassification
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
            self._region_cells, self._pending_actions = process_pending_actions(self._region_cells, self._pending_actions)
            if self._region_cells:
                # Greenhouse thermal feedback (Phase 2 — SDK ClimateSimulator port)
                # Apply 0.5% of current greenhouse delta per tick so temperature evolves visibly
                co2 = region.atmosphericState.co2Ratio if region.atmosphericState.co2Ratio > 0 else 0.0004
                greenhouse_k = co2 * 150.0 * 0.005  # simplified linear proxy, capped naturally by co2 ratio
                for index, cell in enumerate(self._region_cells):
                    cell.temperature += 0.04 if index % 3 == 0 else 0.01
                    cell.temperature += greenhouse_k
                    cell.waterRatio = _clamp01(cell.waterRatio + (0.004 if index % 4 == 0 else 0.001))
                    cell.flowAccumulation = min(999, cell.flowAccumulation + (1 if index == 0 else 0))
                    self._region_cells[index] = cell
            else:
                pass

            if region.hasSelectedCell and self._region_cells:
                cell = self._region_cells[0]
                cell.temperature += 0.08
                cell.waterRatio = _clamp01(cell.waterRatio + 0.003)
                cell.flowAccumulation = min(999, cell.flowAccumulation + 1)
                self._region_cells[0] = cell

            region = apply_region_progress(region, self._region_cells)
            # Recalculate atmospheric state from evolved cells (Phase 2)
            region.atmosphericState = compute_atmospheric_state(self._region_cells)
            self._world_state.region = region

            # Emit climate threshold events (Phase 3 — SDK climate events)
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
        # Production des bâtiments (Phase 7.2)
        self._process_building_production()

        # Persist every 10 ticks to avoid per-tick overhead
        if self._tick_count % 10 == 0:
            self._repo.save_world_state(self._world_state, self._tick_interval_seconds)

        # Check space travel arrivals
        for travel in list(self._space_travels.values()):
            if travel.status == TravelStatus.InTransit and self._tick_count >= travel.arrivalTick:
                travel.status = TravelStatus.Arrived
                self._repo.save_space_travel(travel)

    def _check_climate_events(self, region: "RegionState") -> "SimulationEvent | None":
        """Emit climate threshold events (Phase 3 — ported from SDK ClimateEvents)."""
        atm = region.atmosphericState

        # AtmosphereFormed: first time pressure > 10 kPa (one-shot)
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

        # HabitabilityThreshold: score crosses 0.25 / 0.50 / 0.75 / 1.0
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

        # ThermalEquilibrium: avg temp stable ±0.5°C for 10 consecutive ticks
        avg_temp = atm.averageTemperature
        if abs(avg_temp - self._prev_avg_temp) < 0.5:
            self._temp_stable_ticks += 1
        else:
            self._temp_stable_ticks = 0
        self._prev_avg_temp = avg_temp
        if self._temp_stable_ticks == 10:  # emit once per equilibrium episode
            return SimulationEvent(
                eventId=str(uuid4()),
                type=SimulationEventType.ThermalEquilibrium,
                tickCount=self._tick_count,
                message=f"Thermal equilibrium reached — avg {avg_temp:.1f}°C",
                hasRegion=True,
                coordinates=region.coordinates,
            )

        return None

    def _build_projection_state(self,
                                planet_name: str,
                                projection_override: DebugCoherenceOverride,
                                projection_water_level: float) -> ProjectionState:
        base_water = _clamp01(0.52 + projection_water_level)
        summary = ProjectionDebugSummary(
            cols=48,
            rows=24,
            totalCells=1152,
            dryCells=312,
            coastCells=184,
            inlandWaterCells=98,
            openOceanCells=402,
            frozenWaterCells=34,
            rockTerrainCells=328,
            iceTerrainCells=52,
            toxicTerrainCells=24,
            waterTerrainCells=488,
            vegetationTerrainCells=210,
            metalTerrainCells=50,
            averageWaterRatio=base_water,
            averageTemperature=12.4,
        )
        return ProjectionState(
            isValid=True,
            planetName=planet_name,
            projectionOverride=projection_override,
            projectionWaterLevel=projection_water_level,
            summary=summary,
        )

    def _build_region_state(self, planet_name: str, coordinates: SimulationCoordinates, tick_count: int) -> RegionState:
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
                rockHardness=0.46,
                organicContent=0.32,
                porosity=0.52,
                mineralDensity=0.41,
                toxicSoil=False,
                thermalConductivity=0.28,
            ),
        )

        self._region_cells = self._build_region_cells(selected_cell, projected_water_ratio, average_temperature)
        self._pending_actions = []

        summary = HexGridDebugSummary(
            totalCells=91,
            dryCells=24,
            coastCells=14,
            inlandWaterCells=11,
            openOceanCells=16,
            frozenWaterCells=2,
            ridgeCells=10,
            basinCells=13,
            channelCells=15,
            sourceCells=4,
            riverCells=9,
            downstreamCells=18,
            overflowCells=3,
            rockTerrainCells=28,
            iceTerrainCells=3,
            toxicTerrainCells=2,
            waterTerrainCells=30,
            vegetationTerrainCells=22,
            metalTerrainCells=6,
            averageWaterRatio=projected_water_ratio,
            averageTemperature=average_temperature,
            maxFlowAccumulation=max((cell.flowAccumulation for cell in self._region_cells), default=selected_cell.flowAccumulation),
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

    def _build_region_cells(self,
                            selected_cell: SimulationCellState,
                            projected_water_ratio: float,
                            average_temperature: float) -> list[SimulationCellState]:
        cells = [selected_cell.model_copy(deep=True)]
        for index in range(1, 24):
            dryness = index / 24.0
            water_ratio = _clamp01(projected_water_ratio + 0.18 - dryness * 0.28)
            temperature = average_temperature + 3.0 - dryness * 9.0
            terrain_type = TerrainType.Vegetation if water_ratio > 0.42 and temperature > 4.0 else (TerrainType.Eau if water_ratio > 0.58 else TerrainType.Roche)
            water_classification = WaterClassification.OpenOcean if water_ratio > 0.8 else (WaterClassification.Coast if water_ratio > 0.45 else WaterClassification.Dry)
            cells.append(
                SimulationCellState(
                    address=SimulationCellAddress(q=index % 6, r=-(index // 6)),
                    terrainName="Vegetated Shelf" if terrain_type == TerrainType.Vegetation else ("Water Shelf" if terrain_type == TerrainType.Eau else "Rock Shelf"),
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
                )
            )
        return cells

    # ── Body registry ─────────────────────────────────────────────────────────

    def _register_spherical_body_locked(
        self,
        body_id: str | None,
        name: str,
        body_type: BodyType,
        radius_km: float,
        coherence_override: DebugCoherenceOverride,
        water_level: float,
        seed: int,
        parent_id: str | None = None,
        atmosphere_density: float | None = None,  # kept for backward-compat; ignored when atmosphere= is set
        atmosphere: AtmosphericComposition | None = None,
    ) -> SphericalBodyState:
        """Create and store a SphericalBodyState; tiles generated lazily on first request.
        Prefer passing atmosphere= (AtmosphericComposition) directly.
        atmosphere_density is a legacy float and is only used to compute a trivial
        vacuum/thin/thick selection when no atmosphere object is provided.
        """
        if atmosphere is None:
            # Legacy path: map float density to nearest preset
            if atmosphere_density is None:
                _atmo_defaults = {
                    DebugCoherenceOverride.Ocean:  0.65,
                    DebugCoherenceOverride.Arid:   0.15,
                    DebugCoherenceOverride.Frozen: 0.30,
                    DebugCoherenceOverride.Coast:  0.70,
                    DebugCoherenceOverride.Basin:  0.50,
                    DebugCoherenceOverride.None_:  0.50,
                }
                atmosphere_density = _atmo_defaults.get(coherence_override, 0.50)
            # Map density float to a rough AtmosphericComposition
            if atmosphere_density <= 0.01:
                atmosphere = ATMOSPHERE_PRESETS["vacuum"]
            elif atmosphere_density <= 0.05:
                atmosphere = AtmosphericComposition(
                    totalPressureKpa=atmosphere_density * 101.3,
                    gases=[],
                )
            else:
                # Generic atmosphere proportional to Earth baseline
                from .models import AtmosphericGas
                atmosphere = AtmosphericComposition(
                    totalPressureKpa=atmosphere_density * 101.3,
                    gases=[
                        AtmosphericGas(name="N2",  fraction=0.78, greenhouseCoeff=0.0,  molarMass=28.0),
                        AtmosphericGas(name="CO2", fraction=0.02, greenhouseCoeff=1.0,  molarMass=44.0),
                        AtmosphericGas(name="O2",  fraction=0.20, greenhouseCoeff=0.0,  molarMass=32.0),
                    ],
                )
        h3_res = _body_h3_resolution(radius_km)
        tile_count = 2 + 120 * (7 ** h3_res)  # H3 formula: c(r) = 2 + 120*7^r
        bid = body_id or str(uuid4())
        body = SphericalBodyState(
            bodyId=bid,
            bodyType=body_type,
            name=name,
            parentId=parent_id,
            seed=seed,
            radiusKm=radius_km,
            h3Resolution=h3_res,
            tileCount=tile_count,
            projectionOverride=coherence_override,
            waterLevel=water_level,
            atmosphere=atmosphere,
        )
        self._bodies[bid] = body
        if not self._active_body_id or body_type == BodyType.Planet:
            self._active_body_id = bid
        self._repo.save_body(body)
        return body

    def list_bodies(self) -> list[BodyBase]:
        """Return all registered bodies without tiles/cells."""
        with self._lock:
            return [b.model_copy(deep=True, update={"tiles": [], "cells": []}) for b in self._bodies.values()]

    def get_body(self, body_id: str) -> AnyBodyState:
        """Return a body's metadata without tiles/cells."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            return body.model_copy(deep=True, update={"tiles": [], "cells": []})

    def get_body_tiles(self, body_id: str, page: int = 0, size: int = 100) -> list:
        """Return a paginated list of GoldbergTileState for a spherical body.
        Tiles are generated on first access and cached in the body object.
        """
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            start = page * size
            return [t.model_copy(deep=True) for t in body.tiles[start:start + size]]

    def get_body_tiles_lod(self, body_id: str, h3_resolution: int, page: int = 0, size: int = 200) -> list:
        """Return tiles at a different H3 resolution than the stored one (LOD support).
        Generated in-memory, not persisted. resolution is clamped to [0, 3].
        Results are cached so the first call is slow (2s for res=3) but subsequent calls are instant.
        """
        h3_resolution = min(max(0, h3_resolution), 3)
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            # If requesting the stored resolution, just delegate (uses body.tiles cache)
            if h3_resolution == body.h3Resolution:
                return self.get_body_tiles(body_id, page=page, size=size)
            cache_key = (body_id, h3_resolution)
            cached = self._lod_tile_cache.get(cache_key)
            if cached is not None:
                start = page * size
                return [t.model_copy(deep=True) for t in cached[start:start + size]]
            # Save params before releasing lock
            override, water, seed, atmo = body.projectionOverride, body.waterLevel, body.seed, body.atmosphereDensity
        # Generate outside the lock — can be slow for res=3 (~2s)
        tiles = generate_spherical_tiles(h3_resolution, override, water, seed, atmo)
        with self._lock:
            # Cache only if still relevant (body hasn't been replaced)
            if body_id in self._bodies:
                self._lod_tile_cache[(body_id, h3_resolution)] = tiles
        start = page * size
        return [t.model_copy(deep=True) for t in tiles[start:start + size]]

    def get_body_tile(self, body_id: str, tile_id: str):
        """Return a single GoldbergTileState by H3 tile_id string."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            return tile.model_copy(deep=True)

    def get_body_tile_neighbors(self, body_id: str, tile_id: str) -> list:
        """Return the neighboring GoldbergTileStates of a given H3 tile (up to 6)."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            neighbor_ids = set(tile.neighborIds)
            return [t.model_copy(deep=True) for t in body.tiles if t.tileId in neighbor_ids]

    def get_body_tile_at(self, body_id: str, lat: float, lon: float):
        """Return the tile whose H3 cell contains the given lat/lon coordinates."""
        import h3 as _h3
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
                body.summary = summarize_spherical_tiles(tiles)
                body.tiles = tiles
            cell = _h3.latlng_to_cell(lat, lon, body.h3Resolution)
            tile = next((t for t in body.tiles if t.tileId == cell), None)
            if tile is None:
                raise KeyError(f"No tile at lat={lat}, lon={lon} on body {body_id}")
            return tile.model_copy(deep=True)

    def apply_body_tile_delta(
        self,
        body_id: str,
        tile_id: str,
        water_delta: float = 0.0,
        temperature_delta: float = 0.0,
    ):
        """Apply additive water/temperature deltas to a surface tile."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            tile.waterRatio = max(0.0, min(1.0, tile.waterRatio + water_delta))
            tile.temperature += temperature_delta
            from .logic import is_tile_habitable
            tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)
            if not body.isModified:
                body.isModified = True
                body.generationVersion = GENERATION_VERSION
                self._repo.save_body(body)
            self._repo.upsert_tile_mutation(body_id, TileMutation(
                tile_id=tile_id,
                water_ratio=tile.waterRatio,
                temperature=tile.temperature,
                toxin_level=tile.toxinLevel,
            ))
            return tile.model_copy(deep=True)

    def apply_body_tile_action(self, body_id: str, tile_id: str, action: TerraformAction):
        """Apply an immediate terraform action modifier to a surface tile."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            definitions = terraform_action_definitions()
            modifier = definitions[action].modifier
            tile.waterRatio = max(0.0, min(1.0, tile.waterRatio + modifier.waterDelta))
            tile.temperature += modifier.tempDelta
            tile.toxinLevel = max(0.0, min(1.0, tile.toxinLevel + modifier.toxinDelta))
            from .logic import is_tile_habitable
            tile.isHabitable = is_tile_habitable(tile.terrainType, tile.temperature, tile.waterRatio)
            if not body.isModified:
                body.isModified = True
                body.generationVersion = GENERATION_VERSION
                self._repo.save_body(body)
            self._repo.upsert_tile_mutation(body_id, TileMutation(
                tile_id=tile_id,
                water_ratio=tile.waterRatio,
                temperature=tile.temperature,
                toxin_level=tile.toxinLevel,
            ))
            return tile.model_copy(deep=True)

    # ── Atmosphere API ─────────────────────────────────────────────────────────

    def get_body_atmosphere(self, body_id: str) -> dict:
        """Return the atmospheric composition and equilibrium temperature of a body."""
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} has no atmosphere (interior zone)")
            return {
                "atmosphere": body.atmosphere.model_copy(deep=True),
                "equilibriumTemperature": body.equilibriumTemperature,
                "luminosityLsun": body.luminosityLsun,
            }

    def patch_atmosphere(self, body_id: str, gas_name: str, fraction_delta: float) -> AtmosphericComposition:
        """Add fraction_delta to a named gas in a body's atmosphere (clamped to [0, 1]).
        The gas must already exist in atmosphere.gases; unknown names raise KeyError.
        Returns the updated AtmosphericComposition.
        """
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} has no atmosphere")
            gas = next((g for g in body.atmosphere.gases if g.name.upper() == gas_name.upper()), None)
            if gas is None:
                raise KeyError(f"Gas '{gas_name}' not tracked in body {body_id} atmosphere")
            gas.fraction = max(0.0, min(1.0, gas.fraction + fraction_delta))
            body.isModified = True
            self._repo.save_body(body)
            return body.atmosphere.model_copy(deep=True)

    def apply_tile_atmosphere_delta(
        self,
        body_id: str,
        tile_id: str,
        co2_delta: float = 0.0,
        o2_delta: float = 0.0,
    ):
        """Set per-tick atmospheric deltas on a tile (from a building/plant action).
        These accumulate and are folded into planet atmosphere by aggregate_tile_deltas().
        Returns the updated tile.
        """
        with self._lock:
            body = self._bodies.get(body_id)
            if body is None:
                raise KeyError(f"Body not found: {body_id}")
            if not isinstance(body, SphericalBodyState):
                raise TypeError(f"Body {body_id} is not a spherical body")
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                )
            tile = next((t for t in body.tiles if t.tileId == tile_id), None)
            if tile is None:
                raise KeyError(f"Tile {tile_id} not found on body {body_id}")
            tile.atmosphereDeltaCo2 = co2_delta
            tile.atmosphereDeltaO2  = o2_delta
            return tile.model_copy(deep=True)

    def register_interior_zone(
        self,
        parent_body_id: str,
        zone_type: ZoneType,
        cols: int,
        rows: int,
        parent_tile_id: str | None = None,
        seed: int | None = None,
    ) -> InteriorZoneState:
        """Create an interior zone attached to a body tile and populate its hex cells."""
        with self._lock:
            parent = self._bodies.get(parent_body_id)
            if parent is None:
                raise KeyError(f"Parent body not found: {parent_body_id}")
            effective_seed = seed if seed is not None else (hash(f"{parent_body_id}{zone_type}{parent_tile_id}") & 0x7FFFFFFF)
            zone_id = str(uuid4())
            cells = generate_interior_cells(cols, rows, zone_type, effective_seed)
            summary = summarize_region_cells(cells)
            zone = InteriorZoneState(
                bodyId=zone_id,
                bodyType=BodyType.SpaceStation if zone_type in (ZoneType.Station, ZoneType.Ship) else BodyType.Planet,
                name=f"{zone_type.name} ({parent.name})",
                parentId=parent_body_id,
                seed=effective_seed,
                zoneType=zone_type,
                parentTileId=parent_tile_id,
                cols=cols,
                rows=rows,
                summary=summary,
                cells=cells,
            )
            self._bodies[zone_id] = zone
            # Link zone to parent tile if applicable
            if parent_tile_id is not None and isinstance(parent, SphericalBodyState) and parent.tiles:
                tile = next((t for t in parent.tiles if t.tileId == parent_tile_id), None)
                if tile is not None:
                    tile.childZoneIds.append(zone_id)
            # Mark parent body as modified (a zone was built on it)
            if isinstance(parent, SphericalBodyState) and not parent.isModified:
                parent.isModified = True
                parent.generationVersion = GENERATION_VERSION
                self._repo.save_body(parent)
            self._repo.save_body(zone)
            return zone.model_copy(deep=True)

    def get_interior_zone(self, zone_id: str) -> InteriorZoneState:
        """Return an interior zone with all cells populated."""
        with self._lock:
            body = self._bodies.get(zone_id)
            if body is None:
                raise KeyError(f"Zone not found: {zone_id}")
            if not isinstance(body, InteriorZoneState):
                raise TypeError(f"Body {zone_id} is not an interior zone")
            return body.model_copy(deep=True)

    # ── Galaxy layer ───────────────────────────────────────────────────────────

    def wipe_galaxy(self) -> dict:
        """Destroy all galaxy bodies, systems, routes and travels, then re-bootstrap.
        Intended for testing and world-reset workflows.
        Re-runs bootstrap_sol() for a full fresh Sol system.
        Returns a summary dict with counts of deleted and recreated items.
        """
        with self._lock:
            deleted_bodies = sum(
                1 for b in self._bodies.values()
                if isinstance(b, SphericalBodyState) and b.systemId
            )
            deleted_systems = len(self._solar_systems)
            deleted_routes = len(self._stellar_routes)
            deleted_travels = len(self._space_travels)

        # bootstrap_sol acquires the RLock internally; it wipes everything and rebuilds
        self.bootstrap_sol()

        with self._lock:
            return {
                "deleted": {
                    "bodies": deleted_bodies,
                    "systems": deleted_systems,
                    "routes": deleted_routes,
                    "travels": deleted_travels,
                },
                "created": {
                    "systems": len(self._solar_systems),
                    "bodies": sum(
                        1 for b in self._bodies.values()
                        if isinstance(b, SphericalBodyState) and b.systemId
                    ),
                    "routes": len(self._stellar_routes),
                },
            }

    def _bootstrap_galaxy_locked(self) -> None:
        """Create the Kepler-442 home system and a distant Sol system as exploration target.
        Called from bootstrap_demo() while the lock is already held.
        Idempotent: skips if systems already exist.
        """
        if self._solar_systems:
            return

        def _make_system(name: str, x: float, y: float, z: float) -> SolarSystemState:
            sid = str(uuid4())
            system = SolarSystemState(
                systemId=sid, name=name,
                position=GalacticPosition(x=x, y=y, z=z),
            )
            self._solar_systems[sid] = system
            self._repo.save_solar_system(system)
            return system

        def _add_star(system: SolarSystemState, name: str, radius_km: float, spectral: str, seed: int,
                      orbital: OrbitalParameters | None = None) -> SphericalBodyState:
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=BodyType.Star,
                radius_km=radius_km, coherence_override=DebugCoherenceOverride.None_,
                water_level=0.0, seed=seed,
            )
            body.spectralType = spectral
            body.systemId = system.systemId
            body.orbitalParams = orbital
            if system.rootBodyId == "":
                system.rootBodyId = body.bodyId
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body

        def _add_body(system: SolarSystemState, name: str, body_type: BodyType,
                      radius_km: float, water_level: float, seed: int,
                      orbital: OrbitalParameters, parent_id: str | None = None,
                      spectral: str = "") -> SphericalBodyState:
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=body_type,
                radius_km=radius_km,
                coherence_override=(DebugCoherenceOverride.Ocean if water_level > 0.5
                                    else DebugCoherenceOverride.Arid if water_level < 0.05
                                    else DebugCoherenceOverride.Coast),
                water_level=water_level, seed=seed, parent_id=parent_id,
            )
            body.systemId = system.systemId
            body.orbitalParams = orbital
            body.spectralType = spectral
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body

        # ── System Kepler-442 (système du joueur) ────────────────────
        kepler = _make_system("Kepler-442", 0.0, 0.0, 0.0)
        kepler_star = _add_star(kepler, "Kepler-442", 513000.0, "K", 3001)

        # Lier le corps bootstrappé (Kepler-442b, Astra-Prime, ou autre) à ce système
        active_planet = next(
            (b for b in self._bodies.values()
             if isinstance(b, SphericalBodyState) and b.bodyType == BodyType.Planet),
            None,
        )
        if active_planet is not None:
            active_planet.systemId = kepler.systemId
            active_planet.orbitalParams = OrbitalParameters(
                semiMajorAxisAU=0.409, eccentricity=0.0, periodTicks=112,
            )
            active_planet.parentId = kepler_star.bodyId
            kepler.bodyIds.append(active_planet.bodyId)
            self._repo.save_body(active_planet)
            self._repo.save_solar_system(kepler)

        # ── System Sol (cible d'exploration distante, cachée) ─────────
        sol = _make_system("Sol", 1200.0, 0.0, 0.0)
        sol.isDiscovered = False  # cachée jusqu'à l'exploration
        self._repo.save_solar_system(sol)
        sun = _add_star(sol, "Sun", 695700.0, "G2V", 1001)
        _add_body(sol, "Earth", BodyType.Planet, 6371.0, 0.71, 1004,
                  OrbitalParameters(semiMajorAxisAU=1.0, eccentricity=0.017, periodTicks=365),
                  sun.bodyId)

        # ── Route cachée Kepler-442 → Sol ────────────────────────────
        route = self._create_stellar_route_locked(
            from_system_id=kepler.systemId,
            to_system_id=sol.systemId,
            travel_time_modifier=1.0,
            description="Signal interstellaire capté par les sondes de Kepler-442b.",
        )
        _ = route

    def _create_stellar_route_locked(
        self,
        from_system_id: str,
        to_system_id: str,
        travel_time_modifier: float = 1.0,
        description: str = "",
        status: RouteStatus = RouteStatus.Hidden,
    ) -> StellarRoute:
        """Create a stellar route; distance calculated from system positions. Lock must be held."""
        src = self._solar_systems.get(from_system_id)
        dst = self._solar_systems.get(to_system_id)
        if src is None:
            raise KeyError(f"System not found: {from_system_id}")
        if dst is None:
            raise KeyError(f"System not found: {to_system_id}")
        dx = src.position.x - dst.position.x
        dy = src.position.y - dst.position.y
        dz = src.position.z - dst.position.z
        dist_ly = math.sqrt(dx * dx + dy * dy + dz * dz)
        route = StellarRoute(
            routeId=str(uuid4()),
            fromSystemId=from_system_id,
            toSystemId=to_system_id,
            distanceLy=round(dist_ly, 4),
            travelTimeModifier=travel_time_modifier,
            status=status,
            description=description,
        )
        self._stellar_routes[route.routeId] = route
        self._repo.save_stellar_route(route)
        return route

    # ── Public galaxy API ─────────────────────────────────────────────

    def create_solar_system(
        self,
        name: str,
        x: float,
        y: float,
        z: float,
        description: str = "",
    ) -> SolarSystemState:
        """Create a new solar system at the given galactic position (light-years)."""
        with self._lock:
            system = SolarSystemState(
                systemId=str(uuid4()),
                name=name,
                position=GalacticPosition(x=x, y=y, z=z),
                description=description,
            )
            self._solar_systems[system.systemId] = system
            self._repo.save_solar_system(system)
            return system.model_copy(deep=True)

    def get_solar_system(self, system_id: str) -> SolarSystemState:
        with self._lock:
            system = self._solar_systems.get(system_id)
            if system is None:
                raise KeyError(f"System not found: {system_id}")
            return system.model_copy(deep=True)

    def list_solar_systems(self) -> list[SolarSystemState]:
        with self._lock:
            return [s.model_copy(deep=True) for s in self._solar_systems.values()]

    def add_body_to_system(
        self,
        system_id: str,
        body_type: BodyType,
        name: str,
        radius_km: float,
        water_level: float = 0.0,
        seed: int = 0,
        parent_body_id: str | None = None,
        orbital_semi_major_axis_au: float = 1.0,
        orbital_eccentricity: float = 0.0,
        orbital_inclination_deg: float = 0.0,
        orbital_initial_phase_deg: float = 0.0,
        orbital_period_ticks: int = 365,
        spectral_type: str = "",
        is_system_root: bool = False,
    ) -> SphericalBodyState:
        """Create a SphericalBodyState, attach orbital parameters, and register it in the system."""
        with self._lock:
            system = self._solar_systems.get(system_id)
            if system is None:
                raise KeyError(f"System not found: {system_id}")
            coherence = (DebugCoherenceOverride.Ocean if water_level > 0.5
                         else DebugCoherenceOverride.Arid if water_level < 0.05
                         else DebugCoherenceOverride.Coast)
            effective_seed = seed or (hash(f"{system_id}{name}") & 0x7FFFFFFF)
            body = self._register_spherical_body_locked(
                body_id=None, name=name, body_type=body_type,
                radius_km=radius_km, coherence_override=coherence,
                water_level=water_level, seed=effective_seed,
                parent_id=parent_body_id,
            )
            body.systemId = system_id
            body.spectralType = spectral_type
            if not is_system_root:
                body.orbitalParams = OrbitalParameters(
                    semiMajorAxisAU=orbital_semi_major_axis_au,
                    eccentricity=orbital_eccentricity,
                    inclinationDeg=orbital_inclination_deg,
                    initialPhaseDeg=orbital_initial_phase_deg,
                    periodTicks=orbital_period_ticks,
                )
            if is_system_root or system.rootBodyId == "":
                system.rootBodyId = body.bodyId
            system.bodyIds.append(body.bodyId)
            self._repo.save_body(body)
            self._repo.save_solar_system(system)
            return body.model_copy(deep=True, update={"tiles": [], "cells": []})

    def remove_body_from_system(self, system_id: str, body_id: str) -> None:
        """Remove a body from a system and from the body registry."""
        with self._lock:
            system = self._solar_systems.get(system_id)
            if system is None:
                raise KeyError(f"System not found: {system_id}")
            if body_id not in self._bodies:
                raise KeyError(f"Body not found: {body_id}")
            system.bodyIds = [b for b in system.bodyIds if b != body_id]
            if system.rootBodyId == body_id:
                system.rootBodyId = system.bodyIds[0] if system.bodyIds else ""
            del self._bodies[body_id]
            self._repo.save_solar_system(system)

    def get_body_position_at_tick(self, body_id: str, tick: int | None = None) -> dict:
        """Compute the 3D position (AU) of a body relative to its system root at a given tick."""
        with self._lock:
            effective_tick = tick if tick is not None else self._tick_count
            return compute_body_position_at_tick(body_id, effective_tick, self._bodies)

    # ── Stellar routes ────────────────────────────────────────────────

    def create_stellar_route(
        self,
        from_system_id: str,
        to_system_id: str,
        travel_time_modifier: float = 1.0,
        description: str = "",
        status: RouteStatus = RouteStatus.Hidden,
    ) -> StellarRoute:
        with self._lock:
            return self._create_stellar_route_locked(
                from_system_id, to_system_id, travel_time_modifier, description, status,
            )

    def list_stellar_routes(self, known_only: bool = False) -> list[StellarRoute]:
        with self._lock:
            return [
                r.model_copy(deep=True) for r in self._stellar_routes.values()
                if not known_only or r.status == RouteStatus.Known
            ]

    def get_stellar_route(self, route_id: str) -> StellarRoute:
        with self._lock:
            route = self._stellar_routes.get(route_id)
            if route is None:
                raise KeyError(f"Route not found: {route_id}")
            return route.model_copy(deep=True)

    def reveal_stellar_route(self, route_id: str) -> StellarRoute:
        with self._lock:
            route = self._stellar_routes.get(route_id)
            if route is None:
                raise KeyError(f"Route not found: {route_id}")
            route.status = RouteStatus.Known
            self._repo.save_stellar_route(route)
            return route.model_copy(deep=True)

    def delete_stellar_route(self, route_id: str) -> None:
        with self._lock:
            if route_id not in self._stellar_routes:
                raise KeyError(f"Route not found: {route_id}")
            del self._stellar_routes[route_id]
            self._repo.delete_stellar_route(route_id)

    # ── Space travel ──────────────────────────────────────────────────

    def initiate_travel(
        self,
        from_system_id: str,
        to_system_id: str,
        route_id: str,
        faction_id: str = "",
    ) -> SpaceTravel:
        """Start a journey. Route must be Known. Arrival tick computed from distance × modifier."""
        with self._lock:
            route = self._stellar_routes.get(route_id)
            if route is None:
                raise KeyError(f"Route not found: {route_id}")
            if route.status != RouteStatus.Known:
                raise ValueError(f"Route {route_id} is not known — must be revealed first")
            # Route must connect the requested systems (either direction)
            pair = {route.fromSystemId, route.toSystemId}
            if from_system_id not in pair or to_system_id not in pair:
                raise ValueError("Route does not connect the requested systems")
            ticks_needed = max(1, round(route.distanceLy * TICKS_PER_LIGHT_YEAR * route.travelTimeModifier))
            travel = SpaceTravel(
                travelId=str(uuid4()),
                factionId=faction_id,
                fromSystemId=from_system_id,
                toSystemId=to_system_id,
                routeId=route_id,
                distanceLy=route.distanceLy,
                departedAtTick=self._tick_count,
                arrivalTick=self._tick_count + ticks_needed,
                status=TravelStatus.InTransit,
            )
            self._space_travels[travel.travelId] = travel
            self._repo.save_space_travel(travel)
            return travel.model_copy(deep=True)

    def get_travel(self, travel_id: str) -> SpaceTravel:
        with self._lock:
            travel = self._space_travels.get(travel_id)
            if travel is None:
                raise KeyError(f"Travel not found: {travel_id}")
            return travel.model_copy(deep=True)

    def list_active_travels(self) -> list[SpaceTravel]:
        with self._lock:
            return [t.model_copy(deep=True) for t in self._space_travels.values()
                    if t.status == TravelStatus.InTransit]

    def cancel_travel(self, travel_id: str) -> SpaceTravel:
        with self._lock:
            travel = self._space_travels.get(travel_id)
            if travel is None:
                raise KeyError(f"Travel not found: {travel_id}")
            if travel.status != TravelStatus.InTransit:
                raise ValueError(f"Travel {travel_id} is not in-transit (status={travel.status.name})")
            travel.status = TravelStatus.Cancelled
            self._repo.save_space_travel(travel)
            return travel.model_copy(deep=True)

    def galaxy_overview(self) -> dict:
        with self._lock:
            return {
                "systemCount": len(self._solar_systems),
                "knownRouteCount": sum(1 for r in self._stellar_routes.values() if r.status == RouteStatus.Known),
                "hiddenRouteCount": sum(1 for r in self._stellar_routes.values() if r.status == RouteStatus.Hidden),
                "activeTravelCount": sum(1 for t in self._space_travels.values() if t.status == TravelStatus.InTransit),
            }