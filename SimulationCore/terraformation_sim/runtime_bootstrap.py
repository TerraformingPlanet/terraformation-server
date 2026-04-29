from __future__ import annotations

import json
from uuid import uuid4

from .models import (
    AtmosphericComposition,
    AtmosphericGas,
    ATMOSPHERE_PRESETS,
    BodyType,
    BuildingData,
    CorporationData,
    ContractData,
    DebugCoherenceOverride,
    GalacticPosition,
    InteriorZoneState,
    LocalMarketState,
    NationalizationProcess,
    OrbitalParameters,
    PendingTerraformAction,
    RegionState,
    SimulationCoordinates,
    SimulationEvent,
    SimulationEventType,
    SolarSystemState,
    SpaceTravel,
    SphericalBodyState,
    StellarRoute,
    StateData,
    StateType,
    TerritoryData,
    TerritoryQueue,
    TradeRoute,
    WorldState,
)
from .logic import (
    build_territories_from_tiles,
    compute_equilibrium_temperature,
    compute_planetary_irradiance,
    compute_tile_irradiance,
    generate_spherical_tiles,
    GENERATION_VERSION,
    seed_tile_population,
    spectral_type_to_luminosity,
    summarize_spherical_tiles,
    _hydrate_tiles_from_db,
)
from .models import STATE_PROFILES, StateProfile


