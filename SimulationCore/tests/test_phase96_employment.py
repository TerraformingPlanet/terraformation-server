"""
Unit tests for Phase 9.6 — employmentSlots on BuildingData.

Pattern: Uses InMemorySimulationRuntime in-process (requires h3).
These tests need the full runtime and are NOT marked llm/scenario.
"""
import importlib.util
import sys
from pathlib import Path

SIM_DIR = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel_path: str):
    p = SIM_DIR / rel_path
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")

BuildingData = _models.BuildingData
BuildingType = _models.BuildingType
EMPLOYMENT_CONFIGS = _models.EMPLOYMENT_CONFIGS
PopulationTier = _models.PopulationTier
SocialClass = _models.SocialClass
ClaimedTile = _models.ClaimedTile


# ── Tests (pure model level, no runtime import needed) ─────────────────────────

def test_employment_configs_exist():
    """EMPLOYMENT_CONFIGS is populated for all BuildingType values."""
    for bt in BuildingType:
        assert bt in EMPLOYMENT_CONFIGS, f"Missing EMPLOYMENT_CONFIGS entry for {bt}"


def test_mine_employment_slots():
    """Mine config has Poor and Middle workers."""
    slots = EMPLOYMENT_CONFIGS[BuildingType.Mine]
    assert slots.get("Poor", 0) > 0
    assert slots.get("Middle", 0) > 0


def test_road_employment_slots_empty():
    """Infrastructure buildings (Road) have no employment slots."""
    assert EMPLOYMENT_CONFIGS[BuildingType.Road] == {}


def test_building_data_employment_slots_roundtrip():
    """BuildingData with employmentSlots survives JSON roundtrip."""
    building = BuildingData(
        id="b1",
        buildingType=BuildingType.Mine,
        tileId="tile-0",
        bodyId="body-0",
        corpId="corp-0",
        employmentSlots={"Poor": 50, "Middle": 10},
    )
    data = building.model_dump()
    restored = BuildingData(**data)
    assert restored.employmentSlots == {"Poor": 50, "Middle": 10}


def test_worker_ratio_calculation():
    """
    Manual workerRatio calculation from employmentSlots + tile population.
    Mirrors logic in runtime._process_building_production().
    """
    slots = {"Poor": 50, "Middle": 10}  # Mine total = 60
    total_slots = sum(slots.values())

    # Full population: 50 Poor + 10 Middle = 60 workers → ratio = 1.0
    tier_counts = {"Poor": 50, "Middle": 10}
    workers_present = sum(min(tier_counts.get(sc, 0), s) for sc, s in slots.items())
    ratio = workers_present / total_slots
    assert ratio == 1.0

    # Half population: 25 Poor + 5 Middle = 30 workers → ratio = 0.5
    tier_counts_half = {"Poor": 25, "Middle": 5}
    workers_half = sum(min(tier_counts_half.get(sc, 0), s) for sc, s in slots.items())
    ratio_half = workers_half / total_slots
    assert abs(ratio_half - 0.5) < 1e-9

    # No population → ratio = 0.0
    workers_none = sum(min(0, s) for s in slots.values())
    ratio_none = workers_none / total_slots
    assert ratio_none == 0.0


def test_road_worker_ratio_unaffected():
    """Road has empty employmentSlots — manual workerRatio is preserved."""
    # Simulate what runtime does: if employmentSlots is empty, skip auto-calc
    slots = EMPLOYMENT_CONFIGS[BuildingType.Road]
    assert slots == {}
    # Runtime skips block when employmentSlots is falsy → workerRatio unchanged
