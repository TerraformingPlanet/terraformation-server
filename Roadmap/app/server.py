"""
Roadmap Service — FastAPI + FastMCP server
Port 8001  |  MCP at /mcp

REST endpoints:
  GET  /health
  GET  /phases?status=
  GET  /phases/{id}
  GET  /queue           — non-done phases ordered by sort_order
  POST /phases           — add a phase
  POST /phases/{id}/complete?force=false
  POST /phases/{id}/move?after_id= — requeue a phase
  POST /seed             — bulk import from roadmap.json shape
  GET  /test            — run all assertion scripts, return full report
  GET  /test?skip=llm   — skip llm/benchmark group
  GET  /test?only=agent — run only agent group
  GET  /test?skip=llm,benchmark&only= — combine filters
  DELETE /phases/{id}

MCP tools (all prefixed roadmap_):
  roadmap_summary
  roadmap_list_phases
  roadmap_get_phase
  roadmap_get_next
  roadmap_add_phase
  roadmap_move_phase
  roadmap_reorder_phases
  roadmap_complete_phase
  roadmap_validate_phase
  roadmap_test_all
  roadmap_seed
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastmcp import FastMCP

from . import db
from .models import (
    AuditEntry,
    AuditResult,
    CompletionResult,
    MoveResult,
    PhaseCreate,
    PhaseRecord,
    PhaseStatus,
    SeedPayload,
    SeedResult,
    TestAllResult,
    ValidationResult,
)

# ── configuration ─────────────────────────────────────────────────────────────

_DEFAULT_DB = str(Path(__file__).parent.parent / "roadmap.db")
_DEFAULT_WORKSPACE = str(Path(__file__).parent.parent.parent)

DB_PATH: str = os.environ.get("DB_PATH", _DEFAULT_DB)
WORKSPACE_PATH: str = os.environ.get("WORKSPACE_PATH", _DEFAULT_WORKSPACE)
PORT: int = int(os.environ.get("PORT", "8001"))

# ── lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    db.configure(DB_PATH)
    db.init_schema()
    yield


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Terraformation Roadmap Service", version="1.0.0", lifespan=_lifespan)


# ── internal: pytest gate ─────────────────────────────────────────────────────

def _run_assertion_script(assertion_script: str) -> tuple[int, str]:
    """Run a pytest script path (relative to WORKSPACE_PATH). Returns (exit_code, output)."""
    target = os.path.join(WORKSPACE_PATH, assertion_script)
    cmd = [sys.executable, "-m", "pytest", target, "--tb=short", "--no-header", "-q"]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.path.join(WORKSPACE_PATH, "SimulationCore")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def _run_pytest(
    validation_filter: str | None = None,
    test_files: list[str] | None = None,
) -> tuple[int, str]:
    """Run pytest inside the workspace. Returns (exit_code, output).

    If test_files is provided, runs those specific files (paths relative to tests/).
    validation_filter adds a -k keyword filter on top.
    """
    tests_root = os.path.join(WORKSPACE_PATH, "SimulationCore", "tests")
    if test_files:
        targets = [os.path.join(tests_root, f) for f in test_files]
    else:
        targets = [tests_root]

    cmd = [sys.executable, "-m", "pytest", *targets, "--tb=short", "--no-header", "-q"]
    if validation_filter:
        cmd += ["-k", validation_filter]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = os.path.join(WORKSPACE_PATH, "SimulationCore")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def _complete_phase(phase_id: str, force: bool) -> CompletionResult:
    phase = db.get_phase(phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail=f"Phase '{phase_id}' not found")

    if phase.status == "done":
        return CompletionResult(
            phase=phase,
            status="ok",
            message=f"Already done ({phase.completed_date})",
        )

    # ── assertion_script auto-gate ─────────────────────────────────────────────
    if phase.assertion_script and not force:
        exit_code, script_output = _run_assertion_script(phase.assertion_script)
        if exit_code not in (0, 5):  # 5 = no tests collected (all skipped) — acceptable
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Assertion script failed — phase not completed",
                    "assertion_script": phase.assertion_script,
                    "script_output": script_output,
                },
            )

    # ── test-files reminder gate (agent doit les lancer lui-même) ─────────────────────
    if phase.tests and not force:
        tests_path = "SimulationCore/tests/"
        return CompletionResult(
            phase=phase,
            status="needs_validation",
            test_files=phase.tests,
            message=(
                f"Lance ces tests (depuis e:\\terraformation) puis re-appelle avec -Force :\n"
                + "\n".join(f"  pytest {tests_path}{f}" for f in phase.tests)
            ),
        )

    # ── pytest gate (legacy — validation_filter sans tests explicites) ──────────────
    pytest_output: str | None = None
    if phase.validation_filter and not phase.tests:
        exit_code, pytest_output = _run_pytest(validation_filter=phase.validation_filter)
        if exit_code != 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Tests failed — phase not completed",
                    "pytest_output": pytest_output,
                },
            )

    # ── visual confirmation gate ───────────────────────────────────────────────
    needs_visual = (
        not phase.tests
        and not phase.validation_filter
        and phase.notes
        and "visuelle" in phase.notes.lower()
    )
    if needs_visual and not force:
        return CompletionResult(
            phase=phase,
            pytest_output=pytest_output,
            status="needs_confirmation",
            message=(
                "This phase requires visual validation in Unity Play Mode. "
                "Re-call with force=true once confirmed."
            ),
        )

    # ── mark done ─────────────────────────────────────────────────────────────
    updated = db.mark_complete(phase_id)
    assert updated is not None
    return CompletionResult(
        phase=updated,
        pytest_output=pytest_output,
        status="ok",
        message="Phase marked as done",
    )


# ── REST routes ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "terraformation-roadmap"}


@app.get("/queue", response_model=list[PhaseRecord])
def get_queue():
    """Return all non-done phases ordered by sort_order (the active work queue)."""
    return [p for p in db.get_all_phases() if p.status != "done"]


@app.get("/phases", response_model=list[PhaseRecord])
def list_phases(status: PhaseStatus | None = Query(default=None)):
    return db.get_all_phases(status)


@app.get("/phases/{phase_id}", response_model=PhaseRecord)
def get_phase(phase_id: str):
    phase = db.get_phase(phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail=f"Phase '{phase_id}' not found")
    return phase


@app.post("/phases", response_model=PhaseRecord, status_code=201)
def add_phase(payload: PhaseCreate):
    existing = db.get_phase(payload.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Phase '{payload.id}' already exists")
    record = PhaseRecord(**payload.model_dump())
    return db.upsert_phase(record)


@app.post("/phases/{phase_id}/move", response_model=MoveResult)
def move_phase(phase_id: str, after_id: str | None = Query(default=None)):
    """
    Requeue phase_id to just after after_id.
    Pass after_id=null to move to front of queue.
    """
    try:
        return db.move_phase_after(phase_id, after_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/phases/{phase_id}/complete", response_model=CompletionResult)
def complete_phase(phase_id: str, force: bool = Query(default=False)):
    return _complete_phase(phase_id, force)


@app.post("/seed", response_model=SeedResult)
def seed(payload: SeedPayload, update: bool = Query(default=False)):
    """Bulk-import phases. With ?update=true, refreshes metadata (tests, filter, etc.) for existing phases without overwriting status."""
    records = [p.to_record() for p in payload.phases]
    inserted, skipped = db.seed_phases(records, update_metadata=update)
    return SeedResult(inserted=inserted, skipped=skipped, total=len(records))


@app.delete("/phases/{phase_id}", status_code=204)
def delete_phase(phase_id: str):
    if not db.delete_phase(phase_id):
        raise HTTPException(status_code=404, detail=f"Phase '{phase_id}' not found")


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_audit() -> AuditResult:
    """Build an AuditResult from all non-done phases."""
    active = [p for p in db.get_all_phases() if p.status != "done"]
    entries = [
        AuditEntry(
            id=p.id,
            name=p.name,
            status=p.status,
            exit_criteria=p.exit_criteria,
            tests_to_run=p.tests,
            validation_filter=p.validation_filter,
            assertion_script=p.assertion_script,
            notes=p.notes,
        )
        for p in active
    ]
    with_tests = sum(1 for e in entries if e.tests_to_run)
    visual_only = sum(1 for e in entries if not e.tests_to_run and not e.validation_filter)
    return AuditResult(
        total=len(entries),
        with_tests=with_tests,
        visual_only=visual_only,
        phases=entries,
    )


# ── test groups ──────────────────────────────────────────────────────────────
# A "group" is matched against the assertion_script path (case-insensitive substring).
# Built-in groups: llm (matches llm + benchmark), benchmark, agent

_GROUP_PATTERNS: dict[str, list[str]] = {
    "llm":       ["llm", "benchmark"],
    "benchmark": ["benchmark"],
    "agent":     ["agent"],
}


def _script_matches_groups(script: str | None, groups: list[str]) -> bool:
    """Return True if the script path matches any of the given group names."""
    if not script:
        return False
    low = script.lower()
    for g in groups:
        patterns = _GROUP_PATTERNS.get(g.lower(), [g.lower()])
        if any(p in low for p in patterns):
            return True
    return False


def _run_all_assertions(
    skip: list[str] | None = None,
    only: list[str] | None = None,
) -> TestAllResult:
    """
    Run every assertion_script registered across all phases.

    skip: group names to exclude (e.g. ['llm', 'benchmark'])
    only: group names to run exclusively
    Groups are matched against assertion_script path as substrings.
    Built-in groups: llm, benchmark, agent
    """
    phases = db.get_all_phases()
    results: list[ValidationResult] = []
    no_script = 0

    for phase in phases:
        if not phase.assertion_script:
            no_script += 1
            results.append(ValidationResult(
                phase_id=phase.id,
                status="no_script",
                assertion_script=None,
            ))
            continue

        # ── group filtering ────────────────────────────────────────────────
        if only and not _script_matches_groups(phase.assertion_script, only):
            results.append(ValidationResult(
                phase_id=phase.id,
                status="no_script",
                assertion_script=phase.assertion_script,
            ))
            no_script += 1
            continue
        if skip and _script_matches_groups(phase.assertion_script, skip):
            results.append(ValidationResult(
                phase_id=phase.id,
                status="no_script",
                assertion_script=phase.assertion_script,
            ))
            no_script += 1
            continue

        target = os.path.join(WORKSPACE_PATH, phase.assertion_script)
        if not os.path.isfile(target):
            results.append(ValidationResult(
                phase_id=phase.id,
                status="error",
                exit_code=None,
                output=f"File not found: {target}",
                assertion_script=phase.assertion_script,
            ))
            continue

        exit_code, output = _run_assertion_script(phase.assertion_script)
        results.append(ValidationResult(
            phase_id=phase.id,
            status="pass" if exit_code in (0, 5) else "fail",  # 5 = all skipped
            exit_code=exit_code,
            output=output,
            assertion_script=phase.assertion_script,
        ))

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    errors = sum(1 for r in results if r.status == "error")
    total = passed + failed + errors

    return TestAllResult(
        total=total,
        passed=passed,
        failed=failed,
        no_script=no_script,
        errors=errors,
        results=results,
    )


@app.get("/test", response_model=TestAllResult)
def test_all(
    skip: str | None = Query(
        default=None,
        description="Groupes à ignorer, séparés par virgule. Ex: llm,benchmark",
        example="llm,benchmark",
    ),
    only: str | None = Query(
        default=None,
        description="Groupes à exécuter exclusivement, séparés par virgule. Ex: agent",
        example="agent",
    ),
):
    """
    Run all assertion scripts registered across all roadmap phases.

    Returns a full report:
    - total: phases with an assertion_script
    - passed / failed / errors: counts
    - no_script: phases without assertion_script (skipped)
    - results: per-phase ValidationResult

    **Filtrage par groupe** (basé sur le nom du fichier assertion_script) :
    - `?skip=llm` — ignore les scripts contenant "llm" ou "benchmark"
    - `?skip=llm,benchmark` — plusieurs groupes (virgule)
    - `?only=agent` — exécute seulement les scripts contenant "agent"
    - Groupes intégrés : `llm` (→ llm + benchmark), `benchmark`, `agent`
    - Personnalisé : n'importe quel mot est cherché comme sous-chaîne dans le chemin du script
    """
    skip_list = [g.strip() for g in skip.split(",") if g.strip()] if skip else None
    only_list = [g.strip() for g in only.split(",") if g.strip()] if only else None
    return _run_all_assertions(skip=skip_list, only=only_list)


@app.get("/audit", response_model=AuditResult)
def audit():
    """
    Return all pending/not-started phases with their test files and validation info.
    Use this to know exactly what an agent needs to validate before marking phases done.
    """
    return _build_audit()


# ── FastMCP tools ──────────────────────────────────────────────────────────────

mcp = FastMCP("terraformation-roadmap")


@mcp.tool()
def roadmap_summary() -> dict:
    """Return counts of phases by status (done/pending/not-started)."""
    return db.get_summary()


@mcp.tool()
def roadmap_audit() -> dict:
    """
    Return all pending/not-started phases with their test files and validation info.

    Use this as the FIRST step when asked to validate the roadmap.
    For each phase returned:
    - If tests_to_run is non-empty  → run: pytest SimulationCore/tests/<file>
    - If visual_only (no tests)     → validate in Unity Play Mode, then use -Force
    - validation_filter (if set)    → legacy pytest -k filter (fallback)

    After all tests pass, call roadmap_complete_phase(phase_id, force=True) for each.
    """
    return _build_audit().model_dump()


@mcp.tool()
def roadmap_get_next() -> dict:
    """
    Return the next phase to work on (first non-done phase by sort_order).

    This is the ENTRY POINT of the queue. Always call this first to know
    what phase the dev should work on. Never skip ahead.
    Returns the full PhaseRecord, or {"status": "queue_empty"} if all done.
    """
    phase = db.get_next_phase()
    if phase is None:
        return {"status": "queue_empty", "message": "All phases are done!"}
    return phase.model_dump()


@mcp.tool()
def roadmap_move_phase(phase_id: str, after_id: str | None = None) -> dict:
    """
    Requeue a phase to a different position.

    - after_id = None  → move to FRONT of queue (highest priority)
    - after_id = "p10" → insert just AFTER p10

    Use this to:
    - Intercalate an urgent phase: roadmap_move_phase("p14-urgent", after_id="p10-current")
    - Delay a phase:               roadmap_move_phase("p13-slow", after_id="p15-other")
    Returns the full updated queue.
    """
    try:
        result = db.move_phase_after(phase_id, after_id)
        return result.model_dump()
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def roadmap_reorder_phases(ordered_ids_json: str) -> dict:
    """
    Bulk reorder the entire queue by providing the full desired id order as a JSON array.

    Example: '["p10", "p14-urgent", "p11", "p12", "p13"]'

    Any phases NOT listed are appended at the end in their current relative order.
    Returns the full updated queue.
    """
    import json as _json
    try:
        ids = _json.loads(ordered_ids_json)
    except Exception as exc:
        return {"error": f"Invalid JSON: {exc}"}
    if not isinstance(ids, list):
        return {"error": "Expected a JSON array of phase ids"}
    try:
        result = db.reorder_phases(ids)
        return result.model_dump()
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def roadmap_list_phases(status_filter: str | None = None) -> list[dict]:
    """
    List roadmap phases. Optional status_filter: 'done' | 'pending' | 'not-started'.
    Returns id, name, status, exit_criteria, notes for each phase.
    """
    statuses: list[PhaseStatus] = ["done", "pending", "not-started"]
    if status_filter and status_filter not in statuses:
        return [{"error": f"Invalid status '{status_filter}'. Use: {statuses}"}]
    phases = db.get_all_phases(status_filter)  # type: ignore[arg-type]
    return [p.model_dump() for p in phases]


@mcp.tool()
def roadmap_get_phase(phase_id: str) -> dict:
    """Get full details of a roadmap phase by its id."""
    phase = db.get_phase(phase_id)
    if phase is None:
        return {"error": f"Phase '{phase_id}' not found"}
    return phase.model_dump()


@mcp.tool()
def roadmap_test_all(
    skip: str | None = None,
    only: str | None = None,
) -> dict:
    """
    Run ALL assertion scripts across ALL roadmap phases and return a full report.

    Use this:
    - After implementing a batch of features, to check global regression
    - Before a release, to confirm all phases pass their assertions

    Group filtering (based on assertion_script filename):
    - skip="llm"           → skip scripts whose path contains 'llm' or 'benchmark'
    - skip="llm,benchmark" → skip multiple groups (comma-separated)
    - only="agent"         → run only scripts whose path contains 'agent'
    - Built-in groups: llm (→ llm+benchmark), benchmark, agent
    - Custom: any word matched as plain substring of the script path

    Returns:
    {
      "total": N, "passed": N, "failed": N,
      "no_script": N,  "errors": N,
      "results": [{"phase_id": "p10", "status": "pass", "output": "..."}, ...]
    }

    Convention:
      Script path = SimulationCore/tests/assertions/test_<phase_id_underscored>.py
      Template   = SimulationCore/tests/assertions/_template.py
    """
    skip_list = [g.strip() for g in skip.split(",") if g.strip()] if skip else None
    only_list = [g.strip() for g in only.split(",") if g.strip()] if only else None
    return _run_all_assertions(skip=skip_list, only=only_list).model_dump()


@mcp.tool()
def roadmap_validate_phase(phase_id: str) -> dict:
    """
    Run the assertion script attached to a phase and report pass/fail.

    The planificateur calls this BEFORE roadmap_complete_phase:
    - status='pass'      → call roadmap_complete_phase(phase_id, force=True)
    - status='fail'      → fix the code, update the script, then retry
    - status='no_script' → no assertion_script set; use force=True directly or set one via roadmap_add_phase
    - status='error'     → phase not found or unexpected error
    """
    phase = db.get_phase(phase_id)
    if phase is None:
        return ValidationResult(
            phase_id=phase_id,
            status="error",
            output=f"Phase '{phase_id}' not found",
        ).model_dump()

    if not phase.assertion_script:
        return ValidationResult(
            phase_id=phase_id,
            status="no_script",
            output="No assertion_script configured for this phase.",
        ).model_dump()

    exit_code, output = _run_assertion_script(phase.assertion_script)
    return ValidationResult(
        phase_id=phase_id,
        status="pass" if exit_code in (0, 5) else "fail",  # 5 = all skipped
        exit_code=exit_code,
        output=output,
        assertion_script=phase.assertion_script,
    ).model_dump()


@mcp.tool()
def roadmap_add_phase(
    phase_id: str,
    name: str,
    exit_criteria: str,
    roadmap_anchor: str | None = None,
    validation_filter: str | None = None,
    assertion_script: str | None = None,
    notes: str | None = None,
    design_ref: str | None = None,
    insert_after_id: str | None = None,
) -> dict:
    """
    Add a new phase to the roadmap queue.
    phase_id must be unique (e.g. 'p14-my-feature').
    assertion_script: path relative to workspace root (e.g. 'SimulationCore/tests/test_p14.py').
    insert_after_id: place the phase just after this phase in the queue.
                     If None (default), appended at end of queue.
    """
    existing = db.get_phase(phase_id)
    if existing:
        return {"error": f"Phase '{phase_id}' already exists. Use roadmap_get_phase to inspect."}

    if insert_after_id:
        after_phase = db.get_phase(insert_after_id)
        if after_phase is None:
            return {"error": f"insert_after_id '{insert_after_id}' not found"}
        sort_order = after_phase.sort_order  # will be shifted during move
    else:
        sort_order = db.get_max_sort_order() + 1

    record = PhaseRecord(
        id=phase_id,
        name=name,
        exit_criteria=exit_criteria,
        roadmap_anchor=roadmap_anchor,
        validation_filter=validation_filter,
        assertion_script=assertion_script,
        notes=notes,
        design_ref=design_ref,
        status="not-started",
        sort_order=sort_order,
    )
    db.upsert_phase(record)

    if insert_after_id:
        db.move_phase_after(phase_id, insert_after_id)

    created = db.get_phase(phase_id)
    assert created is not None
    return created.model_dump()


@mcp.tool()
def roadmap_complete_phase(phase_id: str, force: bool = False) -> dict:
    """
    Validate and mark a roadmap phase as done.
    - Runs pytest if validation_filter is set. Blocks if tests fail.
    - Requires force=True for visual-only phases (no tests).
    Returns CompletionResult with status 'ok', 'blocked', or 'needs_confirmation'.
    """
    try:
        result = _complete_phase(phase_id, force)
        return result.model_dump()
    except HTTPException as e:
        return {"error": e.detail}


@mcp.tool()
def roadmap_seed(phases_json: str) -> dict:
    """
    Bulk-import phases from a JSON string matching the roadmap.json format.
    Only inserts phases that don't already exist (idempotent).
    Pass the full content of Documentation/roadmap.json as phases_json.
    """
    import json as _json
    try:
        data = _json.loads(phases_json)
    except Exception as exc:
        return {"error": f"Invalid JSON: {exc}"}
    try:
        payload = SeedPayload(**data)
    except Exception as exc:
        return {"error": f"Validation error: {exc}"}
    records = [p.to_record() for p in payload.phases]
    inserted, skipped = db.seed_phases(records, update_metadata=True)
    return {"inserted": inserted, "skipped": skipped, "total": len(records)}


# ── mount MCP into FastAPI ─────────────────────────────────────────────────────

app.mount("/mcp", mcp.http_app())


# ── entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=PORT, reload=False)
