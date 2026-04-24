"""
Assertion script — p85-agents
Runs all stable agent logic/models/scenarios tests (excludes benchmark LLM and behavior/noise).
"""
import subprocess
import sys
import os


def test_p85_agents_suite():
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sim_core = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    files = [
        os.path.join(tests_dir, "test_phase85_agent_logic.py"),
        os.path.join(tests_dir, "test_phase85_agent_models.py"),
        os.path.join(tests_dir, "test_phase85_agent_scenarios.py"),
        os.path.join(tests_dir, "test_phase85_agent_behavior.py"),
        os.path.join(tests_dir, "test_phase85_agent_llm.py"),
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
