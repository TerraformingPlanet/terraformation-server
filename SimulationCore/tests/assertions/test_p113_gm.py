"""
Assertion script — p113-gm
Validates the game master system (Phase 11.3).
"""
import pytest

# ── imports nécessaires à la phase ────────────────────────────────────────────
# from terraformation_sim.models import ...


# ── fixtures ──────────────────────────────────────────────────────────────────

# @pytest.fixture
# def gm_state():
#     """Provide a GM state for testing."""
#     ...


# ── tests des critères de sortie ──────────────────────────────────────────────

def test_p113_gm_suite():
    import subprocess, sys, os
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = sim_core
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         os.path.join(tests_dir, "test_phase113_gm.py"),
         "--tb=short", "-q"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")