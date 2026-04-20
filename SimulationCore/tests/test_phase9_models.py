"""
Tests Phase 9.1 — Modèles routes commerciales & expéditions.

Chargement direct de models.py via importlib pour éviter les dépendances
h3 / noise du package __init__.py. Tests autonomes, sans Docker, sans DB.
"""
import importlib.util
import json
import sys
from pathlib import Path

# ── Chargement direct de models.py (bypass __init__.py) ───────────────────────
_models_path = Path(__file__).parent.parent / "terraformation_sim" / "models.py"
_spec = importlib.util.spec_from_file_location("terraformation_sim.models", _models_path)
_models = importlib.util.module_from_spec(_spec)
sys.modules["terraformation_sim.models"] = _models
_spec.loader.exec_module(_models)

# Raccourcis
BuildingType            = _models.BuildingType
ResourceType            = _models.ResourceType
BUILDING_CONFIGS        = _models.BUILDING_CONFIGS
SimulationEventType     = _models.SimulationEventType
TradeRouteType          = _models.TradeRouteType
TradeRouteActivityStatus = _models.TradeRouteActivityStatus
ExpeditionStatus        = _models.ExpeditionStatus
TradeRoute              = _models.TradeRoute
ExpeditionUnit          = _models.ExpeditionUnit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _roundtrip(model_instance):
    """Sérialise en JSON puis désérialise dans le même type — vérifie la compatibilité Pydantic."""
    cls = type(model_instance)
    raw = model_instance.model_dump_json()
    restored = cls.model_validate_json(raw)
    return restored


def ok(label: str):
    print(f"  ✓ {label}")


def fail(label: str, detail: str):
    print(f"  ✗ {label}: {detail}")
    sys.exit(1)


# ── Tests BuildingType ─────────────────────────────────────────────────────────

def test_building_type_extended():
    expected = {0: "Mine", 1: "Farm", 2: "EnergyPlant", 3: "Research",
                4: "Road", 5: "SeaPort", 6: "Spaceport"}
    for val, name in expected.items():
        if BuildingType(val).name != name:
            fail("BuildingType", f"BuildingType({val}) → {BuildingType(val).name} ≠ {name}")
    ok("BuildingType values (0..6 correct)")


def test_building_configs_has_infrastructure():
    for bt in (BuildingType.Road, BuildingType.SeaPort, BuildingType.Spaceport):
        if bt not in BUILDING_CONFIGS:
            fail("BUILDING_CONFIGS", f"Missing entry for {bt}")
        if BUILDING_CONFIGS[bt] != {}:
            fail("BUILDING_CONFIGS", f"{bt} should produce nothing (empty dict)")
    ok("BUILDING_CONFIGS infrastructure entries exist and are empty")


# ── Tests EventType ────────────────────────────────────────────────────────────

def test_event_type_phase9():
    expected = {
        12: "ExpeditionLost",
        13: "ExpeditionDelayed",
        14: "TradeRouteEstablished",
    }
    for val, name in expected.items():
        if SimulationEventType(val).name != name:
            fail("SimulationEventType", f"SimulationEventType({val}) → {SimulationEventType(val).name} ≠ {name}")
    ok("SimulationEventType phase 9 entries (12, 13, 14 correct)")


# ── Tests TradeRouteType ───────────────────────────────────────────────────────

def test_trade_route_type_values():
    assert TradeRouteType.Land.value == 0
    assert TradeRouteType.Maritime.value == 1
    assert TradeRouteType.Orbital.value == 2
    ok("TradeRouteType values (Land=0, Maritime=1, Orbital=2)")


# ── Tests TradeRouteActivityStatus ────────────────────────────────────────────

def test_trade_route_status_values():
    assert TradeRouteActivityStatus.Active.value == 0
    assert TradeRouteActivityStatus.Suspended.value == 1
    ok("TradeRouteActivityStatus values (Active=0, Suspended=1)")


# ── Tests ExpeditionStatus ────────────────────────────────────────────────────

def test_expedition_status_values():
    assert ExpeditionStatus.InTransit.value == 0
    assert ExpeditionStatus.Success.value == 1
    assert ExpeditionStatus.Failed.value == 2
    ok("ExpeditionStatus values (InTransit=0, Success=1, Failed=2)")


# ── Tests TradeRoute defaults & round-trip ─────────────────────────────────────

