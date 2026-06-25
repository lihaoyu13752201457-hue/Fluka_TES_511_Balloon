#!/usr/bin/env python3
"""Build the Phase-3 name-level source region/material audit for Cu-64 positions."""

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
DEFAULT_POSITIONS = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "03_full_geometry_same_source/cu64_common_positions.csv"
)
DEFAULT_REGION_MAP = (
    Path("/home/ubuntu/TES_511_Balloon")
    / "engineering/fluka_crosscode_validation_20260624"
    / "02_geometry_translation/region_map.csv"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "03_full_geometry_same_source"
)

AUDIT_FIELDS = [
    "common_event_id",
    "source_event_id",
    "production_tag",
    "x_cm",
    "y_cm",
    "z_cm",
    "source_volume",
    "canonical_volume_for_reporting_only",
    "canonical_differs_from_source_volume",
    "geant4_logical_volume_name_authority",
    "fluka_region_name",
    "material",
    "fluka_material",
    "translation_status",
    "critical_flag",
    "original_activity_weight_Bq",
    "audit_status",
    "audit_note",
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
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def build_region_lookup(region_map: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(region_map)
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        name = row["source_volume_name"]
        if name not in lookup:
            lookup[name] = row
    return lookup


def audit_rows(positions: list[dict[str, str]], region_lookup: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in positions:
        source_volume = row["source_volume"]
        mapped = region_lookup.get(source_volume)
        canonical_differs = row["canonical_volume_for_reporting_only"] != source_volume
        if mapped is None:
            status = "FAIL_MISSING_REGION_MAP"
            note = "source_volume is absent from FLUKA translation region_map"
            mapped = {}
        elif not mapped.get("translation_status", "").startswith("TRANSLATED"):
            status = "FAIL_NOT_TRANSLATED"
            note = "source_volume exists but is not marked translated"
        else:
            status = "PASS_NAME_LEVEL"
            note = "source_volume maps to translated FLUKA region/material by name; coordinate containment is not tested here"
        audited.append(
            {
                "common_event_id": row["common_event_id"],
                "source_event_id": row["source_event_id"],
                "production_tag": row["production_tag"],
                "x_cm": row["x_cm"],
                "y_cm": row["y_cm"],
                "z_cm": row["z_cm"],
                "source_volume": source_volume,
                "canonical_volume_for_reporting_only": row["canonical_volume_for_reporting_only"],
                "canonical_differs_from_source_volume": str(canonical_differs),
                "geant4_logical_volume_name_authority": mapped.get("logical_volume_name", source_volume),
                "fluka_region_name": mapped.get("fluka_region_name", ""),
                "material": mapped.get("material", ""),
                "fluka_material": mapped.get("fluka_material", ""),
                "translation_status": mapped.get("translation_status", ""),
                "critical_flag": mapped.get("critical_flag", ""),
                "original_activity_weight_Bq": row["original_activity_weight_Bq"],
                "audit_status": status,
                "audit_note": note,
            }
        )
    return audited


def aggregate_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter(str(row[key]) for row in rows)
    weights: dict[str, Decimal] = {}
    for row in rows:
        value = str(row[key])
        weights[value] = weights.get(value, Decimal("0")) + Decimal(str(row["original_activity_weight_Bq"]))
    total = sum(weights.values())
    return [
        {
            key: value,
            "rows": counts[value],
            "activity_weight_Bq": str(weights[value]),
            "activity_fraction": str(weights[value] / total if total else Decimal("0")),
        }
        for value in sorted(counts, key=lambda item: (-weights[item], item))
    ]


def write_summary_md(out_dir: Path, summary: dict[str, Any]) -> None:
    md = [
        "# Phase-3 Cu-64 Source Region/Material Name Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- rows: `{summary['rows']}`",
        f"- pass_name_level_rows: `{summary['pass_name_level_rows']}`",
        f"- missing_region_map_rows: `{summary['missing_region_map_rows']}`",
        f"- coordinate_containment_tested: `{summary['coordinate_containment_tested']}`",
        f"- audit_csv: `{summary['audit_csv']}`",
        "",
        "## Material Summary",
        "",
        "| material | rows | activity_weight_Bq | activity_fraction |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["material_summary"]:
        md.append(
            f"| `{row['material']}` | `{row['rows']}` | `{row['activity_weight_Bq']}` | `{row['activity_fraction']}` |"
        )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- This audit checks source-volume name mapping against the FLUKA translation `region_map.csv`.",
            "- It does not test coordinate containment, nearest-boundary distance, or runtime Geant4/FLUKA point location.",
            "- A later coordinate-level audit must still resolve each point in both engines before high-stat full transport.",
            "",
        ]
    )
    (out_dir / "source_region_material_name_audit.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    ap.add_argument("--region-map", type=Path, default=DEFAULT_REGION_MAP)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    positions = args.positions.expanduser().resolve()
    region_map = args.region_map.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    audited = audit_rows(read_csv(positions), build_region_lookup(region_map))
    audit_csv = out_dir / "cu64_source_region_material_name_audit.csv"
    material_csv = out_dir / "cu64_source_material_name_summary.csv"
    status_csv = out_dir / "cu64_source_region_material_name_status_summary.csv"
    canonical_csv = out_dir / "cu64_source_canonical_name_diff_summary.csv"
    write_csv(audit_csv, audited, AUDIT_FIELDS)
    material_rows = aggregate_by(audited, "material")
    status_rows = aggregate_by(audited, "audit_status")
    canonical_rows = aggregate_by(audited, "canonical_differs_from_source_volume")
    write_csv(material_csv, material_rows, ["material", "rows", "activity_weight_Bq", "activity_fraction"])
    write_csv(status_csv, status_rows, ["audit_status", "rows", "activity_weight_Bq", "activity_fraction"])
    write_csv(canonical_csv, canonical_rows, ["canonical_differs_from_source_volume", "rows", "activity_weight_Bq", "activity_fraction"])

    missing = sum(1 for row in audited if row["audit_status"] == "FAIL_MISSING_REGION_MAP")
    not_translated = sum(1 for row in audited if row["audit_status"] == "FAIL_NOT_TRANSLATED")
    passed = sum(1 for row in audited if row["audit_status"] == "PASS_NAME_LEVEL")
    summary = {
        "status": "SOURCE_REGION_MATERIAL_NAME_AUDIT_PASS" if missing == 0 and not_translated == 0 else "SOURCE_REGION_MATERIAL_NAME_AUDIT_FAIL",
        "rows": len(audited),
        "pass_name_level_rows": passed,
        "missing_region_map_rows": missing,
        "not_translated_rows": not_translated,
        "coordinate_containment_tested": False,
        "positions_csv": rel(positions),
        "positions_sha256": sha256_path(positions),
        "region_map_csv": str(region_map),
        "region_map_sha256": sha256_path(region_map),
        "audit_csv": rel(audit_csv),
        "audit_sha256": sha256_path(audit_csv),
        "material_summary_csv": rel(material_csv),
        "material_summary_sha256": sha256_path(material_csv),
        "status_summary_csv": rel(status_csv),
        "status_summary_sha256": sha256_path(status_csv),
        "canonical_name_diff_summary_csv": rel(canonical_csv),
        "canonical_name_diff_summary_sha256": sha256_path(canonical_csv),
        "material_summary": material_rows,
        "status_summary": status_rows,
        "canonical_name_diff_summary": canonical_rows,
        "boundary": "name-level audit only; coordinate containment and runtime point location remain open",
    }
    write_json(out_dir / "source_region_material_name_audit.json", summary)
    write_summary_md(out_dir, summary)
    print(json.dumps({"status": summary["status"], "rows": len(audited), "out_dir": rel(out_dir)}, sort_keys=True))
    return 0 if summary["status"].endswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
