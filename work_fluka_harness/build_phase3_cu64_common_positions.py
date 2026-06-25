#!/usr/bin/env python3
"""Build the Phase-3 Cu-64 common full-geometry source-position authority."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any


getcontext().prec = 80

ROOT = Path(__file__).resolve().parents[1]
TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
DEFAULT_SOURCE = (
    TES_ROOT
    / "engineering/delayed_source_authority_v2_20260624"
    / "04_custom_source_v2/delayed_position_weights_v2.csv"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "03_full_geometry_same_source"
)

FIELDS = [
    "common_event_id",
    "source_event_id",
    "source_name",
    "production_tag",
    "Z",
    "A",
    "isomer",
    "x_cm",
    "y_cm",
    "z_cm",
    "source_volume",
    "source_material",
    "canonical_volume_for_reporting_only",
    "original_activity_weight_Bq",
    "sampling_probability",
    "nuclide",
    "state_id",
    "exc_keV_decimal",
    "point_index_within_key",
    "key_activity_Bq",
    "key_rpip_count",
    "event_weight_Bq",
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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def parse_za(za_text: str) -> tuple[int, int]:
    value = int(za_text)
    return value // 1000, value % 1000


def isomer_from_state(state_id: str, exc_keV_decimal: str) -> int:
    if state_id == "gs" or Decimal(exc_keV_decimal or "0") == 0:
        return 0
    return 1


def build_rows(source: Path) -> list[dict[str, Any]]:
    selected: list[dict[str, str]] = []
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["nuclide"] == "Cu-64":
                selected.append(row)
    if not selected:
        raise SystemExit(f"no Cu-64 rows found in {source}")

    total_weight = sum(Decimal(row["event_weight_Bq"]) for row in selected)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=1):
        z, a = parse_za(row["ZA"])
        weight = Decimal(row["event_weight_Bq"])
        rows.append(
            {
                "common_event_id": idx,
                "source_event_id": row["event_id"],
                "source_name": row["source_name"],
                "production_tag": row["production_tag"],
                "Z": z,
                "A": a,
                "isomer": isomer_from_state(row["state_id"], row["exc_keV_decimal"]),
                "x_cm": row["x_cm"],
                "y_cm": row["y_cm"],
                "z_cm": row["z_cm"],
                "source_volume": row["raw_volume"],
                "source_material": "PENDING_REGION_AUDIT",
                "canonical_volume_for_reporting_only": row["canonical_volume_for_reporting_only"],
                "original_activity_weight_Bq": str(weight),
                "sampling_probability": str(weight / total_weight),
                "nuclide": row["nuclide"],
                "state_id": row["state_id"],
                "exc_keV_decimal": row["exc_keV_decimal"],
                "point_index_within_key": row["point_index_within_key"],
                "key_activity_Bq": row["key_activity_Bq"],
                "key_rpip_count": row["key_rpip_count"],
                "event_weight_Bq": row["event_weight_Bq"],
            }
        )
    return rows


def volume_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(str(row["source_volume"]) for row in rows)
    weights: dict[str, Decimal] = {}
    for row in rows:
        volume = str(row["source_volume"])
        weights[volume] = weights.get(volume, Decimal("0")) + Decimal(str(row["original_activity_weight_Bq"]))
    total = sum(weights.values())
    return [
        {
            "source_volume": volume,
            "rows": counts[volume],
            "activity_weight_Bq": str(weights[volume]),
            "activity_fraction": str(weights[volume] / total if total else Decimal("0")),
        }
        for volume in sorted(counts, key=lambda item: (-weights[item], item))
    ]


def write_summary_md(out_dir: Path, summary: dict[str, Any]) -> None:
    md = [
        "# Phase-3 Cu-64 Common Positions",
        "",
        f"- status: `{summary['status']}`",
        f"- rows: `{summary['rows']}`",
        f"- total_activity_weight_Bq: `{summary['total_activity_weight_Bq']}`",
        f"- source_csv: `{summary['source_csv']}`",
        f"- output_csv: `{summary['output_csv']}`",
        f"- volume_summary_csv: `{summary['volume_summary_csv']}`",
        "",
        "## Production Tags",
        "",
        "| production_tag | rows | activity_weight_Bq |",
        "|---|---:|---:|",
    ]
    for row in summary["production_tag_summary"]:
        md.append(f"| `{row['production_tag']}` | `{row['rows']}` | `{row['activity_weight_Bq']}` |")
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a source-position authority only; it does not resolve final Geant4 logical volume or FLUKA region/material.",
            "- `source_material` is intentionally `PENDING_REGION_AUDIT` and must be replaced by the Phase-3 region/material audit.",
            "- `sampling_probability` is normalized over Cu-64 rows only and is suitable for deterministic Cu-64 parent resampling.",
            "",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    source = args.source.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = build_rows(source)
    output_csv = out_dir / "cu64_common_positions.csv"
    volume_csv = out_dir / "cu64_common_position_volume_summary.csv"
    write_csv(output_csv, rows, FIELDS)
    volume_rows = volume_summary(rows)
    write_csv(volume_csv, volume_rows, ["source_volume", "rows", "activity_weight_Bq", "activity_fraction"])

    tag_summary: list[dict[str, Any]] = []
    for tag in sorted({str(row["production_tag"]) for row in rows}):
        tag_rows = [row for row in rows if row["production_tag"] == tag]
        tag_weight = sum(Decimal(str(row["original_activity_weight_Bq"])) for row in tag_rows)
        tag_summary.append({"production_tag": tag, "rows": len(tag_rows), "activity_weight_Bq": str(tag_weight)})

    total_weight = sum(Decimal(str(row["original_activity_weight_Bq"])) for row in rows)
    prob_sum = sum(Decimal(str(row["sampling_probability"])) for row in rows)
    summary = {
        "status": "CU64_COMMON_POSITIONS_COMPLETE",
        "source_csv": rel(source),
        "source_sha256": sha256_path(source),
        "output_csv": rel(output_csv),
        "output_sha256": sha256_path(output_csv),
        "volume_summary_csv": rel(volume_csv),
        "volume_summary_sha256": sha256_path(volume_csv),
        "rows": len(rows),
        "Z": 29,
        "A": 64,
        "isomer_values": sorted({int(row["isomer"]) for row in rows}),
        "total_activity_weight_Bq": str(total_weight),
        "sampling_probability_sum": str(prob_sum),
        "production_tag_summary": tag_summary,
        "top_source_volumes": volume_rows[:20],
        "source_material_policy": "PENDING_REGION_AUDIT",
    }
    write_json(out_dir / "summary.json", summary)
    write_summary_md(out_dir, summary)
    print(json.dumps({"status": summary["status"], "rows": len(rows), "out_dir": rel(out_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
