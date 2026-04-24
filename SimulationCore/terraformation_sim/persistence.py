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
        CorporationData,
        ContractData,
        ExpeditionUnit,
        InteriorZoneState,
        LocalMarketState,
        NationalizationProcess,
        PendingTerraformAction,
        SolarSystemState,
        SpaceTravel,
        SphericalBodyState,
        StellarRoute,
        StateData,
        TerritoryQueue,
        TradeRoute,
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
    # Gameplay entities (Sprint DB)
    corporations_json: list[str] = field(default_factory=list)
    contracts_json: list[str] = field(default_factory=list)
    states_json: list[str] = field(default_factory=list)
    nationalizations_json: list[str] = field(default_factory=list)
    reputations_raw: list[tuple[str, str, float]] = field(default_factory=list)  # (source_id, target_id, score)
    trade_routes_json: list[str] = field(default_factory=list)
    expeditions_json: list[str] = field(default_factory=list)
    construction_queues_json: list[str] = field(default_factory=list)
    markets_json: list[str] = field(default_factory=list)

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
    def clear_cell_mutations(self) -> None: ...

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
    def create_player(self, player_id: str, username: str, password_hash: str) -> None: ...

    @abstractmethod
    def get_player_by_username(self, username: str) -> "dict | None": ...

    @abstractmethod
    def link_player_corp(self, player_id: str, corp_id: str) -> None: ...

    # -- Sprint DB gameplay entities --
    @abstractmethod
    def save_corporation(self, corp: "CorporationData") -> None: ...
    @abstractmethod
    def delete_corporation(self, corp_id: str) -> None: ...
    @abstractmethod
    def clear_corporations(self) -> None: ...

    @abstractmethod
    def save_contract(self, contract: "ContractData") -> None: ...
    @abstractmethod
    def delete_contract(self, contract_id: str) -> None: ...
    @abstractmethod
    def clear_contracts(self) -> None: ...

    @abstractmethod
    def save_state(self, state: "StateData") -> None: ...
    @abstractmethod
    def delete_state(self, state_id: str) -> None: ...
    @abstractmethod
    def clear_states(self) -> None: ...

    @abstractmethod
    def save_nationalization(self, nat: "NationalizationProcess") -> None: ...
    @abstractmethod
    def delete_nationalization(self, nat_id: str) -> None: ...
    @abstractmethod
    def clear_nationalizations(self) -> None: ...

    @abstractmethod
    def upsert_reputation(self, source_id: str, target_id: str, score: float) -> None: ...
    @abstractmethod
    def clear_reputations(self) -> None: ...

    @abstractmethod
    def save_trade_route(self, route: "TradeRoute") -> None: ...
    @abstractmethod
    def delete_trade_route(self, route_id: str) -> None: ...
    @abstractmethod
    def clear_trade_routes(self) -> None: ...

    @abstractmethod
    def save_expedition(self, exp: "ExpeditionUnit") -> None: ...
    @abstractmethod
    def delete_expedition(self, exp_id: str) -> None: ...
    @abstractmethod
    def clear_expeditions(self) -> None: ...

    @abstractmethod
    def save_construction_queue(self, queue: "TerritoryQueue") -> None: ...
    @abstractmethod
    def delete_construction_queue(self, territory_id: str) -> None: ...
    @abstractmethod
    def clear_construction_queues(self) -> None: ...

    @abstractmethod
    def save_market(self, market: "LocalMarketState") -> None: ...
    @abstractmethod
    def delete_market(self, territory_id: str) -> None: ...
    @abstractmethod
    def clear_markets(self) -> None: ...

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
    def clear_cell_mutations(self) -> None: pass
    def save_pending_action(self, action) -> None: pass
    def delete_pending_action(self, action_id) -> None: pass
    def clear_pending_actions(self) -> None: pass
    def save_solar_system(self, system) -> None: pass
    def delete_solar_system(self, system_id) -> None: pass
    def save_stellar_route(self, route) -> None: pass
    def delete_stellar_route(self, route_id) -> None: pass
    def save_space_travel(self, travel) -> None: pass
    def delete_space_travel(self, travel_id) -> None: pass
    def create_player(self, player_id: str, username: str, password_hash: str) -> None: pass
    def get_player_by_username(self, username: str) -> "dict | None": return None
    def link_player_corp(self, player_id: str, corp_id: str) -> None: pass
    # Sprint DB gameplay entities
    def save_corporation(self, corp) -> None: pass
    def delete_corporation(self, corp_id) -> None: pass
    def clear_corporations(self) -> None: pass
    def save_contract(self, contract) -> None: pass
    def delete_contract(self, contract_id) -> None: pass
    def clear_contracts(self) -> None: pass
    def save_state(self, state) -> None: pass
    def delete_state(self, state_id) -> None: pass
    def clear_states(self) -> None: pass
    def save_nationalization(self, nat) -> None: pass
    def delete_nationalization(self, nat_id) -> None: pass
    def clear_nationalizations(self) -> None: pass
    def upsert_reputation(self, source_id, target_id, score) -> None: pass
    def clear_reputations(self) -> None: pass
    def save_trade_route(self, route) -> None: pass
    def delete_trade_route(self, route_id) -> None: pass
    def clear_trade_routes(self) -> None: pass
    def save_expedition(self, exp) -> None: pass
    def delete_expedition(self, exp_id) -> None: pass
    def clear_expeditions(self) -> None: pass
    def save_construction_queue(self, queue) -> None: pass
    def delete_construction_queue(self, territory_id) -> None: pass
    def clear_construction_queues(self) -> None: pass
    def save_market(self, market) -> None: pass
    def delete_market(self, territory_id) -> None: pass
    def clear_markets(self) -> None: pass

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

