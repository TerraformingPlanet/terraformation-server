import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as _BaseModel

from terraformation_sim import (
    ClaimedTile,
    CorporationData,
    AnyBodyState,
    AtmosphericComposition,
    BodyBase,
    BodyType,
    DebugCoherenceOverride,
    GalacticPosition,
    GoldbergTileState,
    InMemoryRepository,
    InMemorySimulationRuntime,
    InteriorZoneState,
    PostgresRepository,
    ProjectionState,
    RegionState,
    RouteStatus,
    SimulationActionCatalog,
    SimulationCellAddress,
    SimulationCellState,
    SimulationEvent,
    SolarSystemState,
    SpaceTravel,
    SphericalBodyState,
    StellarRoute,
    TerraformAction,
    TerraformActionDefinition,
    TravelStatus,
    WorldState,
    ZoneType,
)


app = FastAPI(title="terraformation-dedicated-server", version="0.2.0")

_server_mode = os.environ.get("SERVER_MODE", "in-memory")
_database_url = os.environ.get("DATABASE_URL", "")

if _server_mode == "postgres" and _database_url:
    _repository = PostgresRepository(_database_url)
else:
    _repository = InMemoryRepository()

runtime = InMemorySimulationRuntime(
    tick_interval_seconds=float(os.environ.get("SERVER_TICK_INTERVAL", "5.0")),
    auto_resume=os.environ.get("SERVER_AUTO_RESUME", "0") == "1",
    repository=_repository,
)


@app.get("/health")
def health() -> dict:
    status = runtime.health()
    status["service"] = "terraformation-dedicated-server"
    status["mode"] = os.environ.get("SERVER_MODE", "in-memory")
    return status


@app.get("/world", response_model=WorldState)
def get_world() -> WorldState:
    return runtime.world_state()


@app.get("/projection", response_model=ProjectionState)
def get_projection() -> ProjectionState:
    return runtime.projection_state()


@app.get("/region", response_model=RegionState)
def get_region() -> RegionState:
    return runtime.region_state()


@app.get("/events/last", response_model=SimulationEvent)
def get_last_event() -> SimulationEvent:
    return runtime.last_event()


@app.get("/actions/definitions", response_model=list[TerraformActionDefinition])
def get_action_definitions() -> list[TerraformActionDefinition]:
    return runtime.action_definitions()


@app.get("/actions/catalog", response_model=SimulationActionCatalog)
def get_action_catalog() -> SimulationActionCatalog:
    return SimulationActionCatalog(actions=runtime.action_definitions())


@app.post("/commands/bootstrap-demo", response_model=WorldState)
def bootstrap_demo(planet_name: str = "Astra-Prime",
                   projection_override: DebugCoherenceOverride = DebugCoherenceOverride.Coast,
                   projection_water_level: float = 0.08) -> WorldState:
    return runtime.bootstrap_demo(planet_name=planet_name,
                                  projection_override=projection_override,
                                  projection_water_level=projection_water_level)


@app.post("/commands/bootstrap-sol", response_model=WorldState)
def bootstrap_sol() -> WorldState:
    return runtime.bootstrap_sol()


@app.post("/commands/open-region", response_model=RegionState)
def open_region(latitude: float, longitude: float) -> RegionState:
    return runtime.open_region(latitude=latitude, longitude=longitude)


@app.post("/commands/queue-action", response_model=WorldState)
def queue_action(action_type: TerraformAction,
                 q: int | None = None,
                 r: int | None = None) -> WorldState:
    cell = SimulationCellAddress(q=q, r=r) if q is not None and r is not None else None
    return runtime.queue_terraform_action(action=action_type, cell=cell)


@app.post("/commands/apply-cell-delta", response_model=WorldState)
def apply_cell_delta(water_delta: float = 0.0,
                     temperature_delta: float = 0.0,
                     q: int | None = None,
                     r: int | None = None) -> WorldState:
    cell = SimulationCellAddress(q=q, r=r) if q is not None and r is not None else None
    return runtime.apply_direct_cell_delta(
        water_delta=water_delta,
        temperature_delta=temperature_delta,
        cell=cell,
    )


