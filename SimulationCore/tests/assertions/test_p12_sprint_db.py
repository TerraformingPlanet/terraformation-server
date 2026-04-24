"""
Assertion script — p12-sprint-db
Runs sprint DB round-trip tests + building level upgrade/downgrade tests.
"""
import subprocess
import sys
import os


def test_p12_sprint_db_suite():
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    files = [
        os.path.join(tests_dir, "test_phase_sprint_db.py"),
        os.path.join(tests_dir, "test_phase12_building_level.py"),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = sim_core
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "--tb=short", "-q"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
