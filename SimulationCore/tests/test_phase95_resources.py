"""
Test Phase 9.5 — Nouveaux ResourceType (Iron, Oxygen, Water, Tech).

Tests de round-trip JSON + vérification présence dans TRADABLE_RESOURCES.
"""
import json
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

# Load market.py
spec = importlib.util.spec_from_file_location("terraformation_sim.logic.market",
    _SIM / "logic" / "market.py")
market = importlib.util.module_from_spec(spec)
sys.modules["terraformation_sim.logic.market"] = market
spec.loader.exec_module(market)

def test_resource_type_values():
    """Vérifier que les nouvelles ressources existent avec les bonnes valeurs."""
    assert models.ResourceType.Minerals == 0
    assert models.ResourceType.Food == 1
    assert models.ResourceType.Energy == 2
    assert models.ResourceType.ResearchPoints == 3
    assert models.ResourceType.Waste == 4
    assert models.ResourceType.Iron == 5, f"Iron should be 5, got {models.ResourceType.Iron}"
    assert models.ResourceType.Oxygen == 6, f"Oxygen should be 6, got {models.ResourceType.Oxygen}"
    assert models.ResourceType.Water == 7, f"Water should be 7, got {models.ResourceType.Water}"
    assert models.ResourceType.Tech == 8, f"Tech should be 8, got {models.ResourceType.Tech}"
    print("✓ ResourceType values correct")

def test_tradable_resources_includes_new():
    """Vérifier que les 4 nouvelles ressources sont dans TRADABLE_RESOURCES."""
    tradable_names = {rt.name for rt in market.TRADABLE_RESOURCES}
    
    assert "Iron" in tradable_names, f"Iron not in TRADABLE_RESOURCES. Got: {tradable_names}"
    assert "Oxygen" in tradable_names, f"Oxygen not in TRADABLE_RESOURCES. Got: {tradable_names}"
    assert "Water" in tradable_names, f"Water not in TRADABLE_RESOURCES. Got: {tradable_names}"
    assert "Tech" in tradable_names, f"Tech not in TRADABLE_RESOURCES. Got: {tradable_names}"
    print(f"✓ All 4 new resources in TRADABLE_RESOURCES: {tradable_names}")

def test_resource_listing_roundtrip():
    """Tester que ResourceListing peut être sérialisé/désérialisé pour chaque ResourceType."""
    for resource_type in models.ResourceType:
        # Créer une listing
        listing = models.ResourceListing(
            resourceType=resource_type,
            price=1.5,
            supply=10.0,
            demand=8.0,
            priceVelocity=0.05,
            priceHistory=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        )
        
        # Sérialiser
        json_str = listing.model_dump_json()
        data = json.loads(json_str)
        assert data["resourceType"] == resource_type.value, f"ResourceType {resource_type.name} round-trip failed"
        
        # Désérialiser
        listing2 = models.ResourceListing.model_validate_json(json_str)
        assert listing2.resourceType == resource_type, f"ResourceType {resource_type.name} deserialize failed"
        assert listing2.price == 1.5
        assert listing2.supply == 10.0
        assert listing2.demand == 8.0
        assert listing2.priceVelocity == 0.05
        assert len(listing2.priceHistory) == 6
    
    print(f"✓ ResourceListing round-trip OK for all {len(list(models.ResourceType))} resource types")

def test_init_market_listings():
    """Vérifier que init_market_listings() crée une listing pour chaque TRADABLE_RESOURCE."""
    listings = market.init_market_listings()
    
    expected_count = len(market.TRADABLE_RESOURCES)
    assert len(listings) == expected_count, f"Expected {expected_count} listings, got {len(listings)}"
    
    # Vérifier que tous les types tradables sont présents
    listing_types = {l.resourceType for l in listings}
    tradable_types = set(market.TRADABLE_RESOURCES)
    assert listing_types == tradable_types, f"Listing types {listing_types} != TRADABLE_RESOURCES {tradable_types}"
    
    print(f"✓ init_market_listings() creates {len(listings)} listings for all TRADABLE_RESOURCES")

if __name__ == "__main__":
    test_resource_type_values()
    test_tradable_resources_includes_new()
    test_resource_listing_roundtrip()
    test_init_market_listings()
    print("\n✅ All Phase 9.5 M1 resource tests passed!")