class BootstrapMixin:
    """World bootstrap: fresh Sol system, Earth colonisation, state from persistence.

    State accessed via self:
        self._lock, self._bodies, self._active_body_id, self._solar_systems,
        self._stellar_routes, self._space_travels, self._corporations,
        self._tile_ownership, self._buildings, self._markets, self._contracts,
        self._states, self._reputations, self._nationalizations, self._game_events,
        self._agent_memories, self._construction_queues, self._territories,
        self._territory_tile_index, self._trade_routes, self._expeditions,
        self._lod_tile_cache, self._region_mutations, self._pending_actions,
        self._world_state, self._last_event, self._tick_count, self._tick_running,
        self._tick_interval_seconds, self._speed_multiplier, self._terrain_type_defs,
        self._gm_cooldown_tick, self._gm_last_lever, self._repo
    """

    # ── Public entry point ─────────────────────────────────────────────────────

    def bootstrap(self) -> WorldState:
        """Bootstrap the Sol solar system as the player's home system.

        Wipes all existing bodies and galaxy state first.
        Earth is the active planet. All 8 planets + key moons are registered.
        Kepler-442 is created as a hidden distant system.
        """
        with self._lock:
            # ── Wipe existing state ──────────────────────────────────────────
            for bid in list(self._bodies):
                self._repo.delete_tile_mutations(bid)
                self._repo.delete_body(bid)
            self._repo.clear_all_tiles()
            self._repo.clear_all_buildings()
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
            self._region_mutations = {}
            self._river_arrival_ticks = {}
            self._repo.clear_cell_mutations()
            self._corporations = {}
            self._repo.clear_corporations()
            self._tile_ownership = {}
            self._buildings = {}
            self._markets = {}
            self._repo.clear_markets()
            self._contracts = {}
            self._repo.clear_contracts()
            self._states = {}
            self._repo.clear_states()
            self._reputations = {}
            self._repo.clear_reputations()
            self._nationalizations = {}
            self._repo.clear_nationalizations()
            self._game_events = []
            self._agent_memories = {}
            self._construction_queues = {}
            self._repo.clear_construction_queues()
            self._repo.clear_trade_routes()
            self._repo.clear_expeditions()
            self._gm_cooldown_tick = 0
            self._gm_last_lever = ""
            self._territories = {}
            self._territory_tile_index = {}
            self._repo.clear_territories()

            # ── Bootstrap Sol ────────────────────────────────────────────────
            earth_name = "Earth"
            earth_water = 0.63
            earth_override = DebugCoherenceOverride.Coast
            earth_seed = 1004

            projection = self._build_projection_state(earth_name, earth_override, earth_water)
            region = self._build_region_state(
                earth_name,
                SimulationCoordinates(latitude=0.47, longitude=0.18),
                self._tick_count,
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
            self._bootstrap_earth_colonization_locked(earth)
            self._bootstrap_sol_galaxy_locked(earth)
            return self._world_state.model_copy(deep=True)

    # ── Earth colonisation ─────────────────────────────────────────────────────

    def _bootstrap_earth_colonization_locked(self, earth: SphericalBodyState) -> None:
        """Partition Earth's terrestrial tiles into nation-state territories and seed population.
        Lock must be held.
        """
        from .logic.generation import summarize_spherical_tiles as _summarize
        from .logic.colonization import assign_tile_to_continent  # noqa: F401

        body_id = earth.bodyId

        if not earth.tiles:
            tiles = generate_spherical_tiles(
                earth.h3Resolution, earth.projectionOverride, earth.waterLevel, earth.seed,
                atmosphere_density=earth.atmosphereDensity,
                terrain_defs=self._terrain_type_defs or None,
            )
            earth.summary = _summarize(tiles)
            earth.tiles = tiles
            self._repo.save_tiles_bulk(body_id, tiles)

        territories, _tile_to_zone = build_territories_from_tiles(
            earth.tiles, body_id, population_base=500
        )

        zone_to_state_id: dict[str, str] = {}
        zone_to_profile: dict[str, StateProfile] = {}

        for terr in territories:
            base_name = terr.name.split(" (Région")[0]
            if base_name not in zone_to_state_id:
                profile = STATE_PROFILES.get(terr.profileKey, STATE_PROFILES["Standard"])
                zone_to_profile[base_name] = profile
                state = StateData(
                    id=str(uuid4()),
                    name=base_name,
                    stateType=StateType.Capitalist,
                    taxRate=profile.taxRate,
                    corruptionRate=profile.corruptionRate,
                    bureaucracy=profile.bureaucracy,
                    literacyRate=profile.literacyRate,
                    profileKey=terr.profileKey,
                    isAiControlled=True,
                )
                zone_to_state_id[base_name] = state.id
                self._states[state.id] = state
                self._repo.save_state(state)

        tile_map = {t.tileId: t for t in earth.tiles}
        for terr in territories:
            base_name = terr.name.split(" (Région")[0]
            state_id = zone_to_state_id[base_name]
            profile  = zone_to_profile[base_name]
            terr.stateId = state_id

            self._territories[terr.id] = terr
            for tid in terr.tileIds:
                self._territory_tile_index[f"{body_id}::{tid}"] = terr.id

            state = self._states[state_id]
            if terr.id not in state.territoryIds:
                state.territoryIds.append(terr.id)
            state.tileIds.extend(terr.tileIds)

            for tile_id in terr.tileIds:
                tile = tile_map.get(tile_id)
                if tile is None:
                    continue
                pop = seed_tile_population(tile, terr.populationBase, profile.popDistribution)
                if pop:
                    # Store population directly on the GoldbergTileState (tile-centric model)
                    tile_map[tile_id] = tile.model_copy(update={"population": pop})

            self._repo.save_territory(terr)

        # Propagate updated tiles (with population) back into earth.tiles
        earth.tiles = list(tile_map.values())
        # Re-save tiles now that population has been seeded
        self._repo.save_tiles_bulk(body_id, earth.tiles)

        for state in self._states.values():
            self._repo.save_state(state)

    # ── Sol galaxy bootstrap ───────────────────────────────────────────────────

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

        def _add_star(
            system: SolarSystemState, name: str, radius_km: float,
            spectral: str, seed: int,
        ) -> SphericalBodyState:
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
            atmosphere: AtmosphericComposition | None = None,
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

        # ── Sol (home system) ────────────────────────────────────────────────
        sol = _make_system("Sol", 0.0, 0.0, 0.0)
        sun = _add_star(sol, "Sun", 695700.0, "G2V", 1001)

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

        _add_body(sol, "Luna",    BodyType.Moon,   1737.0,  0.01, 2001, 0.00257, 27,  active_earth.bodyId, atmosphere_density=0.00)

        jupiter = _add_body(sol, "Jupiter", BodyType.Planet, 69911.0, 0.00, 1006, 5.203,  4333,  sun.bodyId,
                            DebugCoherenceOverride.None_, atmosphere_density=0.90)
        saturn  = _add_body(sol, "Saturn",  BodyType.Planet, 58232.0, 0.00, 1007, 9.537,  10759, sun.bodyId,
                            DebugCoherenceOverride.None_, atmosphere_density=0.85)
        _add_body(sol, "Uranus",  BodyType.Planet, 25362.0, 0.00, 1008, 19.19,  30685, sun.bodyId,
                  DebugCoherenceOverride.Frozen, atmosphere_density=0.75)
        _add_body(sol, "Neptune", BodyType.Planet, 24622.0, 0.00, 1009, 30.07,  60190, sun.bodyId,
                  DebugCoherenceOverride.Frozen, atmosphere_density=0.75)

        _add_body(sol, "Io",       BodyType.Moon, 1821.0, 0.00, 2002, 0.00282, 2,  jupiter.bodyId, atmosphere_density=0.05)
        _add_body(sol, "Europa",   BodyType.Moon, 1560.0, 0.70, 2003, 0.00449, 4,  jupiter.bodyId, atmosphere_density=0.02)
        _add_body(sol, "Ganymede", BodyType.Moon, 2634.0, 0.30, 2004, 0.00716, 7,  jupiter.bodyId, atmosphere_density=0.01)

        _add_body(sol, "Titan",    BodyType.Moon, 2575.0, 0.10, 2005, 0.00817, 16, saturn.bodyId, atmosphere_density=0.95)

        # ── Kepler-442 (hidden exploration target) ───────────────────────────
        kepler = _make_system("Kepler-442", 1200.0, 0.0, 0.0)
        kepler.isDiscovered = False
        self._repo.save_solar_system(kepler)
        kepler_star = _add_star(kepler, "Kepler-442", 513000.0, "K", 3001)
        _add_body(kepler, "Kepler-442b", BodyType.Planet, 7600.0, 0.55, 3002,
                  0.409, 112, kepler_star.bodyId, DebugCoherenceOverride.Ocean,
                  atmosphere=AtmosphericComposition(
                      totalPressureKpa=40.0,
                      gases=[
                          AtmosphericGas(name="N2",  fraction=0.70, greenhouseCoeff=0.0, molarMass=28.0),
                          AtmosphericGas(name="CO2", fraction=0.15, greenhouseCoeff=1.0, molarMass=44.0),
                          AtmosphericGas(name="H2O", fraction=0.05, greenhouseCoeff=0.5, molarMass=18.0),
                          AtmosphericGas(name="O2",  fraction=0.10, greenhouseCoeff=0.0, molarMass=32.0),
                      ],
                  ))

        # ── Luminosity and equilibrium temperature passes ─────────────────────
        for body in self._bodies.values():
            if isinstance(body, SphericalBodyState) and body.bodyType == BodyType.Star:
                body.luminosityLsun = spectral_type_to_luminosity(body.spectralType, body.radiusKm)
                self._repo.save_body(body)

        for body in self._bodies.values():
            if not isinstance(body, SphericalBodyState):
                continue
            if body.bodyType == BodyType.Star or body.orbitalParams is None:
                continue
            parent = self._bodies.get(body.parentId or "")
            if parent is None or not isinstance(parent, SphericalBodyState):
                continue
            if parent.bodyType == BodyType.Star:
                star_luminosity = parent.luminosityLsun
                star_au = body.orbitalParams.semiMajorAxisAU
            else:
                grandparent = self._bodies.get(parent.parentId or "")
                if grandparent is None or not isinstance(grandparent, SphericalBodyState) or grandparent.bodyType != BodyType.Star:
                    continue
                star_luminosity = grandparent.luminosityLsun
                star_au = parent.orbitalParams.semiMajorAxisAU if parent.orbitalParams else 0.0
            if star_luminosity > 0.0 and star_au > 0.0:
                irr = compute_planetary_irradiance(star_luminosity, star_au)
                body.equilibriumTemperature = compute_equilibrium_temperature(irr, body.atmosphere)
                self._repo.save_body(body)

        for body in self._bodies.values():
            if not isinstance(body, SphericalBodyState):
                continue
            if body.bodyType == BodyType.Star or body.orbitalParams is None:
                continue
            parent = self._bodies.get(body.parentId or "")
            if parent is None or not isinstance(parent, SphericalBodyState):
                continue
            if parent.bodyType == BodyType.Star:
                star_luminosity = parent.luminosityLsun
                star_au = body.orbitalParams.semiMajorAxisAU
            else:
                grandparent = self._bodies.get(parent.parentId or "")
                if grandparent is None or not isinstance(grandparent, SphericalBodyState) or grandparent.bodyType != BodyType.Star:
                    continue
                star_luminosity = grandparent.luminosityLsun
                star_au = parent.orbitalParams.semiMajorAxisAU if parent.orbitalParams else 0.0
            if star_luminosity > 0.0 and star_au > 0.0 and body.tiles:
                planet_irradiance_wm2 = compute_planetary_irradiance(star_luminosity, star_au)
                for tile in body.tiles:
                    tile.solarIrradiance = compute_tile_irradiance(tile.latDeg, planet_irradiance_wm2)
                self._repo.save_body(body)

        self._create_stellar_route_locked(
            from_system_id=sol.systemId,
            to_system_id=kepler.systemId,
            travel_time_modifier=1.0,
            description="Signal interstellaire capté depuis l'orbite de Mars.",
        )
        _ = mars  # referenced for future use

    # ── Hydrate from persistence ───────────────────────────────────────────────

    def _hydrate_from_saved(self, saved) -> None:
        """Restore runtime state from a SavedState loaded from the repository."""
        self._tick_count = saved.tick_count
        self._tick_running = saved.tick_running
        self._tick_interval_seconds = max(0.1, saved.tick_interval_seconds)

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

        import logging as _logging
        _tile_log = _logging.getLogger(__name__)

        if saved.terrain_type_defs:
            self._terrain_type_defs = {r["terrain_type_id"]: r for r in saved.terrain_type_defs}

        for body_id, tile_rows in saved.tile_data.items():
            body = self._bodies.get(body_id)
            if body is None or not isinstance(body, SphericalBodyState):
                continue
            if tile_rows:
                body.tiles = _hydrate_tiles_from_db(tile_rows)
                _tile_log.info("Body %s: loaded %d tiles from DB", body_id, len(body.tiles))

        for body_id, mutations in saved.tile_mutations.items():
            body = self._bodies.get(body_id)
            if body is None or not isinstance(body, SphericalBodyState):
                continue
            if body.tiles:
                continue
            if body.isModified and body.generationVersion != GENERATION_VERSION:
                _tile_log.warning(
                    "Body %s was modified under generation version %r but current is %r — "
                    "tiles will regenerate on next access",
                    body_id, body.generationVersion, GENERATION_VERSION,
                )
            if not body.tiles:
                body.tiles = generate_spherical_tiles(
                    body.h3Resolution, body.projectionOverride, body.waterLevel, body.seed,
                    atmosphere_density=body.atmosphereDensity,
                    terrain_defs=self._terrain_type_defs or None,
                )
                self._repo.save_tiles_bulk(body_id, body.tiles)
            tile_by_id = {t.tileId: t for t in body.tiles}
            for m in mutations:
                tile = tile_by_id.get(m.tile_id)
                if tile is not None:
                    tile.waterRatio = m.water_ratio
                    tile.temperature = m.temperature
                    tile.toxinLevel = m.toxin_level

        active_name = saved.active_planet_name or "Astra-Prime"
        override = DebugCoherenceOverride(saved.projection_override)
        projection = self._build_projection_state(active_name, override, saved.projection_water_level)
        coords = SimulationCoordinates(latitude=saved.region_lat, longitude=saved.region_lon)
        region = (
            self._build_region_state(active_name, coords, self._tick_count)
            if saved.has_region
            else RegionState()
        )

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

        for action_json in saved.pending_actions_json:
            try:
                self._pending_actions.append(PendingTerraformAction.model_validate_json(action_json))
            except Exception:
                pass

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

        for region_key, cell_list in saved.cell_mutations.items():
            for m in cell_list:
                try:
                    data = json.loads(m.cell_json)
                    k = (m.cell_q, m.cell_r)
                    self._region_mutations.setdefault(region_key, {})[k] = (
                        float(data.get("wd", 0.0)),
                        float(data.get("td", 0.0)),
                    )
                except Exception:
                    pass

        for corp_json in saved.corporations_json:
            try:
                corp = CorporationData.model_validate_json(corp_json)
                self._corporations[corp.id] = corp
                for tile in corp.claimedTiles:
                    self._tile_ownership.setdefault(tile.bodyId, {})[tile.tileId] = corp.id
                for b in corp.buildings:
                    self._buildings[b.id] = b
            except Exception:
                pass

        if saved.buildings_data:
            self._buildings.clear()
            for body_id, bldg_rows in saved.buildings_data.items():
                for row in bldg_rows:
                    try:
                        b = BuildingData(
                            id=row["building_id"],
                            buildingType=row["building_type"],
                            tileId=row["tile_id"],
                            bodyId=row["body_id"],
                            corpId=row["corp_id"],
                            workerRatio=row["worker_ratio"],
                            ticksActive=row["ticks_active"],
                            level=row["level"],
                            employmentSlots=json.loads(row["employment_slots"]),
                        )
                        self._buildings[b.id] = b
                    except Exception:
                        pass

        for contract_json in saved.contracts_json:
            try:
                contract = ContractData.model_validate_json(contract_json)
                self._contracts[contract.id] = contract
            except Exception:
                pass

        for state_json in saved.states_json:
            try:
                state = StateData.model_validate_json(state_json)
                self._states[state.id] = state
            except Exception:
                pass

        for nat_json in saved.nationalizations_json:
            try:
                nat = NationalizationProcess.model_validate_json(nat_json)
                self._nationalizations[nat.id] = nat
            except Exception:
                pass

        for source_id, target_id, score in saved.reputations_raw:
            self._reputations[(source_id, target_id)] = score

        for route_json in saved.trade_routes_json:
            try:
                route = TradeRoute.model_validate_json(route_json)
                self._trade_routes[route.id] = route
            except Exception:
                pass

        from .models import ExpeditionUnit as _ExpeditionUnit, TerritoryQueue as _TerritoryQueue
        for exp_json in saved.expeditions_json:
            try:
                exp = _ExpeditionUnit.model_validate_json(exp_json)
                self._expeditions[exp.id] = exp
            except Exception:
                pass

        for queue_json in saved.construction_queues_json:
            try:
                queue = TerritoryQueue.model_validate_json(queue_json)
                self._construction_queues[queue.territoryId] = queue
            except Exception:
                pass

        for market_json in saved.markets_json:
            try:
                market = LocalMarketState.model_validate_json(market_json)
                self._markets[market.territoryId] = market
            except Exception:
                pass

        try:
            self._tile_ownership = json.loads(saved.tile_ownership_json)
        except Exception:
            pass

        for terr_json in saved.territories_json:
            try:
                terr = TerritoryData.model_validate_json(terr_json)
                self._territories[terr.id] = terr
                for tid in terr.tileIds:
                    self._territory_tile_index[f"{terr.bodyId}::{tid}"] = terr.id
            except Exception:
                pass

        if not self._solar_systems:
            self._bootstrap_galaxy_locked()

        self._last_event = SimulationEvent(
            eventId=str(uuid4()),
            type=SimulationEventType.SnapshotCaptured,
            message=f"State restored from persistence (tick={self._tick_count})",
        )
