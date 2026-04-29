"""
Assertion script — p115-ecology
Validates the ecology system (Phase 11.5).
"""
import pytest

# ── imports nécessaires à la phase ────────────────────────────────────────────
# from terraformation_sim.models import ...


# ── fixtures ──────────────────────────────────────────────────────────────────

# @pytest.fixture
# def ecology_state():
#     """Provide an ecology state for testing."""
#     ...


# ── tests des critères de sortie ──────────────────────────────────────────────

def test_p115_ecology_suite():
    import subprocess, sys, os
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env = os.environ.copy()
    env["PYTHONPATH"] = sim_core
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         os.path.join(tests_dir, "test_phase115_ecology.py"),
         "--tb=short", "-q"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")