"""
test_phase_sprint_db.py — Sprint DB: persistence complète des entités gameplay.

Tests couverts :
    T01 — register_corporation → SavedState → hydrate → corps + tile_ownership reconstruits
    T02 — claim_tile + hydrate → _tile_ownership reconstruit correctement
    T03 — propose_contract → SavedState → hydrate → contrat présent
    T04 — create_state + upsert_reputation → SavedState → hydrate → state + rep présents
    T05 — bootstrap_sol() appelle clear_X() pour les 9 entités (mock repo)

Pas de Docker, pas de réseau. Durée < 5 s.
"""
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, call

# ---------------------------------------------------------------------------
# Module loading helpers (identical pattern to test_phase11_spaceport.py)
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


_load("models", "models.py")

try:
    import noise as _noise_mod  # noqa: F401
except ImportError:
    import pytest
    pytest.skip(
        "noise package not installed — skipping Sprint DB tests",
        allow_module_level=True,
    )

if str(_SIM.parent) not in sys.path:
    sys.path.insert(0, str(_SIM.parent))
import terraformation_sim.logic  # noqa: F401  — logic.py split into logic/ package
_load("persistence", "persistence.py")
_load("runtime", "runtime.py")

import pytest
from terraformation_sim.runtime import InMemorySimulationRuntime
from terraformation_sim.persistence import InMemoryRepository, SavedState
from terraformation_sim.models import StateType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rt() -> InMemorySimulationRuntime:
    return InMemorySimulationRuntime(tick_interval_seconds=5.0, auto_resume=False)


def _snapshot_to_saved(rt: InMemorySimulationRuntime) -> SavedState:
    """Build a SavedState that mirrors what the repo would persist, using
    InMemoryRepository (no-ops) but manually injecting the JSON lists from
    the live runtime collections — simulates a round-trip without Postgres."""
    from terraformation_sim.models import CorporationData, ContractData, StateData

    saved = SavedState()
    saved.corporations_json = [c.model_dump_json() for c in rt._corporations.values()]
    saved.contracts_json = [c.model_dump_json() for c in rt._contracts.values()]
    saved.states_json = [s.model_dump_json() for s in rt._states.values()]
    saved.nationalizations_json = [n.model_dump_json() for n in rt._nationalizations.values()]
    saved.reputations_raw = list(
        (src, tgt, score) for (src, tgt), score in rt._reputations.items()
    )
    saved.trade_routes_json = [r.model_dump_json() for r in rt._trade_routes.values()]
    saved.expeditions_json = [e.model_dump_json() for e in rt._expeditions.values()]
    saved.construction_queues_json = [
        q.model_dump_json() for q in rt._construction_queues.values()
    ]
    saved.markets_json = [m.model_dump_json() for m in rt._markets.values()]
    return saved


