"""
Assertion script for Phase Biome Mutation — DB-driven biome transitions.

Exit criteria:
- TerrainType enum extended with Desert=7, Jungle=8, ZoneHumide=9 (Python + C#)
- BiomeTransitionRule model with 14 condition fields (temperature/humidity/vegetation/tree_count/has_river/has_lake/water_ratio/toxin)
- DB schema + seed data (8 rules for Desert/Vegetation/Jungle transitions)
- Mutations logic: evaluate_biome_transitions() returns tile_id -> new_type for qualifying tiles
- Runtime catalog: list/get/upsert/delete biome rules, list/update terrain types
- Server endpoints: 6 catalog endpoints (GET/POST/PATCH/DELETE biome-rules, GET/PATCH terrain-types)
- MCP tools: 7 tools (list/get/create/update/delete biome rules, list/update terrain types)
- Tick integration: _process_biome_tick_locked() every BIOME_TICK_INTERVAL=5 ticks, applies mutations to DB
- Cache invalidation: upsert/delete biome rules invalidates _biome_rules_cache
"""
import pytest

from terraformation_sim.models import TerrainType, BiomeTransitionRule, GoldbergTileState
from terraformation_sim.logic.mutations import evaluate_biome_transitions, rules_from_db_rows
from terraformation_sim.persistence import _BIOME_TRANSITION_RULES_SEED
from terraformation_sim.runtime import InMemorySimulationRuntime, BIOME_TICK_INTERVAL


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def runtime():
    """Provide a minimal runtime for testing."""
    return InMemorySimulationRuntime()


@pytest.fixture
def seeded_rules():
    """Provide seeded biome transition rules."""
    return rules_from_db_rows(_BIOME_TRANSITION_RULES_SEED)


# ── tests des critères de sortie ──────────────────────────────────────────────

def test_terrain_type_enum_extended():
    """TerrainType enum has Desert=7, Jungle=8, ZoneHumide=9."""
    assert TerrainType.Desert == 7
    assert TerrainType.Jungle == 8
    assert TerrainType.ZoneHumide == 9
    assert len(TerrainType) == 10  # Original 7 + 3 new


def test_biome_transition_rule_model():
    """BiomeTransitionRule has all 14 condition fields."""
    rule = BiomeTransitionRule(
        rule_id=1,
        name="Test Rule",
        target_terrain_type=TerrainType.Desert,
        from_terrain_types=[TerrainType.Vegetation],
        priority=1,
        is_enabled=True,
        temperature_min=30.0,
        temperature_max=50.0,
        humidity_min=0.0,
        humidity_max=0.1,
        vegetation_min=0.5,
        vegetation_max=1.0,
        tree_count_min=0,
        tree_count_max=10,
        has_river=True,
        has_lake=False,
        water_ratio_min=0.0,
        water_ratio_max=0.2,
        toxin_min=0.0,
        toxin_max=0.1,
        description="Test rule for desertification"
    )
    assert rule.rule_id == 1
    assert rule.target_terrain_type == TerrainType.Desert
    assert rule.from_terrain_types == [TerrainType.Vegetation]
    assert rule.has_river is True
    assert rule.has_lake is False


def test_db_seed_data(seeded_rules):
    """DB seed has 8 rules for Desert/Vegetation/Jungle transitions."""
    assert len(seeded_rules) == 8
    rule_names = [r.name for r in seeded_rules]
    assert "Vegetation → Desert (dry)" in rule_names
    assert "Vegetation → Foret (dense trees)" in rule_names
    assert "Foret → Jungle (hot humid)" in rule_names


def test_mutations_logic(seeded_rules):
    """evaluate_biome_transitions returns correct mutations."""
    # Desert test: vegetation sèche → Desert
    tile_dry = GoldbergTileState(
        tileId='test1',
        terrainType=TerrainType.Vegetation,
        humidity=0.02,
        vegetationLevel=1.0,
        treeCount=2.0,
        hasRiver=False,
        hasLake=False
    )

    mutations = evaluate_biome_transitions([tile_dry], seeded_rules)
    assert mutations == [('test1', TerrainType.Desert)]

    # Foret test: Vegetation dense → Foret
    tile_dense = GoldbergTileState(
        tileId='test2',
        terrainType=TerrainType.Vegetation,
        treeCount=2500.0
    )
    mutations = evaluate_biome_transitions([tile_dense], seeded_rules)
    assert mutations == [('test2', TerrainType.Foret)]

    # Jungle test: Foret chaud humide → Jungle
    tile_jungle = GoldbergTileState(
        tileId='test3',
        terrainType=TerrainType.Foret,
        temperature=38.0,
        humidity=0.65
    )
    mutations = evaluate_biome_transitions([tile_jungle], seeded_rules)
    assert mutations == [('test3', TerrainType.Jungle)]


def test_runtime_catalog_methods(runtime):
    """Runtime has catalog methods for biome rules and terrain types."""
    # Test biome rules
    rules = runtime.list_biome_transition_rules()
    assert isinstance(rules, list)
    assert len(rules) >= 8  # At least seeded rules

    rule = runtime.get_biome_transition_rule(1)
    assert rule is not None
    assert rule.rule_id == 1

    # Test terrain types
    defs = runtime.list_terrain_type_defs()
    assert isinstance(defs, list)
    assert len(defs) == 10  # All terrain types
    names = [d['name'] for d in defs]
    assert 'Desert' in names
    assert 'Jungle' in names
    assert 'ZoneHumide' in names


def test_runtime_cache_invalidation(runtime):
    """Cache invalidation works on upsert/delete."""
    # Initial cache load
    rules1 = runtime._get_biome_rules_cached()
    assert len(rules1) >= 8

    # Upsert should invalidate
    new_rule = BiomeTransitionRule(
        rule_id=999,
        name="Test Cache",
        target_terrain_type=TerrainType.Desert,
        from_terrain_types=[TerrainType.Vegetation],
        priority=1,
        is_enabled=True,
        description="Test rule"
    )
    runtime.upsert_biome_transition_rule(new_rule)
    assert runtime._biome_rules_cache is None  # Cache invalidated

    # Reload cache
    rules2 = runtime._get_biome_rules_cached()
    assert len(rules2) >= 9  # New rule added

    # Delete should invalidate
    runtime.delete_biome_transition_rule(999)
    assert runtime._biome_rules_cache is None  # Cache invalidated


def test_tick_integration_constant():
    """BIOME_TICK_INTERVAL is defined as 5."""
    assert BIOME_TICK_INTERVAL == 5


def test_tick_integration_method(runtime):
    """Runtime has _process_biome_tick_locked method."""
    assert hasattr(runtime, '_process_biome_tick_locked')
    # Method should not raise on call (though no-op without active body)
    runtime._tick_count = BIOME_TICK_INTERVAL  # Set to trigger
    runtime._process_biome_tick_locked()  # Should not raise</content>
<parameter name="filePath">e:\terraformation\SimulationCore\tests\assertions\test_p_biome_mutation.py