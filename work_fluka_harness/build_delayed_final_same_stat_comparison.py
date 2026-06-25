#!/usr/bin/env python3
"""Apply TES Step05 final selection to FLUKA delayed isotope-source runs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from build_prompt_final_same_stat_comparison import (
    ACTIVE_VETO_THRESHOLD_KEV,
    EVENT_CATALOG,
    OFFICIAL_RATES,
    WINDOWS,
    Hit,
    candidate_windows,
    event_hits,
    find_file,
    load_csv,
    now_utc,
    poisson_sigma_from_weights,
    side_entry_disk,
    side_keep_from_hits,
    summarize_stage,
    write_csv,
    write_json,
)


def init_stage() -> dict[str, Any]:
    return {"events": 0, "rate": 0.0, "sigma2": 0.0, "weights": [], "class_counts": Counter()}


def add_weight(stage: dict[str, Any], weight: float) -> None:
    stage["events"] += 1
    stage["rate"] += weight
    stage["sigma2"] += weight * weight
    stage["weights"].append(weight)


def ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def z_score(fluka: float, fsig: float, g4: float, gsig: float) -> float | None:
    den = math.sqrt(fsig * fsig + gsig * gsig)
    return None if den == 0 else (fluka - g4) / den


def load_g4_delayed(disk: dict[str, Any]) -> dict[str, Any]:
    with EVENT_CATALOG.open("rb") as f:
        cat = pickle.load(f)
    stream = np.asarray(cat["stream"], dtype=object)
    tes = np.asarray(cat["tes_total_keV"], dtype=float)
    bgo = np.asarray(cat["bgo_total_keV"], dtype=float)
    rate = np.asarray(cat["rate_hz"], dtype=float)
    base = stream == "delayed"
    details = {"histories": int(cat.get("n_generated_events_seen", 0)), "windows": {}}
    for window, (lo, hi) in WINDOWS.items():
        raw_mask = base & (tes >= lo) & (tes < hi)
        active_mask = raw_mask & (bgo < ACTIVE_VETO_THRESHOLD_KEV)
        final = init_stage()
        for idx in np.flatnonzero(active_mask):
            keep, cls = side_keep_from_hits(event_hits(cat, int(idx)), disk)
            final["class_counts"][cls] += 1
            if keep:
                add_weight(final, float(rate[idx]))
        details["windows"][window] = {
            "raw": {
                "events": int(np.count_nonzero(raw_mask)),
                "rate_s-1": float(np.sum(rate[raw_mask])),
                "mc_sigma_s-1": poisson_sigma_from_weights(rate[raw_mask]),
                "side_compton_class_counts": {},
            },
            "active_veto_pass": {
                "events": int(np.count_nonzero(active_mask)),
                "rate_s-1": float(np.sum(rate[active_mask])),
                "mc_sigma_s-1": poisson_sigma_from_weights(rate[active_mask]),
                "side_compton_class_counts": {},
            },
            "side_compton_fov_pass": summarize_stage(final),
        }
    return details


def official_delayed_rates() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    for row in load_csv(OFFICIAL_RATES):
        if row.get("stream") == "delayed":
            out[(row["window"], row["stage"])] = {"events": int(row["events"]), "rate_s-1": float(row["rate_s-1"])}
    return out


def validate_g4(details: dict[str, Any]) -> dict[str, Any]:
    rows = []
    ok = True
    for (window, stage), ref in official_delayed_rates().items():
        got = details["windows"][window][stage]
        event_delta = int(got["events"]) - int(ref["events"])
        rate_delta = float(got["rate_s-1"]) - float(ref["rate_s-1"])
        passed = event_delta == 0 and abs(rate_delta) <= max(1.0e-12, abs(ref["rate_s-1"]) * 1.0e-9)
        ok = ok and passed
        rows.append(
            {
                "window": window,
                "stage": stage,
                "official_events": ref["events"],
                "computed_events": got["events"],
                "event_delta": event_delta,
                "official_rate_s-1": ref["rate_s-1"],
                "computed_rate_s-1": got["rate_s-1"],
                "rate_delta_s-1": rate_delta,
                "status": "PASS" if passed else "FAIL",
            }
        )
    return {"status": "PASS" if ok else "FAIL", "checks": rows}


def load_source_weights(run_root: Path) -> tuple[dict[int, float], dict[int, str]]:
    weights: dict[int, float] = {}
    nuclide: dict[int, str] = {}
    with (run_root / "raw_events/delayed_sources.csv").open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = int(row["history_id"])
            weights[hid] = float(row["history_weight"])
            nuclide[hid] = row.get("nuclide", "")
    return weights, nuclide


def fluka_hits_for_candidates(run_root: Path, candidates: set[int]) -> dict[int, list[Hit]]:
    if not candidates:
        return {}
    deposits_path = find_file(run_root / "fluka_run", "raw_deposits_tmp.csv")
    by_history_region: dict[int, dict[str, dict[str, float]]] = defaultdict(dict)
    with deposits_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        for row in reader:
            if "TES" not in row[idx["detector_kind"]].upper():
                continue
            hid = int(row[idx["history_id"]])
            if hid not in candidates:
                continue
            region = row[idx["region_name"]].strip()
            e = float(row[idx["deposit_keV"]])
            if e <= 0:
                continue
            rec = by_history_region[hid].setdefault(region, {"e": 0.0, "wx": 0.0, "wy": 0.0, "wz": 0.0})
            rec["e"] += e
            rec["wx"] += e * float(row[idx["x_cm"]])
            rec["wy"] += e * float(row[idx["y_cm"]])
            rec["wz"] += e * float(row[idx["z_cm"]])
    out: dict[int, list[Hit]] = {}
    for hid, by_region in by_history_region.items():
        hits = []
        for region, rec in sorted(by_region.items()):
            e = rec["e"]
            hits.append(Hit(x=rec["wx"] / e, y=rec["wy"] / e, z=rec["wz"] / e, e=e, pixel_uid=region))
        out[hid] = hits
    return out


def load_fluka_delayed(run_root: Path, disk: dict[str, Any]) -> dict[str, Any]:
    weights, nuclides = load_source_weights(run_root)
    stages = {window: {"raw": init_stage(), "active_veto_pass": init_stage(), "side_compton_fov_pass": init_stage()} for window in WINDOWS}
    by_nuclide = defaultdict(lambda: {window: {"raw": init_stage(), "active_veto_pass": init_stage(), "side_compton_fov_pass": init_stage()} for window in WINDOWS})
    active_candidates: dict[int, list[str]] = {}
    totals_path = find_file(run_root / "fluka_run", "event_totals_tmp.csv")
    with totals_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        for row in reader:
            hid = int(row[idx["history_id"]])
            weight = weights.get(hid, 0.0)
            nuclide = nuclides.get(hid, "")
            raw_windows, active_windows = candidate_windows(float(row[idx["tes_total_keV"]]), float(row[idx["shield_total_keV"]]))
            for window in raw_windows:
                add_weight(stages[window]["raw"], weight)
                add_weight(by_nuclide[nuclide][window]["raw"], weight)
            for window in active_windows:
                add_weight(stages[window]["active_veto_pass"], weight)
                add_weight(by_nuclide[nuclide][window]["active_veto_pass"], weight)
                active_candidates.setdefault(hid, []).append(window)

    hits_by_history = fluka_hits_for_candidates(run_root, set(active_candidates))
    for hid, windows in active_candidates.items():
        hits = hits_by_history.get(hid, [])
        if not hits:
            keep, cls = False, "missing_tes_hits"
        else:
            keep, cls = side_keep_from_hits(hits, disk)
        nuclide = nuclides.get(hid, "")
        for window in windows:
            stages[window]["side_compton_fov_pass"]["class_counts"][cls] += 1
            by_nuclide[nuclide][window]["side_compton_fov_pass"]["class_counts"][cls] += 1
            if keep:
                weight = weights.get(hid, 0.0)
                add_weight(stages[window]["side_compton_fov_pass"], weight)
                add_weight(by_nuclide[nuclide][window]["side_compton_fov_pass"], weight)

    return {
        "histories": len(weights),
        "source_activity_Bq": sum(weights.values()),
        "windows": {window: {stage: summarize_stage(stages[window][stage]) for stage in stages[window]} for window in WINDOWS},
        "by_nuclide": {
            nuc: {window: {stage: summarize_stage(payload[window][stage]) for stage in payload[window]} for window in WINDOWS}
            for nuc, payload in sorted(by_nuclide.items())
        },
    }


def comparison_rows(g4: dict[str, Any], fluka: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for window in WINDOWS:
        for stage in ("raw", "active_veto_pass", "side_compton_fov_pass"):
            g = g4["windows"][window][stage]
            f = fluka["windows"][window][stage]
            rows.append(
                {
                    "window": window,
                    "stage": stage,
                    "g4_events": g["events"],
                    "g4_rate_s-1": g["rate_s-1"],
                    "g4_sigma_s-1": g["mc_sigma_s-1"],
                    "fluka_events": f["events"],
                    "fluka_rate_s-1": f["rate_s-1"],
                    "fluka_sigma_s-1": f["mc_sigma_s-1"],
                    "fluka_over_g4": ratio(float(f["rate_s-1"]), float(g["rate_s-1"])),
                    "z": z_score(float(f["rate_s-1"]), float(f["mc_sigma_s-1"]), float(g["rate_s-1"]), float(g["mc_sigma_s-1"])),
                    "fluka_class_counts": json.dumps(f.get("side_compton_class_counts", {}), sort_keys=True),
                }
            )
    return rows


def render(payload: dict[str, Any], rows: list[dict[str, object]]) -> str:
    lines = [
        "# Delayed Isotope Source Step05 Same-Statistic Comparison",
        "",
        f"- status: `{payload['status']}`",
        f"- source_mode: `{payload['source_mode']}`",
        f"- no `.sim.gz` replay: `{payload['no_sim_gz_replay']}`",
        f"- fluka_histories: `{payload['fluka']['histories']}`",
        f"- fluka_source_activity_Bq: `{payload['fluka']['source_activity_Bq']:.12g}`",
        f"- g4_step05_validation: `{payload['g4_validation']['status']}`",
        "",
        "| window | stage | G4 events/rate | FLUKA events/rate | FLUKA/G4 | z |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {window} | {stage} | {ge} / {gr:.7g} | {fe} / {fr:.7g} | {ratio} | {z} |".format(
                window=row["window"],
                stage=row["stage"],
                ge=row["g4_events"],
                gr=float(row["g4_rate_s-1"]),
                fe=row["fluka_events"],
                fr=float(row["fluka_rate_s-1"]),
                ratio="" if row["fluka_over_g4"] is None else f"{float(row['fluka_over_g4']):.4g}",
                z="" if row["z"] is None else f"{float(row['z']):.3g}",
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fluka-run", type=Path, default=Path("work_fluka_harness/delayed_isotope_source_pilot1000"))
    ap.add_argument("--out-dir", type=Path, default=Path("work_fluka_harness/delayed_final_same_stat_isotope_source_pilot1000"))
    args = ap.parse_args()
    disk = side_entry_disk()
    g4 = load_g4_delayed(disk)
    validation = validate_g4(g4)
    if validation["status"] != "PASS":
        raise SystemExit("G4 delayed Step05 validation failed")
    fluka = load_fluka_delayed(args.fluka_run, disk)
    rows = comparison_rows(g4, fluka)
    payload = {
        "created_utc": now_utc(),
        "status": "DELAYED_ISOTOPE_SOURCE_SAME_STAT_PRESENT",
        "source_mode": "delayed_source_v2_weighted_exact_position_isotope_eventlist",
        "no_sim_gz_replay": True,
        "inputs": {"fluka_run": str(args.fluka_run), "event_catalog": str(EVENT_CATALOG), "official_rates": str(OFFICIAL_RATES)},
        "g4_validation": validation,
        "g4": g4,
        "fluka": fluka,
        "comparison_rows": rows,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "summary.json", payload)
    write_csv(args.out_dir / "same_stat_comparison.csv", rows, list(rows[0].keys()))
    write_csv(args.out_dir / "g4_step05_validation.csv", validation["checks"], list(validation["checks"][0].keys()))
    (args.out_dir / "summary.md").write_text(render(payload, rows), encoding="utf-8")
    print(args.out_dir / "summary.md")
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
