"""
Unit tests for Phase 9.6 — avgIncome on PopulationTier.

Pattern: Load models + logic/market.py directly via importlib to avoid noise/h3.
"""
import importlib.util
import sys
import types
from pathlib import Path

SIM_DIR = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel_path: str):
    p = SIM_DIR / rel_path
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


# Load logic package properly so downstream imports (e.g. InMemorySimulationRuntime) work
if "terraformation_sim.logic" not in sys.modules:
    if str(SIM_DIR.parent) not in sys.path:
        sys.path.insert(0, str(SIM_DIR.parent))
    import terraformation_sim.logic as _logic_pkg  # noqa: F401


_models = _load("models", "models.py")
# market.py imports models — already cached in sys.modules
_market = _load("logic.market", "logic/market.py")

PopulationTier = _models.PopulationTier
SocialClass = _models.SocialClass
compute_population_demand = _market.compute_population_demand
apply_social_mobility = _market.apply_social_mobility
auto_init_tile_population = _market.auto_init_tile_population
ClaimedTile = _models.ClaimedTile
LocalMarketState = _models.LocalMarketState
ResourceType = _models.ResourceType


# ── Helpers ────────────────────────────────────────────────────────────────────

def _market_state(territory_id: str = "t0") -> LocalMarketState:
    prices = {r.name: 1.0 for r in ResourceType}
    stock = {r.name: 100.0 for r in ResourceType}
    demand = {r.name: 10.0 for r in ResourceType}
    return LocalMarketState(
        territoryId=territory_id,
        tileIds=["tile-0"],
        prices=prices,
        stock=stock,
        demand=demand,
    )


def _tile_with_pop(poor: int, avg_income: float = 0.0) -> ClaimedTile:
    return ClaimedTile(
        tileId="tile-0",
        bodyId="body-0",
        corpId="corp-0",
        population=[
            PopulationTier(socialClass=SocialClass.Poor, count=poor, avgIncome=avg_income),
        ],
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_population_tier_roundtrip_with_avg_income():
    """PopulationTier with avgIncome survives JSON roundtrip."""
    tier = PopulationTier(socialClass=SocialClass.Poor, count=100, avgIncome=1.5)
    data = tier.model_dump()
    restored = PopulationTier(**data)
    assert restored.avgIncome == 1.5
    assert restored.socialClass == SocialClass.Poor


def test_population_tier_default_avg_income():
    """avgIncome defaults to 0.0 when not specified."""
    tier = PopulationTier(socialClass=SocialClass.Middle, count=50)
    assert tier.avgIncome == 0.0


def test_compute_population_demand_weighted_by_income():
    """Higher avgIncome → higher demand than default (income_mult=1)."""
    tile_low = _tile_with_pop(poor=100, avg_income=0.0)   # mult=1.0 (fallback)
    tile_high = _tile_with_pop(poor=100, avg_income=3.0)  # mult=3.0

    demand_low = compute_population_demand([tile_low])
    demand_high = compute_population_demand([tile_high])

    # High income should generate more demand
    total_low = sum(demand_low.values())
    total_high = sum(demand_high.values())
    assert total_high > total_low


def test_auto_init_tile_population_seeds_income():
    """auto_init_tile_population seeds avgIncome for new Poor tier."""
    tile = ClaimedTile(tileId="tile-0", bodyId="b0", corpId="c0", population=[])
    updated = auto_init_tile_population(tile)
    poor_tiers = [t for t in updated.population if t.socialClass == SocialClass.Poor]
    assert poor_tiers, "Expected at least one Poor tier after init"
    assert poor_tiers[0].avgIncome > 0.0


def test_apply_social_mobility_updates_avg_income():
    """apply_social_mobility nudges avgIncome up when employment is high."""
    tier = PopulationTier(socialClass=SocialClass.Poor, count=1000, avgIncome=1.0)
    tile = ClaimedTile(tileId="tile-0", bodyId="b0", corpId="c0", population=[tier])
    # High employment rate
    tile_updated = apply_social_mobility(tile, employment_ratio=1.0)
    poor_after = next(t for t in tile_updated.population if t.socialClass == SocialClass.Poor)
    assert poor_after.avgIncome >= 1.0


def test_apply_social_mobility_clamps_income_within_bounds():
    """avgIncome for Poor tier must stay within [0.5, 2.0]."""
    tier = PopulationTier(socialClass=SocialClass.Poor, count=1000, avgIncome=2.0)
    tile = ClaimedTile(tileId="tile-0", bodyId="b0", corpId="c0", population=[tier])
    # Run many ticks at high employment, income should not exceed 2.0 for Poor
    for _ in range(100):
        tile = apply_social_mobility(tile, employment_ratio=1.0)
    poor = next(t for t in tile.population if t.socialClass == SocialClass.Poor)
    assert poor.avgIncome <= 2.0 + 1e-6
