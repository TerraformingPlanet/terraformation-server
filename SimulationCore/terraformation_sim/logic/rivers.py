"""Pure river propagation logic — Phase p-hydro-2 / p-hydro-3.

All functions are side-effect-free with respect to the runtime registry:
they receive tile lists and dicts, mutate them in-place, and return
diagnostic lists of affected tileIds.  The runtime mixin (runtime_rivers.py)
owns the arrival_ticks dict and the body tile write-back.
"""
from __future__ import annotations

from ..models import GoldbergTileState, WaterClassification

# Ticks for a maximum-capacity river (3.0 m³/tick) to advance one tile.
BASE_PROPAGATION_TICKS: int = 3
# Reference maximum spring flow (m³/tick) used to normalise propagation speed.
MAX_SOURCE_CAPACITY: float = 3.0


def _is_terminal_water(tile: GoldbergTileState) -> bool:
    """True when a river should stop propagating into this tile."""
    return tile.waterClassification in (
        WaterClassification.OpenOcean,
        WaterClassification.Coast,
        WaterClassification.InlandWater,
    )


def propagation_delay_ticks(flow: float) -> int:
    """Ticks to wait before a river front advances one tile.

    Stronger rivers (higher flow) advance faster.
    flow=3.0 → 3 ticks.  flow=0.3 → 30 ticks.  Minimum: 1 tick.
    """
    ratio = min(flow / MAX_SOURCE_CAPACITY, 1.0)
    return max(1, round(BASE_PROPAGATION_TICKS / max(ratio, 0.1)))


def activate_sources(
    tiles: list[GoldbergTileState],
    current_tick: int,
    arrival_ticks: dict[str, int],
) -> list[str]:
    """Activate springs where atmospheric temperature allows liquid water (> 0 °C).

    Modifies `tiles` and `arrival_ticks` in-place.
    Returns list of newly-activated tileIds.
    """
    newly_activated: list[str] = []
    for tile in tiles:
        if (
            tile.hasWaterSource
            and not tile.hasRiver
            and tile.temperature > 0.0
            and tile.sourceCapacity is not None
        ):
            tile.hasRiver = True
            tile.riverFlow = tile.sourceCapacity
            tile.riverSourceTileId = tile.tileId
            arrival_ticks[tile.tileId] = current_tick
            newly_activated.append(tile.tileId)
    return newly_activated


def propagate_river_step(
    tiles: list[GoldbergTileState],
    current_tick: int,
    arrival_ticks: dict[str, int],
) -> list[str]:
    """Advance all active river fronts by one step when enough ticks have elapsed.

    For each tile with hasRiver=True that has a riverDirection pointing to a dry
    tile, wait propagation_delay_ticks(flow) before wetting the downstream tile.

    Modifies `tiles` and `arrival_ticks` in-place.
    Returns list of newly-wet tileIds.
    """
    tile_by_id: dict[str, GoldbergTileState] = {t.tileId: t for t in tiles}
    newly_wet: list[str] = []

    # Only process river-front tiles (have a downstream that is still dry)
    frontier = [
        t for t in tiles
        if t.hasRiver
        and t.riverDirection is not None
        and t.riverDirection in tile_by_id
        and not tile_by_id[t.riverDirection].hasRiver
        and not _is_terminal_water(t)
    ]

    for tile in frontier:
        flow = tile.riverFlow or tile.sourceCapacity or 1.0
        delay = propagation_delay_ticks(flow)
        arrival = arrival_ticks.get(tile.tileId, current_tick)
        if current_tick - arrival < delay:
            continue

        downstream = tile_by_id[tile.riverDirection]
        if _is_terminal_water(downstream):
            continue  # river discharges here — stop

        downstream.hasRiver = True
        downstream.riverFlow = flow
        downstream.riverSourceTileId = tile.riverSourceTileId or tile.tileId
        arrival_ticks[downstream.tileId] = current_tick
        newly_wet.append(downstream.tileId)

    return newly_wet


def fill_lake_step(
    tiles: list[GoldbergTileState],
    current_tick: int,
    arrival_ticks: dict[str, int],
) -> list[str]:
    """Fill basin sink tiles that receive river flow but have no downhill exit.

    Each tick the inflow is added to lakeVolume.  When lakeVolume >= lakeCapacity
    the lake overflows: the lowest non-wet neighbour receives the river and the
    basin tile's riverDirection is set to that neighbour so normal propagation
    resumes from there.

    Modifies `tiles` and `arrival_ticks` in-place.
    Returns list of tileIds that received overflow river extension.
    """
    tile_by_id: dict[str, GoldbergTileState] = {t.tileId: t for t in tiles}
    overflow_targets: list[str] = []

    # Sink tiles: active river, no downhill path, not already a water body
    sink_tiles = [
        t for t in tiles
        if t.hasRiver
        and t.riverDirection is None
        and t.waterClassification not in (
            WaterClassification.OpenOcean,
            WaterClassification.Coast,
            WaterClassification.InlandWater,
        )
    ]

    for tile in sink_tiles:
        # First visit: initialise lake
        if not tile.hasLake:
            tile.hasLake = True
            tile.waterClassification = WaterClassification.InlandWater
            neighbor_alts = [
                tile_by_id[nid].altitude
                for nid in tile.neighborIds
                if nid in tile_by_id
            ]
            if neighbor_alts:
                wall_height = min(neighbor_alts) - tile.altitude
                tile.lakeCapacity = max(1.0, round(wall_height * 100.0, 1))
            else:
                tile.lakeCapacity = 10.0
            tile.lakeVolume = 0.0

        inflow = tile.riverFlow or 0.5
        tile.lakeVolume = (tile.lakeVolume or 0.0) + inflow

        if tile.lakeCapacity and tile.lakeVolume >= tile.lakeCapacity:
            # Overflow: route to lowest non-wet neighbour
            candidates = [
                tile_by_id[nid]
                for nid in tile.neighborIds
                if nid in tile_by_id
                and not tile_by_id[nid].hasRiver
                and tile_by_id[nid].waterClassification not in (
                    WaterClassification.OpenOcean,
                    WaterClassification.InlandWater,
                )
            ]
            if candidates:
                lowest = min(candidates, key=lambda t: t.altitude)
                lowest.hasRiver = True
                lowest.riverFlow = inflow
                lowest.riverSourceTileId = tile.riverSourceTileId
                tile.riverDirection = lowest.tileId
                arrival_ticks[lowest.tileId] = current_tick
                overflow_targets.append(lowest.tileId)

    return overflow_targets
