"""
Tests for the sub-hex slot system (Phase slot-v1).

Tests 1-4, 7 are pure-logic (no runtime needed).
Tests 5-6 require a SphericalBodyState with tiles in the runtime.
"""
from __future__ import annotations

import pytest
from terraformation_sim.logic.subhex import init_sub_hexes, SLOT_RANGES
from terraformation_sim.models import (
    GoldbergTileState,
    TerrainType,
    SubHex,
    CorporationData,
    SUBHEX_FEATURE_EMPTY,
    SUBHEX_FEATURE_RIVER,
    SUBHEX_FEATURE_FOREST,
    SUBHEX_FEATURE_MINERAL,
    SUBHEX_FEATURE_WATER_SOURCE,
    SUBHEX_FEATURE_RESIDENTIAL,
    EB_FORTUNE_POP_THRESHOLD,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _tile(
    tile_id: str = "t1",
    terrain: TerrainType = TerrainType.Foret,
    has_river: bool = False,
    population: int = 0,
    tree_count: int = 0,
) -> GoldbergTileState:
    t = GoldbergTileState(tileId=tile_id, terrainType=terrain)
    t.hasRiver = has_river
    t.treeCount = tree_count
    if population:
        # GoldbergTileState.population is a list of pop entries
        # For tests we use the simple integer approach via direct assignment
        t.population = population  # type: ignore[assignment]
    return t


def _make_runtime():
    from terraformation_sim.runtime import InMemorySimulationRuntime
    rt = InMemorySimulationRuntime()
    rt._corporations["corp_alpha"] = CorporationData(id="corp_alpha", name="Alpha Corp")
    return rt


def _runtime_with_body(tile_terrain=TerrainType.Vegetation, n_free_slots: int | None = None):
    """Return a runtime that has a body 'earth' with tile 'tile_a' loaded."""
    from terraformation_sim.runtime import InMemorySimulationRuntime
    from terraformation_sim.models import SphericalBodyState

    rt = InMemorySimulationRuntime()
    rt._corporations["corp_alpha"] = CorporationData(id="corp_alpha", name="Alpha Corp")

    tile = GoldbergTileState(tileId="tile_a", terrainType=tile_terrain)
    tile.subHexes = []

    if n_free_slots is not None:
        # Force a fixed sub-hex layout with exactly n_free_slots buildable and empty
        total = 7
        tile.subHexes = [
            SubHex(
                index=i,
                feature=SUBHEX_FEATURE_EMPTY,
                buildable=(i < n_free_slots),
                buildingId="",
            )
            for i in range(total)
        ]
    # else: lazy init will run inside get_body_tile

    body = SphericalBodyState(bodyId="earth", name="Earth")
    body.tiles = [tile]

    rt._bodies["earth"] = body
    return rt


# ── Test 1 : slot count within SLOT_RANGES bounds ─────────────────────────────

def test_slot_count_within_range():
    """For a Foret tile the buildable count must be in [3, 5]."""
    tile = _tile(terrain=TerrainType.Foret)
    subs = init_sub_hexes(tile)
    buildable = sum(1 for s in subs if s.buildable)
    lo, hi = SLOT_RANGES[TerrainType.Foret]
    assert lo <= buildable <= hi, f"Expected [{lo}, {hi}], got {buildable}"


# ── Test 2 : determinism ──────────────────────────────────────────────────────

def test_deterministic_seed():
    """Calling init_sub_hexes twice on the same tile gives identical results."""
    tile = _tile(tile_id="stable_tile", terrain=TerrainType.Roche)
    first = init_sub_hexes(tile)
    second = init_sub_hexes(tile)
    assert [s.feature for s in first] == [s.feature for s in second]
    assert [s.buildable for s in first] == [s.buildable for s in second]


# ── Test 3 : river feature assigned ───────────────────────────────────────────

def test_river_feature_assigned():
    """A tile with hasRiver=True should have at least one sub-hex with RIVER."""
    tile = _tile(terrain=TerrainType.Vegetation, has_river=True)
    subs = init_sub_hexes(tile)
    river_slots = [s for s in subs if s.feature == SUBHEX_FEATURE_RIVER]
    assert len(river_slots) >= 1, "Expected ≥1 RIVER slot"


# ── Test 4 : Eau tile → 0 buildable ───────────────────────────────────────────

def test_eau_no_slots():
    """An ocean/water tile must have 0 buildable sub-hexes."""
    tile = _tile(terrain=TerrainType.Eau)
    subs = init_sub_hexes(tile)
    buildable = sum(1 for s in subs if s.buildable)
    assert buildable == 0, f"Expected 0 buildable for Eau, got {buildable}"


# ── Test 5 : placement reserves a slot ────────────────────────────────────────

def test_placement_reserves_slot():
    """Enqueueing construction on a tile with sub-hexes must reserve one slot."""
    rt = _runtime_with_body(tile_terrain=TerrainType.Vegetation)
    item = rt.construct_building("corp_alpha", "earth", "tile_a", "Mine")
    tile = rt.get_body_tile("earth", "tile_a")
    reserved = [s for s in tile.subHexes if s.buildingId == item.id]
    assert len(reserved) == 1, f"Expected 1 reserved slot, got {len(reserved)}"


# ── Test 6 : no free slots raises ValueError ──────────────────────────────────

def test_slot_full_raises():
    """Building on a tile with 0 free slots must raise ValueError."""
    rt = _runtime_with_body(n_free_slots=0)
    with pytest.raises(ValueError, match="slot"):
        rt.construct_building("corp_alpha", "earth", "tile_a", "Mine")


# ── Test 7 : EB de fortune pop threshold ─────────────────────────────────────

def test_eb_fortune_pop_threshold():
    """
    _check_eb_de_fortune_locked returns:
      - EB_FORTUNE_CAPACITY when tile pop >= EB_FORTUNE_POP_THRESHOLD
      - 0 when pop < threshold
    """
    from terraformation_sim.models import EB_FORTUNE_CAPACITY, SphericalBodyState, PopulationTier

    rt = _make_runtime()

    # Build a body with two tiles: one above threshold, one below
    body = SphericalBodyState(bodyId="home", name="Home")

    tile_good = GoldbergTileState(tileId="tile_good", terrainType=TerrainType.Vegetation)
    tile_good.population = [PopulationTier(count=EB_FORTUNE_POP_THRESHOLD)]

    tile_low = GoldbergTileState(tileId="tile_low", terrainType=TerrainType.Vegetation)
    tile_low.population = [PopulationTier(count=EB_FORTUNE_POP_THRESHOLD - 1)]

    body.tiles = [tile_good, tile_low]
    rt._bodies["home"] = body
    # use the public method via the runtime lock instead.
    with rt._lock:
        result_high = rt._check_eb_de_fortune_locked("corp_alpha", "home", ["tile_good"])
        result_low  = rt._check_eb_de_fortune_locked("corp_alpha", "home", ["tile_low"])

    assert result_high == EB_FORTUNE_CAPACITY, f"Expected {EB_FORTUNE_CAPACITY}, got {result_high}"
    assert result_low == 0, f"Expected 0, got {result_low}"
