"""
Assertion script — p94-prices
Validates the pricing system (Phase 9.4).
"""
import pytest

# ── imports nécessaires à la phase ────────────────────────────────────────────
# from terraformation_sim.models import ...


# ── fixtures ──────────────────────────────────────────────────────────────────

# @pytest.fixture
# def pricing_state():
#     """Provide a pricing state for testing."""
#     ...


# ── tests des critères de sortie ──────────────────────────────────────────────

def test_p94_prices_suite():
    import subprocess, sys, os
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = sim_core
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         os.path.join(tests_dir, "test_phase94_market.py"),
         "--tb=short", "-q"],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr