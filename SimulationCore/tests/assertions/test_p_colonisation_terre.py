"""
Assertion script — p-colonisation-terre
Validates Phase Colonisation Initiale Terre exit criteria.
"""
import subprocess
import sys
import os


def test_phase_colonisation_suite():
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    test_file = os.path.join(tests_dir, "test_phase_earth_colonization.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = sim_core
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "--tb=short", "-v"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