_players_table = Table(
    "players", _metadata,
    Column("player_id", String(36), primary_key=True),
    Column("username", String(64), nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("corp_id", String(36), nullable=True),
)

# Sprint DB — gameplay entities
_corporations_table = Table(
    "corporations", _metadata,
    Column("corp_id", String(36), primary_key=True),
    Column("corp_json", Text, nullable=False),
)

_contracts_table = Table(
    "contracts", _metadata,
    Column("contract_id", String(36), primary_key=True),
    Column("contract_json", Text, nullable=False),
)

_states_table = Table(
    "game_states", _metadata,  # 'states' conflicts with SQLAlchemy internals on some DBs
    Column("state_id", String(36), primary_key=True),
    Column("state_json", Text, nullable=False),
)

_nationalizations_table = Table(
    "nationalizations", _metadata,
    Column("nat_id", String(36), primary_key=True),
    Column("nat_json", Text, nullable=False),
)

_reputations_table = Table(
    "reputations", _metadata,
    Column("source_id", String(36), nullable=False),
    Column("target_id", String(36), nullable=False),
    Column("score", Float, nullable=False),
)

_trade_routes_table = Table(
    "trade_routes", _metadata,
    Column("route_id", String(36), primary_key=True),
    Column("route_json", Text, nullable=False),
)

_expeditions_table = Table(
    "expeditions", _metadata,
    Column("expedition_id", String(36), primary_key=True),
    Column("expedition_json", Text, nullable=False),
)

_construction_queues_table = Table(
    "construction_queues", _metadata,
    Column("territory_id", String(128), primary_key=True),
    Column("queue_json", Text, nullable=False),
)

_markets_table = Table(
    "markets", _metadata,
    Column("territory_id", String(128), primary_key=True),
    Column("market_json", Text, nullable=False),
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
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_reputations
                ON reputations (source_id, target_id)
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

    def clear_cell_mutations(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_cell_mutations_table.delete())

    # -- Sprint DB gameplay entities --

    def _upsert(self, table, pk_col: str, pk_val: str, json_col: str, json_val: str) -> None:
        """Generic upsert for single-pk JSON tables."""
        row = {pk_col: pk_val, json_col: json_val}
        stmt = pg_insert(table).values(row).on_conflict_do_update(
            index_elements=[pk_col],
            set_={json_col: json_val},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def _delete_by_pk(self, table, pk_col: str, pk_val: str) -> None:
        """Generic delete by primary key."""
        with self._engine.begin() as conn:
            conn.execute(table.delete().where(getattr(table.c, pk_col) == pk_val))

    def save_corporation(self, corp: "CorporationData") -> None:
        self._upsert(_corporations_table, "corp_id", corp.id, "corp_json", corp.model_dump_json())

    def delete_corporation(self, corp_id: str) -> None:
        self._delete_by_pk(_corporations_table, "corp_id", corp_id)

    def clear_corporations(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_corporations_table.delete())

    def save_contract(self, contract: "ContractData") -> None:
        self._upsert(_contracts_table, "contract_id", contract.id, "contract_json", contract.model_dump_json())

    def delete_contract(self, contract_id: str) -> None:
        self._delete_by_pk(_contracts_table, "contract_id", contract_id)

    def clear_contracts(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_contracts_table.delete())

    def save_state(self, state: "StateData") -> None:
        self._upsert(_states_table, "state_id", state.id, "state_json", state.model_dump_json())

    def delete_state(self, state_id: str) -> None:
        self._delete_by_pk(_states_table, "state_id", state_id)

    def clear_states(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_states_table.delete())

    def save_nationalization(self, nat: "NationalizationProcess") -> None:
        self._upsert(_nationalizations_table, "nat_id", nat.id, "nat_json", nat.model_dump_json())

    def delete_nationalization(self, nat_id: str) -> None:
        self._delete_by_pk(_nationalizations_table, "nat_id", nat_id)

    def clear_nationalizations(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_nationalizations_table.delete())

    def upsert_reputation(self, source_id: str, target_id: str, score: float) -> None:
        row = {"source_id": source_id, "target_id": target_id, "score": score}
        stmt = pg_insert(_reputations_table).values(row).on_conflict_do_update(
            index_elements=["source_id", "target_id"],
            set_={"score": score},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def clear_reputations(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_reputations_table.delete())

    def save_trade_route(self, route: "TradeRoute") -> None:
        self._upsert(_trade_routes_table, "route_id", route.id, "route_json", route.model_dump_json())

    def delete_trade_route(self, route_id: str) -> None:
        self._delete_by_pk(_trade_routes_table, "route_id", route_id)

    def clear_trade_routes(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_trade_routes_table.delete())

    def save_expedition(self, exp: "ExpeditionUnit") -> None:
        self._upsert(_expeditions_table, "expedition_id", exp.id, "expedition_json", exp.model_dump_json())

    def delete_expedition(self, exp_id: str) -> None:
        self._delete_by_pk(_expeditions_table, "expedition_id", exp_id)

    def clear_expeditions(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_expeditions_table.delete())

    def save_construction_queue(self, queue: "TerritoryQueue") -> None:
        self._upsert(_construction_queues_table, "territory_id", queue.territoryId, "queue_json", queue.model_dump_json())

    def delete_construction_queue(self, territory_id: str) -> None:
        self._delete_by_pk(_construction_queues_table, "territory_id", territory_id)

    def clear_construction_queues(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_construction_queues_table.delete())

    def save_market(self, market: "LocalMarketState") -> None:
        self._upsert(_markets_table, "territory_id", market.territoryId, "market_json", market.model_dump_json())

    def delete_market(self, territory_id: str) -> None:
        self._delete_by_pk(_markets_table, "territory_id", territory_id)

    def clear_markets(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_markets_table.delete())

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

    def create_player(self, player_id: str, username: str, password_hash: str) -> None:
        row = {"player_id": player_id, "username": username, "password_hash": password_hash}
        stmt = pg_insert(_players_table).values(row).on_conflict_do_nothing()
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def get_player_by_username(self, username: str) -> "dict | None":
        with self._engine.connect() as conn:
            row = conn.execute(
                _players_table.select().where(_players_table.c.username == username)
            ).fetchone()
            if row is None:
                return None
            return {"player_id": row.player_id, "username": row.username, "password_hash": row.password_hash, "corp_id": row.corp_id}

    def link_player_corp(self, player_id: str, corp_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _players_table.update()
                .where(_players_table.c.player_id == player_id)
                .values(corp_id=corp_id)
            )
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

            # Sprint DB — gameplay entities
            corp_rows = conn.execute(_corporations_table.select()).fetchall()
            state.corporations_json = [row.corp_json for row in corp_rows]

            contract_rows = conn.execute(_contracts_table.select()).fetchall()
            state.contracts_json = [row.contract_json for row in contract_rows]

            state_rows = conn.execute(_states_table.select()).fetchall()
            state.states_json = [row.state_json for row in state_rows]

            nat_rows = conn.execute(_nationalizations_table.select()).fetchall()
            state.nationalizations_json = [row.nat_json for row in nat_rows]

            rep_rows = conn.execute(_reputations_table.select()).fetchall()
            state.reputations_raw = [(row.source_id, row.target_id, row.score) for row in rep_rows]

            trade_route_rows = conn.execute(_trade_routes_table.select()).fetchall()
            state.trade_routes_json = [row.route_json for row in trade_route_rows]

            exp_rows = conn.execute(_expeditions_table.select()).fetchall()
            state.expeditions_json = [row.expedition_json for row in exp_rows]

            queue_rows = conn.execute(_construction_queues_table.select()).fetchall()
            state.construction_queues_json = [row.queue_json for row in queue_rows]

            market_rows = conn.execute(_markets_table.select()).fetchall()
            state.markets_json = [row.market_json for row in market_rows]

        return state
