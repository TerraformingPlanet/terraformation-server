import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as _BaseModel
from jose import jwt as _jwt
import bcrypt as _bcrypt_lib

from terraformation_sim import (
    ClaimedTile,
    CorporationData,
    BuildingData,
    BuildingType,
    LocalMarketState,
    ContractData,
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
    StateType,
    StateData,
    NationalizationProcess,
    ScoreboardEntry,
    EventData,
    GlobalMarketState,
    AgentAction,
    SpeciesData,
    ConstructionItem,
)


# ── JWT constants ───────────────────────────────────────────────────────────
_JWT_SECRET    = os.environ.get("JWT_SECRET", "terraformation-dev-secret")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_DAYS = 7


def _make_token(player_id: str, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=_JWT_EXPIRE_DAYS)
    return _jwt.encode(
        {"sub": player_id, "username": username, "exp": exp},
        _JWT_SECRET,
        algorithm=_JWT_ALGORITHM,
    )


# ── Auth Pydantic models ─────────────────────────────────────────────────────
class _AuthRequest(_BaseModel):
    username: str
    password: str


class _AuthResponse(_BaseModel):
    token: str
    player_id: str
    username: str


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


# ── Auth endpoints ──────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=_AuthResponse, status_code=201)
def auth_register(body: _AuthRequest) -> _AuthResponse:
    """Register a new player account. Returns a JWT token."""
    username = body.username.strip()
    password = body.password
    if not username or not password:
        raise HTTPException(status_code=422, detail="username and password are required")
    if _repository.get_player_by_username(username) is not None:
        raise HTTPException(status_code=409, detail=f"Username '{username}' is already taken")
    player_id    = str(uuid.uuid4())
    password_hash = _bcrypt_lib.hashpw(password.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")
    _repository.create_player(player_id=player_id, username=username, password_hash=password_hash)
    return _AuthResponse(
        token=_make_token(player_id, username),
        player_id=player_id,
        username=username,
    )


@app.post("/auth/login", response_model=_AuthResponse)
def auth_login(body: _AuthRequest) -> _AuthResponse:
    """Authenticate an existing player. Returns a JWT token."""
    username = body.username.strip()
    player = _repository.get_player_by_username(username)
    if player is None or not _bcrypt_lib.checkpw(body.password.encode("utf-8"), player["password_hash"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return _AuthResponse(
        token=_make_token(player["player_id"], player["username"]),
        player_id=player["player_id"],
        username=player["username"],
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


@app.get("/bodies/{body_id}/tiles/{tile_id}/ecology", response_model=list[SpeciesData])
def get_tile_ecology(body_id: str, tile_id: str) -> list[SpeciesData]:
    """Return the species population list for a surface tile (Phase 11.5)."""
    try:
        return runtime.get_tile_ecology(body_id, tile_id)
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


@app.delete("/game/corporations/{corp_id}/claim-hex", response_model=CorporationData)
def unclaim_hex(corp_id: str, body_id: str, tile_id: str) -> CorporationData:
    """Release a previously claimed tile from a corporation."""
    try:
        return runtime.unclaim_tile(corp_id, body_id, tile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ── Game layer — Buildings (Phase 7.2) ────────────────────────────────────────

@app.post("/game/corporations/{corp_id}/buildings", response_model=ConstructionItem, status_code=201)
def construct_building(corp_id: str, body_id: str, tile_id: str, building_type: int) -> ConstructionItem:
    """Enqueue a building for multi-tick construction (Phase 10.5).
    Returns the ConstructionItem added to the territory queue.
    Returns 404 if corp not found, 409 if tile not claimed or building already queued.
    """
    try:
        return runtime.construct_building(corp_id, body_id, tile_id, BuildingType(building_type))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/game/corporations/{corp_id}/construction-queue", response_model=list[ConstructionItem])
def list_construction_queue(corp_id: str) -> list[ConstructionItem]:
    """List all pending/in-progress construction items for a corporation."""
    return runtime.list_construction_items(corp_id)


@app.get("/game/corporations/{corp_id}/buildings", response_model=list[BuildingData])
def list_buildings(corp_id: str) -> list[BuildingData]:
    """List all buildings owned by a corporation."""
    return runtime.list_buildings(corp_id)


@app.delete("/game/corporations/{corp_id}/buildings/{building_id}", status_code=204)
def demolish_building(corp_id: str, building_id: str) -> None:
    """Demolish a building. Returns 404 if not found, 409 if corp mismatch."""
    try:
        runtime.demolish_building(corp_id, building_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.patch("/game/corporations/{corp_id}/buildings/{building_id}/workers", response_model=BuildingData)
def set_worker_ratio(corp_id: str, building_id: str, worker_ratio: float) -> BuildingData:
    """Update the worker ratio (0.0–1.0) for a building."""
    try:
        return runtime.set_building_worker_ratio(corp_id, building_id, worker_ratio)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/game/corporations/{corp_id}/buildings/{building_id}/upgrade", response_model=BuildingData)
def upgrade_building(corp_id: str, building_id: str) -> BuildingData:
    """Upgrade a building by one level (max 5). Phase 12."""
    try:
        return runtime.upgrade_building(corp_id, building_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/game/corporations/{corp_id}/buildings/{building_id}/downgrade", response_model=BuildingData)
def downgrade_building(corp_id: str, building_id: str) -> BuildingData:
    """Downgrade a building by one level (min 1). Phase 12."""
    try:
        return runtime.downgrade_building(corp_id, building_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ── Game layer — Local Market (Phase 7.3) ─────────────────────────────────────

@app.get("/game/market", response_model=list[LocalMarketState])
def list_market_states() -> list[LocalMarketState]:
    """List all corporation market states."""
    return runtime.list_market_states()


@app.get("/game/market/{corp_id}", response_model=LocalMarketState)
def get_market_state(corp_id: str) -> LocalMarketState:
    """Get the local market state for a corporation."""
    result = runtime.get_market_state(corp_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No market state for corporation '{corp_id}'")
    return result


# ── Game layer — Contracts (Phase 7.4) ────────────────────────────────────────

class ContractProposalRequest(_BaseModel):
    proposerId: str
    resourceType: str
    resourceAmount: float
    rewardCredits: float
    penaltyCredits: float = 0.0
    durationTicks: int = 0
    visibility: str = "Private"
    targetId: str = ""
    biddingWindowTicks: int = 5
    knowledgeBonus: float = 0.0


class BidRequest(_BaseModel):
    bidderId: str


class ConfirmBidderRequest(_BaseModel):
    proposerId: str
    bidderId: str


class AcceptContractRequest(_BaseModel):
    acceptorId: str


class BreakContractRequest(_BaseModel):
    corpId: str


@app.post("/game/contracts", response_model=ContractData, status_code=201)
def propose_contract(body: ContractProposalRequest) -> ContractData:
    """Propose a new resource-delivery contract."""
    try:
        return runtime.propose_contract(
            proposer_id=body.proposerId,
            resource_type=body.resourceType,
            resource_amount=body.resourceAmount,
            reward_credits=body.rewardCredits,
            penalty_credits=body.penaltyCredits,
            duration_ticks=body.durationTicks,
            visibility=body.visibility,
            target_id=body.targetId,
            bidding_window_ticks=body.biddingWindowTicks,
            knowledge_bonus=body.knowledgeBonus,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/game/contracts", response_model=list[ContractData])
def list_contracts(corp_id: str = "") -> list[ContractData]:
    """List contracts. If corp_id provided, filter to contracts involving that corporation."""
    return runtime.list_contracts(corp_id if corp_id else None)


@app.get("/game/contracts/public", response_model=list[ContractData])
def list_public_contracts() -> list[ContractData]:
    """List all open public contracts available for bidding."""
    return runtime.list_public_contracts()


@app.get("/game/contracts/{contract_id}", response_model=ContractData)
def get_contract(contract_id: str) -> ContractData:
    """Get a single contract by ID."""
    result = runtime.get_contract(contract_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found")
    return result


@app.post("/game/contracts/{contract_id}/bid", response_model=ContractData)
def bid_on_contract(contract_id: str, body: BidRequest) -> ContractData:
    """Submit a bid on a public contract."""
    try:
        return runtime.bid_on_contract(contract_id, body.bidderId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/game/contracts/{contract_id}/confirm", response_model=ContractData)
def confirm_bidder(contract_id: str, body: ConfirmBidderRequest) -> ContractData:
    """Proposer confirms a candidate to activate a public contract."""
    try:
        return runtime.confirm_bidder(contract_id, body.proposerId, body.bidderId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/game/contracts/{contract_id}/accept", response_model=ContractData)
def accept_contract(contract_id: str, body: AcceptContractRequest) -> ContractData:
    """Accept a private contract directed at the given corporation."""
    try:
        return runtime.accept_contract(contract_id, body.acceptorId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/game/contracts/{contract_id}/break", response_model=ContractData)
def break_contract(contract_id: str, body: BreakContractRequest) -> ContractData:
    """Break an active contract (penalty applies)."""
    try:
        return runtime.break_contract(contract_id, body.corpId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ── Game layer — States & Reputation (Phase 7.5) ───────────────────────────────────────

class CreateStateRequest(_BaseModel):
    name: str
    stateType: StateType = StateType.Capitalist
    tileIds: list[str] = []
    bureaucracy: float = 0.1
    corruptionRate: float = 0.1
    toleranceThreshold: float = 0.5


class CorruptNationalizationRequest(_BaseModel):
    corpId: str
    bribeAmount: float


class CancelContractNationalizationRequest(_BaseModel):
    contractId: str


@app.post("/game/states", response_model=StateData)
def create_state(body: CreateStateRequest) -> StateData:
    """Register a new in-game State."""
    return runtime.create_state(
        name=body.name,
        state_type=body.stateType,
        tile_ids=body.tileIds,
        bureaucracy=body.bureaucracy,
        corruption_rate=body.corruptionRate,
        tolerance_threshold=body.toleranceThreshold,
    )


@app.get("/game/states", response_model=list[StateData])
def list_states() -> list[StateData]:
    """Return all registered States."""
    return runtime.list_states()


@app.get("/game/states/{state_id}", response_model=StateData)
def get_state(state_id: str) -> StateData:
    """Return a single State by ID."""
    state = runtime.get_state(state_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"State '{state_id}' not found")
    return state


@app.get("/game/reputation/{source_id}/{target_id}", response_model=float)
def get_bilateral_reputation(source_id: str, target_id: str) -> float:
    """Bilateral reputation score from source toward target."""
    return runtime.get_reputation(source_id, target_id)


@app.get("/game/reputation/{corp_id}", response_model=dict[str, float])
def get_corp_reputations(corp_id: str) -> dict[str, float]:
    """All bilateral reputation scores where corp_id is the source."""
    return runtime.list_reputations(corp_id)


@app.get("/game/nationalizations", response_model=list[NationalizationProcess])
def list_nationalizations(corp_id: str | None = None) -> list[NationalizationProcess]:
    """Return nationalisation processes. Filter by corp_id if provided."""
    return runtime.list_nationalizations(corp_id)


@app.post("/game/nationalizations/{process_id}/corrupt", response_model=NationalizationProcess)
def corrupt_nationalization(
    process_id: str, body: CorruptNationalizationRequest
) -> NationalizationProcess:
    """Attempt to cancel a nationalisation via bribery."""
    try:
        return runtime.corrupt_nationalization(process_id, body.corpId, body.bribeAmount)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/game/nationalizations/{process_id}/cancel-contract", response_model=NationalizationProcess)
def cancel_nationalization_via_contract(
    process_id: str, body: CancelContractNationalizationRequest
) -> NationalizationProcess:
    """Cancel a nationalisation by honouring a contract with the State."""
    try:
        return runtime.cancel_nationalization_via_contract(process_id, body.contractId)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/game/scoreboard", response_model=list[ScoreboardEntry])
def get_scoreboard() -> list[ScoreboardEntry]:
    """Return all corporations sorted by composite score descending."""
    return runtime.get_scoreboard()


@app.get("/game/events", response_model=list[EventData])
def list_game_events(limit: int = 20) -> list[EventData]:
    """Return the last *limit* simulation events (newest first, max 200)."""
    return runtime.list_game_events(limit=limit)


@app.get("/game/global-market", response_model=GlobalMarketState)
def get_global_market(system_id: str = "sol") -> GlobalMarketState:
    """Return aggregated global market state for the given solar system."""
    return runtime.get_global_market(system_id=system_id)


@app.get("/game/agent/context/{state_id}")
def get_agent_context(state_id: str) -> dict:
    """Return the LLM context snapshot (state, scoreboard, recent events, memory) for a State entity."""
    result = runtime.get_agent_context(state_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"State {state_id!r} not found")
    return result


@app.post("/game/agent/run/{state_id}", response_model=AgentAction)
def run_agent_for_state(state_id: str) -> AgentAction:
    """Synchronously run one LLM agent cycle for a State entity and return the resulting action."""
    try:
        return runtime.run_agent_for_state(state_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc