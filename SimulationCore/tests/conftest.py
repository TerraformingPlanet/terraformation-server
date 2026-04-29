"""
conftest.py — Shared pytest fixtures and marks for SimulationCore tests.

Marks:
    llm            — Tests that make real HTTP calls to the LLM backend.
                     Skipped automatically when LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
                     are not set in the environment.
    scenario       — Integration tests: LLM + InMemorySimulationRuntime (no Docker).
                     Same skip condition as llm.
    llm_benchmark  — Multi-model comparison tests.
                     Set LLM_BENCHMARK_MODELS=gemma4,Qwen3.6,qwen3.5-sonnet-30b
                     (comma-separated) to choose which models to compare.
                     Defaults to gemma4 only when the env var is absent.

Usage:
    pytest tests/                                          # all tests (LLM skipped if env missing)
    pytest tests/ -m llm                                   # LLM-only
    pytest tests/ -m llm_benchmark                         # multi-model comparison
    pytest tests/ -m "not llm and not scenario"            # fast unit tests only
"""
import os
import json
import time
import logging
from datetime import date
from pathlib import Path
import pytest

_EXCLUSIONS_FILE = Path(__file__).parent / "benchmark_exclusions.json"


def _load_exclusions() -> set[str]:
    """Return the set of model IDs currently excluded from benchmarks."""
    if not _EXCLUSIONS_FILE.exists():
        return set()
    try:
        data = json.loads(_EXCLUSIONS_FILE.read_text(encoding="utf-8"))
        return {e["model"] for e in data.get("excluded", [])}
    except Exception:
        return set()


def _add_exclusion(model: str, reason: str, score: str) -> None:
    """Append a model to the exclusions file."""
    if _EXCLUSIONS_FILE.exists():
        data = json.loads(_EXCLUSIONS_FILE.read_text(encoding="utf-8"))
    else:
        data = {"_comment": "Modèles exclus automatiquement des benchmarks futurs.", "excluded": []}
    # Avoid duplicates
    if any(e["model"] == model for e in data["excluded"]):
        return
    data["excluded"].append({
        "model": model,
        "reason": reason,
        "excluded_on": str(date.today()),
        "score": score,
    })
    _EXCLUSIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.getLogger("conftest").warning(f"Model '{model}' auto-excluded from future benchmarks: {reason}")

# Try to load .env from repo root so tests can be run without manual `export`.
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=str(_env_path), override=True)
except ImportError:
    pass  # python-dotenv not installed — rely on shell environment


def _llm_env_present() -> bool:
    return all(
        os.environ.get(k, "").strip()
        for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
    )


def _llm_reachable() -> bool:
    """Return True only if LLM env vars are set AND the endpoint answers within 5s."""
    if not _llm_env_present():
        return False
    try:
        import httpx
        base_url = os.environ["LLM_BASE_URL"].rstrip("/")
        api_key  = os.environ.get("LLM_API_KEY", "")
        httpx.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5.0,
        ).raise_for_status()
        return True
    except Exception:
        return False


