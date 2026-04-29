"""
Roadmap Service — SQLite persistence layer (stdlib sqlite3, no ORM)
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date
from typing import Generator

from .models import PhaseRecord, PhaseStatus, MoveResult

_lock = threading.Lock()
_DB_PATH: str = "/data/roadmap.db"


def configure(db_path: str) -> None:
    global _DB_PATH
    _DB_PATH = db_path


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_schema() -> None:
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS phases (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'not-started',
                completed_date   TEXT,
                tests            TEXT NOT NULL DEFAULT '[]',
                validation_filter TEXT,
                exit_criteria    TEXT,
                design_ref       TEXT,
                roadmap_anchor   TEXT,
                notes            TEXT,
                assertion_script TEXT,
                sort_order       INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Idempotent migrations for existing DBs
        for col_sql in [
            "ALTER TABLE phases ADD COLUMN assertion_script TEXT",
            "ALTER TABLE phases ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                con.execute(col_sql)
            except Exception:
                pass  # column already exists


# ── helpers ───────────────────────────────────────────────────────────────────

def _row_to_record(row: sqlite3.Row) -> PhaseRecord:
    keys = row.keys()
    return PhaseRecord(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        completed_date=row["completed_date"],
        tests=json.loads(row["tests"] or "[]"),
        validation_filter=row["validation_filter"],
        exit_criteria=row["exit_criteria"],
        design_ref=row["design_ref"],
        roadmap_anchor=row["roadmap_anchor"],
        notes=row["notes"],
        assertion_script=row["assertion_script"] if "assertion_script" in keys else None,
        sort_order=row["sort_order"] if "sort_order" in keys else 0,
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get_all_phases(status: PhaseStatus | None = None) -> list[PhaseRecord]:
    with _conn() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM phases WHERE status = ? ORDER BY sort_order ASC", (status,)
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM phases ORDER BY sort_order ASC").fetchall()
    return [_row_to_record(r) for r in rows]


def get_phase(phase_id: str) -> PhaseRecord | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM phases WHERE id = ?", (phase_id,)).fetchone()
    return _row_to_record(row) if row else None


def upsert_phase(phase: PhaseRecord) -> PhaseRecord:
    with _lock, _conn() as con:
        con.execute(
            """
            INSERT INTO phases
                (id, name, status, completed_date, tests, validation_filter,
                 exit_criteria, design_ref, roadmap_anchor, notes, assertion_script, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name              = excluded.name,
                status            = excluded.status,
                completed_date    = excluded.completed_date,
                tests             = excluded.tests,
                validation_filter = excluded.validation_filter,
                exit_criteria     = excluded.exit_criteria,
                design_ref        = excluded.design_ref,
                roadmap_anchor    = excluded.roadmap_anchor,
                notes             = excluded.notes,
                assertion_script  = excluded.assertion_script,
                sort_order        = excluded.sort_order
            """,
            (
                phase.id,
                phase.name,
                phase.status,
                phase.completed_date,
                json.dumps(phase.tests),
                phase.validation_filter,
                phase.exit_criteria,
                phase.design_ref,
                phase.roadmap_anchor,
                phase.notes,
                phase.assertion_script,
                phase.sort_order,
            ),
        )
    return get_phase(phase.id)  # type: ignore[return-value]


def mark_complete(phase_id: str, completed_date: str | None = None) -> PhaseRecord | None:
    today = completed_date or date.today().isoformat()
    with _lock, _conn() as con:
        con.execute(
            "UPDATE phases SET status = 'done', completed_date = ? WHERE id = ?",
            (today, phase_id),
        )
    return get_phase(phase_id)


def delete_phase(phase_id: str) -> bool:
    with _lock, _conn() as con:
        cur = con.execute("DELETE FROM phases WHERE id = ?", (phase_id,))
    return cur.rowcount > 0


def _update_metadata(phase: PhaseRecord) -> None:
    """Update metadata fields without overwriting status or completed_date."""
    with _lock, _conn() as con:
        con.execute(
            """
            UPDATE phases SET
                name              = ?,
                tests             = ?,
                validation_filter = ?,
                exit_criteria     = ?,
                design_ref        = ?,
                roadmap_anchor    = ?,
                notes             = ?,
                assertion_script  = ?,
                sort_order        = ?
            WHERE id = ?
            """,
            (
                phase.name,
                json.dumps(phase.tests),
                phase.validation_filter,
                phase.exit_criteria,
                phase.design_ref,
                phase.roadmap_anchor,
                phase.notes,
                phase.assertion_script,
                phase.sort_order,
                phase.id,
            ),
        )


def seed_phases(
    phases: list[PhaseRecord],
    update_metadata: bool = False,
    restore: bool = False,
) -> tuple[int, int]:
    """Insert new phases.

    - update_metadata=True  : refresh metadata for existing phases without touching status/completed_date.
    - restore=True          : full upsert including status/completed_date (disaster-recovery only).
    - Default (both False)  : DB is source of truth — new phases inserted as 'not-started',
                              existing phases untouched.

    Returns (inserted_or_updated, skipped).
    """
    inserted = skipped = 0
    for phase in phases:
        existing = get_phase(phase.id)
        if existing is None:
            if restore:
                upsert_phase(phase)
            else:
                # DB is source of truth: new phases always start as not-started
                seed_record = phase.model_copy(update={"status": "not-started", "completed_date": None})
                upsert_phase(seed_record)
            inserted += 1
        elif restore:
            upsert_phase(phase)
            inserted += 1
        elif update_metadata:
            _update_metadata(phase)
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


# ── Queue operations ─────────────────────────────────────────────────────────────

def get_next_phase() -> PhaseRecord | None:
    """Return the first non-done phase by sort_order (front of the queue)."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM phases WHERE status != 'done' ORDER BY sort_order ASC LIMIT 1"
        ).fetchone()
    return _row_to_record(row) if row else None