@app.get("/tick/status")
def tick_status() -> dict:
    return runtime.tick_status()


@app.post("/tick/advance", response_model=WorldState)
def advance_tick(steps: int = 1) -> WorldState:
    return runtime.advance_tick(steps=steps)


@app.post("/tick/pause", response_model=WorldState)
def pause_tick() -> WorldState:
    return runtime.pause()


@app.post("/tick/resume", response_model=WorldState)
def resume_tick() -> WorldState:
    return runtime.resume()


@app.post("/commands/set-projection", response_model=WorldState)
def set_projection(
    projection_override: DebugCoherenceOverride = DebugCoherenceOverride.Coast,
    water_level: float = 0.08,
) -> WorldState:
    return runtime.set_projection(projection_override=projection_override, water_level=water_level)


# ── Body hierarchy endpoints ──────────────────────────────────────────────────

@app.get("/bodies", response_model=list[AnyBodyState])
def list_bodies() -> list[AnyBodyState]:
    return runtime.list_bodies()


@app.get("/bodies/{body_id}", response_model=AnyBodyState)
def get_body(body_id: str) -> AnyBodyState:
    try:
        return runtime.get_body(body_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/bodies/{body_id}/tiles", response_model=list[GoldbergTileState])
def get_body_tiles(body_id: str, page: int = 0, size: int = 100) -> list[GoldbergTileState]:
    size = min(max(1, size), 200)
    try:
        return runtime.get_body_tiles(body_id, page=page, size=size)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bodies/{body_id}/tiles/at", response_model=GoldbergTileState)
def get_body_tile_at(body_id: str, lat: float, lon: float) -> GoldbergTileState:
    """Return the H3 tile containing the given latitude/longitude."""
    try:
        return runtime.get_body_tile_at(body_id, lat, lon)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bodies/{body_id}/tiles/lod", response_model=list[GoldbergTileState])
def get_body_tiles_lod(body_id: str, h3_resolution: int = 3, page: int = 0, size: int = 5000) -> list[GoldbergTileState]:
    """Return tiles at a different H3 resolution for LOD support.
    Generated in-memory, cached after first call. Supports resolution 0-3.
    res=0: 122 tiles | res=1: 842 | res=2: 5 882 | res=3: 41 162 tiles.
    """
    size = min(max(1, size), 10000)
    try:
        return runtime.get_body_tiles_lod(body_id, h3_resolution=h3_resolution, page=page, size=size)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bodies/{body_id}/tiles/{tile_id}", response_model=GoldbergTileState)
def get_body_tile(body_id: str, tile_id: str) -> GoldbergTileState:
    try:
        return runtime.get_body_tile(body_id, tile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (TypeError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bodies/{body_id}/tiles/{tile_id}/neighbors", response_model=list[GoldbergTileState])
def get_body_tile_neighbors(body_id: str, tile_id: str) -> list[GoldbergTileState]:
    """Return the neighboring tiles (up to 6) of an H3 tile."""
    try:
        return runtime.get_body_tile_neighbors(body_id, tile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Atmosphere endpoints ─────────────────────────────────────────────────────

@app.get("/bodies/{body_id}/atmosphere")
def get_body_atmosphere(body_id: str) -> dict:
    """Return the full AtmosphericComposition and equilibrium temperature for a body."""
    try:
        return runtime.get_body_atmosphere(body_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/bodies/{body_id}/atmosphere", response_model=AtmosphericComposition)
def patch_body_atmosphere(
    body_id: str,
    gas: str,
    fraction_delta: float,
) -> AtmosphericComposition:
    """Apply an additive fraction delta to a named gas in the planet atmosphere.
    fraction_delta is clamped to [0, 1]. The gas must already be tracked on this body.
    """
    try:
        return runtime.patch_atmosphere(body_id, gas, fraction_delta)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/bodies/{body_id}/tiles/{tile_id}/atmosphere-delta", response_model=GoldbergTileState)
def apply_tile_atmosphere_delta(
    body_id: str,
    tile_id: str,
    co2_delta: float = 0.0,
    o2_delta: float = 0.0,
) -> GoldbergTileState:
    """Set per-tick CO₂/O₂ deltas on a tile (building/plant production).
    These are aggregated into planet atmosphere on each advance_tick().
    """
    try:
        return runtime.apply_tile_atmosphere_delta(body_id, tile_id, co2_delta=co2_delta, o2_delta=o2_delta)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/bodies/{body_id}/tiles/{tile_id}/delta", response_model=GoldbergTileState)
def apply_body_tile_delta(
    body_id: str,
    tile_id: str,
    water_delta: float = 0.0,
    temperature_delta: float = 0.0,
) -> GoldbergTileState:
    try:
        return runtime.apply_body_tile_delta(body_id, tile_id, water_delta=water_delta, temperature_delta=temperature_delta)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (TypeError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/bodies/{body_id}/tiles/{tile_id}/action", response_model=GoldbergTileState)
def apply_body_tile_action(
    body_id: str,
    tile_id: str,
    action_type: TerraformAction,
) -> GoldbergTileState:
    try:
        return runtime.apply_body_tile_action(body_id, tile_id, action_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (TypeError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/bodies/{body_id}/cells", response_model=list[SimulationCellState])
def get_interior_cells(body_id: str, page: int = 0, size: int = 100) -> list[SimulationCellState]:
    """Return paginated hex cells for an interior zone (cave, building, ship…)."""
    size = min(max(1, size), 200)
    try:
        zone = runtime.get_interior_zone(body_id)
        start = page * size
        return zone.cells[start:start + size]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/bodies/{body_id}/zones", response_model=InteriorZoneState)
def register_interior_zone(
    body_id: str,
    zone_type: ZoneType = ZoneType.Cave,
    cols: int = 9,
    rows: int = 9,
    parent_tile_id: str | None = None,
    seed: int | None = None,
) -> InteriorZoneState:
    """Create an interior zone (cave, building, ship…) attached to a body tile."""
    cols = min(max(3, cols), 64)
    rows = min(max(3, rows), 64)
    try:
        return runtime.register_interior_zone(
            body_id,
            zone_type=zone_type,
            cols=cols,
            rows=rows,
            parent_tile_id=parent_tile_id,
            seed=seed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ───────────────────────────────────────────────────────────────
# Galaxy layer — Solar systems, stellar routes, space travel
# ───────────────────────────────────────────────────────────────

@app.get("/galaxy")
def galaxy_overview() -> dict:
    """Galaxy summary: system count, route visibility, active travels."""
    return runtime.galaxy_overview()


@app.get("/galaxy/systems", response_model=list[SolarSystemState])
def list_solar_systems() -> list[SolarSystemState]:
    return runtime.list_solar_systems()


@app.post("/galaxy/systems", response_model=SolarSystemState)
def create_solar_system(
    name: str,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    description: str = "",
) -> SolarSystemState:
    """Create a new solar system at the given galactic coordinates (light-years)."""
    return runtime.create_solar_system(name=name, x=x, y=y, z=z, description=description)


@app.get("/galaxy/systems/{system_id}", response_model=SolarSystemState)
def get_solar_system(system_id: str) -> SolarSystemState:
    try:
        return runtime.get_solar_system(system_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/galaxy/systems/{system_id}/bodies", response_model=SphericalBodyState)
def add_body_to_system(
    system_id: str,
    name: str,
    body_type: BodyType = BodyType.Planet,
    radius_km: float = 6371.0,
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
    """Add a body (star, planet, moon, asteroid…) to an existing system with orbital parameters."""
    try:
        return runtime.add_body_to_system(
            system_id=system_id,
            body_type=body_type,
            name=name,
            radius_km=radius_km,
            water_level=water_level,
            seed=seed,
            parent_body_id=parent_body_id,
            orbital_semi_major_axis_au=orbital_semi_major_axis_au,
            orbital_eccentricity=orbital_eccentricity,
            orbital_inclination_deg=orbital_inclination_deg,
            orbital_initial_phase_deg=orbital_initial_phase_deg,
            orbital_period_ticks=orbital_period_ticks,
            spectral_type=spectral_type,
            is_system_root=is_system_root,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/galaxy/systems/{system_id}/bodies/{body_id}", status_code=204)
def remove_body_from_system(system_id: str, body_id: str) -> None:
    try:
        runtime.remove_body_from_system(system_id, body_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/galaxy/systems/{system_id}/bodies/{body_id}/position")
def get_body_position(
    system_id: str,
    body_id: str,
    tick: int | None = None,
) -> dict:
    """Compute position of a body (AU) relative to its system root at given tick."""
    try:
        runtime.get_solar_system(system_id)  # validate system exists
        return runtime.get_body_position_at_tick(body_id, tick)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Stellar routes ───────────────────────────────────────────────────────────

@app.get("/galaxy/routes", response_model=list[StellarRoute])
def list_stellar_routes(known_only: bool = False) -> list[StellarRoute]:
    return runtime.list_stellar_routes(known_only=known_only)


@app.post("/galaxy/routes", response_model=StellarRoute)
def create_stellar_route(
    from_system_id: str,
    to_system_id: str,
    travel_time_modifier: float = 1.0,
    description: str = "",
    status: RouteStatus = RouteStatus.Hidden,
) -> StellarRoute:
    """Create a new stellar route between two systems. Distance computed from positions."""
    try:
        return runtime.create_stellar_route(
            from_system_id=from_system_id,
            to_system_id=to_system_id,
            travel_time_modifier=travel_time_modifier,
            description=description,
            status=status,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/galaxy/routes/{route_id}", response_model=StellarRoute)
def get_stellar_route(route_id: str) -> StellarRoute:
    try:
        return runtime.get_stellar_route(route_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/galaxy/routes/{route_id}/reveal", response_model=StellarRoute)
def reveal_stellar_route(route_id: str) -> StellarRoute:
    """Reveal a hidden route, making it available for travel."""
    try:
        return runtime.reveal_stellar_route(route_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/galaxy/routes/{route_id}", status_code=204)
def delete_stellar_route(route_id: str) -> None:
    try:
        runtime.delete_stellar_route(route_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Space travel ─────────────────────────────────────────────────────────

@app.post("/travel", response_model=SpaceTravel)
def initiate_travel(
    from_system_id: str,
    to_system_id: str,
    route_id: str,
    faction_id: str = "",
) -> SpaceTravel:
    """Start a journey along a known stellar route."""
    try:
        return runtime.initiate_travel(
            from_system_id=from_system_id,
            to_system_id=to_system_id,
            route_id=route_id,
            faction_id=faction_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/travel", response_model=list[SpaceTravel])
def list_active_travels() -> list[SpaceTravel]:
    return runtime.list_active_travels()


@app.get("/travel/{travel_id}", response_model=SpaceTravel)
def get_travel(travel_id: str) -> SpaceTravel:
    try:
        return runtime.get_travel(travel_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/travel/{travel_id}/cancel", response_model=SpaceTravel)
def cancel_travel(travel_id: str) -> SpaceTravel:
    try:
        return runtime.cancel_travel(travel_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ───────────────────────────────────────────────────────────────
# Admin
# ───────────────────────────────────────────────────────────────

@app.post("/admin/wipe-galaxy")
def wipe_galaxy() -> dict:
    """Destroy all galaxy bodies, systems, routes and travels, then re-bootstrap.
    Intended for testing and world-reset workflows only.
    Bodies that belong to the active WorldState (no systemId) are preserved.
    """
    return runtime.wipe_galaxy()


# ───────────────────────────────────────────────────────────────
# Debug / generation lab
# ───────────────────────────────────────────────────────────────

@app.get("/debug/generation-stats")
def debug_generation_stats(
    coherence: DebugCoherenceOverride = DebugCoherenceOverride.Coast,
    water_level: float = 0.71,
    seed: int = 1004,
    h3_resolution: int = 2,
    atmosphere_density: float = 0.5,
) -> dict:
    """Generate tiles in-memory and return terrain distribution stats.
    Never stored — safe to call many times without side effects.
    h3_resolution: 0=122 cells, 1=842 cells, 2=5882 cells.

    Returns per-terrain-type counts and percentages, plus climate-oriented metrics
    to iterate on generation without Unity.
    """
    from terraformation_sim.logic import generate_spherical_tiles, summarize_spherical_hydrology

    h3_resolution = min(max(0, h3_resolution), 2)
    atmosphere_density = min(max(0.0, atmosphere_density), 1.0)
    tiles = generate_spherical_tiles(
        h3_resolution=h3_resolution,
        coherence_override=coherence,
        water_level=water_level,
        seed=seed,
        atmosphere_density=atmosphere_density,
    )
    total = len(tiles)
    if total == 0:
        return {"error": "no tiles generated"}

    from collections import Counter
    terrain_counts: Counter = Counter(t.terrainType for t in tiles)
    water_counts: Counter = Counter(t.waterClassification for t in tiles)
    terrain_class_counts: Counter = Counter(t.terrainClass for t in tiles)

    water_ratios = [t.waterRatio for t in tiles]
    temperatures = [t.temperature for t in tiles]
    habitable_count = sum(1 for t in tiles if t.isHabitable)
    dry_count = sum(1 for t in tiles if t.waterRatio < 0.10)
    humid_count = sum(1 for t in tiles if 0.30 <= t.waterRatio < 0.60)
    saturated_count = sum(1 for t in tiles if t.waterRatio >= 0.80)
    cold_count = sum(1 for t in tiles if t.temperature < -20.0)
    temperate_count = sum(1 for t in tiles if 10.0 <= t.temperature <= 50.0)
    hot_count = sum(1 for t in tiles if t.temperature > 50.0)

    terrain_labels = {0: "Roche", 1: "Glace", 2: "AtmosphereToxique", 3: "Eau", 4: "Vegetation", 5: "Metal"}
    water_labels   = {0: "Dry", 1: "Coast", 2: "InlandWater", 3: "OpenOcean", 4: "FrozenWater"}
    terrain_class_labels = {0: "Slope", 1: "Ridge", 2: "Basin", 3: "Channel", 4: "Source"}

    terrain_stats = {
        terrain_labels.get(k, str(k)): {"count": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(terrain_counts.items())
    }
    water_stats = {
        water_labels.get(k, str(k)): {"count": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(water_counts.items())
    }
    terrain_class_stats = {
        terrain_class_labels.get(k, str(k)): {"count": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(terrain_class_counts.items())
    }
    hydrology = summarize_spherical_hydrology(tiles)

    return {
        "params": {
            "coherence": coherence.name,
            "water_level": water_level,
            "seed": seed,
            "h3_resolution": h3_resolution,
            "atmosphere_density": round(atmosphere_density, 3),
        },
        "total_tiles": total,
        "terrain": terrain_stats,
        "terrain_class": terrain_class_stats,
        "water_classification": water_stats,
        "hydrology": hydrology,
        "water_ratio": {
            "min": round(min(water_ratios), 3),
            "max": round(max(water_ratios), 3),
            "avg": round(sum(water_ratios) / total, 3),
        },
        "temperature": {
            "min": round(min(temperatures), 1),
            "max": round(max(temperatures), 1),
            "avg": round(sum(temperatures) / total, 1),
        },
        "quality": {
            "habitable_pct": round(habitable_count / total * 100, 1),
            "dry_pct": round(dry_count / total * 100, 1),
            "humid_pct": round(humid_count / total * 100, 1),
            "saturated_pct": round(saturated_count / total * 100, 1),
            "cold_pct": round(cold_count / total * 100, 1),
            "temperate_pct": round(temperate_count / total * 100, 1),
            "hot_pct": round(hot_count / total * 100, 1),
        },
    }


@app.get("/debug/noise-distribution")
def debug_noise_distribution(
    seed: int = 1004,
    octave: int = 10,
    h3_resolution: int = 2,
    buckets: int = 10,
) -> dict:
    """Show how _tile_noise_h3 is distributed across all H3 cells at given resolution.
    Useful to detect biases in the noise function for a given seed/octave combo.
    Returns histogram with `buckets` equally spaced bins over [0, 1].
    """
    import h3 as _h3
    from terraformation_sim.logic import _tile_noise_h3

    h3_resolution = min(max(0, h3_resolution), 2)
    cells = sorted(_h3.uncompact_cells(_h3.get_res0_cells(), h3_resolution))
    total = len(cells)
    values = [_tile_noise_h3(cell, seed, octave) for cell in cells]

    buckets = min(max(2, buckets), 50)
    histogram = [0] * buckets
    for v in values:
        idx = min(int(v * buckets), buckets - 1)
        histogram[idx] += 1

    # Fraction below common waterLevel thresholds
    thresholds = [0.1, 0.3, 0.5, 0.6, 0.71, 0.8, 0.9]
    below = {str(th): round(sum(1 for v in values if v < th) / total * 100, 1) for th in thresholds}

    return {
        "params": {"seed": seed, "octave": octave, "h3_resolution": h3_resolution},
        "total_cells": total,
        "histogram": {f"{i/buckets:.2f}-{(i+1)/buckets:.2f}": histogram[i] for i in range(buckets)},
        "pct_below_threshold": below,
        "stats": {
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "avg": round(sum(values) / total, 4),
        },
    }


@app.get("/debug/cell")
def debug_cell(q: int, r: int) -> dict:
    """Return the full state of the hex cell at axial coordinates (q, r) in the current region.
    Returns 404 if no region is loaded or the cell is not found.
    """
    cell = runtime.get_region_cell(q, r)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Cell ({q}, {r}) not found in active region")
    return cell.model_dump()


@app.get("/debug/hydrology")
def debug_hydrology() -> dict:
    """Return hydrology distribution statistics for the current region.
    Returns percentages per water classification and terrain class (basin, ridge, channel…).
    Returns 404 if no region is active.
    """
    result = runtime.get_region_hydrology()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/debug/validate")
def debug_validate() -> dict:
    """Validate coherence of the active region cells.
    Flags cells where waterClassification contradicts waterRatio or temperature.
    Returns 404 if no region is active.
    """
    result = runtime.get_region_validation()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── Game layer — Corporations (Phase 7.1) ─────────────────────────────────────

class _CreateCorporationRequest(_BaseModel):
    name: str
    is_ai: bool = False


@app.get("/game/corporations", response_model=list[CorporationData])
def list_corporations() -> list[CorporationData]:
    """List all registered corporations."""
    return runtime.list_corporations()


@app.get("/game/corporations/{corp_id}", response_model=CorporationData)
def get_corporation(corp_id: str) -> CorporationData:
    """Return a corporation by ID."""
    corp = runtime.get_corporation(corp_id)
    if corp is None:
        raise HTTPException(status_code=404, detail=f"Corporation '{corp_id}' not found")
    return corp


@app.post("/game/corporations", response_model=CorporationData, status_code=201)
def create_corporation(body: _CreateCorporationRequest) -> CorporationData:
    """Register a new corporation with 1 000 starting credits."""
    return runtime.register_corporation(name=body.name, is_ai=body.is_ai)


@app.post("/game/corporations/{corp_id}/claim-hex", response_model=CorporationData)
def claim_hex(corp_id: str, body_id: str, tile_id: str) -> CorporationData:
    """Claim a free tile on behalf of a corporation.
    Returns 404 if the corporation does not exist.
    Returns 409 if the tile is already claimed.
    """
    try:
        return runtime.claim_tile(corp_id, body_id, tile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))