_LLM_SKIP = pytest.mark.skipif(
    not _llm_env_present(),
    reason="LLM_BASE_URL / LLM_API_KEY / LLM_MODEL not set — skipping LLM tests",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: requires live LLM backend (ai.prv.jerem.ovh)")
    config.addinivalue_line("markers", "scenario: integration scenario — LLM + in-memory runtime")
    config.addinivalue_line("markers", "llm_benchmark: multi-model comparison — set LLM_BENCHMARK_MODELS env var")


@pytest.fixture(scope="session")
def llm_env():
    """
    Session-scoped fixture: skip the test if LLM env vars are missing or endpoint unreachable.
    Also returns the LLM configuration dict for convenience.
    """
    if not _llm_env_present():
        pytest.skip("LLM env vars not set")
    if not _llm_reachable():
        pytest.skip("LLM endpoint unreachable — check Tailscale / VPN")
    return {
        "base_url": os.environ["LLM_BASE_URL"].rstrip("/"),
        "api_key":  os.environ["LLM_API_KEY"],
        "model":    os.environ["LLM_MODEL"],
    }


@pytest.fixture(scope="session")
def fast_model(llm_env):
    """
    Returns an llm_env dict overridden with the Always-On fast model.
    Uses LLM_MODEL_FAST env var, falls back to llm_env["model"].
    """
    model = os.environ.get("LLM_MODEL_FAST", "").strip() or llm_env["model"]
    return {**llm_env, "model": model}


@pytest.fixture(scope="session")
def deep_model(llm_env):
    """
    Returns an llm_env dict using the DEEP tier model (LLM_MODEL_DEEP env var).
    Falls back to qwen3.5-sonnet-30b then to LLM_MODEL.
    Use for tests requiring function calling or complex reasoning.
    """
    model = (
        os.environ.get("LLM_MODEL_DEEP", "").strip()
        or "qwen3.5-sonnet-30b"
    )
    return {**llm_env, "model": model}


# ── Multi-model benchmark ──────────────────────────────────────────────────────

def _benchmark_model_ids() -> list[str]:
    """
    Read LLM_BENCHMARK_MODELS env var (comma-separated model names).
    Filters out models listed in benchmark_exclusions.json.
    Fallback: gemma4 only.
    """
    raw = os.environ.get("LLM_BENCHMARK_MODELS", "").strip()
    candidates = [m.strip() for m in raw.split(",") if m.strip()] if raw else ["gemma4"]
    excluded = _load_exclusions()
    filtered = [m for m in candidates if m not in excluded]
    skipped = [m for m in candidates if m in excluded]
    if skipped:
        logging.getLogger("conftest").info(
            f"Benchmark: skipping excluded models: {', '.join(skipped)} "
            f"(see tests/benchmark_exclusions.json)"
        )
    return filtered if filtered else ["gemma4"]


_ALWAYS_ON_MODELS = {"gemma4", "bge-reranker", "nomic-embed-text-v2"}
_WARMUP_TIMEOUT_S = 180.0  # llama-swap model swap can take ~90s


def _direct_base_url() -> str | None:
    """
    Return LLM_DIRECT_BASE_URL if set — direct llama-swap, bypasses OpenWebUI proxy.
    OpenWebUI has its own timeout (~60s) that cuts off cold-start loads (~90s).
    Falls back to None (will use LLM_BASE_URL).
    """
    url = os.environ.get("LLM_DIRECT_BASE_URL", "").strip()
    return url.rstrip("/") if url else None


def _warmup_model(base_url: str, api_key: str, model: str) -> None:
    """
    Send a cheap request to force llama-swap to load the model.
    Always uses LLM_DIRECT_BASE_URL when available — bypasses OpenWebUI proxy
    which would cut off the connection before the ~90s cold-start completes.
    No-op for Always-On models.
    """
    if model in _ALWAYS_ON_MODELS:
        return
    import httpx
    import logging
    log = logging.getLogger("conftest.warmup")
    warmup_url = _direct_base_url() or base_url
    # llama-swap direct does not require auth, but sending the key is harmless
    log.info(f"Warming up model '{model}' via {warmup_url} (llama-swap swap may take ~90s)…")
    t0 = time.perf_counter()
    try:
        resp = httpx.post(
            f"{warmup_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "temperature": 0.0,
            },
            timeout=_WARMUP_TIMEOUT_S,
        )
        resp.raise_for_status()
        log.info(f"Warm-up '{model}' done in {time.perf_counter() - t0:.1f}s")
    except Exception as exc:
        log.warning(f"Warm-up '{model}' failed after {time.perf_counter() - t0:.1f}s: {exc}")


@pytest.fixture(
    scope="session",
    params=_benchmark_model_ids(),
    ids=_benchmark_model_ids(),
)
def benchmark_model(request, llm_env):
    """
    Parametrized fixture: one test run per model listed in LLM_BENCHMARK_MODELS.
    Performs a warm-up request to trigger llama-swap model loading before timed tests.
    Each value is a dict with base_url / api_key / model / _name.
    """
    model_name = request.param
    # Use direct llama-swap URL for benchmark calls too — bypasses OpenWebUI proxy timeout
    direct = _direct_base_url()
    effective_base_url = direct if direct else llm_env["base_url"]
    _warmup_model(effective_base_url, llm_env["api_key"], model_name)
    return {
        **llm_env,
        "base_url": effective_base_url,
        "model": model_name,
        "_name": model_name,
    }


# ── Benchmark result collector ─────────────────────────────────────────────────

class _BenchmarkStore:
    """Thread-safe store for (model, scenario) → {passed, latency_s, max_latency_s, detail}."""
    ABORT_THRESHOLD = 4  # nb d'échecs avant d'abandonner le modèle

    def __init__(self):
        self._data: dict[tuple[str, str], dict] = {}
        self._fail_counts: dict[str, int] = {}
        self._aborted: set[str] = set()

    def is_aborted(self, model: str) -> bool:
        return model in self._aborted

    def record(
        self,
        model: str,
        scenario: str,
        passed: bool,
        latency_s: float,
        detail: str = "",
        max_latency_s: float | None = None,
    ):
        # Latency exceeded counts as a failure for the abort counter
        overtime = max_latency_s is not None and latency_s > max_latency_s
        is_failure = not passed or overtime
        if is_failure:
            self._fail_counts[model] = self._fail_counts.get(model, 0) + 1
            if self._fail_counts[model] >= self.ABORT_THRESHOLD:
                self._aborted.add(model)
        self._data[(model, scenario)] = {
            "passed":       passed,
            "latency_s":    latency_s,
            "max_latency_s": max_latency_s,
            "detail":       detail,
        }

    def all_models(self) -> list[str]:
        seen, out = set(), []
        for (m, _) in self._data:
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out

    def all_scenarios(self) -> list[str]:
        seen, out = set(), []
        for (_, s) in self._data:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def get(self, model: str, scenario: str) -> dict | None:
        return self._data.get((model, scenario))


