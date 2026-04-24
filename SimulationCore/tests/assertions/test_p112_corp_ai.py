"""
Assertion script — p112-corp-ai
Runs corp FSM + world agent tests.
"""
import subprocess
import sys
import os


def test_p112_corp_ai_suite():
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    files = [
        os.path.join(tests_dir, "test_phase111_world_agent.py"),
        os.path.join(tests_dir, "test_phase112_corp_fsm.py"),
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
