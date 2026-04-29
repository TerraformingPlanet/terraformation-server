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
        BuildingData,
        CorporationData,
        ContractData,
        ExpeditionUnit,
        GoldbergTileState,
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
    tile_ownership_json: str = "{}"  # JSON string of dict[str, dict[str, str]]
    trade_routes_json: list[str] = field(default_factory=list)
    expeditions_json: list[str] = field(default_factory=list)
    construction_queues_json: list[str] = field(default_factory=list)
    markets_json: list[str] = field(default_factory=list)
    territories_json: list[str] = field(default_factory=list)  # Phase Colonisation
    # Normalized table data (Phase DB normalization)
    tile_data: dict[str, list[dict]] = field(default_factory=dict)  # body_id → tile rows
    buildings_data: dict[str, list[dict]] = field(default_factory=dict)  # body_id → building rows
    terrain_type_defs: list[dict] = field(default_factory=list)  # terrain type definitions (generation config)
    biome_transition_rules: list[dict] = field(default_factory=list)  # biome transition graph (catalog)

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
    def save_territory(self, territory: "TerritoryData") -> None: ...  # Phase Colonisation
    @abstractmethod
    def delete_territory(self, territory_id: str) -> None: ...
    @abstractmethod
    def clear_territories(self) -> None: ...

    # -- Normalized tile table (Phase DB normalization) --
    @abstractmethod
    def save_tiles_bulk(self, body_id: str, tiles: "list[GoldbergTileState]") -> None: ...
    @abstractmethod
    def load_tiles(self, body_id: str) -> list[dict]: ...
    @abstractmethod
    def update_tile_fields(self, body_id: str, tile_id: str, **kwargs: float) -> None: ...
    @abstractmethod
    def delete_tiles(self, body_id: str) -> None: ...
    @abstractmethod
    def clear_all_tiles(self) -> None: ...

    # -- Normalized buildings table --
    @abstractmethod
    def save_building(self, building: "BuildingData") -> None: ...
    @abstractmethod
    def delete_building(self, building_id: str) -> None: ...
    @abstractmethod
    def load_buildings(self, body_id: str) -> list[dict]: ...
    @abstractmethod
    def clear_buildings_for_body(self, body_id: str) -> None: ...
    @abstractmethod
    def clear_all_buildings(self) -> None: ...

    @abstractmethod
    def load_terrain_type_defs(self) -> list[dict]: ...

    @abstractmethod
    def update_terrain_type_def(self, terrain_type_id: int, **kwargs) -> None: ...

    @abstractmethod
    def load_biome_transition_rules(self) -> list[dict]: ...

    @abstractmethod
    def upsert_biome_transition_rule(self, row: dict) -> None: ...

    @abstractmethod
    def delete_biome_transition_rule(self, rule_id: int) -> None: ...

    @abstractmethod
    def load_sub_hex_features(self) -> list[dict]: ...

    @abstractmethod
    def upsert_sub_hex_feature(self, row: dict) -> None: ...

    @abstractmethod
    def delete_sub_hex_feature(self, feature_id: int) -> None: ...

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
    # Phase Colonisation
    def save_territory(self, territory) -> None: pass
    def delete_territory(self, territory_id) -> None: pass
    def clear_territories(self) -> None: pass
    # Normalized tile table
    def save_tiles_bulk(self, body_id, tiles) -> None: pass
    def load_tiles(self, body_id) -> list[dict]: return []
    def update_tile_fields(self, body_id, tile_id, **kwargs) -> None: pass
    def delete_tiles(self, body_id) -> None: pass
    def clear_all_tiles(self) -> None: pass
    # Normalized buildings table
    def save_building(self, building) -> None: pass
    def delete_building(self, building_id) -> None: pass
    def load_buildings(self, body_id) -> list[dict]: return []
    def clear_buildings_for_body(self, body_id) -> None: pass
    def clear_all_buildings(self) -> None: pass
    def load_terrain_type_defs(self) -> list[dict]: return list(_TERRAIN_TYPE_DEFS_SEED)
    def update_terrain_type_def(self, terrain_type_id: int, **kwargs) -> None: pass
    def load_biome_transition_rules(self) -> list[dict]: return list(_BIOME_TRANSITION_RULES_SEED)
    def upsert_biome_transition_rule(self, row: dict) -> None: pass
    def delete_biome_transition_rule(self, rule_id: int) -> None: pass
    def load_sub_hex_features(self) -> list[dict]: return list(_SUB_HEX_FEATURES_SEED)
    def upsert_sub_hex_feature(self, row: dict) -> None: pass
    def delete_sub_hex_feature(self, feature_id: int) -> None: pass

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

