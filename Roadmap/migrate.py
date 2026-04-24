"""
Roadmap Service — migration from Documentation/roadmap.json to local SQLite.

Usage (run from e:\\terraformation\\Roadmap or any directory):
    python migrate.py
    python migrate.py --update     # also refresh metadata for existing phases
    python migrate.py --json path/to/roadmap.json

The script auto-detects the roadmap.json location relative to this file
(../../Documentation/roadmap.json).
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Ensure the app package is importable when run directly
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

# Allow override of DB_PATH before importing app modules
_default_db = str(_HERE / "roadmap.db")
os.environ.setdefault("DB_PATH", _default_db)
os.environ.setdefault("WORKSPACE_PATH", str(_HERE.parent))

from app import db  # noqa: E402 — must come after path/env setup
from app.models import SeedPhaseInput  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed/migrate roadmap.json → local SQLite")
    parser.add_argument(
        "--json",
        dest="json_path",
        default=str(_HERE.parent / "Documentation" / "roadmap.json"),
        help="Path to roadmap.json (default: ../../Documentation/roadmap.json)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Also update metadata for phases that already exist (preserves status/completed_date)",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default=os.environ["DB_PATH"],
        help="Path to SQLite DB file (default: roadmap.db next to this script)",
    )
    args = parser.parse_args()

    db.configure(args.db_path)
    db.init_schema()

    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"ERROR: roadmap.json not found at {json_path}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(json_path.read_text(encoding="utf-8-sig"))
    phases_data = raw.get("phases", [])
    if not phases_data:
        print("WARNING: No phases found in roadmap.json", file=sys.stderr)
        sys.exit(0)

    records = []
    for i, p in enumerate(phases_data):
        # Assign sortOrder from array index if not set in JSON (preserves roadmap.json order)
        p.setdefault("sortOrder", i)
        records.append(SeedPhaseInput(**p).to_record())
    inserted, skipped = db.seed_phases(records, update_metadata=args.update)

    action = "Updated" if args.update else "Inserted"
    print(f"DB: {args.db_path}")
    print(f"{action}: {inserted}  |  Skipped: {skipped}  |  Total: {len(records)}")


if __name__ == "__main__":
    main()
