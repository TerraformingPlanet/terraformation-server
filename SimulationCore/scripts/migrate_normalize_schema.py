"""
Migration script: populate normalized `tiles` and `buildings` tables from existing JSON blobs.

Run once after deploying the updated persistence.py schema.
Requires DATABASE_URL env var (same as DedicatedServer).

Usage:
    python SimulationCore/scripts/migrate_normalize_schema.py

Safe to run multiple times (idempotent — ON CONFLICT DO UPDATE).
"""
import json
import os
import sys

# Ensure SimulationCore is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from terraformation_sim.persistence import (
    PostgresRepository,
    _bodies_table,
    _corporations_table,
    _tile_mutations_table,
)
from terraformation_sim.models import (
    SphericalBodyState,
    BuildingData,
)
from terraformation_sim.logic.generation import generate_spherical_tiles


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.", file=sys.stderr)
        sys.exit(1)

    repo = PostgresRepository(db_url)

    # Ensure schema is up to date (creates tiles + buildings tables if missing)
    print("Schema ready.")

    with repo._engine.connect() as conn:
        body_rows = conn.execute(_bodies_table.select()).fetchall()
        corp_rows = conn.execute(_corporations_table.select()).fetchall()

    print(f"Found {len(body_rows)} bodies, {len(corp_rows)} corporations.")

    # ── Phase 1: migrate tiles ────────────────────────────────────────────────
    tiles_written = 0
    for row in body_rows:
        data = json.loads(row.body_json)
        if data.get("surfaceType", "goldberg") != "goldberg":
            continue
        body = SphericalBodyState.model_validate(data)
        body_id = body.bodyId

        # Check if tiles already in normalized table
        existing = repo.load_tiles(body_id)
        if existing:
            print(f"  Body {body_id[:8]} ({data.get('bodyName','?')}): {len(existing)} tiles already in DB — skipping.")
            continue

        print(f"  Body {body_id[:8]} ({data.get('bodyName','?')}): generating tiles...", end="", flush=True)
        tiles = generate_spherical_tiles(
            body.h3Resolution,
            body.projectionOverride,
            body.waterLevel,
            body.seed,
            atmosphere_density=body.atmosphereDensity,
        )
        print(f" {len(tiles)} tiles generated. Writing...", end="", flush=True)
        repo.save_tiles_bulk(body_id, tiles)
        tiles_written += len(tiles)
        print(" done.")

    print(f"Tiles migrated: {tiles_written} rows written.")

    # ── Phase 2: migrate buildings ────────────────────────────────────────────
    buildings_written = 0
    for row in corp_rows:
        corp_data = json.loads(row.corp_json)
        for b_data in corp_data.get("buildings", []):
            try:
                b = BuildingData.model_validate(b_data)
                repo.save_building(b)
                buildings_written += 1
            except Exception as exc:
                print(f"  WARNING: could not migrate building {b_data.get('id','?')}: {exc}")

    print(f"Buildings migrated: {buildings_written} rows written.")

    print("\nMigration complete.")
    print("You can now run the server — tiles and buildings will be loaded from the normalized tables.")
    print()
    print("Verification SQL:")
    print("  SELECT terrain_type, COUNT(*), ROUND(AVG(humidity)::numeric, 2) as avg_hum FROM tiles GROUP BY terrain_type ORDER BY COUNT(*) DESC;")
    print("  SELECT building_type, COUNT(*) FROM buildings GROUP BY building_type;")


if __name__ == "__main__":
    main()
