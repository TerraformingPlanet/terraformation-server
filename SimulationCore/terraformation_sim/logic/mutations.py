"""
Biome transition engine — pure, stateless, no I/O.

Usage:
    from terraformation_sim.logic.mutations import evaluate_biome_transitions
    transitions = evaluate_biome_transitions(tiles, rules)
    # transitions: list of (tile_id, new TerrainType)

Call this from the tick loop at whatever cadence you choose (every N ticks,
or every tick).  The caller is responsible for applying the returned mutations
to the live tile objects and persisting them.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import BiomeTransitionRule, GoldbergTileState, TerrainType


def _rule_matches(tile: "GoldbergTileState", rule: "BiomeTransitionRule") -> bool:
    """Return True if *tile* satisfies every non-None condition in *rule*."""

    # Source terrain filter — empty list means 'any terrain'
    if rule.from_terrain_types and tile.terrainType not in rule.from_terrain_types:
        return False

    t = tile.temperature
    h = tile.humidity
    v = tile.vegetationLevel
    tr = tile.treeCount
    wr = tile.waterRatio
    tx = tile.toxinLevel

    if rule.temperature_min is not None and t < rule.temperature_min:
        return False
    if rule.temperature_max is not None and t > rule.temperature_max:
        return False
    if rule.humidity_min is not None and h < rule.humidity_min:
        return False
    if rule.humidity_max is not None and h > rule.humidity_max:
        return False
    if rule.vegetation_min is not None and v < rule.vegetation_min:
        return False
    if rule.vegetation_max is not None and v > rule.vegetation_max:
        return False
    if rule.tree_count_min is not None and tr < rule.tree_count_min:
        return False
    if rule.tree_count_max is not None and tr > rule.tree_count_max:
        return False
    if rule.has_river is not None and tile.hasRiver != rule.has_river:
        return False
    if rule.has_lake is not None and tile.hasLake != rule.has_lake:
        return False
    if rule.water_ratio_min is not None and wr < rule.water_ratio_min:
        return False
    if rule.water_ratio_max is not None and wr > rule.water_ratio_max:
        return False
    if rule.toxin_min is not None and tx < rule.toxin_min:
        return False
    if rule.toxin_max is not None and tx > rule.toxin_max:
        return False

    return True


def evaluate_biome_transitions(
    tiles: "list[GoldbergTileState]",
    rules: "list[BiomeTransitionRule]",
) -> "list[tuple[str, TerrainType]]":
    """Evaluate which tiles should transition to a new biome this tick.

    Rules are expected to be pre-sorted by descending priority (highest first).
    Only the first matching rule per tile is applied.

    Returns:
        List of (tile_id, target_TerrainType) for tiles that need to change.
        Tiles whose current terrainType already equals the target are excluded.
    """
    enabled_rules = [r for r in rules if r.is_enabled]
    # Sort descending by priority (defensive — caller should have already sorted)
    enabled_rules.sort(key=lambda r: r.priority, reverse=True)

    result: list[tuple[str, TerrainType]] = []

    for tile in tiles:
        for rule in enabled_rules:
            if _rule_matches(tile, rule):
                if tile.terrainType != rule.target_terrain_type:
                    result.append((tile.tileId, rule.target_terrain_type))
                break  # first matching rule wins

    return result


def rules_from_db_rows(rows: list[dict]) -> "list[BiomeTransitionRule]":
    """Convert raw DB dict rows (from load_biome_transition_rules) to BiomeTransitionRule objects.

    Handles the JSON-encoded `from_terrain_type_ids` column.
    """
    from ..models import BiomeTransitionRule, TerrainType

    result: list[BiomeTransitionRule] = []
    for row in rows:
        from_ids_raw = row.get("from_terrain_type_ids", "[]") or "[]"
        if isinstance(from_ids_raw, str):
            from_ids: list[int] = json.loads(from_ids_raw)
        else:
            from_ids = list(from_ids_raw)

        result.append(BiomeTransitionRule(
            rule_id=row["rule_id"],
            name=row.get("name", ""),
            target_terrain_type=TerrainType(row["target_terrain_type_id"]),
            from_terrain_types=[TerrainType(i) for i in from_ids],
            priority=row.get("priority", 10),
            is_enabled=row.get("is_enabled", True),
            temperature_min=row.get("temperature_min"),
            temperature_max=row.get("temperature_max"),
            humidity_min=row.get("humidity_min"),
            humidity_max=row.get("humidity_max"),
            vegetation_min=row.get("vegetation_min"),
            vegetation_max=row.get("vegetation_max"),
            tree_count_min=row.get("tree_count_min"),
            tree_count_max=row.get("tree_count_max"),
            has_river=row.get("has_river"),
            has_lake=row.get("has_lake"),
            water_ratio_min=row.get("water_ratio_min"),
            water_ratio_max=row.get("water_ratio_max"),
            toxin_min=row.get("toxin_min"),
            toxin_max=row.get("toxin_max"),
            description=row.get("description", ""),
        ))
    return result
