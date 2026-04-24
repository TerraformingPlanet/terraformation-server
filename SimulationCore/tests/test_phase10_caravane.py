"""
test_phase10_caravane.py — Phase 10 : Caravane colonisation.

Tests couverts :
    - Une expédition terrestre (Land) arrivant sur une tuile non revendiquée
      la revendique pour la corporation propriétaire de l'expédition.
    - La tuile est ajoutée à corp.claimedTiles avec une population initiale.
    - Une expédition spatiale (Space) n'effectue pas de colonisation.

Pas de Docker, pas de réseau. Durée < 2 s.
"""
import sys
import importlib.util
from pathlib import Path

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

# Runtime needs noise — skip if absent
try:
    import noise as _noise_mod  # noqa: F401
except ImportError:
    import pytest
    pytest.skip("noise package not installed — skipping Phase 10 caravane tests", allow_module_level=True)

if str(_SIM.parent) not in sys.path:
    sys.path.insert(0, str(_SIM.parent))
import terraformation_sim.logic  # noqa: F401  — logic.py split into logic/ package
_load("persistence", "persistence.py")
_load("runtime", "runtime.py")

import pytest
from terraformation_sim.runtime import InMemorySimulationRuntime
from terraformation_sim.models import (
    CorporationData,
    TradeRoute,
    TradeRouteType,
    TradeRouteActivityStatus,
    ExpeditionUnit,
    ExpeditionStatus,
    ClaimedTile,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runtime() -> InMemorySimulationRuntime:
    return InMemorySimulationRuntime(tick_interval_seconds=5.0, auto_resume=False)


def _add_corp(rt: InMemorySimulationRuntime, corp_id: str, body_id: str, tile_id: str) -> None:
    """Register a corporation and claim a single starting tile for it."""
    rt._corporations[corp_id] = CorporationData(id=corp_id, name="TestCorp")
    rt._tile_ownership.setdefault(body_id, {})[tile_id] = corp_id
    rt._corporations[corp_id].claimedTiles.append(
        ClaimedTile(bodyId=body_id, tileId=tile_id)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_land_expedition_colonises_unclaimed_tile():
    """
    A Land expedition that arrives on an unclaimed tile should claim it for
    the owning corporation and add it to corp.claimedTiles.
    """
    rt = _make_runtime()

    corp_id  = "corp-001"
    body_id  = "body-001"
    from_tid = "tile-A"
    to_tid   = "tile-B"   # unclaimed

    _add_corp(rt, corp_id, body_id, from_tid)

    # Create an expedition that is 1 tick away from arrival
    exp_id = "exp-001"
    rt._expeditions[exp_id] = ExpeditionUnit(
        id=exp_id,
        ownerCorpId=corp_id,
        fromPortTileId=from_tid,
        toPortTileId=to_tid,
        bodyId=body_id,
        routeType=TradeRouteType.Land,
        ticksRemaining=1,
        totalTicks=5,
        status=ExpeditionStatus.InTransit,
    )

    # Patch the RNG to never fail or delay
    rt._expedition_rng.random = lambda: 0.99  # above all thresholds

    # Advance one tick (inside the lock because _advance_tick_locked requires it)
    with rt._lock:
        rt._process_expedition_tick_locked()

    exp = rt._expeditions[exp_id]
    assert exp.status == ExpeditionStatus.Success, f"Expected Success, got {exp.status}"

    # tile-B should now be claimed
    body_ownership = rt._tile_ownership.get(body_id, {})
    assert to_tid in body_ownership, "tile-B should be claimed after Land expedition arrives"
    assert body_ownership[to_tid] == corp_id, "tile-B should belong to corp-001"

    # corp.claimedTiles should include the new tile
    corp = rt._corporations[corp_id]
    claimed_ids = {t.tileId for t in corp.claimedTiles}
    assert to_tid in claimed_ids, "corp.claimedTiles should include tile-B"


def test_land_expedition_does_not_steal_already_claimed_tile():
    """
    A Land expedition arriving on an already-claimed tile should NOT overwrite
    the existing ownership.
    """
    rt = _make_runtime()

    attacker_id = "corp-attacker"
    defender_id = "corp-defender"
    body_id     = "body-001"
    from_tid    = "tile-A"
    to_tid      = "tile-B"

    _add_corp(rt, attacker_id, body_id, from_tid)
    _add_corp(rt, defender_id, body_id, to_tid)  # tile-B already owned by defender

    exp_id = "exp-002"
    rt._expeditions[exp_id] = ExpeditionUnit(
        id=exp_id,
        ownerCorpId=attacker_id,
        fromPortTileId=from_tid,
        toPortTileId=to_tid,
        bodyId=body_id,
        routeType=TradeRouteType.Land,
        ticksRemaining=1,
        totalTicks=5,
        status=ExpeditionStatus.InTransit,
    )
    rt._expedition_rng.random = lambda: 0.99

    with rt._lock:
        rt._process_expedition_tick_locked()

    body_ownership = rt._tile_ownership.get(body_id, {})
    assert body_ownership[to_tid] == defender_id, "Existing ownership must not be overwritten"


def test_space_expedition_does_not_colonise():
    """
    A Space expedition should NOT trigger tile colonisation even when it arrives.
    """
    rt = _make_runtime()

    corp_id  = "corp-space"
    body_id  = "body-space"
    from_tid = "tile-X"
    to_tid   = "tile-Y"

    _add_corp(rt, corp_id, body_id, from_tid)

    exp_id = "exp-space"
    rt._expeditions[exp_id] = ExpeditionUnit(
        id=exp_id,
        ownerCorpId=corp_id,
        fromPortTileId=from_tid,
        toPortTileId=to_tid,
        bodyId=body_id,
        routeType=TradeRouteType.Orbital,
        ticksRemaining=1,
        totalTicks=10,
        status=ExpeditionStatus.InTransit,
    )
    rt._expedition_rng.random = lambda: 0.99

    with rt._lock:
        rt._process_expedition_tick_locked()

    body_ownership = rt._tile_ownership.get(body_id, {})
    assert to_tid not in body_ownership, "Space expedition must not claim tiles"
