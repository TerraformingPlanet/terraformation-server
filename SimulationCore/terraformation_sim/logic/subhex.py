"""
Sub-hex slot logic — Phase slot-v1.

Pure functions: no side effects, no registry, no self.
Each GoldbergTileState contains 7 sub-hexes (index 0=centre, 1-6=ring).
The number of buildable slots is determined by terrain type and a seeded RNG.
Features (River, Forest, Mineral…) are assigned based on tile physical state.
"""
from __future__ import annotations

import random

from ..models import (
    GoldbergTileState,
    SubHex,
    SUBHEX_FEATURE_EMPTY,
    SUBHEX_FEATURE_RIVER,
    SUBHEX_FEATURE_FOREST,
    SUBHEX_FEATURE_MINERAL,
    SUBHEX_FEATURE_WATER_SOURCE,
    SUBHEX_FEATURE_RESIDENTIAL,
    TerrainType,
)

# ── Slot range per terrain type ───────────────────────────────────────────────
# (min_buildable, max_buildable) — out of 7 sub-hexes
SLOT_RANGES: dict[TerrainType, tuple[int, int]] = {
    TerrainType.Vegetation:         (4, 6),
    TerrainType.Foret:              (3, 5),
    TerrainType.Jungle:             (3, 5),
    TerrainType.ZoneHumide:         (3, 5),
    TerrainType.Desert:             (3, 5),
    TerrainType.Metal:              (3, 5),
    TerrainType.Roche:              (2, 4),
    TerrainType.Glace:              (1, 3),
    TerrainType.AtmosphereToxique:  (1, 2),
    TerrainType.Eau:                (0, 0),
}

# Sub-hex adjacency: index → neighbor indices within the 7-cell grid
# Centre (0) touches all ring cells (1-6); ring cell n touches centre + 2 ring neighbours
_RING_NEIGHBORS: dict[int, list[int]] = {
    0: [1, 2, 3, 4, 5, 6],
    1: [0, 2, 6],
    2: [0, 1, 3],
    3: [0, 2, 4],
    4: [0, 3, 5],
    5: [0, 4, 6],
    6: [0, 5, 1],
}


def init_sub_hexes(tile: GoldbergTileState) -> list[SubHex]:
    """Generate the 7 sub-hexes for a tile.

    Deterministic: seeded on hash(tile.tileId) so the same tile always produces
    the same layout.  Buildable count comes from SLOT_RANGES[terrain] ± random.
    Non-buildable sub-hexes are assigned from the end of the ring (indices 6, 5, …).

    Feature assignment priority (mutually exclusive per slot):
      1. River           — if tile.hasRiver  (1-2 ring slots)
      2. WaterSource     — if tile.hasWaterSource or tile.hasLake  (1 slot, centre preferred)
      3. Forest          — if terrain Foret/Jungle or treeCount > 100  (2-3 ring slots)
      4. Mineral         — if terrain Metal  (2-3 ring slots)
      5. Residential     — if tile.population is non-empty  (1 centre slot)
      6. Empty           — all remaining buildable slots
    """
    terrain = tile.terrainType
    lo, hi = SLOT_RANGES.get(terrain, (0, 0))

    rng = random.Random(hash(tile.tileId) & 0xFFFF_FFFF)
    n_buildable = rng.randint(lo, hi)

    # All 7 indices; non-buildable = highest ring indices first
    all_indices = list(range(7))
    non_buildable_set: set[int] = set(all_indices[7 - (7 - n_buildable):]) if n_buildable < 7 else set()
    if n_buildable == 0:
        non_buildable_set = set(range(7))

    # Feature pools — ring slots only (avoid locking centre for terrain features)
    ring_buildable = [i for i in range(1, 7) if i not in non_buildable_set]
    rng.shuffle(ring_buildable)
    feature_map: dict[int, int] = {}  # slot index -> feature_id

    ptr = 0

    # River (1–2 slots)
    if tile.hasRiver and ring_buildable:
        count = min(2, len(ring_buildable) - ptr)
        for _ in range(count):
            feature_map[ring_buildable[ptr]] = SUBHEX_FEATURE_RIVER
            ptr += 1

    # WaterSource (1 slot — prefer centre if buildable, else first ring)
    if (tile.hasWaterSource or tile.hasLake) and ptr < len(ring_buildable):
        if 0 not in non_buildable_set and 0 not in feature_map:
            feature_map[0] = SUBHEX_FEATURE_WATER_SOURCE
        else:
            feature_map[ring_buildable[ptr]] = SUBHEX_FEATURE_WATER_SOURCE
            ptr += 1

    # Forest (2–3 slots)
    is_forested = terrain in (TerrainType.Foret, TerrainType.Jungle) or tile.treeCount > 100
    if is_forested:
        count = min(3 if terrain in (TerrainType.Foret, TerrainType.Jungle) else 2,
                    len(ring_buildable) - ptr)
        for _ in range(count):
            if ptr < len(ring_buildable):
                feature_map[ring_buildable[ptr]] = SUBHEX_FEATURE_FOREST
                ptr += 1

    # Mineral (2–3 slots)
    if terrain == TerrainType.Metal:
        count = min(3, len(ring_buildable) - ptr)
        for _ in range(count):
            if ptr < len(ring_buildable):
                feature_map[ring_buildable[ptr]] = SUBHEX_FEATURE_MINERAL
                ptr += 1

    # Residential (centre only, if population present)
    if tile.population and 0 not in non_buildable_set and 0 not in feature_map:
        feature_map[0] = SUBHEX_FEATURE_RESIDENTIAL

    # Build final list
    result: list[SubHex] = []
    for i in all_indices:
        result.append(SubHex(
            index=i,
            feature=feature_map.get(i, SUBHEX_FEATURE_EMPTY),
            buildable=(i not in non_buildable_set),
            buildingId="",
        ))
    return result


def find_free_slot(sub_hexes: list[SubHex]) -> int:
    """Return the index of the first buildable, unoccupied sub-hex, or -1 if none."""
    for sh in sub_hexes:
        if sh.buildable and not sh.buildingId:
            return sh.index
    return -1


def occupied_slot_count(sub_hexes: list[SubHex]) -> int:
    """Count sub-hexes that have a building (or construction) assigned."""
    return sum(1 for sh in sub_hexes if sh.buildingId)


def free_slot_count(sub_hexes: list[SubHex]) -> int:
    """Count buildable sub-hexes with no building assigned."""
    return sum(1 for sh in sub_hexes if sh.buildable and not sh.buildingId)
