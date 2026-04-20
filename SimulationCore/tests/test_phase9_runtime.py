"""
Unit tests for Phase 9.2 — Expeditions & Trade Routes (Models only).

Pattern: Load models directly via importlib (skip __init__.py to avoid noise/h3).
Tests focus on model creation and JSON roundtrips.
Runtime integration tests should be done via Docker DedicatedServer.
"""
import importlib.util
import sys
from pathlib import Path

# ── Load models directly via importlib ────────────────────────────────────────

SIM_DIR = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel_path: str):
    p = SIM_DIR / rel_path
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")

# ── Extract classes ──────────────────────────────────────────────────────────

ExpeditionUnit = _models.ExpeditionUnit
ExpeditionStatus = _models.ExpeditionStatus
TradeRoute = _models.TradeRoute
TradeRouteType = _models.TradeRouteType
TradeRouteActivityStatus = _models.TradeRouteActivityStatus

# ── Tests ──────────────────────────────────────────────────────────────────────


def test_expedition_unit_defaults():
    """Test: ExpeditionUnit can be created with defaults."""
    exp = ExpeditionUnit(
        ownerCorpId="corp-a",
        fromPortTileId="tile-a",
        toPortTileId="tile-b",
        bodyId="earth",
        routeType=TradeRouteType.Orbital,
        ticksRemaining=10,
        totalTicks=10,
    )
    
    assert exp.ownerCorpId == "corp-a"
    assert exp.status == ExpeditionStatus.InTransit
    assert exp.isPhantom == False
    return True


def test_expedition_unit_roundtrip():
    """Test: ExpeditionUnit JSON roundtrip."""
    exp1 = ExpeditionUnit(
        id="exp-001",
        ownerCorpId="corp-a",
        fromPortTileId="tile-a",
        toPortTileId="tile-b",
        bodyId="earth",
        routeType=TradeRouteType.Maritime,
        ticksRemaining=15,
        totalTicks=20,
        pathTileIds=["tile-a", "tile-c", "tile-b"],
    )
    
    # Roundtrip through JSON
    json_str = exp1.model_dump_json()
    exp2 = ExpeditionUnit.model_validate_json(json_str)
    
    assert exp1 == exp2
    assert exp2.pathTileIds == ["tile-a", "tile-c", "tile-b"]
    return True


def test_trade_route_defaults():
    """Test: TradeRoute can be created with defaults."""
    route = TradeRoute(
        fromTileId="tile-a",
        toTileId="tile-b",
        bodyId="earth",
        ownerCorpId="corp-a",
        routeType=TradeRouteType.Land,
    )
    
    assert route.status == TradeRouteActivityStatus.Active
    assert route.baseEfficiency == 1.0
    assert route.currentEfficiency == 1.0
    return True


def test_trade_route_roundtrip():
    """Test: TradeRoute JSON roundtrip."""
    route1 = TradeRoute(
        id="route-001",
        fromTileId="tile-a",
        toTileId="tile-b",
        bodyId="earth",
        ownerCorpId="corp-a",
        routeType=TradeRouteType.Maritime,
        knownByEntityIds=["corp-a", "corp-b"],
        portMalusFrom=0.2,
        portMalusTo=0.0,
        currentEfficiency=0.8,
    )
    
    json_str = route1.model_dump_json()
    route2 = TradeRoute.model_validate_json(json_str)
    
    assert route1 == route2
    assert route2.knownByEntityIds == ["corp-a", "corp-b"]
    return True


def test_expedition_status_enum():
    """Test: ExpeditionStatus enum values."""
    assert ExpeditionStatus.InTransit.value == 0
    assert ExpeditionStatus.Success.value == 1
    assert ExpeditionStatus.Failed.value == 2
    return True


def test_trade_route_activity_status_enum():
    """Test: TradeRouteActivityStatus enum values."""
    assert TradeRouteActivityStatus.Active.value == 0
    assert TradeRouteActivityStatus.Suspended.value == 1
    return True


def test_trade_route_type_enum():
    """Test: TradeRouteType enum values."""
    assert TradeRouteType.Land.value == 0
    assert TradeRouteType.Maritime.value == 1
    assert TradeRouteType.Orbital.value == 2
    return True


def test_expedition_orbital_phantom():
    """Test: ExpeditionUnit orbital phantom route."""
    exp = ExpeditionUnit(
        ownerCorpId="corp-a",
        fromPortTileId="orbit-station-1",
        toPortTileId="orbit-station-2",
        bodyId="mars",
        routeType=TradeRouteType.Orbital,
        ticksRemaining=10,
        totalTicks=10,
        isPhantom=True,
    )
    
    assert exp.isPhantom == True
    
    # Roundtrip
    json_str = exp.model_dump_json()
    exp2 = ExpeditionUnit.model_validate_json(json_str)
    
    assert exp2.isPhantom == True
    return True


# ── Main runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("test_expedition_unit_defaults", test_expedition_unit_defaults),
        ("test_expedition_unit_roundtrip", test_expedition_unit_roundtrip),
        ("test_trade_route_defaults", test_trade_route_defaults),
        ("test_trade_route_roundtrip", test_trade_route_roundtrip),
        ("test_expedition_status_enum", test_expedition_status_enum),
        ("test_trade_route_activity_status_enum", test_trade_route_activity_status_enum),
        ("test_trade_route_type_enum", test_trade_route_type_enum),
        ("test_expedition_orbital_phantom", test_expedition_orbital_phantom),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            result = test_fn()
            if result:
                print(f"  ✓ {name}")
                passed += 1
            else:
                print(f"  ✗ {name}")
                failed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
    
    print("")
    print("─" * 50)
    print(f"  PASS — {passed}/{len(tests)} tests reussis")
    if failed > 0:
        print(f"  FAIL — {failed} tests echoues")
        sys.exit(1)
    else:
        print("  Tous les tests Phase 9.2 reussis.")
        sys.exit(0)