def _hydrate_fresh(saved: SavedState) -> InMemorySimulationRuntime:
    """Create a fresh runtime and hydrate it from saved state."""
    rt2 = _make_rt()
    rt2._hydrate_from_saved(saved)
    return rt2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSprintDb:

    # ── T01 ─────────────────────────────────────────────────────────────────

    def test_T01_register_corporation_round_trip(self):
        """register_corporation → snapshot → hydrate → corp present in new runtime."""
        rt = _make_rt()
        corp = rt.register_corporation("Terracorp")
        corp_id = corp.id

        saved = _snapshot_to_saved(rt)
        assert len(saved.corporations_json) == 1

        rt2 = _hydrate_fresh(saved)
        assert corp_id in rt2._corporations
        assert rt2._corporations[corp_id].name == "Terracorp"

    # ── T02 ─────────────────────────────────────────────────────────────────

    def test_T02_claim_tile_ownership_reconstructed(self):
        """claim_tile → snapshot → hydrate → _tile_ownership rebuilt correctly."""
        rt = _make_rt()
        corp = rt.register_corporation("TileCorp")
        corp_id = corp.id

        # Manually insert a body and ownership (no full planet needed)
        rt._tile_ownership.setdefault("body-earth", {})
        # Use claim_tile directly after registering the body in tile_ownership dict
        # (claim_tile raises if body not registered — we bypass by direct dict write)
        from terraformation_sim.models import ClaimedTile
        from terraformation_sim.runtime import auto_init_tile_population
        tile = auto_init_tile_population(ClaimedTile(bodyId="body-earth", tileId="tile-001"))
        rt._corporations[corp_id].claimedTiles.append(tile)
        rt._tile_ownership["body-earth"]["tile-001"] = corp_id

        saved = _snapshot_to_saved(rt)
        rt2 = _hydrate_fresh(saved)

        assert "body-earth" in rt2._tile_ownership
        assert rt2._tile_ownership["body-earth"].get("tile-001") == corp_id

    # ── T03 ─────────────────────────────────────────────────────────────────

    def test_T03_propose_contract_round_trip(self):
        """propose_contract → snapshot → hydrate → contract present in new runtime."""
        rt = _make_rt()
        corp = rt.register_corporation("ContractCorp")
        contract = rt.propose_contract(
            proposer_id=corp.id,
            resource_type="Iron",
            resource_amount=100.0,
            reward_credits=500.0,
            visibility="Public",
        )
        contract_id = contract.id

        saved = _snapshot_to_saved(rt)
        assert len(saved.contracts_json) == 1

        rt2 = _hydrate_fresh(saved)
        assert contract_id in rt2._contracts
        assert rt2._contracts[contract_id].proposerId == corp.id

    # ── T04 ─────────────────────────────────────────────────────────────────

    def test_T04_state_and_reputation_round_trip(self):
        """create_state + upsert_reputation → snapshot → hydrate → both restored."""
        rt = _make_rt()
        corp = rt.register_corporation("StateCorp")

        state = rt.create_state(
            name="Republic",
            state_type=StateType.Capitalist,
            tile_ids=["tile-a", "tile-b"],
        )
        state_id = state.id

        # Manually set a reputation (normally set via _apply_reputation_event_locked)
        rt._reputations[(state_id, corp.id)] = 0.75

        saved = _snapshot_to_saved(rt)
        assert len(saved.states_json) == 1
        assert len(saved.reputations_raw) == 1

        rt2 = _hydrate_fresh(saved)
        assert state_id in rt2._states
        assert rt2._states[state_id].name == "Republic"
        assert rt2._reputations.get((state_id, corp.id)) == pytest.approx(0.75)

    # ── T05 ─────────────────────────────────────────────────────────────────

    def test_T05_bootstrap_sol_calls_all_clears(self):
        """bootstrap_sol() must call clear_X() on all 9 entity tables."""
        rt = _make_rt()

        mock_repo = MagicMock(spec_set=rt._repo)
        # Make load() return empty state so bootstrap doesn't choke
        mock_repo.load.return_value = SavedState()
        # Make save_world_state a no-op
        mock_repo.save_world_state.return_value = None
        mock_repo.save_body.return_value = None
        mock_repo.save_solar_system.return_value = None
        mock_repo.save_stellar_route.return_value = None
        mock_repo.delete_tile_mutations.return_value = None
        mock_repo.delete_body.return_value = None
        mock_repo.delete_solar_system.return_value = None
        mock_repo.delete_stellar_route.return_value = None
        mock_repo.delete_space_travel.return_value = None
        mock_repo.clear_cell_mutations.return_value = None
        mock_repo.clear_corporations.return_value = None
        mock_repo.clear_markets.return_value = None
        mock_repo.clear_contracts.return_value = None
        mock_repo.clear_states.return_value = None
        mock_repo.clear_reputations.return_value = None
        mock_repo.clear_nationalizations.return_value = None
        mock_repo.clear_construction_queues.return_value = None
        mock_repo.clear_trade_routes.return_value = None
        mock_repo.clear_expeditions.return_value = None

        rt._repo = mock_repo
        rt.bootstrap_sol()

        expected_clears = [
            "clear_cell_mutations",
            "clear_corporations",
            "clear_markets",
            "clear_contracts",
            "clear_states",
            "clear_reputations",
            "clear_nationalizations",
            "clear_construction_queues",
            "clear_trade_routes",
            "clear_expeditions",
        ]
        for method_name in expected_clears:
            getattr(mock_repo, method_name).assert_called_once(), (
                f"Expected {method_name}() to be called once by bootstrap_sol()"
            )
