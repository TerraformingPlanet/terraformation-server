"""
test_phase105_construction.py — Phase 10.5 : Construction multi-tick & File de territoire.

Tests couverts :
    [models — no runtime, always run]
    - ConstructionItem / TerritoryQueue roundtrip JSON
    - BUILDING_CONSTRUCTION_COST values present and > 0 for all BuildingTypes
    - ConstructionStatus enum values

    [runtime — skipped if noise absent]
    - construct_building() renvoie un ConstructionItem (pas un BuildingData)
    - Le bâtiment n'est pas dans _buildings avant completion
    - Sans capacité → pas de completion
    - Avec EB de fortune (Wood + pop) → completion après N ticks
    - Overflow : surplus déversé sur l'item suivant dans le même tick
    - Doublon interdit (même buildingType + tileId)
    - cancel_construction_item() supprime l'item
    - list_construction_queues() filtre par corp
    - bootstrap() efface les queues

Pas de Docker, pas de réseau. Durée < 2 s.
"""
import json
import sys
import importlib.util
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    full_name = f"terraformation_sim.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(full_name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load models only (no h3 / noise needed)
_models = _load("models", "models.py")

import pytest

BuildingType              = _models.BuildingType
ConstructionItem          = _models.ConstructionItem
ConstructionStatus        = _models.ConstructionStatus
TerritoryQueue            = _models.TerritoryQueue
BUILDING_CONSTRUCTION_COST = _models.BUILDING_CONSTRUCTION_COST
EB_FORTUNE_CAPACITY       = _models.EB_FORTUNE_CAPACITY
EB_FORTUNE_WOOD_COST      = _models.EB_FORTUNE_WOOD_COST
PopulationTier            = _models.PopulationTier
SocialClass               = _models.SocialClass
CorporationData           = _models.CorporationData
ClaimedTile               = _models.ClaimedTile
BuildingData              = _models.BuildingData

# ---------------------------------------------------------------------------
# ── Model-level tests (no runtime needed) ─────────────────────────────────
# ---------------------------------------------------------------------------

def test_construction_item_defaults():
    item = ConstructionItem()
    assert item.status == ConstructionStatus.Pending
    assert item.ticksRemaining == 0
    assert item.totalCostPts == 0


def test_territory_queue_defaults():
    q = TerritoryQueue()
    assert q.items == []
    assert q.tileIds == []
    assert q.constructionCapacity == 0.0
    assert not q.isEBDeFortune


def test_construction_item_roundtrip():
    item = ConstructionItem(
        id="abc",
        buildingType=BuildingType.Mine,
        tileId="tile_x",
        bodyId="earth",
        corpId="corp1",
        status=ConstructionStatus.InProgress,
        ticksRemaining=30,
        totalCostPts=60,
        pointsAccumulated=30,
    )
    assert ConstructionItem.model_validate_json(item.model_dump_json()) == item


def test_territory_queue_roundtrip():
    q = TerritoryQueue(
        territoryId="corp1::earth::tile_x",
        corpId="corp1",
        bodyId="earth",
        tileIds=["tile_x"],
        constructionCapacity=30.0,
        items=[
            ConstructionItem(id="i1", buildingType=BuildingType.Farm, tileId="tile_x",
                             bodyId="earth", corpId="corp1", ticksRemaining=45, totalCostPts=45)
        ],
    )
    assert TerritoryQueue.model_validate_json(q.model_dump_json()) == q


def test_building_construction_cost_all_types():
    for bt in BuildingType:
        assert bt in BUILDING_CONSTRUCTION_COST, f"Missing cost for {bt.name}"
        assert BUILDING_CONSTRUCTION_COST[bt] > 0


def test_construction_status_enum():
    assert ConstructionStatus.Pending == 0
    assert ConstructionStatus.InProgress == 1
    assert ConstructionStatus.Done == 2


# ---------------------------------------------------------------------------
# ── Runtime tests (need noise — skipped if absent) ─────────────────────────
# ---------------------------------------------------------------------------

def _noise_available() -> bool:
    try:
        import noise  # noqa: F401
        return True
    except ImportError:
        return False


_skip_no_noise = pytest.mark.skipif(
    not _noise_available(),
    reason="noise package not compiled — skipping runtime construction tests",
)

if _noise_available():
    if str(_SIM.parent) not in sys.path:
        sys.path.insert(0, str(_SIM.parent))
    import terraformation_sim.logic  # noqa: F401  — logic.py split into logic/ package
    _load("persistence", "persistence.py")
    _load("runtime", "runtime.py")

# ── Helpers ───────────────────────────────────────────────────────────────────

BODY_ID = "earth"
TILE_A  = "tile_a"
TILE_B  = "tile_b"
CORP_A  = "corp_alpha"
CORP_B  = "corp_beta"


