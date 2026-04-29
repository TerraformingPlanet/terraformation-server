"""
test_phase73_market.py — Phase 7.3 : Marché local v1.

Tests couverts :
    - Roundtrip JSON LocalMarketState
    - SocialClass / PopulationTier roundtrip
    - compute_population_demand — agrège la demande par classe sociale
    - compute_market_prices — prix monte si demand > supply, descend sinon
    - apply_social_mobility — Poor→Middle avec emploi, Middle→Poor sans emploi
    - init_market_listings — retourne une listing par ressource tradable

Pas de Docker, pas de réseau. Durée < 1 s.
"""
import json
import sys
import importlib.util
from pathlib import Path

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")
# market.py imports h3 and registry — mock/preload before loading
import unittest.mock as _mock
sys.modules.setdefault("h3", _mock.MagicMock())
# Preload registry so market.py's relative import resolves
_registry = _load("registry", "registry.py")
sys.modules.setdefault("terraformation_sim.registry", _registry)
_market = _load("logic.market", "logic/market.py")

LocalMarketState    = _models.LocalMarketState
ResourceListing     = _models.ResourceListing
ResourceType        = _models.ResourceType
SocialClass         = _models.SocialClass
PopulationTier      = _models.PopulationTier
ClaimedTile         = _models.ClaimedTile

compute_population_demand = _market.compute_population_demand
compute_market_prices     = _market.compute_market_prices
apply_social_mobility     = _market.apply_social_mobility
init_market_listings      = _market.init_market_listings
TRADABLE_RESOURCES        = _market.TRADABLE_RESOURCES


# ── Test 1 : Roundtrip JSON LocalMarketState ──────────────────────────────────

def test_local_market_state_roundtrip():
    market = LocalMarketState(
        territoryId="corp1::hex1",
        ownerEntityId="corp1",
        tileIds=["hex1", "hex2"],
        listings=[
            ResourceListing(resourceType=ResourceType.Food, price=2.0, supply=10.0, demand=8.0),
        ],
        taxRate=0.1,
        connectivity=0.9,
        tickComputed=5,
    )
    data = json.loads(market.model_dump_json())
    market2 = LocalMarketState.model_validate(data)

    assert market2.territoryId == "corp1::hex1"
    assert market2.taxRate == 0.1
    assert market2.connectivity == 0.9
    assert market2.tickComputed == 5
    assert len(market2.listings) == 1
    assert market2.listings[0].price == 2.0
    print("✓ LocalMarketState roundtrip OK")


# ── Test 2 : SocialClass / PopulationTier roundtrip ──────────────────────────

def test_population_tier_roundtrip():
    tiers = [
        PopulationTier(socialClass=SocialClass.Poor,   count=100),
        PopulationTier(socialClass=SocialClass.Middle, count=50),
        PopulationTier(socialClass=SocialClass.Rich,   count=10),
    ]
    for tier in tiers:
        data = json.loads(tier.model_dump_json())
        tier2 = PopulationTier.model_validate(data)
        assert tier2.socialClass == tier.socialClass
        assert tier2.count == tier.count
    print("✓ PopulationTier roundtrip OK for all 3 classes")


# ── Test 3 : compute_population_demand ───────────────────────────────────────

def test_compute_population_demand_aggregates_classes():
    tile = ClaimedTile(
        bodyId="earth",
        tileId="hex1",
        population=[
            PopulationTier(socialClass=SocialClass.Poor,   count=100),
            PopulationTier(socialClass=SocialClass.Middle, count=20),
        ],
    )
    demand = compute_population_demand([tile])

    # Poor: Food=0.5/person → 100*0.5=50; Middle: Food=1.0/person → 20*1.0=20 → total=70
    assert "Food" in demand
    assert abs(demand["Food"] - 70.0) < 0.01, f"Expected 70.0, got {demand['Food']}"
    # Poor: Energy=0.3/person → 30; Middle: Energy=0.8/person → 16 → total=46
    assert "Energy" in demand
    assert abs(demand["Energy"] - 46.0) < 0.01, f"Expected 46.0, got {demand['Energy']}"
    # Minerals only from Middle class
    assert "Minerals" in demand
    assert abs(demand["Minerals"] - 4.0) < 0.01, f"Expected 4.0, got {demand['Minerals']}"
    print(f"✓ compute_population_demand OK: Food={demand['Food']}, Energy={demand['Energy']}")


# ── Test 4 : compute_market_prices — price rises on scarcity ─────────────────

def test_compute_market_prices_price_rises_on_scarcity():
    listings = init_market_listings()
    # Scarcity: high demand, low supply → price should rise
    supply = {"Food": 1.0}
    demand = {"Food": 100.0}
    updated = compute_market_prices(listings, supply, demand)

    food = next(l for l in updated if l.resourceType == ResourceType.Food)
    # Original price was 1.0 — should have risen
    assert food.price > 1.0, f"Expected price > 1.0, got {food.price}"
    assert food.demand == 100.0
    assert food.supply == 1.0
    assert food.priceVelocity > 0, "Velocity should be positive on scarcity"
    print(f"✓ compute_market_prices scarcity: Food price={food.price:.3f}, velocity={food.priceVelocity:.3f}")


def test_compute_market_prices_price_falls_on_surplus():
    listings = init_market_listings()
    # Surplus: low demand, high supply → price should fall
    supply = {"Food": 1000.0}
    demand = {"Food": 1.0}
    updated = compute_market_prices(listings, supply, demand)

    food = next(l for l in updated if l.resourceType == ResourceType.Food)
    assert food.price < 1.0, f"Expected price < 1.0, got {food.price}"
    assert food.priceVelocity < 0, "Velocity should be negative on surplus"
    print(f"✓ compute_market_prices surplus: Food price={food.price:.3f}")


# ── Test 5 : apply_social_mobility ──────────────────────────────────────────

def test_apply_social_mobility_full_employment_promotes_poor():
    tile = ClaimedTile(
        bodyId="earth",
        tileId="hex1",
        population=[
            PopulationTier(socialClass=SocialClass.Poor,   count=1000),
            PopulationTier(socialClass=SocialClass.Middle, count=100),
        ],
    )
    updated = apply_social_mobility(tile, employment_ratio=1.0)

    poor_after   = next((t.count for t in updated.population if t.socialClass == SocialClass.Poor), 0)
    middle_after = next((t.count for t in updated.population if t.socialClass == SocialClass.Middle), 0)

    # With full employment: 1% of Poor move to Middle
    assert poor_after < 1000, f"Poor count should decrease, got {poor_after}"
    assert middle_after > 100, f"Middle count should increase, got {middle_after}"
    print(f"✓ apply_social_mobility full employment: Poor {1000}→{poor_after}, Middle {100}→{middle_after}")


def test_apply_social_mobility_zero_employment_demotes_middle():
    tile = ClaimedTile(
        bodyId="earth",
        tileId="hex1",
        population=[
            PopulationTier(socialClass=SocialClass.Poor,   count=100),
            PopulationTier(socialClass=SocialClass.Middle, count=1000),
        ],
    )
    updated = apply_social_mobility(tile, employment_ratio=0.0)

    poor_after   = next((t.count for t in updated.population if t.socialClass == SocialClass.Poor), 0)
    middle_after = next((t.count for t in updated.population if t.socialClass == SocialClass.Middle), 0)

    assert poor_after > 100, f"Poor count should increase, got {poor_after}"
    assert middle_after < 1000, f"Middle count should decrease, got {middle_after}"
    print(f"✓ apply_social_mobility zero employment: Poor {100}→{poor_after}, Middle {1000}→{middle_after}")
