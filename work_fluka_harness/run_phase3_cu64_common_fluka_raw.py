#!/usr/bin/env python3
"""Run FLUKA raw deposits from the Phase-3 common Cu-64 parent list."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

from run_delayed_isotope_raw_mvp import (
    build_delayed_raw_events,
    compile_delayed_executable,
    delayed_input,
    find_file,
    load_region_crosswalk,
    now_utc,
    parse_event_totals,
    rows_from_csv,
    run,
    sha256_path,
    write_csv,
    write_isotopes_dat,
    write_json,
)
from run_eplus_raw_mvp import RAW_EVENT_FIELDS, closure_from_outputs
import build_raw_scoring_smoke as scoring


ROOT = Path(__file__).resolve().parents[1]
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_PARENT_LIST = PHASE3_DIR / "full_untracked/cu64_parent_resampling_1e6.csv"
DEFAULT_PARENT_SAMPLE = PHASE3_DIR / "cu64_parent_resampling_sample.csv"
DEFAULT_OUT = PHASE3_DIR / "fluka_cu64_common_raw_smoke"
RFLUKA = scoring.RFLUKA

BANDS = [
    ("all_tes_gt0", "all TES > 0", 0.0, float("inf")),
    ("e480_550", "480-550 keV", 480.0, 550.0),
    ("w2_510p58_511p42", "W2 510.58-511.42 keV", 510.58, 511.42),
    ("e1500_3000", "1500-3000 keV", 1500.0, 3000.0),
    ("e3000_10000", "3000-10000 keV", 3000.0, 10000.0),
]


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def source_rows_from_parent_list(path: Path, max_events: int | None, start_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in rows_from_csv(path):
        parent_history_id = int(row["resampled_history_id"])
        if parent_history_id < start_index:
            continue
        rows.append(
            {
                **row,
                "history_id": len(rows) + 1,
                "parent_resampled_history_id": parent_history_id,
                "event_id": row["common_event_id"],
                "nuclide": "Cu-64",
                "source_name": f"phase3_cu64_common_parent_{parent_history_id:09d}",
                "isotope_Z": 29,
                "isotope_A": 64,
                "isomer": 0,
                "dx": 0.0,
                "dy": 0.0,
                "dz": 1.0,
                "time_s": 0.0,
                "history_weight": 1.0,
                "event_weight_Bq": row.get("original_activity_weight_Bq", ""),
                "key_activity_Bq": row.get("original_activity_weight_Bq", ""),
                "key_rpip_count": "",
                "raw_volume": row.get("source_volume", ""),
            }
        )
        if max_events is not None and len(rows) >= max_events:
            break
    if not rows:
        raise ValueError("no Phase-3 Cu-64 parent rows selected")
    return rows


def source_csv_fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "history_id",
        "parent_resampled_history_id",
        "selected_position_row_index",
        "common_event_id",
        "source_event_id",
        "source_name",
        "production_tag",
        "source_volume",
        "resolved_static_material",
        "nuclide",
        "isotope_Z",
        "isotope_A",
        "isomer",
        "x_cm",
        "y_cm",
        "z_cm",
        "dx",
        "dy",
        "dz",
        "time_s",
        "history_weight",
        "event_weight_Bq",
        "sampling_probability",
        "selection_u64",
    ]
    rest = sorted(set().union(*(row.keys() for row in rows)) - set(preferred))
    return preferred + rest


def event_total_summaries(totals_path: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, float]]]:
    totals = parse_event_totals(totals_path)
    rows = []
    for history_id, vals in sorted(totals.items()):
        rows.append(
            {
                "history_id": history_id,
                "tes_total_keV": vals["tes_total_keV"],
                "shield_total_keV": vals["shield_total_keV"],
            }
        )
    return rows, totals


def band_summary(sources: list[dict[str, Any]], totals: dict[int, dict[str, float]]) -> list[dict[str, Any]]:
    src_by_history = {int(row["history_id"]): row for row in sources}
    out = []
    for band, label, lo, hi in BANDS:
        matched = []
        material_counts: Counter[str] = Counter()
        volume_counts: Counter[str] = Counter()
        for history_id, vals in totals.items():
            tes = vals["tes_total_keV"]
            if (lo == 0.0 and tes > 0.0) or (lo != 0.0 and lo <= tes < hi):
                matched.append(history_id)
                src = src_by_history[history_id]
                material_counts[str(src["resolved_static_material"])] += 1
                volume_counts[str(src["source_volume"])] += 1
        out.append(
            {
                "band": band,
                "band_label": label,
                "histories": len(sources),
                "events": len(matched),
                "efficiency_per_parent": len(matched) / len(sources) if sources else 0.0,
                "top_material_counts": json.dumps(dict(material_counts.most_common(5)), sort_keys=True),
                "top_source_volume_counts": json.dumps(dict(volume_counts.most_common(5)), sort_keys=True),
            }
        )
    return out


def sample_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(0, limit)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-list", type=Path, default=DEFAULT_PARENT_LIST)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=24066800)
    ap.add_argument("--max-events", type=int, default=1000)
    ap.add_argument("--start-index", type=int, default=1)
    ap.add_argument("--reuse-executable", action="store_true")
    ap.add_argument("--sample-rows", type=int, default=1000)
    args = ap.parse_args()

    parent_list = args.parent_list.expanduser().resolve()
    if not parent_list.exists() and parent_list == DEFAULT_PARENT_LIST.resolve():
        parent_list = DEFAULT_PARENT_SAMPLE.resolve()
    if not parent_list.exists():
        raise SystemExit(f"parent list does not exist: {parent_list}")
    if args.max_events is not None and args.max_events < 1:
        raise SystemExit("max-events must be positive")
    if args.start_index < 1:
        raise SystemExit("start-index must be >= 1")

    out_dir = args.out_dir.expanduser().resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    raw_dir = out_dir / "raw_events"
    fluka_dir = out_dir / "fluka_run"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fluka_dir.mkdir(parents=True, exist_ok=True)

    sources = source_rows_from_parent_list(parent_list, args.max_events, args.start_index)
    run_id = f"phase3_cu64_common_fluka_seed{args.seed}_n{len(sources)}"
    write_csv(raw_dir / "phase3_cu64_common_sources.csv", sources, source_csv_fields(sources))
    write_isotopes_dat(fluka_dir / "isotopes.dat", sources)

    exe = out_dir / "scoring_routines/fluka_delayed_raw"
    if not (args.reuse_executable and exe.exists()):
        exe = compile_delayed_executable(out_dir)

    input_stem = "phase3_cu64_common_raw"
    input_path = fluka_dir / f"{input_stem}.inp"
    input_path.write_text(
        delayed_input("TES511 Phase3 Cu64 common raw", len(sources), args.seed),
        encoding="ascii",
    )

    started = now_utc()
    t0 = time.time()
    returncode = run([str(RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", input_stem], fluka_dir, fluka_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()
    if returncode != 0:
        write_json(
            out_dir / "summary.json",
            {
                "status": "PHASE3_CU64_COMMON_FLUKA_RAW_FAILED",
                "returncode": returncode,
                "histories": len(sources),
                "rfluka_log": str(fluka_dir / "rfluka.log"),
            },
        )
        return 2

    deposits_file = find_file(fluka_dir, "raw_deposits_tmp.csv")
    totals_file = find_file(fluka_dir, "event_totals_tmp.csv")
    raw_events = build_delayed_raw_events(deposits_file, totals_file, sources, run_id, args.seed)
    write_csv(raw_dir / "raw_events.csv", raw_events, RAW_EVENT_FIELDS)

    _, region_kind = load_region_crosswalk()
    closure = closure_from_outputs(fluka_dir, raw_events, len(sources), float(len(sources)), region_kind, input_stem)
    closure.update(
        {
            "raw_deposits_file": str(deposits_file),
            "event_totals_file": str(totals_file),
            "raw_event_rows": len(raw_events),
            "created_at_utc": now_utc(),
        }
    )
    write_json(out_dir / "scoring_closure.json", closure)

    total_rows, totals = event_total_summaries(totals_file)
    bands = band_summary(sources, totals)
    write_csv(out_dir / "event_total_sample.csv", sample_rows(total_rows, args.sample_rows), ["history_id", "tes_total_keV", "shield_total_keV"])
    write_csv(
        out_dir / "raw_event_sample.csv",
        sample_rows(raw_events, args.sample_rows),
        RAW_EVENT_FIELDS,
    )
    write_csv(
        out_dir / "band_summary.csv",
        bands,
        ["band", "band_label", "histories", "events", "efficiency_per_parent", "top_material_counts", "top_source_volume_counts"],
    )

    manifest = {
        "run_id": run_id,
        "histories": len(sources),
        "seed": args.seed,
        "returncode": returncode,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "elapsed_s": elapsed_s,
        "fluka_executable": str(exe),
        "fluka_executable_sha256": sha256_path(exe),
        "input": str(input_path),
        "input_sha256": sha256_path(input_path),
        "source_mode": "phase3_cu64_common_parent_resampling",
        "parent_list": str(parent_list),
        "parent_list_sha256": sha256_path(parent_list),
        "no_sim_gz_replay": True,
        "raw_deposits_file": str(deposits_file),
        "event_totals_file": str(totals_file),
        "scoring_closure_status": closure["status"],
    }
    write_csv(out_dir / "run_manifest.csv", [manifest], list(manifest.keys()))

    status = "PHASE3_CU64_COMMON_FLUKA_RAW_PASS" if closure["status"] == "PASS" else "BLOCKED_PHASE3_CU64_COMMON_SCORING_CLOSURE"
    summary = {
        "status": status,
        "source_mode": "phase3_cu64_common_parent_resampling",
        "no_sim_gz_replay": True,
        "transport_code": "FLUKA",
        "histories": len(sources),
        "seed": args.seed,
        "parent_list": rel(parent_list),
        "parent_list_sha256": sha256_path(parent_list),
        "raw_event_rows": len(raw_events),
        "raw_events_csv": str(raw_dir / "raw_events.csv"),
        "sources_csv": str(raw_dir / "phase3_cu64_common_sources.csv"),
        "run_manifest": str(out_dir / "run_manifest.csv"),
        "band_summary_csv": str(out_dir / "band_summary.csv"),
        "raw_event_sample_csv": str(out_dir / "raw_event_sample.csv"),
        "event_total_sample_csv": str(out_dir / "event_total_sample.csv"),
        "scoring_closure": closure,
        "band_summary": bands,
        "boundary": "FLUKA-only Phase-3 common Cu-64 raw-deposit run; MEGAlib side and common event builder remain open",
    }
    write_json(out_dir / "summary.json", summary)
    band_lines = [
        "## Smoke Band Counts",
        "",
        "| band | events / histories | efficiency_per_parent | top_material_counts |",
        "|---|---:|---:|---|",
    ]
    for row in bands:
        band_lines.append(
            f"| `{row['band_label']}` | `{row['events']} / {row['histories']}` | "
            f"`{row['efficiency_per_parent']:.6g}` | `{row['top_material_counts']}` |"
        )
    (out_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Phase-3 Cu-64 Common FLUKA Raw-Deposit Run",
                "",
                f"- status: `{status}`",
                "- source_mode: `phase3_cu64_common_parent_resampling`",
                "- no `.sim.gz` replay: `True`",
                f"- histories: `{len(sources)}`",
                f"- raw_event_rows: `{len(raw_events)}`",
                f"- scoring_closure: `{closure['status']}`",
                f"- elapsed_s: `{elapsed_s:.3f}`",
                f"- band_summary_csv: `{rel(out_dir / 'band_summary.csv')}`",
                "",
                *band_lines,
                "",
                "## Scoring Closure",
                "",
                f"- raw_dump_tes_total_keV: `{closure['raw_dump_tes_total_keV']}`",
                f"- score_tes_total_keV: `{closure['score_tes_total_keV']}`",
                f"- tes_relative_delta: `{closure['tes_relative_delta']}`",
                f"- raw_dump_shield_total_keV: `{closure['raw_dump_shield_total_keV']}`",
                f"- score_shield_total_keV: `{closure['score_shield_total_keV']}`",
                f"- shield_relative_delta: `{closure['shield_relative_delta']}`",
                "",
                "## Boundary",
                "",
                "- This is the FLUKA side only.",
                "- It validates full-geometry raw-deposit plumbing for the Phase-3 common Cu-64 parent stream.",
                "- MEGAlib transport, common event building, and production-statistics closure remain open.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(out_dir / "summary.md")
    print(status)
    return 0 if status == "PHASE3_CU64_COMMON_FLUKA_RAW_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