def _make_runtime():
    from terraformation_sim.runtime import InMemorySimulationRuntime
    return InMemorySimulationRuntime(tick_interval_seconds=5.0, auto_resume=False)


def _add_corp(rt, corp_id: str, tile_id: str) -> None:
    rt._corporations[corp_id] = CorporationData(id=corp_id, name=corp_id)
    rt._tile_ownership.setdefault(BODY_ID, {})[tile_id] = corp_id
    rt._corporations[corp_id].claimedTiles.append(
        ClaimedTile(bodyId=BODY_ID, tileId=tile_id)
    )


def _add_population(rt, corp_id: str, tile_id: str, count: int = 100) -> None:
    corp = rt._corporations[corp_id]
    for tile in corp.claimedTiles:
        if tile.tileId == tile_id:
            tile.population = [PopulationTier(socialClass=SocialClass.Poor, count=count)]
            return


# ── Tests ─────────────────────────────────────────────────────────────────────

@_skip_no_noise
def test_construct_returns_construction_item():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    result = rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
    assert isinstance(result, ConstructionItem)
    assert result.buildingType == BuildingType.Mine
    assert result.corpId == CORP_A
    assert result.tileId == TILE_A


@_skip_no_noise
def test_building_not_in_registry_before_completion():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
    live = [b for b in rt._buildings.values() if b.tileId == TILE_A and b.buildingType == BuildingType.Mine]
    assert not live


@_skip_no_noise
def test_no_capacity_means_no_completion():
    """Sans EB et sans population → capacity = 0 → jamais terminé."""
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
    for _ in range(5):
        rt._process_construction_tick_locked()
    live = [b for b in rt._buildings.values() if b.tileId == TILE_A and b.buildingType == BuildingType.Mine]
    assert not live


@_skip_no_noise
def test_building_completes_with_eb_de_fortune():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    _add_population(rt, CORP_A, TILE_A, count=50)
    cost = BUILDING_CONSTRUCTION_COST[BuildingType.Mine]
    ticks_needed = math.ceil(cost / EB_FORTUNE_CAPACITY)
    rt._corporations[CORP_A].resources["Wood"] = EB_FORTUNE_WOOD_COST * (ticks_needed + 5)

    rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
    for _ in range(ticks_needed):
        rt._process_construction_tick_locked()

    live = [b for b in rt._buildings.values() if b.tileId == TILE_A and b.buildingType == BuildingType.Mine]
    assert live, "bâtiment doit être complété avec EB de fortune"


@_skip_no_noise
def test_overflow_completes_second_item_same_tick():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    _add_population(rt, CORP_A, TILE_A, count=100)
    huge = 1000.0
    rt._corporations[CORP_A].resources["Wood"] = huge * 10

    import terraformation_sim.runtime as rt_mod
    original = rt_mod.EB_FORTUNE_CAPACITY
    rt_mod.EB_FORTUNE_CAPACITY = huge
    try:
        rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
        rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Road)
        rt._process_construction_tick_locked()
        live_types = {b.buildingType for b in rt._buildings.values() if b.tileId == TILE_A}
        assert BuildingType.Mine in live_types
        assert BuildingType.Road in live_types
    finally:
        rt_mod.EB_FORTUNE_CAPACITY = original


@_skip_no_noise
def test_duplicate_building_type_raises():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
    with pytest.raises(ValueError, match="already"):
        rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)


@_skip_no_noise
def test_cancel_construction_item():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    item = rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Farm)
    rt.cancel_construction_item(CORP_A, item.id)
    all_items = rt.list_construction_items(CORP_A)
    assert not any(i.id == item.id for i in all_items)


@_skip_no_noise
def test_cancel_unknown_item_raises():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    with pytest.raises(KeyError):
        rt.cancel_construction_item(CORP_A, "nonexistent-id")


@_skip_no_noise
def test_list_queues_filters_by_corp():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    _add_corp(rt, CORP_B, TILE_B)
    rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Farm)
    rt.construct_building(CORP_B, BODY_ID, TILE_B, BuildingType.Mine)
    items_a = rt.list_construction_items(CORP_A)
    items_b = rt.list_construction_items(CORP_B)
    assert all(i.corpId == CORP_A for i in items_a)
    assert all(i.corpId == CORP_B for i in items_b)
    assert len(items_a) == 1
    assert len(items_b) == 1


@_skip_no_noise
def test_bootstrap_wipes_construction_queues():
    rt = _make_runtime()
    _add_corp(rt, CORP_A, TILE_A)
    rt.construct_building(CORP_A, BODY_ID, TILE_A, BuildingType.Mine)
    assert rt._construction_queues
    rt.bootstrap()
    assert not rt._construction_queues
