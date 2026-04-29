"""
Assertion script — p105-construction
Runs Phase 10.5 territory construction queue tests.
"""
import subprocess
import sys
import os


def test_p105_construction_suite():
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    files = [
        os.path.join(tests_dir, "test_phase105_construction.py"),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = sim_core
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "--tb=short", "-q"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