@pytest.fixture(scope="session")
def benchmark_store() -> _BenchmarkStore:
    return _BenchmarkStore()


# Make the store accessible from the terminal summary hook via config
def pytest_sessionstart(session):
    session.config._benchmark_store_instance = None


@pytest.fixture(scope="session", autouse=True)
def _register_store(request):
    """Auto-use: registers the BenchmarkStore on config so the summary hook can find it."""
    store = request.getfixturevalue("benchmark_store")
    request.config._benchmark_store_instance = store


@pytest.fixture
def bench_recorder(benchmark_model, benchmark_store):
    """
    Helper returned as a callable:
      `record(scenario, passed, latency_s, detail='', max_latency_s=None)`
    Automatically tags with the current model name.
    If max_latency_s is provided and latency_s exceeds it, the result is marked
    as a latency failure (⚠️) in the summary table even if the content passed.
    Skips the test immediately if the model already reached ABORT_THRESHOLD failures.
    """
    model_name = benchmark_model["_name"]

    # Early abort: skip test before even calling the LLM
    if benchmark_store.is_aborted(model_name):
        fails = benchmark_store._fail_counts.get(model_name, 0)
        pytest.skip(
            f"⛔ '{model_name}' abandonné après {fails} échec(s) "
            f"(seuil={benchmark_store.ABORT_THRESHOLD})"
        )

    def _record(
        scenario: str,
        passed: bool,
        latency_s: float,
        detail: str = "",
        max_latency_s: float | None = None,
    ):
        benchmark_store.record(model_name, scenario, passed, latency_s, detail, max_latency_s)

    return _record


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print the multi-model benchmark comparison table after all tests.
    Auto-excludes models scoring 0 passed on all timed scenarios.
    """
    store: _BenchmarkStore | None = None
    # Retrieve via the fixture manager if available
    try:
        store = config._benchmark_store_instance
    except AttributeError:
        return
    if store is None:
        return

    models    = store.all_models()
    scenarios = store.all_scenarios()
    if not models or not scenarios:
        return

    COL_W = max(len(m) for m in models) + 2
    HDR_W = max(len(s) for s in scenarios) + 2

    terminalreporter.write_sep("=", "LLM Benchmark — Comparison Table")
    header = f"{'Scénario':<{HDR_W}}" + "".join(f"{m:^{COL_W}}" for m in models)
    terminalreporter.write_line(header)
    terminalreporter.write_line("-" * len(header))

    for scenario in scenarios:
        row = f"{scenario:<{HDR_W}}"
        for model in models:
            r = store.get(model, scenario)
            if r is None:
                cell = "N/A"
            else:
                lat      = r["latency_s"]
                max_lat  = r.get("max_latency_s")
                overtime = max_lat is not None and lat > max_lat
                icon     = "✅" if r["passed"] else "❌"
                timing   = f"{lat:.1f}s"
                if overtime:
                    timing = f"⚠️{lat:.1f}s>{max_lat:.0f}s"
                cell = f"{icon} {timing}"
            row += f"{cell:^{COL_W}}"
        terminalreporter.write_line(row)
    terminalreporter.write_sep("-", "")

    # ── Auto-exclusion: modèles avec 0 pass sur tous les scénarios (hors N/A) ──
    for model in models:
        results = [store.get(model, s) for s in scenarios]
        scored  = [r for r in results if r is not None]  # exclude N/A
        if not scored:
            continue
        passed_count = sum(1 for r in scored if r["passed"])
        # stable_noop passe même sur timeout (faux positif) → on l'ignore dans le score net
        meaningful = [r for r in scored if r.get("detail", "") != "" or r["passed"]]
        net_passed = sum(1 for r in meaningful if r["passed"] and r["latency_s"] < (r.get("max_latency_s") or 9999))
        if net_passed == 0 and len(scored) >= 3:
            reason = f"Score 0/{len(scored)} sur tous les scénarios (timeouts systématiques)"
            _add_exclusion(model, reason, f"0/{len(scored)}")
            terminalreporter.write_line(
                f"⛔  '{model}' auto-exclu des prochains benchmarks → tests/benchmark_exclusions.json"
            )
