"""
test_phase11_persistence.py — Region mutations hydration from SavedState.

Tests couverts :
    T01 — _hydrate_from_saved() avec cell_mutations peuplé → _region_mutations correct
    T02 — JSON malformé dans cell_mutations → ignoré silencieusement
    T03 — bootstrap() appelle clear_cell_mutations() sur le repo

Pas de Docker, pas de réseau. Durée < 2 s.
"""
import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, call

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
    pytest.skip(
        "noise package not installed — skipping Phase 11 persistence tests",
        allow_module_level=True,
    )

if str(_SIM.parent) not in sys.path:
    sys.path.insert(0, str(_SIM.parent))
import terraformation_sim.logic  # noqa: F401  — logic.py split into logic/ package
_persistence = _load("persistence", "persistence.py")
_load("runtime", "runtime.py")

from terraformation_sim.runtime import InMemorySimulationRuntime
from terraformation_sim.persistence import CellMutation, InMemoryRepository, SavedState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime() -> InMemorySimulationRuntime:
    return InMemorySimulationRuntime(tick_interval_seconds=5.0, auto_resume=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_T01_hydrate_restores_region_mutations():
    """T01 — _hydrate_from_saved() populates _region_mutations from cell_mutations."""
    rt = _make_runtime()

    saved = SavedState(
        has_region=False,
        cell_mutations={
            "0.470,0.180": [
                CellMutation(cell_q=3, cell_r=-2, cell_json=json.dumps({"wd": 0.15, "td": -1.5})),
                CellMutation(cell_q=5, cell_r=0, cell_json=json.dumps({"wd": 0.0, "td": 2.0})),
            ],
            "1.000,2.000": [
                CellMutation(cell_q=0, cell_r=0, cell_json=json.dumps({"wd": 0.05, "td": 0.5})),
            ],
        },
    )

    rt._hydrate_from_saved(saved)

    assert "0.470,0.180" in rt._region_mutations
    assert rt._region_mutations["0.470,0.180"][(3, -2)] == (0.15, -1.5)
    assert rt._region_mutations["0.470,0.180"][(5, 0)] == (0.0, 2.0)
    assert rt._region_mutations["1.000,2.000"][(0, 0)] == (0.05, 0.5)


def test_T02_hydrate_ignores_malformed_cell_json():
    """T02 — Malformed cell_json entries are silently skipped."""
    rt = _make_runtime()

    saved = SavedState(
        has_region=False,
        cell_mutations={
            "0.470,0.180": [
                CellMutation(cell_q=1, cell_r=1, cell_json="NOT_JSON"),
                CellMutation(cell_q=2, cell_r=2, cell_json=json.dumps({"wd": 0.1, "td": 0.2})),
            ],
        },
    )

    rt._hydrate_from_saved(saved)

    # Only the valid entry should be present
    region = rt._region_mutations.get("0.470,0.180", {})
    assert (1, 1) not in region
    assert region.get((2, 2)) == (0.1, 0.2)


def test_T03_bootstrap_calls_clear_cell_mutations():
    """T03 — bootstrap() wipes _region_mutations and calls clear_cell_mutations()."""
    mock_repo = MagicMock(spec=InMemoryRepository)
    mock_repo.load.return_value = SavedState()
    rt = InMemorySimulationRuntime(
        tick_interval_seconds=5.0, auto_resume=False, repository=mock_repo
    )

    # Pre-populate to verify wipe
    rt._region_mutations = {"0.470,0.180": {(1, 1): (0.5, 0.5)}}

    rt.bootstrap()

    assert rt._region_mutations == {}
    mock_repo.clear_cell_mutations.assert_called_once()
