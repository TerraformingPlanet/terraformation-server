"""
Assertion script — p96-employment
Runs employment, expeditions, and income tests.
"""
import subprocess
import sys
import os


def test_p96_employment_suite():
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    files = [
        os.path.join(tests_dir, "test_phase96_employment.py"),
        os.path.join(tests_dir, "test_phase96_expeditions.py"),
        os.path.join(tests_dir, "test_phase96_income.py"),
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
