from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


PROFILES: list[dict[str, float | int | str]] = [
    {"name": "Coast", "coherence": 4, "water_level": 0.71, "atmosphere_density": 0.70, "seed": 1004},
    {"name": "Ocean", "coherence": 1, "water_level": 0.85, "atmosphere_density": 0.65, "seed": 1011},
    {"name": "Arid", "coherence": 2, "water_level": 0.03, "atmosphere_density": 0.12, "seed": 1021},
    {"name": "Frozen", "coherence": 3, "water_level": 0.35, "atmosphere_density": 0.30, "seed": 1031},
    {"name": "Basin", "coherence": 5, "water_level": 0.18, "atmosphere_density": 0.45, "seed": 1041},
]


def _request_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_health(base_url: str, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    health_url = f"{base_url.rstrip('/')}/health"
    last_error = ""
    while time.time() < deadline:
        try:
            payload = _request_json(health_url)
            if payload.get("service") == "terraformation-dedicated-server":
                return
        except Exception as exc:  # pragma: no cover - best effort polling
            last_error = str(exc)
        time.sleep(1.0)
    raise RuntimeError(f"Dedicated server did not become healthy within {timeout_seconds:.0f}s: {last_error}")


def _metric_pct(stats_map: dict, key: str) -> float:
    entry = stats_map.get(key, {}) if isinstance(stats_map, dict) else {}
    value = entry.get("pct", 0.0) if isinstance(entry, dict) else 0.0
    return float(value or 0.0)


def _fetch_generation_stats(base_url: str, profile: dict[str, float | int | str], h3_resolution: int) -> dict:
    query = urllib.parse.urlencode(
        {
            "coherence": profile["coherence"],
            "water_level": profile["water_level"],
            "atmosphere_density": profile["atmosphere_density"],
            "seed": profile["seed"],
            "h3_resolution": h3_resolution,
        }
    )
    return _request_json(f"{base_url.rstrip('/')}/debug/generation-stats?{query}")


def _build_row(stats: dict) -> dict[str, float | int | str]:
    terrain = stats.get("terrain", {})
    water = stats.get("water_classification", {})
    terrain_class = stats.get("terrain_class", {})
    quality = stats.get("quality", {})
    temperature = stats.get("temperature", {})
    params = stats.get("params", {})
    return {
        "preset": params.get("coherence", "Unknown"),
        "seed": params.get("seed", 0),
        "atmosphereDensity": params.get("atmosphere_density", 0.0),
        "waterLevel": params.get("water_level", 0.0),
        "dryPct": float(quality.get("dry_pct", 0.0)),
        "humidPct": float(quality.get("humid_pct", 0.0)),
        "saturatedPct": float(quality.get("saturated_pct", 0.0)),
        "habitablePct": float(quality.get("habitable_pct", 0.0)),
        "coldPct": float(quality.get("cold_pct", 0.0)),
        "hotPct": float(quality.get("hot_pct", 0.0)),
        "vegetationPct": _metric_pct(terrain, "Vegetation"),
        "openOceanPct": _metric_pct(water, "OpenOcean"),
        "frozenPct": _metric_pct(water, "FrozenWater"),
        "coastPct": _metric_pct(water, "Coast"),
        "inlandPct": _metric_pct(water, "InlandWater"),
        "basinPct": _metric_pct(terrain_class, "Basin"),
        "temperatureAvg": float(temperature.get("avg", 0.0)),
    }


def _evaluate(results: list[dict[str, float | int | str]]) -> dict:
    checks: list[dict[str, object]] = []

    def add_check(preset: str, name: str, passed: bool, message: str) -> None:
        checks.append({"preset": preset, "check": name, "passed": passed, "message": message})

    for row in results:
        preset = str(row["preset"])
        if preset == "Coast":
            add_check(preset, "coast-band-present", float(row["coastPct"]) >= 5.0,
                      f"Coast should keep at least 5% coastal tiles, got {float(row['coastPct']):.1f}%.")
            add_check(preset, "vegetation-present", float(row["vegetationPct"]) >= 5.0,
                      f"Coast should keep at least 5% vegetation, got {float(row['vegetationPct']):.1f}%.")
        elif preset == "Ocean":
            add_check(preset, "ocean-dominant", float(row["openOceanPct"]) >= 45.0,
                      f"Ocean should have at least 45% open ocean, got {float(row['openOceanPct']):.1f}%.")
            add_check(preset, "not-overdry", float(row["dryPct"]) <= 25.0,
                      f"Ocean should not be dry above 25%, got {float(row['dryPct']):.1f}%.")
        elif preset == "Arid":
            add_check(preset, "dry-dominant", float(row["dryPct"]) >= 60.0,
                      f"Arid should have at least 60% dry tiles, got {float(row['dryPct']):.1f}%.")
            add_check(preset, "limited-vegetation", float(row["vegetationPct"]) <= 15.0,
                      f"Arid should keep vegetation under 15%, got {float(row['vegetationPct']):.1f}%.")
        elif preset == "Frozen":
            add_check(preset, "cold-dominant", float(row["coldPct"]) >= 40.0,
                      f"Frozen should have at least 40% cold tiles, got {float(row['coldPct']):.1f}%.")
            add_check(preset, "ice-present", float(row["frozenPct"]) >= 5.0,
                      f"Frozen should have at least 5% frozen water, got {float(row['frozenPct']):.1f}%.")
        elif preset == "Basin":
            add_check(preset, "inland-water-present", float(row["inlandPct"]) >= 5.0,
                      f"Basin should have at least 5% inland water, got {float(row['inlandPct']):.1f}%.")
            add_check(preset, "basin-shapes-present", float(row["basinPct"]) >= 9.5,
                      f"Basin should keep at least 9.5% terrainClass Basin, got {float(row['basinPct']):.1f}%.")

    failures = [check for check in checks if not bool(check["passed"])]
    return {"ok": len(failures) == 0, "checks": checks, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="Dedicated server generation smoke suite")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--h3-resolution", type=int, default=2)
    parser.add_argument("--health-timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    _wait_for_health(args.base_url, args.health_timeout)

    results: list[dict[str, float | int | str]] = []
    for profile in PROFILES:
        stats = _fetch_generation_stats(args.base_url, profile, args.h3_resolution)
        row = _build_row(stats)
        row["preset"] = profile["name"]
        results.append(row)

    verdict = _evaluate(results)
    payload = {
        "baseUrl": args.base_url,
        "h3Resolution": args.h3_resolution,
        "results": results,
        **verdict,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        normalized_path = output_path.with_name(output_path.stem + ".normalized.json")
        normalized_payload = {
            "h3Resolution": payload["h3Resolution"],
            "ok": payload["ok"],
            "results": sorted(payload["results"], key=lambda row: str(row["preset"])),
            "checks": sorted(payload["checks"], key=lambda check: (str(check["preset"]), str(check["check"]))),
        }
        normalized_path.write_text(json.dumps(normalized_payload, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Generation preset summary:")
        for row in results:
            print(
                f"- {row['preset']}: dry={float(row['dryPct']):.1f}% humid={float(row['humidPct']):.1f}% "
                f"openOcean={float(row['openOceanPct']):.1f}% vegetation={float(row['vegetationPct']):.1f}% "
                f"basin={float(row['basinPct']):.1f}% tempAvg={float(row['temperatureAvg']):.1f}"
            )
        if payload["ok"]:
            print("All generation checks passed.")
        else:
            print("Generation checks failed:")
            for failure in payload["failures"]:
                print(f"- {failure['preset']} / {failure['check']}: {failure['message']}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())