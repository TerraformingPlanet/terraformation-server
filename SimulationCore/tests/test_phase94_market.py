#!/usr/bin/env python3
"""
Phase 9.4 — Market price velocity and history tests.

Pattern: Load models.py and market.py directly via importlib to bypass
noise/h3 dependencies in __init__.py.

Tests:
  1. ResourceListing round-trip JSON serialization (new fields included)
  2. compute_market_prices: velocity > 0 when demand > supply
  3. priceHistory bounded to 10 entries after repeated calls
  4. priceVelocity == 0.0 on initialization (no crash)
"""

import importlib.util
import json
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────

SIM_DIR = Path(__file__).parent.parent / "terraformation_sim"

# Load models.py directly
models_path = SIM_DIR / "models.py"
models_spec = importlib.util.spec_from_file_location("terraformation_sim.models", models_path)
models_module = importlib.util.module_from_spec(models_spec)
sys.modules["terraformation_sim.models"] = models_module
models_spec.loader.exec_module(models_module)

# Load market.py logic (depends on models)
market_path = SIM_DIR / "logic" / "market.py"
market_spec = importlib.util.spec_from_file_location("terraformation_sim.logic.market", market_path)
market_module = importlib.util.module_from_spec(market_spec)
sys.modules["terraformation_sim.logic.market"] = market_module
market_spec.loader.exec_module(market_module)

# Shortcuts
ResourceType = models_module.ResourceType
ResourceListing = models_module.ResourceListing
compute_market_prices = market_module.compute_market_prices

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Round-trip JSON serialization
# ─────────────────────────────────────────────────────────────────────────────

def test_resource_listing_json_roundtrip():
    """ResourceListing with priceVelocity and priceHistory can round-trip JSON."""
    original = ResourceListing(
        resourceType=ResourceType.Food,
        price=10.5,
        supply=100.0,
        demand=120.0,
        priceVelocity=0.05,  # Phase 9.4
        priceHistory=[9.5, 9.8, 10.0, 10.2, 10.5],  # Phase 9.4
    )
    
    json_str = original.model_dump_json()
    roundtrip = ResourceListing.model_validate_json(json_str)
    
    assert roundtrip.resourceType == ResourceType.Food
    assert roundtrip.price == 10.5
    assert roundtrip.priceVelocity == 0.05
    assert roundtrip.priceHistory == [9.5, 9.8, 10.0, 10.2, 10.5]
    print("✓ Test 1 PASS: JSON round-trip with priceVelocity and priceHistory")

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Velocity > 0 when demand > supply
# ─────────────────────────────────────────────────────────────────────────────

def test_price_velocity_on_demand_increase():
    """compute_market_prices increases velocity when demand > supply."""
    listings = [
        ResourceListing(
            resourceType=ResourceType.Minerals,
            price=5.0,
            supply=100.0,
            demand=100.0,
            priceVelocity=0.0,
            priceHistory=[5.0],
        )
    ]
    
    # Demand increases → price should increase → velocity > 0
    supply = {"Minerals": 100.0}
    demand = {"Minerals": 200.0}  # 2x demand
    
    updated = compute_market_prices(listings, supply, demand)
    
    assert len(updated) == 1
    new_listing = updated[0]
    assert new_listing.price > 5.0, "Price should increase with higher demand"
    assert new_listing.priceVelocity > 0.0, "Velocity should be positive"
    assert new_listing.priceHistory[-1] == new_listing.price, "Last history entry should be new price"
    print("✓ Test 2 PASS: priceVelocity > 0 when demand increases")

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: History bounded to 10 entries
# ─────────────────────────────────────────────────────────────────────────────

def test_price_history_bounded_to_10():
    """priceHistory is bounded to 10 entries after repeated compute calls."""
    listing = ResourceListing(
        resourceType=ResourceType.Energy,
        price=20.0,
        supply=500.0,
        demand=500.0,
        priceVelocity=0.0,
        priceHistory=[20.0],
    )
    
    # Simulate 15 ticks of price updates
    supply = {"Energy": 500.0}
    demand = {"Energy": 600.0}
    
    for tick in range(15):
        result = compute_market_prices([listing], supply, demand)
        listing = result[0]
    
    # History should have exactly 10 entries (oldest 5 discarded)
    assert len(listing.priceHistory) == 10, f"Expected 10 history entries, got {len(listing.priceHistory)}"
    print(f"✓ Test 3 PASS: priceHistory bounded to 10 entries (now: {listing.priceHistory})")

# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Zero velocity on init (no crash)
# ─────────────────────────────────────────────────────────────────────────────

def test_price_velocity_init_zero():
    """New ResourceListing has priceVelocity == 0.0 (no crash on compute)."""
    listing = ResourceListing(
        resourceType=ResourceType.ResearchPoints,
        price=1.0,
        supply=10.0,
        demand=10.0,
        # priceVelocity defaults to 0.0
        # priceHistory defaults to []
    )
    
    assert listing.priceVelocity == 0.0
    assert listing.priceHistory == []
    
    # Compute with empty history should not crash
    supply = {"ResearchPoints": 10.0}
    demand = {"ResearchPoints": 10.0}
    updated = compute_market_prices([listing], supply, demand)
    
    assert len(updated) == 1
    assert updated[0].priceHistory == [1.0], "History should contain the initial price"
    print("✓ Test 4 PASS: priceVelocity == 0.0 on init, compute doesn't crash")

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        test_resource_listing_json_roundtrip()
        test_price_velocity_on_demand_increase()
        test_price_history_bounded_to_10()
        test_price_velocity_init_zero()
        print("\n" + "="*60)
        print("✓ All 4 tests PASSED")
        print("="*60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
