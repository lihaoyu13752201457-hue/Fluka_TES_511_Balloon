#!/usr/bin/env python3
"""Validate sampled source authority against TES Geant4 IA INIT truth."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_eplus_raw_mvp import (  # noqa: E402
    load_surrounding_sphere_center,
    sample_primaries,
    rotate_y,
    source_energy_policy,
)


TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
RUN_SUMMARY = TES_ROOT / "runs/step02_instant_fix5_fullstat_v2/run_summary.csv"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def quantile(vals: list[float], q: float) -> float:
    if not vals:
        return float("nan")
    xs = sorted(vals)
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def summarize(vals: list[float]) -> dict[str, float]:
    return {
        "n": float(len(vals)),
        "p10": quantile(vals, 0.10),
        "median": quantile(vals, 0.50),
        "p90": quantile(vals, 0.90),
        "min": min(vals) if vals else float("nan"),
        "max": max(vals) if vals else float("nan"),
    }


def ratio(a: float, b: float) -> float | None:
    if b == 0 or math.isnan(a) or math.isnan(b):
        return None
    return a / b


def sim_paths(primary_tag: str) -> list[Path]:
    out: list[Path] = []
    with RUN_SUMMARY.open(newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "PASS" or row.get("particle") != primary_tag:
                continue
            out.append(TES_ROOT / row["sim_path"])
    return out


def parse_sim_truth(paths: list[Path], max_events: int, source_rotation_y_deg: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line.startswith("IA INIT"):
                    continue
                parts = [p.strip() for p in line.split("IA INIT", 1)[1].split(";")]
                if len(parts) < 23:
                    continue
                x = float(parts[4])
                y = float(parts[5])
                z = float(parts[6])
                u = float(parts[16])
                v = float(parts[17])
                w = float(parts[18])
                energy_keV = float(parts[22])
                x, y, z = rotate_y(x, y, z, source_rotation_y_deg)
                u, v, w = rotate_y(u, v, w, source_rotation_y_deg)
                rows.append(
                    {
                        "energy_keV": energy_keV,
                        "radius_cm": math.sqrt(x * x + y * y + z * z),
                        "dz": w,
                    }
                )
                if len(rows) >= max_events:
                    return rows
    return rows


def sampled_truth(primary_tag: str, histories: int, seed: int, source_rotation_y_deg: float) -> list[dict[str, float]]:
    center = load_surrounding_sphere_center(primary_tag)
    primaries, _audit = sample_primaries(
        histories=histories,
        seed=seed,
        run_id=f"{primary_tag}_source_truth_validation",
        primary_tag=primary_tag,
        source_start_area_center_cm=center,
        source_rotation_y_deg=source_rotation_y_deg,
        normalization_histories=histories,
    )
    rows: list[dict[str, float]] = []
    for p in primaries:
        x = float(p["primary_x_cm"])
        y = float(p["primary_y_cm"])
        z = float(p["primary_z_cm"])
        rows.append(
            {
                "energy_keV": float(p["primary_energy_keV"]),
                "radius_cm": math.sqrt(x * x + y * y + z * z),
                "dz": float(p["primary_dz"]),
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary-tag", required=True)
    ap.add_argument("--max-events", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=24065401)
    ap.add_argument("--source-rotation-y-deg", type=float, default=-45.0)
    ap.add_argument("--out-dir", type=Path, default=Path("work_fluka_harness/source_truth_validation"))
    args = ap.parse_args()

    paths = sim_paths(args.primary_tag)
    if not paths:
        raise SystemExit(f"no PASS sim jobs for {args.primary_tag}")
    sim_rows = parse_sim_truth(paths, args.max_events, args.source_rotation_y_deg)
    n = len(sim_rows)
    if n < 100:
        raise SystemExit(f"too few IA INIT rows parsed for {args.primary_tag}: {n}")
    sampled_rows = sampled_truth(args.primary_tag, n, args.seed, args.source_rotation_y_deg)

    metrics = {}
    status = "PASS"
    for key in ["energy_keV", "radius_cm", "dz"]:
        s = summarize([r[key] for r in sampled_rows])
        g = summarize([r[key] for r in sim_rows])
        med_ratio = ratio(s["median"], g["median"])
        entry = {"sampled": s, "sim_ia_init": g, "median_ratio": med_ratio}
        if key in {"energy_keV", "radius_cm"}:
            ok = med_ratio is not None and 0.90 <= med_ratio <= 1.10
        else:
            ok = abs(s["median"] - g["median"]) <= 0.10
            entry["median_abs_delta"] = s["median"] - g["median"]
        entry["status"] = "PASS" if ok else "FAIL"
        if not ok:
            status = "BLOCKED_SOURCE_SEMANTICS"
        metrics[key] = entry

    result = {
        "created_utc": now_utc(),
        "status": status,
        "primary_tag": args.primary_tag,
        "samples_compared": n,
        "source_rotation_y_deg": args.source_rotation_y_deg,
        "sampled_source_energy_policy": source_energy_policy(),
        "sim_paths": [str(p) for p in paths],
        "metrics": metrics,
    }
    out_dir = args.out_dir / args.primary_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "source_truth_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# {args.primary_tag} Source Truth Validation",
        "",
        f"- status: `{status}`",
        f"- samples compared: `{n}`",
        f"- sampled source energy policy: `{source_energy_policy()}`",
        "",
        "| dimension | sampled median | IA INIT median | ratio/delta | status |",
        "|---|---:|---:|---:|---|",
    ]
    for key, entry in metrics.items():
        s_med = entry["sampled"]["median"]
        g_med = entry["sim_ia_init"]["median"]
        if key == "dz":
            rd = entry["median_abs_delta"]
        else:
            rd = entry["median_ratio"]
        lines.append(f"| {key} | {s_med:.6g} | {g_med:.6g} | {rd:.6g} | {entry['status']} |")
    (out_dir / "source_truth_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "source_truth_validation.md")
    print(status)
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