def test_trade_route_defaults():
    r = TradeRoute()
    assert r.routeType == TradeRouteType.Land
    assert r.status == TradeRouteActivityStatus.Active
    assert r.baseEfficiency == 1.0
    assert r.currentEfficiency == 1.0
    assert r.portMalusFrom == 0.0
    assert r.portMalusTo == 0.0
    assert r.pathTileIds == []
    assert r.knownByEntityIds == []
    ok("TradeRoute — valeurs par défaut correctes")


def test_trade_route_roundtrip():
    r = TradeRoute(
        id="route-001",
        routeType=TradeRouteType.Maritime,
        fromTileId="8928308280fffff",
        toTileId="8928308281fffff",
        bodyId="body-mars",
        pathTileIds=["8928308280fffff", "8928308283fffff", "8928308281fffff"],
        ownerCorpId="corp-alpha",
        knownByEntityIds=["corp-beta"],
        status=TradeRouteActivityStatus.Active,
        baseEfficiency=1.0,
        currentEfficiency=0.85,
        portMalusFrom=0.0,
        portMalusTo=0.1,
        tickCreated=42,
        knowledgeTransferTicks=3,
    )
    restored = _roundtrip(r)
    assert restored.id == r.id
    assert restored.routeType == TradeRouteType.Maritime
    assert restored.currentEfficiency == 0.85
    assert restored.toTileId == "8928308281fffff"
    assert len(restored.pathTileIds) == 3
    assert restored.knownByEntityIds == ["corp-beta"]
    ok("TradeRoute — JSON round-trip ✓")


# ── Tests ExpeditionUnit defaults & round-trip ────────────────────────────────

def test_expedition_unit_defaults():
    e = ExpeditionUnit()
    assert e.status == ExpeditionStatus.InTransit
    assert e.routeType == TradeRouteType.Land
    assert e.ticksRemaining == 0
    assert e.totalTicks == 0
    assert e.isPhantom is False
    assert e.pathTileIds == []
    ok("ExpeditionUnit — valeurs par défaut correctes")


def test_expedition_unit_roundtrip():
    e = ExpeditionUnit(
        id="exp-001",
        ownerCorpId="corp-alpha",
        fromPortTileId="8928308280fffff",
        toPortTileId="892830828dfffff",
        bodyId="body-mars",
        routeType=TradeRouteType.Land,
        ticksRemaining=5,
        totalTicks=10,
        pathTileIds=["a", "b", "c"],
        status=ExpeditionStatus.InTransit,
        isPhantom=False,
    )
    restored = _roundtrip(e)
    assert restored.id == e.id
    assert restored.ticksRemaining == 5
    assert restored.totalTicks == 10
    assert restored.routeType == TradeRouteType.Land
    assert restored.status == ExpeditionStatus.InTransit
    assert len(restored.pathTileIds) == 3
    ok("ExpeditionUnit — JSON round-trip ✓")


def test_expedition_unit_orbital_phantom():
    e = ExpeditionUnit(
        id="exp-orbital-001",
        routeType=TradeRouteType.Orbital,
        isPhantom=True,
        ticksRemaining=20,
        totalTicks=20,
    )
    restored = _roundtrip(e)
    assert restored.routeType == TradeRouteType.Orbital
    assert restored.isPhantom is True
    ok("ExpeditionUnit Orbital phantom — round-trip ✓")


# ── Vérification de la cohérence prérequis port/type de route ────────────────

def test_route_type_building_prerequisite_mapping():
    """Vérifie que Road/SeaPort/Spaceport correspondent aux valeurs attendues pour les prérequis."""
    mapping = {
        TradeRouteType.Land:     BuildingType.Road,
        TradeRouteType.Maritime: BuildingType.SeaPort,
        TradeRouteType.Orbital:  BuildingType.Spaceport,
    }
    for route_type, required_building in mapping.items():
        assert required_building in BUILDING_CONFIGS, \
            f"{required_building} manquant dans BUILDING_CONFIGS"
    ok("Mapping RouteType → BuildingType cohérent")


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_building_type_extended,
        test_building_configs_has_infrastructure,
        test_event_type_phase9,
        test_trade_route_type_values,
        test_trade_route_status_values,
        test_expedition_status_values,
        test_trade_route_defaults,
        test_trade_route_roundtrip,
        test_expedition_unit_defaults,
        test_expedition_unit_roundtrip,
        test_expedition_unit_orbital_phantom,
        test_route_type_building_prerequisite_mapping,
    ]

    print(f"\n=== Tests Phase 9.1 — models.py ({len(tests)} tests) ===\n")
    for t in tests:
        t()
    print(f"\n{'─'*50}")
    print(f"  PASS — {len(tests)}/{len(tests)} tests réussis")
