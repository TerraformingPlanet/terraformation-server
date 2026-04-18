"""
Persistence layer for InMemorySimulationRuntime.

Two implementations:
  - InMemoryRepository  : no-op (default, backward-compatible)
  - PostgresRepository  : write-through via SQLAlchemy Core + psycopg2 (sync)

Usage in server.py:
    repo = PostgresRepository(database_url) if mode == "postgres" else InMemoryRepository()
    runtime = InMemorySimulationRuntime(..., repository=repo)
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Boolean,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from .models import (
        AnyBodyState,
        InteriorZoneState,
        PendingTerraformAction,
        SolarSystemState,
        SpaceTravel,
        SphericalBodyState,
        StellarRoute,
        WorldState,
    )


# ---------------------------------------------------------------------------
# Saved state container (returned by load())
# ---------------------------------------------------------------------------

@dataclass
class TileMutation:
    tile_id: str   # H3 cell index string (e.g. '8928308280fffff')
    water_ratio: float
    temperature: float
    toxin_level: float


@dataclass
class CellMutation:
    cell_q: int
    cell_r: int
    cell_json: str  # Pydantic model_dump_json of SimulationCellState


@dataclass
class SavedState:
    tick_count: int = 0
    tick_running: bool = False
    tick_interval_seconds: float = 5.0
    active_planet_name: str = ""
    projection_override: int = 0
    projection_water_level: float = 0.08
    has_region: bool = False
    region_lat: float = 0.47
    region_lon: float = 0.18
    bodies_json: list[str] = field(default_factory=list)
    # body_id → list[TileMutation]
    tile_mutations: dict[str, list[TileMutation]] = field(default_factory=dict)
    # body_id → list[CellMutation]
    cell_mutations: dict[str, list[CellMutation]] = field(default_factory=dict)
    pending_actions_json: list[str] = field(default_factory=list)
    # Galaxy layer
    systems_json: list[str] = field(default_factory=list)
    routes_json: list[str] = field(default_factory=list)
    travels_json: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.bodies_json)


# ---------------------------------------------------------------------------
# Abstract contract
# ---------------------------------------------------------------------------

class StateRepository(ABC):

    @abstractmethod
    def save_world_state(self, ws: "WorldState", tick_interval_seconds: float) -> None: ...

    @abstractmethod
    def save_body(self, body: "AnyBodyState") -> None: ...

    @abstractmethod
    def delete_body(self, body_id: str) -> None: ...

    @abstractmethod
    def delete_tile_mutations(self, body_id: str) -> None: ...

    @abstractmethod
    def upsert_tile_mutation(self, body_id: str, mutation: TileMutation) -> None: ...

    @abstractmethod
    def upsert_cell_mutation(self, body_id: str, mutation: CellMutation) -> None: ...

    @abstractmethod
    def save_pending_action(self, action: "PendingTerraformAction") -> None: ...

    @abstractmethod
    def delete_pending_action(self, action_id: str) -> None: ...

    @abstractmethod
    def clear_pending_actions(self) -> None: ...

    @abstractmethod
    def save_solar_system(self, system: "SolarSystemState") -> None: ...

    @abstractmethod
    def delete_solar_system(self, system_id: str) -> None: ...

    @abstractmethod
    def save_stellar_route(self, route: "StellarRoute") -> None: ...

    @abstractmethod
    def delete_stellar_route(self, route_id: str) -> None: ...

    @abstractmethod
    def save_space_travel(self, travel: "SpaceTravel") -> None: ...

    @abstractmethod
    def delete_space_travel(self, travel_id: str) -> None: ...

    @abstractmethod
    def load(self) -> SavedState: ...


# ---------------------------------------------------------------------------
# No-op implementation (in-memory mode — zero overhead)
# ---------------------------------------------------------------------------

class InMemoryRepository(StateRepository):

    def save_world_state(self, ws, tick_interval_seconds=5.0) -> None: pass
    def save_body(self, body) -> None: pass
    def delete_body(self, body_id) -> None: pass
    def delete_tile_mutations(self, body_id) -> None: pass
    def upsert_tile_mutation(self, body_id, mutation) -> None: pass
    def upsert_cell_mutation(self, body_id, mutation) -> None: pass
    def save_pending_action(self, action) -> None: pass
    def delete_pending_action(self, action_id) -> None: pass
    def clear_pending_actions(self) -> None: pass
    def save_solar_system(self, system) -> None: pass
    def delete_solar_system(self, system_id) -> None: pass
    def save_stellar_route(self, route) -> None: pass
    def delete_stellar_route(self, route_id) -> None: pass
    def save_space_travel(self, travel) -> None: pass
    def delete_space_travel(self, travel_id) -> None: pass

    def load(self) -> SavedState:
        return SavedState()


# ---------------------------------------------------------------------------
# SQLAlchemy Core schema
# ---------------------------------------------------------------------------

_metadata = MetaData()

_world_state_table = Table(
    "world_state", _metadata,
    Column("id", Integer, primary_key=True),           # always id=1
    Column("tick_count", Integer, nullable=False, default=0),
    Column("tick_running", Boolean, nullable=False, default=False),
    Column("tick_interval_seconds", Float, nullable=False, default=5.0),
    Column("active_planet_name", String(128), nullable=False, default=""),
    Column("projection_override", Integer, nullable=False, default=0),
    Column("projection_water_level", Float, nullable=False, default=0.08),
    Column("has_region", Boolean, nullable=False, default=False),
    Column("region_lat", Float, nullable=False, default=0.47),
    Column("region_lon", Float, nullable=False, default=0.18),
)

_bodies_table = Table(
    "bodies", _metadata,
    Column("body_id", String(36), primary_key=True),
    Column("body_json", Text, nullable=False),  # full Pydantic model_dump_json (no tiles/cells)
)

_tile_mutations_table = Table(
    "tile_mutations", _metadata,
    Column("body_id", String(36), nullable=False),
    Column("tile_id", String(20), nullable=False),  # H3 cell index (15 hex chars + prefix)
    Column("water_ratio", Float, nullable=False),
    Column("temperature", Float, nullable=False),
    Column("toxin_level", Float, nullable=False),
)

_cell_mutations_table = Table(
    "cell_mutations", _metadata,
    Column("body_id", String(36), nullable=False),
    Column("cell_q", Integer, nullable=False),
    Column("cell_r", Integer, nullable=False),
    Column("cell_json", Text, nullable=False),
)

_pending_actions_table = Table(
    "pending_actions", _metadata,
    Column("action_id", String(36), primary_key=True),
    Column("action_json", Text, nullable=False),
)

_solar_systems_table = Table(
    "solar_systems", _metadata,
    Column("system_id", String(36), primary_key=True),
    Column("system_json", Text, nullable=False),
)

_stellar_routes_table = Table(
    "stellar_routes", _metadata,
    Column("route_id", String(36), primary_key=True),
    Column("route_json", Text, nullable=False),
)

_space_travels_table = Table(
    "space_travels", _metadata,
    Column("travel_id", String(36), primary_key=True),
    Column("travel_json", Text, nullable=False),
)


# ---------------------------------------------------------------------------
# PostgreSQL implementation
# ---------------------------------------------------------------------------

class PostgresRepository(StateRepository):
    """
    Write-through repository backed by PostgreSQL.
    Uses SQLAlchemy Core (sync) — compatible with the existing threading.RLock runtime.
    Tables are created on __init__ if they don't exist (idempotent).
    """

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
        )
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create tables + unique constraints if they don't exist."""
        with self._engine.begin() as conn:
            _metadata.create_all(conn)
            # Unique constraints on composite PKs (not declared in Column to keep
            # SQLAlchemy Core simple; enforced here via raw DDL on first run)
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_tile_mutations
                ON tile_mutations (body_id, tile_id)
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_cell_mutations
                ON cell_mutations (body_id, cell_q, cell_r)
            """))

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def save_world_state(self, ws: "WorldState", tick_interval_seconds: float = 5.0) -> None:
        row = {
            "id": 1,
            "tick_count": ws.tickCount,
            "tick_running": ws.tickRunning,
            "tick_interval_seconds": tick_interval_seconds,
            "active_planet_name": ws.activePlanetName or "",
            "projection_override": int(ws.projectionOverride),
            "projection_water_level": ws.projectionWaterLevel,
            "has_region": ws.hasRegion,
            "region_lat": ws.region.coordinates.latitude if ws.hasRegion else 0.47,
            "region_lon": ws.region.coordinates.longitude if ws.hasRegion else 0.18,
        }
        stmt = pg_insert(_world_state_table).values(row).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in row.items() if k != "id"},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def save_body(self, body: "AnyBodyState") -> None:
        # Serialize without tiles/cells to keep the row small
        body_dict = body.model_dump(exclude={"tiles", "cells"})
        row = {
            "body_id": body.bodyId,
            "body_json": json.dumps(body_dict),
        }
        stmt = pg_insert(_bodies_table).values(row).on_conflict_do_update(
            index_elements=["body_id"],
            set_={"body_json": row["body_json"]},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_body(self, body_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _bodies_table.delete().where(_bodies_table.c.body_id == body_id)
            )

    def delete_tile_mutations(self, body_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _tile_mutations_table.delete().where(_tile_mutations_table.c.body_id == body_id)
            )

    def upsert_tile_mutation(self, body_id: str, mutation: TileMutation) -> None:
        row = {
            "body_id": body_id,
            "tile_id": mutation.tile_id,
            "water_ratio": mutation.water_ratio,
            "temperature": mutation.temperature,
            "toxin_level": mutation.toxin_level,
        }
        stmt = pg_insert(_tile_mutations_table).values(row).on_conflict_do_update(
            index_elements=["body_id", "tile_id"],
            set_={k: v for k, v in row.items() if k not in ("body_id", "tile_id")},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def upsert_cell_mutation(self, body_id: str, mutation: CellMutation) -> None:
        row = {
            "body_id": body_id,
            "cell_q": mutation.cell_q,
            "cell_r": mutation.cell_r,
            "cell_json": mutation.cell_json,
        }
        stmt = pg_insert(_cell_mutations_table).values(row).on_conflict_do_update(
            index_elements=["body_id", "cell_q", "cell_r"],
            set_={"cell_json": mutation.cell_json},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def save_pending_action(self, action: "PendingTerraformAction") -> None:
        row = {
            "action_id": action.actionId,
            "action_json": action.model_dump_json(),
        }
        stmt = pg_insert(_pending_actions_table).values(row).on_conflict_do_update(
            index_elements=["action_id"],
            set_={"action_json": row["action_json"]},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_pending_action(self, action_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _pending_actions_table.delete().where(
                    _pending_actions_table.c.action_id == action_id
                )
            )

    def clear_pending_actions(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_pending_actions_table.delete())

    def save_solar_system(self, system: "SolarSystemState") -> None:
        row = {"system_id": system.systemId, "system_json": system.model_dump_json()}
        stmt = pg_insert(_solar_systems_table).values(row).on_conflict_do_update(
            index_elements=["system_id"],
            set_={"system_json": row["system_json"]},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_solar_system(self, system_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _solar_systems_table.delete().where(
                    _solar_systems_table.c.system_id == system_id
                )
            )

    def save_stellar_route(self, route: "StellarRoute") -> None:
        row = {"route_id": route.routeId, "route_json": route.model_dump_json()}
        stmt = pg_insert(_stellar_routes_table).values(row).on_conflict_do_update(
            index_elements=["route_id"],
            set_={"route_json": row["route_json"]},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_stellar_route(self, route_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _stellar_routes_table.delete().where(
                    _stellar_routes_table.c.route_id == route_id
                )
            )

    def save_space_travel(self, travel: "SpaceTravel") -> None:
        row = {"travel_id": travel.travelId, "travel_json": travel.model_dump_json()}
        stmt = pg_insert(_space_travels_table).values(row).on_conflict_do_update(
            index_elements=["travel_id"],
            set_={"travel_json": row["travel_json"]},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_space_travel(self, travel_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _space_travels_table.delete().where(
                    _space_travels_table.c.travel_id == travel_id
                )
            )

    # ------------------------------------------------------------------
    # Read / hydration
    # ------------------------------------------------------------------

    def load(self) -> SavedState:
        with self._engine.connect() as conn:
            # world_state
            ws_row = conn.execute(
                _world_state_table.select().where(_world_state_table.c.id == 1)
            ).fetchone()

            if ws_row is None:
                return SavedState()

            state = SavedState(
                tick_count=ws_row.tick_count,
                tick_running=ws_row.tick_running,
                tick_interval_seconds=ws_row.tick_interval_seconds,
                active_planet_name=ws_row.active_planet_name,
                projection_override=ws_row.projection_override,
                projection_water_level=ws_row.projection_water_level,
                has_region=ws_row.has_region,
                region_lat=ws_row.region_lat,
                region_lon=ws_row.region_lon,
            )

            # bodies
            bodies = conn.execute(_bodies_table.select()).fetchall()
            state.bodies_json = [row.body_json for row in bodies]

            # tile mutations
            tile_rows = conn.execute(_tile_mutations_table.select()).fetchall()
            for row in tile_rows:
                state.tile_mutations.setdefault(row.body_id, []).append(
                    TileMutation(
                        tile_id=row.tile_id,
                        water_ratio=row.water_ratio,
                        temperature=row.temperature,
                        toxin_level=row.toxin_level,
                    )
                )

            # cell mutations
            cell_rows = conn.execute(_cell_mutations_table.select()).fetchall()
            for row in cell_rows:
                state.cell_mutations.setdefault(row.body_id, []).append(
                    CellMutation(
                        cell_q=row.cell_q,
                        cell_r=row.cell_r,
                        cell_json=row.cell_json,
                    )
                )

            # pending actions
            action_rows = conn.execute(_pending_actions_table.select()).fetchall()
            state.pending_actions_json = [row.action_json for row in action_rows]

            # galaxy — solar systems
            system_rows = conn.execute(_solar_systems_table.select()).fetchall()
            state.systems_json = [row.system_json for row in system_rows]

            # galaxy — stellar routes
            route_rows = conn.execute(_stellar_routes_table.select()).fetchall()
            state.routes_json = [row.route_json for row in route_rows]

            # galaxy — space travels (only in-transit)
            travel_rows = conn.execute(_space_travels_table.select()).fetchall()
            state.travels_json = [row.travel_json for row in travel_rows]

        return state
