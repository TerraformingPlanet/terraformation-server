"""
conftest.py — Shared pytest fixtures and marks for SimulationCore tests.

Marks:
    llm       — Tests that make real HTTP calls to the LLM backend.
                 Skipped automatically when LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
                 are not set in the environment.
    scenario  — Integration tests: LLM + InMemorySimulationRuntime (no Docker).
                 Same skip condition as llm.

Usage:
    pytest tests/                              # all tests (LLM skipped if env missing)
    pytest tests/ -m llm                       # LLM-only
    pytest tests/ -m "not llm and not scenario" # fast unit tests only
"""
import os
import pytest

# Try to load .env from repo root so tests can be run without manual `export`.
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on shell environment


def _llm_env_present() -> bool:
    return all(
        os.environ.get(k, "").strip()
        for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
    )


_LLM_SKIP = pytest.mark.skipif(
    not _llm_env_present(),
    reason="LLM_BASE_URL / LLM_API_KEY / LLM_MODEL not set — skipping LLM tests",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: requires live LLM backend (ai.prv.jerem.ovh)")
    config.addinivalue_line("markers", "scenario: integration scenario — LLM + in-memory runtime")


@pytest.fixture(scope="session")
def llm_env():
    """
    Session-scoped fixture: skip the test if LLM env vars are missing.
    Also returns the LLM configuration dict for convenience.
    """
    if not _llm_env_present():
        pytest.skip("LLM env vars not set")
    return {
        "base_url": os.environ["LLM_BASE_URL"].rstrip("/"),
        "api_key":  os.environ["LLM_API_KEY"],
        "model":    os.environ["LLM_MODEL"],
    }


@pytest.fixture(scope="session")
def fast_model(llm_env):
    """
    Returns an llm_env dict overridden with the Always-On 4B model.
    Use in LLM tests to keep latency low without touching production LLM_MODEL.
    """
    return {**llm_env, "model": "gemma-4-E4B-it-Q5_K_M"}
