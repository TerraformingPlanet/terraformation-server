"""
test_phase11_spaceport.py — Spaceport building prerequisite for space travel.

Tests couverts :
    T01 — Corp avec Spaceport dans le système source → initiate_travel réussit
    T02 — Corp sans Spaceport dans le système source → ValueError
    T03 — faction_id="" → initiate_travel réussit sans Spaceport (rétro-compat)

Pas de Docker, pas de réseau. Durée < 2 s.
"""
import sys
import importlib.util
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_SIM = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel: str):
    full_name = f"terraformation_sim.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    p = _SIM / rel
    spec = importlib.util.spec_from_file_location(full_name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load dependencies in order
_load("models", "models.py")

try:
    import noise as _noise_mod  # noqa: F401
except ImportError:
    import pytest
    pytest.skip("noise package not installed — skipping Phase 11 spaceport tests", allow_module_level=True)

if str(_SIM.parent) not in sys.path:
    sys.path.insert(0, str(_SIM.parent))
import terraformation_sim.logic  # noqa: F401  — logic.py split into logic/ package
_load("persistence", "persistence.py")
_load("runtime", "runtime.py")

import pytest
from terraformation_sim.runtime import InMemorySimulationRuntime
from terraformation_sim.models import (
    BuildingData,
    BuildingType,
    CorporationData,
    RouteStatus,
    SolarSystemState,
    StellarRoute,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime() -> InMemorySimulationRuntime:
    return InMemorySimulationRuntime(tick_interval_seconds=5.0, auto_resume=False)


def _setup_galaxy(rt: InMemorySimulationRuntime):
    """Insert two solar systems and one Known stellar route into the runtime."""
    sol_id = "sys-sol"
    kep_id = "sys-kepler"
    body_sol = "body-earth"
    body_kep = "body-kepler-prime"

    sol = SolarSystemState(systemId=sol_id, name="Sol", bodyIds=[body_sol])
    kep = SolarSystemState(systemId=kep_id, name="Kepler-442", bodyIds=[body_kep])
    rt._solar_systems[sol_id] = sol
    rt._solar_systems[kep_id] = kep

    route_id = "route-sol-kep"
    route = StellarRoute(
        routeId=route_id,
        fromSystemId=sol_id,
        toSystemId=kep_id,
        distanceLy=1.0,
        status=RouteStatus.Known,
        travelTimeModifier=1.0,
    )
    rt._stellar_routes[route_id] = route

    return sol_id, kep_id, body_sol, route_id


def _add_corp_with_spaceport(rt: InMemorySimulationRuntime, body_id: str) -> str:
    """Register a corp with a Spaceport on the given body. Returns corp_id."""
    corp_id = str(uuid4())
    corp = CorporationData(id=corp_id, name="TestCorp")
    building = BuildingData(
        buildingId=str(uuid4()),
        buildingType=BuildingType.Spaceport,
        bodyId=body_id,
        ownerCorpId=corp_id,
    )
    corp.buildings.append(building)
    rt._corporations[corp_id] = corp
    return corp_id


def _add_corp_without_spaceport(rt: InMemorySimulationRuntime) -> str:
    """Register a corp with no buildings. Returns corp_id."""
    corp_id = str(uuid4())
    rt._corporations[corp_id] = CorporationData(id=corp_id, name="NoBuildingCorp")
    return corp_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_T01_spaceport_present_travel_succeeds():
    """T01 — Corp with Spaceport in source system → initiate_travel succeeds."""
    rt = _make_runtime()
    sol_id, kep_id, body_sol, route_id = _setup_galaxy(rt)
    corp_id = _add_corp_with_spaceport(rt, body_sol)

    travel = rt.initiate_travel(
        faction_id=corp_id,
        route_id=route_id,
        from_system_id=sol_id,
        to_system_id=kep_id,
    )

    assert travel.travelId != ""
    assert travel.factionId == corp_id
    assert travel.fromSystemId == sol_id
    assert travel.toSystemId == kep_id


def test_T02_no_spaceport_raises_value_error():
    """T02 — Corp without Spaceport in source system → ValueError."""
    rt = _make_runtime()
    sol_id, kep_id, _body_sol, route_id = _setup_galaxy(rt)
    corp_id = _add_corp_without_spaceport(rt)

    with pytest.raises(ValueError, match="Spaceport"):
        rt.initiate_travel(
            faction_id=corp_id,
            route_id=route_id,
            from_system_id=sol_id,
            to_system_id=kep_id,
        )


def test_T03_empty_faction_id_bypasses_spaceport_check():
    """T03 — faction_id="" → travel succeeds without Spaceport (backward compat)."""
    rt = _make_runtime()
    sol_id, kep_id, _body_sol, route_id = _setup_galaxy(rt)

    travel = rt.initiate_travel(
        faction_id="",
        route_id=route_id,
        from_system_id=sol_id,
        to_system_id=kep_id,
    )

    assert travel.travelId != ""
    assert travel.factionId == ""
