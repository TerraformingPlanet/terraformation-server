"""
Test Phase 9.5 M2 — GlobalMarketState and compute_global_market.

Tests aggregation of local markets into global market state.
"""
import sys
import importlib.util
from pathlib import Path

_SIM = Path(__file__).parent.parent / "terraformation_sim"

# Load models.py
spec = importlib.util.spec_from_file_location("terraformation_sim.models",
    _SIM / "models.py")
models = importlib.util.module_from_spec(spec)
sys.modules["terraformation_sim.models"] = models
spec.loader.exec_module(models)

# Pre-load registry to avoid circular import via __init__.py
spec_reg = importlib.util.spec_from_file_location("terraformation_sim.registry",
    _SIM / "registry.py")
registry_mod = importlib.util.module_from_spec(spec_reg)
sys.modules["terraformation_sim.registry"] = registry_mod
spec_reg.loader.exec_module(registry_mod)

# Load market logic
spec = importlib.util.spec_from_file_location("terraformation_sim.logic.market",
    _SIM / "logic" / "market.py")
market_logic = importlib.util.module_from_spec(spec)
sys.modules["terraformation_sim.logic.market"] = market_logic
spec.loader.exec_module(market_logic)

def test_global_market_state_model():
    """Verify GlobalMarketState model exists and can be instantiated."""
    state = models.GlobalMarketState(
        systemId="sol",
        listings=[],
        tick=100,
        marketCount=0,
    )
    assert state.systemId == "sol"
    assert state.tick == 100
    assert state.marketCount == 0
    assert len(state.listings) == 0
    print("✓ GlobalMarketState model works")

def test_compute_global_market_aggregation():
    """Test aggregation of local markets into global market."""
    # Create two local markets with different prices
    market1 = models.LocalMarketState(
        territoryId="sol::tile1",
        ownerEntityId="corp1",
        tileIds=["tile1"],
        listings=[
            models.ResourceListing(resourceType=models.ResourceType.Minerals, price=2.0, supply=10.0, demand=5.0),
            models.ResourceListing(resourceType=models.ResourceType.Food, price=1.5, supply=8.0, demand=12.0),
        ],
        taxRate=0.1,
        tickComputed=100,
    )
    
    market2 = models.LocalMarketState(
        territoryId="sol::tile2",
        ownerEntityId="corp2",
        tileIds=["tile2"],
        listings=[
            models.ResourceListing(resourceType=models.ResourceType.Minerals, price=1.0, supply=20.0, demand=8.0),
            models.ResourceListing(resourceType=models.ResourceType.Food, price=2.0, supply=6.0, demand=10.0),
        ],
        taxRate=0.05,
        tickComputed=100,
    )
    
    # Compute global market
    data = market_logic.compute_global_market([market1, market2], "sol", 100)
    
    assert data["systemId"] == "sol"
    assert data["tick"] == 100
    assert data["marketCount"] == 2
    
    # Should have listings for all TRADABLE_RESOURCES
    assert len(data["listings"]) == len(market_logic.TRADABLE_RESOURCES)
    
    # Check aggregation
    # Minerals: (2.0*10 + 1.0*20) / (10+20) = 40/30 = 1.333...
    # Food: (1.5*8 + 2.0*6) / (8+6) = 24/14 = 1.714...
    minerals_listing = [l for l in data["listings"] if l.resourceType == models.ResourceType.Minerals][0]
    food_listing = [l for l in data["listings"] if l.resourceType == models.ResourceType.Food][0]
    
    assert abs(minerals_listing.price - (40.0/30.0)) < 0.01, f"Expected ~1.33, got {minerals_listing.price}"
    assert minerals_listing.supply == 30.0, f"Expected supply 30, got {minerals_listing.supply}"
    assert minerals_listing.demand == 13.0, f"Expected demand 13, got {minerals_listing.demand}"
    
    assert abs(food_listing.price - (24.0/14.0)) < 0.01, f"Expected ~1.71, got {food_listing.price}"
    assert food_listing.supply == 14.0, f"Expected supply 14, got {food_listing.supply}"
    assert food_listing.demand == 22.0, f"Expected demand 22, got {food_listing.demand}"
    
    print(f"✓ compute_global_market aggregates correctly: Minerals={minerals_listing.price:.2f}, Food={food_listing.price:.2f}")

def test_compute_global_market_empty():
    """Test aggregation with no local markets."""
    data = market_logic.compute_global_market([], "sol", 100)
    
    assert data["systemId"] == "sol"
    assert data["tick"] == 100
    assert data["marketCount"] == 0
    assert len(data["listings"]) == len(market_logic.TRADABLE_RESOURCES)
    
    # All prices should default to 1.0 with 0 supply/demand
    for listing in data["listings"]:
        assert listing.price == 1.0, f"{listing.resourceType.name} price should be 1.0"
        assert listing.supply == 0.0, f"{listing.resourceType.name} supply should be 0.0"
        assert listing.demand == 0.0, f"{listing.resourceType.name} demand should be 0.0"
    
    print("✓ compute_global_market handles empty markets correctly")

def test_global_market_roundtrip():
    """Test that GlobalMarketState can be created from compute_global_market output."""
    market1 = models.LocalMarketState(
        territoryId="sol::tile1",
        ownerEntityId="corp1",
        tileIds=["tile1"],
        listings=[
            models.ResourceListing(resourceType=models.ResourceType.Iron, price=3.0, supply=15.0, demand=10.0),
        ],
    )
    
    data = market_logic.compute_global_market([market1], "sol", 50)
    global_state = models.GlobalMarketState.model_validate(data)
    
    assert global_state.systemId == "sol"
    assert global_state.tick == 50
    assert len(global_state.listings) > 0
    
    # Verify Iron is in listings
    iron_listings = [l for l in global_state.listings if l.resourceType == models.ResourceType.Iron]
    assert len(iron_listings) == 1, "Iron should be in global market"
    assert iron_listings[0].supply == 15.0
    assert iron_listings[0].demand == 10.0
    
    print("✓ GlobalMarketState round-trip works")

if __name__ == "__main__":
    test_global_market_state_model()
    test_compute_global_market_aggregation()
    test_compute_global_market_empty()
    test_global_market_roundtrip()
    print("\n✅ All Phase 9.5 M2 global market tests passed!")
