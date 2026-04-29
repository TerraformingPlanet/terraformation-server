"""Unit tests for natural population growth (Phase pop-growth).

Tests apply_natural_growth() pure function and GrowthConfig extensibility.
No server or database required.
"""
import pytest
from terraformation_sim.models import (
    GoldbergTileState,
    GrowthConfig,
    PopulationTier,
    SocialClass,
    TerrainType,
    WaterClassification,
)
from terraformation_sim.logic import apply_natural_growth, NATURAL_GROWTH_INTERVAL


# ── Helpers ────────────────────────────────────────────────────────────────────

def _land_tile_with_pop(poor: int = 1000, middle: int = 200, rich: int = 10) -> GoldbergTileState:
    return GoldbergTileState(
        tileId="test-tile",
        terrainType=TerrainType.Vegetation,
        waterClassification=WaterClassification.Dry,
        population=[
            PopulationTier(socialClass=SocialClass.Poor,   count=poor,   avgIncome=0.5),
            PopulationTier(socialClass=SocialClass.Middle, count=middle, avgIncome=2.0),
            PopulationTier(socialClass=SocialClass.Rich,   count=rich,   avgIncome=10.0),
        ],
    )


def _ocean_tile() -> GoldbergTileState:
    return GoldbergTileState(
        tileId="ocean-tile",
        terrainType=TerrainType.Eau,
        waterClassification=WaterClassification.OpenOcean,
        population=[
            PopulationTier(socialClass=SocialClass.Poor, count=100),
        ],
    )


# ── NATURAL_GROWTH_INTERVAL constant ──────────────────────────────────────────

def test_growth_interval_is_270():
    """9 months × 30 days at 1 tick/day = 270."""
    assert NATURAL_GROWTH_INTERVAL == 270


# ── apply_natural_growth ───────────────────────────────────────────────────────

def test_growth_with_food_increases_population():
    """With abundant food, total population must increase (use large enough count to exceed int rounding)."""
    tile = _land_tile_with_pop(poor=100_000, middle=20_000, rich=1_000)
    before = sum(t.count for t in tile.population)
    result = apply_natural_growth(tile, food_per_capita=1.0)
    after = sum(t.count for t in result.population)
    assert after > before, f"Expected population growth but got {before} → {after}"


def test_decay_without_food_decreases_population():
    """With zero food, starvation modifier should outweigh birth rate → net decline."""
    tile = _land_tile_with_pop(poor=10_000, middle=2_000, rich=100)
    before = sum(t.count for t in tile.population)
    result = apply_natural_growth(tile, food_per_capita=0.0)
    after = sum(t.count for t in result.population)
    assert after < before, f"Expected population decline but got {before} → {after}"


def test_ocean_tile_unchanged():
    """Ocean tiles must be returned unchanged (no demographic growth under water)."""
    tile = _ocean_tile()
    result = apply_natural_growth(tile, food_per_capita=1.0)
    # Population must not change (early-exit path)
    assert [t.count for t in result.population] == [t.count for t in tile.population]


def test_uninhabited_tile_unchanged():
    """Tile with empty population list must pass through unchanged."""
    tile = GoldbergTileState(tileId="empty", terrainType=TerrainType.Roche)
    result = apply_natural_growth(tile, food_per_capita=1.0)
    assert result.population == []


def test_births_added_to_poor_tier():
    """New births are always credited to the Poor tier."""
    # Use large populations so int rounding doesn't flatten results to zero
    tile = _land_tile_with_pop(poor=500_000, middle=100_000, rich=5_000)
    poor_before = next(t.count for t in tile.population if t.socialClass == SocialClass.Poor)
    result = apply_natural_growth(tile, food_per_capita=1.0)
    poor_after = next(t.count for t in result.population if t.socialClass == SocialClass.Poor)
    rich_before = next(t.count for t in tile.population if t.socialClass == SocialClass.Rich)
    rich_after  = next(t.count for t in result.population if t.socialClass == SocialClass.Rich)
    # Poor receives births + loses proportional deaths; Rich only loses deaths
    assert poor_after - poor_before > rich_after - rich_before, (
        "Births should be allocated to Poor tier, making Poor delta larger than Rich delta"
    )


def test_custom_growth_config_doubles_births():
    """GrowthConfig(growthMultiplier=2.0) should produce ~2× net births vs default."""
    tile_a = _land_tile_with_pop(poor=10_000, middle=2_000, rich=100)
    tile_b = _land_tile_with_pop(poor=10_000, middle=2_000, rich=100)

    default_config = GrowthConfig()
    double_config  = GrowthConfig(growthMultiplier=2.0)

    result_a = apply_natural_growth(tile_a, food_per_capita=1.0, config=default_config)
    result_b = apply_natural_growth(tile_b, food_per_capita=1.0, config=double_config)

    total_a = sum(t.count for t in result_a.population)
    total_b = sum(t.count for t in result_b.population)

    assert total_b > total_a, "2× growth multiplier should produce a higher total population"


def test_pure_function_does_not_mutate_input():
    """apply_natural_growth must return a new GoldbergTileState without mutating the original."""
    tile = _land_tile_with_pop()
    original_pop = [(t.socialClass, t.count) for t in tile.population]
    apply_natural_growth(tile, food_per_capita=1.0)
    assert [(t.socialClass, t.count) for t in tile.population] == original_pop, (
        "Input tile was mutated — apply_natural_growth must be a pure function"
    )
