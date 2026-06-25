#!/usr/bin/env python3
"""Build the deterministic Phase-3 Cu-64 parent resampling authority."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any


getcontext().prec = 80

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "03_full_geometry_same_source/cu64_common_positions.csv"
)
DEFAULT_COORD_AUDIT = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "03_full_geometry_same_source/cu64_source_coordinate_containment_audit.csv"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "03_full_geometry_same_source"
)

FULL_FIELDS = [
    "resampled_history_id",
    "selected_position_row_index",
    "common_event_id",
    "source_event_id",
    "production_tag",
    "Z",
    "A",
    "isomer",
    "x_cm",
    "y_cm",
    "z_cm",
    "source_volume",
    "resolved_static_material",
    "original_activity_weight_Bq",
    "sampling_probability",
    "selection_u64",
]


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def selection_u64(seed: str, history_id: int) -> int:
    payload = f"phase3-cu64-parent-resampling-v1|{seed}|{history_id}\n".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def load_positions(positions_path: Path, coordinate_audit_path: Path) -> list[dict[str, str]]:
    materials = {
        row["common_event_id"]: row["resolved_static_material"]
        for row in read_csv(coordinate_audit_path)
    }
    rows = read_csv(positions_path)
    for idx, row in enumerate(rows, start=1):
        row["selected_position_row_index"] = str(idx)
        row["resolved_static_material"] = materials.get(row["common_event_id"], "")
        if row["Z"] != "29" or row["A"] != "64" or row["isomer"] != "0":
            raise ValueError(f"non-Cu64 row in {positions_path}: common_event_id={row['common_event_id']}")
    return rows


def build_cdf(rows: list[dict[str, str]]) -> list[float]:
    cumulative: list[float] = []
    total = 0.0
    for row in rows:
        total += float(row["sampling_probability"])
        cumulative.append(total)
    if not cumulative:
        raise ValueError("no source positions")
    cumulative[-1] = 1.0
    return cumulative


def full_row(history_id: int, selected: dict[str, str], u64: int) -> dict[str, Any]:
    return {
        "resampled_history_id": history_id,
        "selected_position_row_index": selected["selected_position_row_index"],
        "common_event_id": selected["common_event_id"],
        "source_event_id": selected["source_event_id"],
        "production_tag": selected["production_tag"],
        "Z": selected["Z"],
        "A": selected["A"],
        "isomer": selected["isomer"],
        "x_cm": selected["x_cm"],
        "y_cm": selected["y_cm"],
        "z_cm": selected["z_cm"],
        "source_volume": selected["source_volume"],
        "resolved_static_material": selected["resolved_static_material"],
        "original_activity_weight_Bq": selected["original_activity_weight_Bq"],
        "sampling_probability": selected["sampling_probability"],
        "selection_u64": str(u64),
    }


def canonical_line(row: dict[str, Any]) -> str:
    return ",".join(str(row[field]) for field in FULL_FIELDS) + "\n"


def aggregate_counts(rows: list[dict[str, str]], counts: Counter[int], key: str) -> list[dict[str, Any]]:
    grouped_counts: Counter[str] = Counter()
    grouped_weight: dict[str, Decimal] = {}
    total_count = sum(counts.values())
    for idx, count in counts.items():
        row = rows[idx]
        value = row[key]
        grouped_counts[value] += count
        grouped_weight[value] = grouped_weight.get(value, Decimal("0")) + Decimal(str(row["original_activity_weight_Bq"]))
    return [
        {
            key: value,
            "selected_histories": grouped_counts[value],
            "selection_fraction": grouped_counts[value] / total_count if total_count else 0.0,
            "source_rows_represented_activity_Bq": str(grouped_weight[value]),
        }
        for value in sorted(grouped_counts, key=lambda item: (-grouped_counts[item], item))
    ]


def write_summary_md(out_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Parent Resampling Authority",
        "",
        f"- status: `{summary['status']}`",
        f"- histories: `{summary['histories']}`",
        f"- seed: `{summary['seed']}`",
        f"- selected_unique_positions: `{summary['selected_unique_positions']}`",
        f"- selection_stream_sha256: `{summary['selection_stream_sha256']}`",
        f"- full_list_written: `{summary['full_list_written']}`",
        f"- full_list_csv: `{summary['full_list_csv']}`",
        f"- full_list_csv_sha256: `{summary['full_list_csv_sha256']}`",
        "",
        "## Boundary",
        "",
        "- This is a deterministic parent-index resampling authority for Phase-3 common Cu-64 runs.",
        "- The full list is reproducible from `cu64_common_positions.csv`, this script, the seed, and `histories`.",
        "- The full 1e6-row CSV is intentionally written under ignored `full_untracked/`; git keeps only hashes, summaries, and a bounded sample.",
        "- This does not run FLUKA or MEGAlib transport.",
        "",
    ]
    (out_dir / "cu64_parent_resampling_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    ap.add_argument("--coordinate-audit", type=Path, default=DEFAULT_COORD_AUDIT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--histories", type=int, default=1_000_000)
    ap.add_argument("--seed", default="20260625_phase3_cu64")
    ap.add_argument("--sample-rows", type=int, default=1000)
    ap.add_argument("--write-full-list", action="store_true")
    args = ap.parse_args()

    if args.histories < 1:
        raise SystemExit("histories must be positive")
    if args.sample_rows < 0:
        raise SystemExit("sample-rows must be non-negative")

    positions_path = args.positions.expanduser().resolve()
    coordinate_audit_path = args.coordinate_audit.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    positions = load_positions(positions_path, coordinate_audit_path)
    cdf = build_cdf(positions)
    counts: Counter[int] = Counter()
    sample: list[dict[str, Any]] = []
    stream_hash = hashlib.sha256()

    full_path = out_dir / "full_untracked/cu64_parent_resampling_1e6.csv"
    full_handle = None
    full_writer = None
    if args.write_full_list:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_handle = full_path.open("w", newline="", encoding="utf-8")
        full_writer = csv.DictWriter(full_handle, fieldnames=FULL_FIELDS, lineterminator="\n")
        full_writer.writeheader()

    try:
        for history_id in range(1, args.histories + 1):
            u64 = selection_u64(args.seed, history_id)
            u = (u64 + 0.5) / 18446744073709551616.0
            idx = bisect.bisect_left(cdf, u)
            if idx >= len(positions):
                idx = len(positions) - 1
            selected = positions[idx]
            counts[idx] += 1
            row = full_row(history_id, selected, u64)
            stream_hash.update(canonical_line(row).encode("utf-8"))
            if len(sample) < args.sample_rows:
                sample.append(row)
            if full_writer is not None:
                full_writer.writerow(row)
    finally:
        if full_handle is not None:
            full_handle.close()

    sample_csv = out_dir / "cu64_parent_resampling_sample.csv"
    volume_csv = out_dir / "cu64_parent_resampling_volume_summary.csv"
    material_csv = out_dir / "cu64_parent_resampling_material_summary.csv"
    write_csv(sample_csv, sample, FULL_FIELDS)
    volume_rows = aggregate_counts(positions, counts, "source_volume")
    material_rows = aggregate_counts(positions, counts, "resolved_static_material")
    write_csv(volume_csv, volume_rows, ["source_volume", "selected_histories", "selection_fraction", "source_rows_represented_activity_Bq"])
    write_csv(material_csv, material_rows, ["resolved_static_material", "selected_histories", "selection_fraction", "source_rows_represented_activity_Bq"])

    full_written = bool(args.write_full_list)
    summary = {
        "status": "CU64_PARENT_RESAMPLING_AUTHORITY_COMPLETE",
        "histories": args.histories,
        "seed": args.seed,
        "algorithm": "counter-based SHA256 u64: sha256('phase3-cu64-parent-resampling-v1|{seed}|{history_id}\\n') first 8 bytes big-endian; bisect on sampling_probability CDF",
        "positions_csv": rel(positions_path),
        "positions_sha256": sha256_path(positions_path),
        "coordinate_audit_csv": rel(coordinate_audit_path),
        "coordinate_audit_sha256": sha256_path(coordinate_audit_path),
        "source_position_rows": len(positions),
        "selected_unique_positions": len(counts),
        "selection_stream_sha256": stream_hash.hexdigest(),
        "full_list_written": full_written,
        "full_list_csv": rel(full_path) if full_written else "",
        "full_list_csv_sha256": sha256_path(full_path) if full_written else "",
        "sample_csv": rel(sample_csv),
        "sample_csv_sha256": sha256_path(sample_csv),
        "volume_summary_csv": rel(volume_csv),
        "volume_summary_sha256": sha256_path(volume_csv),
        "material_summary_csv": rel(material_csv),
        "material_summary_sha256": sha256_path(material_csv),
        "top_volume_summary": volume_rows[:20],
        "material_summary": material_rows,
        "no_sim_gz_replay": True,
        "transport_run_performed": False,
        "boundary": "parent resampling authority only; full transport and raw deposits remain open",
    }
    write_json(out_dir / "cu64_parent_resampling_summary.json", summary)
    write_summary_md(out_dir, summary)
    print(json.dumps({"status": summary["status"], "histories": args.histories, "selected_unique_positions": len(counts), "out_dir": rel(out_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