# Normalized full tile table (Phase DB normalization)
_tiles_table = Table(
    "tiles", _metadata,
    Column("body_id", String(36), nullable=False),
    Column("tile_id", String(20), nullable=False),
    Column("terrain_type", String(32), nullable=False),
    Column("water_classification", String(32), nullable=False),
    Column("terrain_class", String(32), nullable=False),
    Column("water_ratio", Float, nullable=False, default=0.0),
    Column("temperature", Float, nullable=False, default=0.0),
    Column("humidity", Float, nullable=False, default=0.0),
    Column("toxin_level", Float, nullable=False, default=0.0),
    Column("altitude", Float, nullable=False, default=0.0),
    Column("albedo", Float, nullable=False, default=0.0),
    Column("solar_irradiance", Float, nullable=False, default=0.0),
    Column("is_habitable", Boolean, nullable=False, default=False),
    Column("lat_deg", Float, nullable=False, default=0.0),
    Column("lon_deg", Float, nullable=False, default=0.0),
    Column("lat_norm", Float, nullable=False, default=0.0),
    Column("lon_norm", Float, nullable=False, default=0.0),
    # ── Runtime biome parameters (added for biome mutation system) ──
    Column("vegetation_level", Float, nullable=False, default=0.0),
    Column("tree_count", Float, nullable=False, default=0.0),
    Column("has_river", Boolean, nullable=False, default=False),
    Column("has_lake", Boolean, nullable=False, default=False),
    Column("population_json", Text, nullable=False, default="[]"),
)