def get_max_sort_order() -> int:
    with _conn() as con:
        row = con.execute("SELECT MAX(sort_order) as m FROM phases").fetchone()
    return (row["m"] or 0)


def _apply_order(ids: list[str]) -> None:
    """Reassign sort_order = index for all provided ids (in one connection)."""
    with _lock, _conn() as con:
        for i, pid in enumerate(ids):
            con.execute("UPDATE phases SET sort_order = ? WHERE id = ?", (i, pid))


def move_phase_after(phase_id: str, after_id: str | None) -> MoveResult:
    """
    Move phase_id to just after after_id in the queue.
    If after_id is None, move to front of queue.
    Raises ValueError if either id is not found.
    """
    with _conn() as con:
        rows = con.execute("SELECT id FROM phases ORDER BY sort_order ASC").fetchall()
    ids = [r["id"] for r in rows]

    if phase_id not in ids:
        raise ValueError(f"Phase '{phase_id}' not found")
    if after_id and after_id not in ids:
        raise ValueError(f"Phase '{after_id}' not found")

    ids.remove(phase_id)
    if after_id is None:
        ids.insert(0, phase_id)
    else:
        pos = ids.index(after_id)
        ids.insert(pos + 1, phase_id)

    _apply_order(ids)
    return MoveResult(moved_id=phase_id, queue=get_all_phases())


def reorder_phases(ordered_ids: list[str]) -> MoveResult:
    """
    Reassign sort_order based on ordered_ids list.
    Any existing phases NOT in the list are appended at the end in their current relative order.
    Raises ValueError if any provided id doesn't exist.
    """
    with _conn() as con:
        rows = con.execute("SELECT id FROM phases ORDER BY sort_order ASC").fetchall()
    all_ids = [r["id"] for r in rows]
    all_ids_set = set(all_ids)

    unknown = [pid for pid in ordered_ids if pid not in all_ids_set]
    if unknown:
        raise ValueError(f"Unknown phase ids: {unknown}")

    ordered_set = set(ordered_ids)
    rest = [pid for pid in all_ids if pid not in ordered_set]
    final_order = ordered_ids + rest

    _apply_order(final_order)
    return MoveResult(moved_id="", queue=get_all_phases())


def get_summary() -> dict:
    with _conn() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) as cnt FROM phases GROUP BY status"
        ).fetchall()
    counts = {r["status"]: r["cnt"] for r in rows}
    total = sum(counts.values())
    return {
        "total": total,
        "done": counts.get("done", 0),
        "pending": counts.get("pending", 0),
        "not_started": counts.get("not-started", 0),
    }
