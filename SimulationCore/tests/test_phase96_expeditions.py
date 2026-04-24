"""
Unit tests for Phase 9.6 — cargo field on ExpeditionUnit.

Pattern: importlib for models only (avoids h3/noise).
Runtime integration (cargo delivery) tested via manual runtime instantiation
only when h3 is importable (skipped otherwise).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

SIM_DIR = Path(__file__).parent.parent / "terraformation_sim"


def _load(name: str, rel_path: str):
    p = SIM_DIR / rel_path
    spec = importlib.util.spec_from_file_location(f"terraformation_sim.{name}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"terraformation_sim.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load("models", "models.py")

ExpeditionUnit = _models.ExpeditionUnit
ExpeditionStatus = _models.ExpeditionStatus
TradeRoute = _models.TradeRoute
TradeRouteType = _models.TradeRouteType
TradeRouteActivityStatus = _models.TradeRouteActivityStatus


# ── Check h3 availability ──────────────────────────────────────────────────────

def _h3_available() -> bool:
    try:
        import h3  # noqa: F401
        return True
    except ImportError:
        return False


_skip_runtime = pytest.mark.skipif(not _h3_available(), reason="h3 not available — skip runtime tests")


# ── Model-level tests (no h3 needed) ──────────────────────────────────────────

def test_expedition_unit_cargo_roundtrip():
    """ExpeditionUnit with cargo survives JSON roundtrip."""
    exp = ExpeditionUnit(
        id="e1",
        ownerCorpId="corp-0",
        fromPortTileId="tile-a",
        toPortTileId="tile-b",
        bodyId="body-0",
        routeType=TradeRouteType.Land,
        ticksRemaining=10,
        totalTicks=10,
        cargo={"Food": 5.0, "Minerals": 3.0},
    )
    data = exp.model_dump()
    restored = ExpeditionUnit(**data)
    assert restored.cargo == {"Food": 5.0, "Minerals": 3.0}
    assert restored.routeType == TradeRouteType.Land


def test_expedition_unit_cargo_default_empty():
    """cargo defaults to empty dict."""
    exp = ExpeditionUnit(
        id="e2",
        ownerCorpId="corp-0",
        fromPortTileId="tile-a",
        toPortTileId="tile-b",
        bodyId="body-0",
        routeType=TradeRouteType.Orbital,
        ticksRemaining=5,
        totalTicks=5,
    )
    assert exp.cargo == {}


def test_expedition_status_default():
    """status defaults to InTransit."""
    exp = ExpeditionUnit(
        id="e3",
        ownerCorpId="corp-0",
        fromPortTileId="tile-a",
        toPortTileId="tile-b",
        bodyId="body-0",
        routeType=TradeRouteType.Maritime,
        ticksRemaining=7,
        totalTicks=7,
    )
    assert exp.status == ExpeditionStatus.InTransit


def test_trade_route_roundtrip():
    """TradeRoute survives JSON roundtrip with default status=Active."""
    route = TradeRoute(
        id="r1",
        routeType=TradeRouteType.Land,
        fromTileId="tile-a",
        toTileId="tile-b",
        bodyId="body-0",
        pathTileIds=["tile-a", "tile-b"],
        ownerCorpId="corp-0",
        tickCreated=0,
    )
    data = route.model_dump()
    restored = TradeRoute(**data)
    assert restored.id == "r1"
    assert restored.status == TradeRouteActivityStatus.Active


# ── Runtime integration tests (require h3 + noise) ────────────────────────────

def test_runtime_trade_route_and_expedition():
    """Full: create route, launch expedition, verify model state."""
    pytest.importorskip("noise", reason="noise not installed — skip runtime tests")

    # Late import — noise is available
    from terraformation_sim import InMemorySimulationRuntime, InMemoryRepository

    runtime = InMemorySimulationRuntime(repository=InMemoryRepository())

    # Bootstrap a corporation with 2 tiles
    from terraformation_sim import CorporationData, ClaimedTile as ClaimedTileR
    corp = CorporationData(id="corp-1", name="Test Corp", credits=10000.0)
    tile_a = ClaimedTileR(tileId="tile-a", bodyId="body-0", corpId="corp-1")
    tile_b = ClaimedTileR(tileId="tile-b", bodyId="body-0", corpId="corp-1")
    corp.claimedTiles = [tile_a, tile_b]
    runtime._corporations["corp-1"] = corp  # noqa: SLF001
    runtime._tile_ownership.setdefault("body-0", {})["tile-a"] = "corp-1"
    runtime._tile_ownership["body-0"]["tile-b"] = "corp-1"

    route = runtime.create_trade_route("corp-1", "body-0", "tile-a", "tile-b", 2)  # Orbital
    assert route.ownerCorpId == "corp-1"
    assert route.status == TradeRouteActivityStatus.Active

    exp = runtime.launch_expedition("corp-1", route.id, cargo={"Food": 10.0})
    assert exp.ownerCorpId == "corp-1"
    assert exp.cargo == {"Food": 10.0}
    assert exp.status == ExpeditionStatus.InTransit

    # list_expeditions filter
    all_exps = runtime.list_expeditions()
    assert any(e.id == exp.id for e in all_exps)
    corp_exps = runtime.list_expeditions("corp-1")
    assert all(e.ownerCorpId == "corp-1" for e in corp_exps)


def test_runtime_delete_trade_route():
    """Deleting a trade route removes it from the registry."""
    pytest.importorskip("noise", reason="noise not installed — skip runtime tests")

    from terraformation_sim import InMemorySimulationRuntime, InMemoryRepository, CorporationData, ClaimedTile as ClaimedTileR

    runtime = InMemorySimulationRuntime(repository=InMemoryRepository())
    corp = CorporationData(id="corp-2", name="Del Corp", credits=5000.0)
    tile_a = ClaimedTileR(tileId="tile-a", bodyId="body-1", corpId="corp-2")
    tile_b = ClaimedTileR(tileId="tile-b", bodyId="body-1", corpId="corp-2")
    corp.claimedTiles = [tile_a, tile_b]
    runtime._corporations["corp-2"] = corp
    runtime._tile_ownership.setdefault("body-1", {})["tile-a"] = "corp-2"
    runtime._tile_ownership["body-1"]["tile-b"] = "corp-2"

    route = runtime.create_trade_route("corp-2", "body-1", "tile-a", "tile-b", 2)
    runtime.delete_trade_route(route.id)
    assert runtime.get_trade_route(route.id) is None

    with pytest.raises(KeyError):
        runtime.delete_trade_route(route.id)
