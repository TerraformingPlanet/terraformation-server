"""Phase p-hydro-2 assertions — Tick-based river propagation.

Tests:
1. Source activates when temperature > 0 °C
2. Source does NOT activate when temperature ≤ 0 °C
3. River front advances one tile after propagation_delay_ticks
4. River stops when it reaches a Coast / OpenOcean tile
5. Basin tile becomes a lake (hasLake=True) when no downhill exit
6. Lake overflows to a lower neighbour once lakeVolume >= lakeCapacity
"""
from __future__ import annotations

import pytest

from terraformation_sim.logic.rivers import (
    activate_sources,
    fill_lake_step,
    propagate_river_step,
    propagation_delay_ticks,
)
from terraformation_sim.models import GoldbergTileState, TerrainClass, WaterClassification


# --- Helpers -------------------------------------------------------------------

def _tile(
    tile_id: str,
    neighbors: list[str] | None = None,
    altitude: float = 0.5,
    temperature: float = 10.0,
    w_class: WaterClassification = WaterClassification.Dry,
    t_class: TerrainClass = TerrainClass.Slope,
    has_source: bool = False,
    capacity: float | None = None,
    river_dir: str | None = None,
) -> GoldbergTileState:
    return GoldbergTileState(
        tileId=tile_id,
        neighborIds=neighbors or [],
        latNorm=0.0,
        lonNorm=0.0,
        latDeg=0.0,
        lonDeg=0.0,
        altitude=altitude,
        temperature=temperature,
        waterClassification=w_class,
        terrainClass=t_class,
        hasWaterSource=has_source,
        sourceCapacity=capacity,
        riverDirection=river_dir,
    )


# --- propagation_delay_ticks ---------------------------------------------------

def test_propagation_delay_max_flow():
    assert propagation_delay_ticks(3.0) == 3


def test_propagation_delay_low_flow():
    delay = propagation_delay_ticks(0.3)
    assert delay > 3  # slower than max flow


def test_propagation_delay_minimum_one():
    assert propagation_delay_ticks(0.0001) >= 1


# --- activate_sources ----------------------------------------------------------

def test_source_activates_when_warm():
    source = _tile("src", temperature=5.0, has_source=True, capacity=1.0)
    arrival: dict[str, int] = {}
    activated = activate_sources([source], current_tick=1, arrival_ticks=arrival)
    assert "src" in activated
    assert source.hasRiver
    assert source.riverFlow == 1.0
    assert "src" in arrival


def test_source_does_not_activate_when_frozen():
    source = _tile("src", temperature=-5.0, has_source=True, capacity=1.0)
    arrival: dict[str, int] = {}
    activated = activate_sources([source], current_tick=1, arrival_ticks=arrival)
    assert activated == []
    assert not source.hasRiver


def test_source_not_reactivated():
    """Already-active source should not appear in newly_activated."""
    source = _tile("src", temperature=5.0, has_source=True, capacity=1.0)
    source.hasRiver = True
    source.riverFlow = 1.0
    arrival = {"src": 0}
    activated = activate_sources([source], current_tick=5, arrival_ticks=arrival)
    assert activated == []


# --- propagate_river_step ------------------------------------------------------

def test_river_front_advances_after_delay():
    upstream = _tile("up", neighbors=["down"], altitude=0.8, temperature=5.0, river_dir="down")
    upstream.hasRiver = True
    upstream.riverFlow = 3.0
    upstream.riverSourceTileId = "up"

    downstream = _tile("down", altitude=0.4)
    tiles = [upstream, downstream]
    arrival = {"up": 0}

    # Tick 0 → delay not elapsed (delay=3, 0-0=0 < 3)
    result = propagate_river_step(tiles, current_tick=0, arrival_ticks=arrival)
    assert result == []
    assert not downstream.hasRiver

    # Tick 3 → delay elapsed
    result = propagate_river_step(tiles, current_tick=3, arrival_ticks=arrival)
    assert "down" in result
    assert downstream.hasRiver
    assert downstream.riverFlow == 3.0


def test_river_stops_at_coast():
    upstream = _tile("up", neighbors=["sea"], altitude=0.5, river_dir="sea")
    upstream.hasRiver = True
    upstream.riverFlow = 1.0

    coast = _tile("sea", w_class=WaterClassification.Coast)
    tiles = [upstream, coast]
    arrival = {"up": 0}

    result = propagate_river_step(tiles, current_tick=100, arrival_ticks=arrival)
    assert result == []
    assert not coast.hasRiver


# --- fill_lake_step ------------------------------------------------------------

def test_basin_becomes_lake():
    basin = _tile("basin", altitude=0.1, t_class=TerrainClass.Basin)
    basin.hasRiver = True
    basin.riverFlow = 1.0
    # No riverDirection → sink
    tiles = [basin]
    arrival = {"basin": 0}

    fill_lake_step(tiles, current_tick=1, arrival_ticks=arrival)
    assert basin.hasLake
    assert basin.waterClassification == WaterClassification.InlandWater
    assert basin.lakeVolume is not None and basin.lakeVolume > 0


def test_lake_overflows_to_lowest_neighbour():
    basin = _tile("basin", neighbors=["low", "high"], altitude=0.1, t_class=TerrainClass.Basin)
    basin.hasRiver = True
    basin.riverFlow = 5.0
    basin.hasLake = True
    basin.lakeCapacity = 5.0
    basin.lakeVolume = 0.0

    low = _tile("low", altitude=0.15)
    high = _tile("high", altitude=0.9)
    tiles = [basin, low, high]
    arrival = {"basin": 0}

    overflow = fill_lake_step(tiles, current_tick=2, arrival_ticks=arrival)
    assert "low" in overflow
    assert low.hasRiver
    assert basin.riverDirection == "low"