# Normalized buildings table (Phase DB normalization)
_buildings_table = Table(
    "buildings", _metadata,
    Column("building_id", String(36), primary_key=True),
    Column("body_id", String(36), nullable=False),
    Column("tile_id", String(20), nullable=False),
    Column("corp_id", String(36), nullable=False),
    Column("building_type", String(64), nullable=False),
    Column("worker_ratio", Float, nullable=False, default=1.0),
    Column("ticks_active", Integer, nullable=False, default=0),
    Column("level", Integer, nullable=False, default=1),
    Column("employment_slots", Text, nullable=False, default="{}"),
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

_territories_table = Table(
    "territories", _metadata,
    Column("territory_id", String(128), primary_key=True),
    Column("territory_json", Text, nullable=False),
)

_sub_hex_features_table = Table(
    "sub_hex_features", _metadata,
    Column("feature_id",            Integer, primary_key=True),   # stable int ID (0=Empty, 1=River…)
    Column("name",                  String(64), nullable=False),   # code name, e.g. "River"
    Column("label_fr",              String(64), nullable=False, default=""),
    Column("description",           Text, nullable=True),
    Column("bonus_building_types",  Text, nullable=False, default="[]"),  # JSON array of BuildingId strings
    Column("is_enabled",            Boolean, nullable=False, default=True),
)

_SUB_HEX_FEATURES_SEED = [
    {"feature_id": 0, "name": "Empty",       "label_fr": "Vide",              "description": "Terrain nu, aucun bonus.",                                         "bonus_building_types": "[]",                           "is_enabled": True},
    {"feature_id": 1, "name": "River",       "label_fr": "Rivière",           "description": "Eau courante. Bonus pour Ferme, Scierie, Port Maritime.",          "bonus_building_types": '["Farm","Sawmill","SeaPort"]', "is_enabled": True},
    {"feature_id": 2, "name": "Forest",      "label_fr": "Forêt",             "description": "Couverture arborée. Bonus pour Scierie; requis pour Wood.",        "bonus_building_types": '["Sawmill"]',                  "is_enabled": True},
    {"feature_id": 3, "name": "Mineral",     "label_fr": "Gisement minéral",  "description": "Dépôt de minerai. Bonus pour Mine.",                              "bonus_building_types": '["Mine"]',                     "is_enabled": True},
    {"feature_id": 4, "name": "WaterSource", "label_fr": "Source d'eau",      "description": "Source naturelle ou rive de lac. Bonus pour Ferme.",               "bonus_building_types": '["Farm"]',                     "is_enabled": True},
    {"feature_id": 5, "name": "Residential", "label_fr": "Zone résidentielle","description": "Habitat existant. Bonus pour Recherche et Centrale Énergétique.", "bonus_building_types": '["Research","EnergyPlant"]',   "is_enabled": True},
]

_terrain_type_defs_table = Table(
    "terrain_type_defs", _metadata,
    Column("terrain_type_id", Integer, primary_key=True),   # TerrainType enum value (0-6)
    Column("name", String(50), nullable=False),              # code name: "Roche", "Foret"…
    Column("label_fr", String(50), nullable=False),          # display label
    Column("color_hex", String(7), nullable=False),          # "#RRGGBB"
    Column("is_enabled", Boolean, nullable=False, default=True),
    # ── Generation thresholds ──────────────────────────────────────────────
    # NULL = not applicable to this type
    Column("humidity_threshold", Float, nullable=True),
    # Foret: min humidity (>= → forest). Vegetation cold-zone: base water-ratio threshold (0.40).
    Column("humidity_clamp_min", Float, nullable=True),
    # Vegetation cold-zone minimum clamp (0.20). Formula: max(clamp_min, base - atmo*0.16).
    Column("noise_threshold", Float, nullable=True),
    # Metal: scatter noise threshold (0.92). AtmosphereToxique: toxin level threshold (0.04).
    Column("temperature_threshold", Float, nullable=True),
    # Glace: max temperature to become ice (-20.0).
    Column("water_ratio_min", Float, nullable=True),
    # Glace: min water_ratio required to be ice rather than rock (0.15).
    Column("extra_params", Text, nullable=True),
    # JSON dict for additional zone thresholds.
    # Vegetation: {"temperate_base":0.54,"temperate_clamp":0.26,"hot_base":0.58,"hot_clamp":0.35}
    Column("spawn_weight", Float, nullable=False, default=1.0),
    # Future: probability multiplier applied during generation.
    Column("description", Text, nullable=True),
)

_biome_transition_rules_table = Table(
    "biome_transition_rules", _metadata,
    Column("rule_id", Integer, primary_key=True),
    Column("name", String(64), nullable=False),
    Column("target_terrain_type_id", Integer, nullable=False),  # TerrainType enum value
    Column("from_terrain_type_ids", Text, nullable=False, default="[]"),  # JSON int array
    Column("priority", Integer, nullable=False, default=10),
    Column("is_enabled", Boolean, nullable=False, default=True),
    # ── Conditions (NULL = not checked) ──
    Column("temperature_min", Float, nullable=True),
    Column("temperature_max", Float, nullable=True),
    Column("humidity_min", Float, nullable=True),
    Column("humidity_max", Float, nullable=True),
    Column("vegetation_min", Float, nullable=True),
    Column("vegetation_max", Float, nullable=True),
    Column("tree_count_min", Float, nullable=True),
    Column("tree_count_max", Float, nullable=True),
    Column("has_river", Boolean, nullable=True),   # NULL=ignore
    Column("has_lake", Boolean, nullable=True),
    Column("water_ratio_min", Float, nullable=True),
    Column("water_ratio_max", Float, nullable=True),
    Column("toxin_min", Float, nullable=True),
    Column("toxin_max", Float, nullable=True),
    Column("description", Text, nullable=True),
)

# Default seed rows — match the current hardcoded values in logic/generation.py
_TERRAIN_TYPE_DEFS_SEED = [
    {
        "terrain_type_id": 0, "name": "Roche", "label_fr": "Roche",
        "color_hex": "#7B5E4A", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Fallback terrain. Appears when no other biome condition matches.",
    },
    {
        "terrain_type_id": 1, "name": "Glace", "label_fr": "Glace",
        "color_hex": "#C8EEFF", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": None,
        "temperature_threshold": -20.0,   # max temperature to form ice
        "water_ratio_min": 0.15,           # if below → Roche instead
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Forms when temp < temperature_threshold. Requires water_ratio > water_ratio_min; otherwise falls back to Roche.",
    },
    {
        "terrain_type_id": 2, "name": "AtmosphereToxique", "label_fr": "Atmosphère Toxique",
        "color_hex": "#8FBC8F", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": 0.04,           # min toxin_level to trigger
        "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Appears on land when toxin_level > noise_threshold. Increase to make toxic terrain rarer.",
    },
    {
        "terrain_type_id": 3, "name": "Eau", "label_fr": "Eau",
        "color_hex": "#1D6FA4", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Driven by the water map (is_water flag). No configurable threshold — controlled by body waterLevel.",
    },
    {
        "terrain_type_id": 4, "name": "Vegetation", "label_fr": "Végétation",
        "color_hex": "#4A7B47", "is_enabled": True,
        "humidity_threshold": 0.40,        # cold-zone base: max(clamp, base - atmo*0.16)
        "humidity_clamp_min": 0.20,        # cold-zone minimum clamp
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": '{"temperate_base": 0.54, "temperate_clamp": 0.26, "hot_base": 0.58, "hot_clamp": 0.35}',
        "spawn_weight": 1.0,
        "description": "Cold zone: max(humidity_clamp_min, humidity_threshold - atmo*0.16). Temperate/hot in extra_params. Higher base → rarer vegetation.",
    },
    {
        "terrain_type_id": 5, "name": "Metal", "label_fr": "Métal",
        "color_hex": "#9B9B9B", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": 0.92,           # scatter noise threshold (higher → rarer)
        "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Appears in dry temperate zones when scatter noise > noise_threshold. Raise threshold to make Metal rarer.",
    },
    {
        "terrain_type_id": 6, "name": "Foret", "label_fr": "Forêt",
        "color_hex": "#1A4D1E", "is_enabled": True,
        "humidity_threshold": 0.62,        # min humidity (non-coastal temperate zones)
        "humidity_clamp_min": None,
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Dense humid temperate zones: humidity >= humidity_threshold AND NOT coastal. Lower to expand forests.",
    },
    {
        "terrain_type_id": 7, "name": "Desert", "label_fr": "Désert",
        "color_hex": "#D4AA70", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Runtime biome — triggered by biome_transition_rules when humidity/vegetation fall below thresholds.",
    },
    {
        "terrain_type_id": 8, "name": "Jungle", "label_fr": "Jungle",
        "color_hex": "#1B4D1A", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Runtime biome — hot + humid + dense vegetation. Triggered by biome_transition_rules.",
    },
    {
        "terrain_type_id": 9, "name": "ZoneHumide", "label_fr": "Zone Humide",
        "color_hex": "#3A7D6E", "is_enabled": True,
        "humidity_threshold": None, "humidity_clamp_min": None,
        "noise_threshold": None, "temperature_threshold": None, "water_ratio_min": None,
        "extra_params": None, "spawn_weight": 1.0,
        "description": "Runtime biome — desert reclaimed by a river + water. Triggered by biome_transition_rules.",
    },
]

# Seed rows for biome_transition_rules — define the biome transition graph.
# Each rule: when a tile's current terrain is in from_terrain_type_ids AND all
# non-NULL conditions are met, the tile transitions to target_terrain_type_id.
# Priority: higher value wins when multiple rules match the same tile.
_BIOME_TRANSITION_RULES_SEED = [
    # ── Desert ─────────────────────────────────────────────────────────────
    {
        "rule_id": 1,
        "name": "Desert from Vegetation/Foret (dry, no water)",
        "target_terrain_type_id": 7,  # Desert
        "from_terrain_type_ids": "[4, 6]",  # Vegetation, Foret
        "priority": 10,
        "is_enabled": True,
        "temperature_min": None, "temperature_max": None,
        "humidity_min": None, "humidity_max": 0.05,
        "vegetation_min": None, "vegetation_max": 2.0,
        "tree_count_min": None, "tree_count_max": 5.0,
        "has_river": False, "has_lake": False,
        "water_ratio_min": None, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Vegetation/Forêt → Désert when humidity < 5%, vegetation < 2, trees < 5, no river, no lake.",
    },
    {
        "rule_id": 2,
        "name": "Desert from Roche (hot + dry)",
        "target_terrain_type_id": 7,  # Desert
        "from_terrain_type_ids": "[0]",  # Roche
        "priority": 8,
        "is_enabled": True,
        "temperature_min": 30.0, "temperature_max": None,
        "humidity_min": None, "humidity_max": 0.10,
        "vegetation_min": None, "vegetation_max": None,
        "tree_count_min": None, "tree_count_max": None,
        "has_river": False, "has_lake": False,
        "water_ratio_min": None, "water_ratio_max": 0.05,
        "toxin_min": None, "toxin_max": None,
        "description": "Roche → Désert lorsque la température est élevée, sec, pas d'eau.",
    },
    # ── Forêt ───────────────────────────────────────────────────────────────
    {
        "rule_id": 3,
        "name": "Foret from Vegetation (tree density)",
        "target_terrain_type_id": 6,  # Foret
        "from_terrain_type_ids": "[4]",  # Vegetation
        "priority": 15,
        "is_enabled": True,
        "temperature_min": None, "temperature_max": None,
        "humidity_min": None, "humidity_max": None,
        "vegetation_min": None, "vegetation_max": None,
        "tree_count_min": 2000.0, "tree_count_max": None,
        "has_river": None, "has_lake": None,
        "water_ratio_min": None, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Végétation → Forêt quand la densité d'arbres dépasse 2000.",
    },
    # ── Jungle ─────────────────────────────────────────────────────────────
    {
        "rule_id": 4,
        "name": "Jungle from Foret/Vegetation (hot + humid)",
        "target_terrain_type_id": 8,  # Jungle
        "from_terrain_type_ids": "[4, 6]",  # Vegetation, Foret
        "priority": 20,
        "is_enabled": True,
        "temperature_min": 35.0, "temperature_max": None,
        "humidity_min": 0.50, "humidity_max": None,
        "vegetation_min": None, "vegetation_max": None,
        "tree_count_min": None, "tree_count_max": None,
        "has_river": None, "has_lake": None,
        "water_ratio_min": None, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Forêt/Végétation → Jungle quand temp ≥ 35°C et humidité ≥ 50%.",
    },
    # ── Zone Humide ─────────────────────────────────────────────────────────
    {
        "rule_id": 5,
        "name": "ZoneHumide from Desert (river + water returns)",
        "target_terrain_type_id": 9,  # ZoneHumide
        "from_terrain_type_ids": "[7]",  # Desert
        "priority": 12,
        "is_enabled": True,
        "temperature_min": None, "temperature_max": None,
        "humidity_min": 0.15, "humidity_max": None,
        "vegetation_min": 5.0, "vegetation_max": None,
        "tree_count_min": None, "tree_count_max": None,
        "has_river": True, "has_lake": None,
        "water_ratio_min": None, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Désert → Zone Humide quand une rivière apparaît, humidité ≥ 15% et végétation ≥ 5.",
    },
    # ── Végétation ──────────────────────────────────────────────────────────
    {
        "rule_id": 6,
        "name": "Vegetation from Desert (rain returns)",
        "target_terrain_type_id": 4,  # Vegetation
        "from_terrain_type_ids": "[7]",  # Desert
        "priority": 9,
        "is_enabled": True,
        "temperature_min": None, "temperature_max": None,
        "humidity_min": 0.20, "humidity_max": None,
        "vegetation_min": 5.0, "vegetation_max": None,
        "tree_count_min": None, "tree_count_max": None,
        "has_river": None, "has_lake": None,
        "water_ratio_min": None, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Désert → Végétation quand les pluies reviennent (humidité ≥ 20%, végétation ≥ 5).",
    },
    # ── Glace → Eau (fonte) ─────────────────────────────────────────────────
    {
        "rule_id": 7,
        "name": "Eau from Glace (thaw)",
        "target_terrain_type_id": 3,  # Eau
        "from_terrain_type_ids": "[1]",  # Glace
        "priority": 25,
        "is_enabled": True,
        "temperature_min": 2.0, "temperature_max": None,
        "humidity_min": None, "humidity_max": None,
        "vegetation_min": None, "vegetation_max": None,
        "tree_count_min": None, "tree_count_max": None,
        "has_river": None, "has_lake": None,
        "water_ratio_min": 0.10, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Glace → Eau quand la température dépasse 2°C (fonte des glaces).",
    },
    # ── Eau → Glace (gel) ──────────────────────────────────────────────────
    {
        "rule_id": 8,
        "name": "Glace from Eau (freeze)",
        "target_terrain_type_id": 1,  # Glace
        "from_terrain_type_ids": "[3]",  # Eau
        "priority": 25,
        "is_enabled": True,
        "temperature_min": None, "temperature_max": -5.0,
        "humidity_min": None, "humidity_max": None,
        "vegetation_min": None, "vegetation_max": None,
        "tree_count_min": None, "tree_count_max": None,
        "has_river": None, "has_lake": None,
        "water_ratio_min": None, "water_ratio_max": None,
        "toxin_min": None, "toxin_max": None,
        "description": "Eau → Glace quand la température descend sous -5°C.",
    },
]


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
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_tiles
                ON tiles (body_id, tile_id)
            """))
            # ADD COLUMN IF NOT EXISTS for biome runtime fields on existing tiles tables
            for col, col_type, default in [
                ("vegetation_level", "FLOAT",  "0.0"),
                ("tree_count",       "FLOAT",  "0.0"),
                ("has_river",        "BOOLEAN", "FALSE"),
                ("has_lake",         "BOOLEAN", "FALSE"),
                ("population_json",  "TEXT",    "'[]'"),
            ]:
                conn.execute(text(
                    f"ALTER TABLE tiles ADD COLUMN IF NOT EXISTS "
                    f"{col} {col_type} NOT NULL DEFAULT {default}"
                ))
            # Seed terrain_type_defs with defaults (INSERT IF NOT EXISTS)
            for row in _TERRAIN_TYPE_DEFS_SEED:
                conn.execute(text("""
                    INSERT INTO terrain_type_defs
                        (terrain_type_id, name, label_fr, color_hex, is_enabled,
                         humidity_threshold, humidity_clamp_min, noise_threshold,
                         temperature_threshold, water_ratio_min, extra_params,
                         spawn_weight, description)
                    VALUES
                        (:terrain_type_id, :name, :label_fr, :color_hex, :is_enabled,
                         :humidity_threshold, :humidity_clamp_min, :noise_threshold,
                         :temperature_threshold, :water_ratio_min, :extra_params,
                         :spawn_weight, :description)
                    ON CONFLICT (terrain_type_id) DO NOTHING
                """), row)
            # Seed sub_hex_features (INSERT IF NOT EXISTS)
            for row in _SUB_HEX_FEATURES_SEED:
                conn.execute(text("""
                    INSERT INTO sub_hex_features
                        (feature_id, name, label_fr, description, bonus_building_types, is_enabled)
                    VALUES
                        (:feature_id, :name, :label_fr, :description, :bonus_building_types, :is_enabled)
                    ON CONFLICT (feature_id) DO NOTHING
                """), row)
            # Seed biome_transition_rules (INSERT IF NOT EXISTS)
            for row in _BIOME_TRANSITION_RULES_SEED:
                conn.execute(text("""
                    INSERT INTO biome_transition_rules
                        (rule_id, name, target_terrain_type_id, from_terrain_type_ids,
                         priority, is_enabled,
                         temperature_min, temperature_max,
                         humidity_min, humidity_max,
                         vegetation_min, vegetation_max,
                         tree_count_min, tree_count_max,
                         has_river, has_lake,
                         water_ratio_min, water_ratio_max,
                         toxin_min, toxin_max,
                         description)
                    VALUES
                        (:rule_id, :name, :target_terrain_type_id, :from_terrain_type_ids,
                         :priority, :is_enabled,
                         :temperature_min, :temperature_max,
                         :humidity_min, :humidity_max,
                         :vegetation_min, :vegetation_max,
                         :tree_count_min, :tree_count_max,
                         :has_river, :has_lake,
                         :water_ratio_min, :water_ratio_max,
                         :toxin_min, :toxin_max,
                         :description)
                    ON CONFLICT (rule_id) DO NOTHING
                """), row)

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

    # -- Normalized tile table methods --

    def save_tiles_bulk(self, body_id: str, tiles: "list[GoldbergTileState]") -> None:
        if not tiles:
            return
        rows = [
            {
                "body_id": body_id,
                "tile_id": t.tileId,
                "terrain_type": t.terrainType.name,
                "water_classification": t.waterClassification.name,
                "terrain_class": t.terrainClass.name,
                "water_ratio": t.waterRatio,
                "temperature": t.temperature,
                "humidity": t.humidity,
                "toxin_level": t.toxinLevel,
                "altitude": t.altitude,
                "albedo": t.albedo,
                "solar_irradiance": t.solarIrradiance,
                "is_habitable": t.isHabitable,
                "lat_deg": t.latDeg,
                "lon_deg": t.lonDeg,
                "lat_norm": t.latNorm,
                "lon_norm": t.lonNorm,
                "vegetation_level": t.vegetationLevel,
                "tree_count": t.treeCount,
                "has_river": t.hasRiver,
                "has_lake": t.hasLake,
                "population_json": json.dumps(
                    [{"socialClass": tier.socialClass.name, "count": tier.count, "avgIncome": tier.avgIncome}
                     for tier in t.population]
                ),
            }
            for t in tiles
        ]
        update_cols = [
            "terrain_type", "water_classification", "terrain_class",
            "water_ratio", "temperature", "humidity", "toxin_level",
            "altitude", "albedo", "solar_irradiance", "is_habitable",
            "lat_deg", "lon_deg", "lat_norm", "lon_norm",
            "vegetation_level", "tree_count", "has_river", "has_lake",
            "population_json",
        ]
        # Batch in chunks of 1000 to avoid hitting PostgreSQL parameter limits
        chunk_size = 1000
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            stmt = pg_insert(_tiles_table).values(chunk).on_conflict_do_update(
                index_elements=["body_id", "tile_id"],
                set_={col: text(f"EXCLUDED.{col}") for col in update_cols},
            )
            with self._engine.begin() as conn:
                conn.execute(stmt)

    def load_tiles(self, body_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                _tiles_table.select().where(_tiles_table.c.body_id == body_id)
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    def update_tile_fields(self, body_id: str, tile_id: str, **kwargs: float) -> None:
        if not kwargs:
            return
        with self._engine.begin() as conn:
            conn.execute(
                _tiles_table.update()
                .where(
                    (_tiles_table.c.body_id == body_id)
                    & (_tiles_table.c.tile_id == tile_id)
                )
                .values(**kwargs)
            )

    def delete_tiles(self, body_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _tiles_table.delete().where(_tiles_table.c.body_id == body_id)
            )

    def clear_all_tiles(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_tiles_table.delete())

    # -- Normalized buildings table methods --

    def save_building(self, building: "BuildingData") -> None:
        row = {
            "building_id": building.id,
            "body_id": building.bodyId,
            "tile_id": building.tileId,
            "corp_id": building.corpId,
            "building_type": building.buildingType,
            "worker_ratio": building.workerRatio,
            "ticks_active": building.ticksActive,
            "level": building.level,
            "employment_slots": json.dumps(building.employmentSlots),
        }
        stmt = pg_insert(_buildings_table).values(row).on_conflict_do_update(
            index_elements=["building_id"],
            set_={k: v for k, v in row.items() if k != "building_id"},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_building(self, building_id: str) -> None:
        self._delete_by_pk(_buildings_table, "building_id", building_id)

    def load_buildings(self, body_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                _buildings_table.select().where(_buildings_table.c.body_id == body_id)
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    def clear_buildings_for_body(self, body_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _buildings_table.delete().where(_buildings_table.c.body_id == body_id)
            )

    def clear_all_buildings(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_buildings_table.delete())

    def load_terrain_type_defs(self) -> list[dict]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                _terrain_type_defs_table.select().order_by(_terrain_type_defs_table.c.terrain_type_id)
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def update_terrain_type_def(self, terrain_type_id: int, **kwargs) -> None:
        if not kwargs:
            return
        with self._engine.begin() as conn:
            conn.execute(
                _terrain_type_defs_table.update()
                .where(_terrain_type_defs_table.c.terrain_type_id == terrain_type_id)
                .values(**kwargs)
            )

    def load_biome_transition_rules(self) -> list[dict]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                _biome_transition_rules_table.select()
                .order_by(_biome_transition_rules_table.c.priority.desc())
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def upsert_biome_transition_rule(self, row: dict) -> None:
        update_cols = [k for k in row if k != "rule_id"]
        stmt = pg_insert(_biome_transition_rules_table).values(row).on_conflict_do_update(
            index_elements=["rule_id"],
            set_={col: text(f"EXCLUDED.{col}") for col in update_cols},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_biome_transition_rule(self, rule_id: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _biome_transition_rules_table.delete()
                .where(_biome_transition_rules_table.c.rule_id == rule_id)
            )

    def load_sub_hex_features(self) -> list[dict]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                _sub_hex_features_table.select().order_by(_sub_hex_features_table.c.feature_id)
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    def upsert_sub_hex_feature(self, row: dict) -> None:
        update_cols = [k for k in row if k != "feature_id"]
        stmt = pg_insert(_sub_hex_features_table).values(row).on_conflict_do_update(
            index_elements=["feature_id"],
            set_={col: text(f"EXCLUDED.{col}") for col in update_cols},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_sub_hex_feature(self, feature_id: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _sub_hex_features_table.delete()
                .where(_sub_hex_features_table.c.feature_id == feature_id)
            )

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

    # Phase Colonisation
    def save_territory(self, territory: "TerritoryData") -> None:
        self._upsert(_territories_table, "territory_id", territory.id, "territory_json", territory.model_dump_json())

    def delete_territory(self, territory_id: str) -> None:
        self._delete_by_pk(_territories_table, "territory_id", territory_id)

    def clear_territories(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(_territories_table.delete())

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

            territory_rows = conn.execute(_territories_table.select()).fetchall()
            state.territories_json = [row.territory_json for row in territory_rows]

            # Normalized tiles (generate-once table)
            tile_result = conn.execute(_tiles_table.select()).fetchall()
            for row in tile_result:
                state.tile_data.setdefault(row.body_id, []).append(dict(row._mapping))

            # Normalized buildings table
            building_result = conn.execute(_buildings_table.select()).fetchall()
            for row in building_result:
                state.buildings_data.setdefault(row.body_id, []).append(dict(row._mapping))

            # Terrain type definitions
            state.terrain_type_defs = self.load_terrain_type_defs()

        return state
