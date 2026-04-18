import os

from fastapi import FastAPI, HTTPException

from terraformation_sim import (
    AnyBodyState,
    BodyBase,
    BodyType,
    DebugCoherenceOverride,
    GoldbergTileState,
    InMemorySimulationRuntime,
    InteriorZoneState,
    ProjectionState,
    RegionState,
    SimulationActionCatalog,
    SimulationCellAddress,
    SimulationCellState,
    SimulationEvent,
    SphericalBodyState,
    TerraformAction,
    TerraformActionDefinition,
    WorldState,
    ZoneType,
)


app = FastAPI(title="terraformation-dedicated-server", version="0.2.0")

runtime = InMemorySimulationRuntime(
    tick_interval_seconds=float(os.environ.get("SERVER_TICK_INTERVAL", "5.0")),
    auto_resume=os.environ.get("SERVER_AUTO_RESUME", "0") == "1",
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


@app.post("/tick/advance", response_model=WorldState)
def advance_tick(steps: int = 1) -> WorldState:
    return runtime.advance_tick(steps=steps)


@app.post("/tick/pause", response_model=WorldState)
def pause_tick() -> WorldState:
    return runtime.pause()


@app.post("/tick/resume", response_model=WorldState)
def resume_tick() -> WorldState:
    return runtime.resume()


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


@app.get("/bodies/{body_id}/tiles/{tile_id}", response_model=GoldbergTileState)
def get_body_tile(body_id: str, tile_id: int) -> GoldbergTileState:
    try:
        return runtime.get_body_tile(body_id, tile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (TypeError, IndexError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/bodies/{body_id}/tiles/{tile_id}/delta", response_model=GoldbergTileState)
def apply_body_tile_delta(
    body_id: str,
    tile_id: int,
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
    tile_id: int,
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
    parent_tile_id: int | None = None,
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