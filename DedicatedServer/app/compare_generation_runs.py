from __future__ import annotations

import argparse
import json
from pathlib import Path


FIELDS = [
    "dryPct",
    "humidPct",
    "saturatedPct",
    "habitablePct",
    "coldPct",
    "hotPct",
    "vegetationPct",
    "openOceanPct",
    "frozenPct",
    "coastPct",
    "inlandPct",
    "basinPct",
    "temperatureAvg",
]


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve_threshold(thresholds: dict, preset: str, field: str) -> float | None:
    preset_overrides = thresholds.get("presets", {}).get(preset, {}) if isinstance(thresholds, dict) else {}
    if isinstance(preset_overrides, dict) and field in preset_overrides:
        return float(preset_overrides[field])
    defaults = thresholds.get("defaults", {}) if isinstance(thresholds, dict) else {}
    if isinstance(defaults, dict) and field in defaults:
        return float(defaults[field])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two generation smoke JSON runs")
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output", default="")
    parser.add_argument("--thresholds", default="")
    args = parser.parse_args()

    baseline = _load(args.baseline)
    candidate = _load(args.candidate)
    thresholds = _load(args.thresholds) if args.thresholds else {}

    baseline_rows = {row["preset"]: row for row in baseline.get("results", [])}
    candidate_rows = {row["preset"]: row for row in candidate.get("results", [])}
    presets = sorted(set(baseline_rows) | set(candidate_rows))

    deltas: list[dict] = []
    violations: list[dict] = []
    for preset in presets:
        base_row = baseline_rows.get(preset, {})
        cand_row = candidate_rows.get(preset, {})
        for field in FIELDS:
            base_value = float(base_row.get(field, 0.0))
            cand_value = float(cand_row.get(field, 0.0))
            delta = round(cand_value - base_value, 4)
            allowed_delta = _resolve_threshold(thresholds, preset, field)
            entry = {
                "preset": preset,
                "field": field,
                "baseline": round(base_value, 4),
                "candidate": round(cand_value, 4),
                "delta": delta,
            }
            if allowed_delta is not None:
                entry["allowedAbsDelta"] = allowed_delta
                entry["withinThreshold"] = abs(delta) <= allowed_delta
                if not entry["withinThreshold"]:
                    violations.append(entry)
            deltas.append(entry)

    payload = {
        "baseline": args.baseline,
        "candidate": args.candidate,
        "baselineOk": bool(baseline.get("ok")),
        "candidateOk": bool(candidate.get("ok")),
        "thresholds": args.thresholds,
        "passed": bool(baseline.get("ok")) and bool(candidate.get("ok")) and len(violations) == 0,
        "violations": violations,
        "deltas": deltas,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())