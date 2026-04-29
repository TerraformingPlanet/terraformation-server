"""Phase p-hydro-1 assertions — Water source seeding at generation time.

Tests:
1. Source distribution stats are within expected probability ranges
2. Ocean / InlandWater tiles never have hasWaterSource=True
3. Tiles with hasWaterSource=True always have sourceCapacity > 0
4. riverDirection is set on non-sink land tiles after generation
5. Determinism: same seed → same sources
"""
from __future__ import annotations

import pytest

from terraformation_sim.logic.generation import (
    generate_spherical_tiles,
    _seed_water_sources,
)
from terraformation_sim.models import (
    GoldbergTileState,
    TerrainClass,
    WaterClassification,
)

# --- Helpers -------------------------------------------------------------------

def _make_land_tile(tile_id: str, altitude: float, t_class: TerrainClass) -> GoldbergTileState:
    return GoldbergTileState(
        tileId=tile_id,
        neighborIds=[],
        latNorm=0.0,
        lonNorm=0.0,
        latDeg=0.0,
        lonDeg=0.0,
        altitude=altitude,
        terrainClass=t_class,
        waterClassification=WaterClassification.Dry,
    )


def _make_water_tile(tile_id: str, w_class: WaterClassification) -> GoldbergTileState:
    return GoldbergTileState(
        tileId=tile_id,
        neighborIds=[],
        latNorm=0.0,
        lonNorm=0.0,
        latDeg=0.0,
        lonDeg=0.0,
        altitude=0.0,
        terrainClass=TerrainClass.Slope,
        waterClassification=w_class,
    )


# --- Tests ---------------------------------------------------------------------

def test_no_source_on_water_tiles():
    """Ocean and inland water tiles must never have a water source."""
    tiles = [
        _make_water_tile("ocean1", WaterClassification.OpenOcean),
        _make_water_tile("inland1", WaterClassification.InlandWater),
        _make_water_tile("frozen1", WaterClassification.FrozenWater),
    ]
    _seed_water_sources(tiles, seed=42)
    for tile in tiles:
        assert not tile.hasWaterSource, f"{tile.tileId} should not have a water source"
        assert tile.sourceCapacity is None


def test_source_capacity_positive_when_source():
    """Any tile with hasWaterSource=True must have sourceCapacity > 0."""
    # Force high-probability tiles (altitude > 0.5, Ridge)
    tiles = [_make_land_tile(str(i), 0.8, TerrainClass.Ridge) for i in range(50)]
    _seed_water_sources(tiles, seed=7)
    sources = [t for t in tiles if t.hasWaterSource]
    assert sources, "Expected some sources on Ridge/altitude>0.5 tiles"
    for tile in sources:
        assert tile.sourceCapacity is not None and tile.sourceCapacity > 0


def test_mountain_ridge_high_probability():
    """altitude>0.5 AND Ridge tiles should have ≥50% source probability over many tiles."""
    tiles = [_make_land_tile(str(i), 0.8, TerrainClass.Ridge) for i in range(200)]
    _seed_water_sources(tiles, seed=99)
    source_count = sum(1 for t in tiles if t.hasWaterSource)
    ratio = source_count / len(tiles)
    assert ratio > 0.50, f"Expected >50% sources on mountain ridges, got {ratio:.1%}"


def test_flat_land_low_probability():
    """Low-altitude flat tiles should have < 15% source probability."""
    tiles = [_make_land_tile(str(i), 0.1, TerrainClass.Slope) for i in range(500)]
    _seed_water_sources(tiles, seed=13)
    source_count = sum(1 for t in tiles if t.hasWaterSource)
    ratio = source_count / len(tiles)
    assert ratio < 0.15, f"Expected <15% sources on flat tiles, got {ratio:.1%}"


def test_determinism_same_seed():
    """Same seed must produce identical source placement."""
    tiles_a = [_make_land_tile(str(i), 0.5, TerrainClass.Ridge) for i in range(100)]
    tiles_b = [_make_land_tile(str(i), 0.5, TerrainClass.Ridge) for i in range(100)]
    _seed_water_sources(tiles_a, seed=2024)
    _seed_water_sources(tiles_b, seed=2024)
    for a, b in zip(tiles_a, tiles_b):
        assert a.hasWaterSource == b.hasWaterSource
        assert a.sourceCapacity == b.sourceCapacity


def test_river_direction_stored_on_land_tiles():
    """generate_spherical_tiles must store riverDirection on non-sink land tiles."""
    from terraformation_sim.models import DebugCoherenceOverride
    tiles = generate_spherical_tiles(
        h3_resolution=1,
        coherence_override=DebugCoherenceOverride.None_,
        water_level=0.5,
        seed=1,
    )
    land_tiles_with_direction = [
        t for t in tiles
        if t.riverDirection is not None
        and t.waterClassification == WaterClassification.Dry
    ]
    assert len(land_tiles_with_direction) > 0, "Expected some land tiles with riverDirection set"
