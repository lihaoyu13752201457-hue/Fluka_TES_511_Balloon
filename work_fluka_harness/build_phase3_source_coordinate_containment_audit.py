#!/usr/bin/env python3
"""Build a static coordinate-containment audit for Phase-3 Cu-64 source points."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any


getcontext().prec = 80

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import build_geometry_translation as geom  # noqa: E402


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

TOL_CM = 1.0e-7
INSTRUMENT_FRAME_ROT_Y_DEG = 45.0

AUDIT_FIELDS = [
    "common_event_id",
    "source_event_id",
    "production_tag",
    "x_cm",
    "y_cm",
    "z_cm",
    "geometry_local_x_cm",
    "geometry_local_y_cm",
    "geometry_local_z_cm",
    "coordinate_transform_policy",
    "source_volume",
    "expected_material",
    "expected_fluka_region_name",
    "expected_shape_type",
    "expected_depth",
    "expected_contains_static",
    "resolved_static_volume",
    "resolved_static_logical",
    "resolved_static_material",
    "resolved_static_fluka_region_name",
    "resolved_static_depth",
    "containing_volume_count",
    "deepest_volume_count",
    "expected_min_boundary_margin_cm_approx",
    "same_material_as_expected",
    "audit_status",
    "audit_note",
    "original_activity_weight_Bq",
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


def build_region_lookup(path: Path) -> dict[str, dict[str, str]]:
    return {row["source_volume_name"]: row for row in read_csv(path)}


def load_geometry_objects() -> tuple[dict[str, geom.ObjectInstance], dict[str, geom.Shape], dict[str, tuple[float, float, float]]]:
    volumes, shapes, orientations, copies = geom.parse_geo_files([geom.INTRO, geom.GEO])
    objects = geom.build_instances(volumes, copies)
    geom.build_fluka_input(objects, shapes, orientations)
    return objects, shapes, orientations


def in_phi(a: float, b: float, phi0: float, dphi: float) -> bool:
    if dphi >= 360.0 - TOL_CM:
        return True
    angle = math.degrees(math.atan2(b, a)) % 360.0
    return ((angle - phi0) % 360.0) <= dphi + 1.0e-8


def source_to_geometry_local(point: tuple[float, float, float]) -> tuple[float, float, float]:
    # Source-v2 positions are in the rotated InstrumentFrame coordinate system,
    # while build_geometry_translation keeps child placements in InstrumentFrame
    # local coordinates and records the 45 degree frame rotation as policy.
    theta = math.radians(INSTRUMENT_FRAME_ROT_Y_DEG)
    x, y, z = point
    return (x * math.cos(theta) - z * math.sin(theta), y, x * math.sin(theta) + z * math.cos(theta))


def interp_radius(z: float, planes: list[tuple[float, float, float]]) -> tuple[float, float] | None:
    if len(planes) == 1:
        zz, rin, rout = planes[0]
        return (rin, rout) if abs(z - zz) <= TOL_CM else None
    ordered = sorted(planes)
    for (z0, rin0, rout0), (z1, rin1, rout1) in zip(ordered[:-1], ordered[1:]):
        lo, hi = min(z0, z1), max(z0, z1)
        if lo - TOL_CM <= z <= hi + TOL_CM:
            t = 0.0 if abs(z1 - z0) <= TOL_CM else (z - z0) / (z1 - z0)
            return (rin0 + t * (rin1 - rin0), rout0 + t * (rout1 - rout0))
    return None


def point_in_brik(point: tuple[float, float, float], center: tuple[float, float, float], params: list[float]) -> bool:
    x, y, z = point
    cx, cy, cz = center
    dx, dy, dz = params[:3]
    return (
        cx - dx - TOL_CM <= x <= cx + dx + TOL_CM
        and cy - dy - TOL_CM <= y <= cy + dy + TOL_CM
        and cz - dz - TOL_CM <= z <= cz + dz + TOL_CM
    )


def margin_brik(point: tuple[float, float, float], center: tuple[float, float, float], params: list[float]) -> float:
    x, y, z = point
    cx, cy, cz = center
    dx, dy, dz = params[:3]
    return min(dx - abs(x - cx), dy - abs(y - cy), dz - abs(z - cz))


def pcon_local(point: tuple[float, float, float], center: tuple[float, float, float], rotation: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    cx, cy, cz = center
    if abs(rotation[1] - 90.0) < 1.0e-8 and abs(rotation[0]) < 1.0e-8 and abs(rotation[2]) < 1.0e-8:
        return (x - cx, y - cy, z - cz)
    return (z - cz, x - cx, y - cy)


def point_in_pcon(point: tuple[float, float, float], center: tuple[float, float, float], params: list[float], rotation: tuple[float, float, float]) -> bool:
    phi0, dphi, n_raw = params[:3]
    n = int(round(n_raw))
    planes = [(params[3 + 3 * i], params[4 + 3 * i], params[5 + 3 * i]) for i in range(n)]
    axial, a, b = pcon_local(point, center, rotation)
    radii = interp_radius(axial, planes)
    if radii is None:
        return False
    rin, rout = radii
    r = math.hypot(a, b)
    return rin - TOL_CM <= r <= rout + TOL_CM and in_phi(a, b, phi0, dphi)


def margin_pcon(point: tuple[float, float, float], center: tuple[float, float, float], params: list[float], rotation: tuple[float, float, float]) -> float:
    _, _, n_raw = params[:3]
    n = int(round(n_raw))
    planes = [(params[3 + 3 * i], params[4 + 3 * i], params[5 + 3 * i]) for i in range(n)]
    axial, a, b = pcon_local(point, center, rotation)
    radii = interp_radius(axial, planes)
    if radii is None:
        z_values = [z for z, _, _ in planes]
        return -min(abs(axial - min(z_values)), abs(axial - max(z_values)))
    rin, rout = radii
    r = math.hypot(a, b)
    z_values = [z for z, _, _ in planes]
    axial_margin = min(axial - min(z_values), max(z_values) - axial)
    radial_margin = min(r - rin, rout - r)
    return min(axial_margin, radial_margin)


def point_in_named(
    point: tuple[float, float, float],
    center: tuple[float, float, float],
    shape_name: str,
    rotation: tuple[float, float, float],
    shapes: dict[str, geom.Shape],
    orientations: dict[str, tuple[float, float, float]],
) -> bool:
    shape = shapes[shape_name]
    if shape.kind == "BRIK":
        return point_in_brik(point, center, shape.params)  # type: ignore[arg-type]
    if shape.kind == "PCON":
        return point_in_pcon(point, center, shape.params, rotation)  # type: ignore[arg-type]
    if shape.kind == "Subtraction":
        full, cut, orient = shape.params  # type: ignore[misc]
        ox, oy, oz = orientations.get(orient, (0.0, 0.0, 0.0))
        cut_center = (center[0] + ox, center[1] + oy, center[2] + oz)
        return point_in_named(point, center, full, rotation, shapes, orientations) and not point_in_named(
            point, cut_center, cut, rotation, shapes, orientations
        )
    return False


def margin_named(
    point: tuple[float, float, float],
    center: tuple[float, float, float],
    shape_name: str,
    rotation: tuple[float, float, float],
    shapes: dict[str, geom.Shape],
    orientations: dict[str, tuple[float, float, float]],
) -> float:
    shape = shapes[shape_name]
    if shape.kind == "BRIK":
        return margin_brik(point, center, shape.params)  # type: ignore[arg-type]
    if shape.kind == "PCON":
        return margin_pcon(point, center, shape.params, rotation)  # type: ignore[arg-type]
    if shape.kind == "Subtraction":
        full, cut, orient = shape.params  # type: ignore[misc]
        ox, oy, oz = orientations.get(orient, (0.0, 0.0, 0.0))
        cut_center = (center[0] + ox, center[1] + oy, center[2] + oz)
        full_margin = margin_named(point, center, full, rotation, shapes, orientations)
        cut_margin = margin_named(point, cut_center, cut, rotation, shapes, orientations)
        return min(full_margin, -cut_margin)
    return float("-inf")


def point_in_object(
    point: tuple[float, float, float],
    obj: geom.ObjectInstance,
    shapes: dict[str, geom.Shape],
    orientations: dict[str, tuple[float, float, float]],
) -> bool:
    try:
        if obj.shape_kind == "BRIK":
            return point_in_brik(point, obj.abs_position, obj.shape_params)  # type: ignore[arg-type]
        if obj.shape_kind == "PCON":
            return point_in_pcon(point, obj.abs_position, obj.shape_params, obj.rotation)  # type: ignore[arg-type]
        if obj.shape_kind == "NAMED":
            return point_in_named(point, obj.abs_position, obj.shape_params, obj.rotation, shapes, orientations)  # type: ignore[arg-type]
    except Exception:
        return False
    return False


def margin_object(
    point: tuple[float, float, float],
    obj: geom.ObjectInstance,
    shapes: dict[str, geom.Shape],
    orientations: dict[str, tuple[float, float, float]],
) -> float:
    try:
        if obj.shape_kind == "BRIK":
            return margin_brik(point, obj.abs_position, obj.shape_params)  # type: ignore[arg-type]
        if obj.shape_kind == "PCON":
            return margin_pcon(point, obj.abs_position, obj.shape_params, obj.rotation)  # type: ignore[arg-type]
        if obj.shape_kind == "NAMED":
            return margin_named(point, obj.abs_position, obj.shape_params, obj.rotation, shapes, orientations)  # type: ignore[arg-type]
    except Exception:
        return float("-inf")
    return float("-inf")


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


def audit_positions(
    positions: list[dict[str, str]],
    objects: dict[str, geom.ObjectInstance],
    shapes: dict[str, geom.Shape],
    orientations: dict[str, tuple[float, float, float]],
    region_lookup: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    locatable = [
        obj
        for obj in objects.values()
        if obj.name not in {"WorldVolume", "InstrumentFrame"} and obj.translation_status.startswith("TRANSLATED")
    ]
    audited: list[dict[str, Any]] = []
    for row in positions:
        source_point = (float(row["x_cm"]), float(row["y_cm"]), float(row["z_cm"]))
        point = source_to_geometry_local(source_point)
        expected_name = row["source_volume"]
        expected = objects.get(expected_name)
        mapped = region_lookup.get(expected_name, {})
        if expected is None:
            expected_contains = False
            containing = [obj for obj in locatable if point_in_object(point, obj, shapes, orientations)]
            status = "FAIL_MISSING_GEOMETRY_OBJECT"
            note = "source_volume is absent from parsed geometry objects"
            margin = float("-inf")
        elif not expected.translation_status.startswith("TRANSLATED"):
            expected_contains = False
            containing = [obj for obj in locatable if point_in_object(point, obj, shapes, orientations)]
            status = "FAIL_EXPECTED_NOT_TRANSLATED"
            note = "source_volume exists but is not marked translated"
            margin = float("-inf")
        else:
            expected_contains = point_in_object(point, expected, shapes, orientations)
            containing = [obj for obj in locatable if point_in_object(point, obj, shapes, orientations)]
            margin = margin_object(point, expected, shapes, orientations)
            if not expected_contains:
                status = "FAIL_EXPECTED_DOES_NOT_CONTAIN_POINT"
                note = "coordinate is outside the declared source_volume in the static geometry parser"
            else:
                max_depth = max((obj.depth for obj in containing), default=-1)
                deepest = [obj for obj in containing if obj.depth == max_depth]
                if not deepest:
                    status = "FAIL_NO_CONTAINING_TRANSLATED_VOLUME"
                    note = "no translated geometry object contains the coordinate"
                elif len(deepest) > 1:
                    status = "FAIL_AMBIGUOUS_DEEPEST_VOLUME"
                    note = "multiple translated objects at the same deepest hierarchy level contain the coordinate"
                elif deepest[0].name != expected_name:
                    status = "FAIL_RESOLVED_VOLUME_MISMATCH"
                    note = "deepest static containing volume differs from declared source_volume"
                else:
                    status = "PASS_STATIC_CONTAINMENT"
                    note = "declared source_volume is the deepest translated static geometry object containing the coordinate"
        max_depth = max((obj.depth for obj in containing), default=-1)
        deepest = [obj for obj in containing if obj.depth == max_depth]
        resolved = deepest[0] if len(deepest) == 1 else None
        expected_material = expected.material if expected is not None else mapped.get("material", "")
        resolved_material = resolved.material if resolved is not None else ""
        audited.append(
            {
                "common_event_id": row["common_event_id"],
                "source_event_id": row["source_event_id"],
                "production_tag": row["production_tag"],
                "x_cm": row["x_cm"],
                "y_cm": row["y_cm"],
                "z_cm": row["z_cm"],
                "geometry_local_x_cm": f"{point[0]:.10g}",
                "geometry_local_y_cm": f"{point[1]:.10g}",
                "geometry_local_z_cm": f"{point[2]:.10g}",
                "coordinate_transform_policy": "inverse InstrumentFrame.Rotation 0 45 0 before static containment",
                "source_volume": expected_name,
                "expected_material": expected_material,
                "expected_fluka_region_name": mapped.get("fluka_region_name", expected.region if expected is not None else ""),
                "expected_shape_type": expected.shape_kind if expected is not None else "",
                "expected_depth": expected.depth if expected is not None else "",
                "expected_contains_static": str(expected_contains),
                "resolved_static_volume": resolved.name if resolved is not None else "",
                "resolved_static_logical": resolved.logical if resolved is not None else "",
                "resolved_static_material": resolved_material,
                "resolved_static_fluka_region_name": resolved.region if resolved is not None else "",
                "resolved_static_depth": resolved.depth if resolved is not None else "",
                "containing_volume_count": len(containing),
                "deepest_volume_count": len(deepest),
                "expected_min_boundary_margin_cm_approx": "" if not math.isfinite(margin) else f"{margin:.10g}",
                "same_material_as_expected": str(bool(expected_material and expected_material == resolved_material)),
                "audit_status": status,
                "audit_note": note,
                "original_activity_weight_Bq": row["original_activity_weight_Bq"],
            }
        )
    return audited


def write_summary_md(out_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Source Coordinate Containment Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- rows: `{summary['rows']}`",
        f"- pass_static_containment_rows: `{summary['pass_static_containment_rows']}`",
        f"- failing_rows: `{summary['failing_rows']}`",
        f"- runtime_point_location_tested: `{summary['runtime_point_location_tested']}`",
        f"- coordinate_transform_policy: `{summary['coordinate_transform_policy']}`",
        f"- audit_csv: `{summary['audit_csv']}`",
        "",
        "## Status Summary",
        "",
        "| audit_status | rows | activity_weight_Bq | activity_fraction |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["status_summary"]:
        lines.append(
            f"| `{row['audit_status']}` | `{row['rows']}` | `{row['activity_weight_Bq']}` | `{row['activity_fraction']}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a static containment audit using the same MEGAlib geometry authority parsed by the FLUKA translator.",
            "- It checks whether each common Cu-64 coordinate is inside its declared source volume and whether that volume is the deepest translated object containing the point.",
            "- It is not a FLUKA runtime point-location scorer and does not replace a future engine-level locator check.",
            "",
        ]
    )
    (out_dir / "source_coordinate_containment_audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    ap.add_argument("--region-map", type=Path, default=DEFAULT_REGION_MAP)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    positions_path = args.positions.expanduser().resolve()
    region_map_path = args.region_map.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    objects, shapes, orientations = load_geometry_objects()
    audited = audit_positions(read_csv(positions_path), objects, shapes, orientations, build_region_lookup(region_map_path))

    audit_csv = out_dir / "cu64_source_coordinate_containment_audit.csv"
    status_csv = out_dir / "cu64_source_coordinate_containment_status_summary.csv"
    resolved_material_csv = out_dir / "cu64_source_coordinate_resolved_material_summary.csv"
    write_csv(audit_csv, audited, AUDIT_FIELDS)
    status_rows = aggregate_by(audited, "audit_status")
    resolved_material_rows = aggregate_by(audited, "resolved_static_material")
    write_csv(status_csv, status_rows, ["audit_status", "rows", "activity_weight_Bq", "activity_fraction"])
    write_csv(resolved_material_csv, resolved_material_rows, ["resolved_static_material", "rows", "activity_weight_Bq", "activity_fraction"])

    pass_rows = sum(1 for row in audited if row["audit_status"] == "PASS_STATIC_CONTAINMENT")
    failing_rows = len(audited) - pass_rows
    finite_margins = [
        float(row["expected_min_boundary_margin_cm_approx"])
        for row in audited
        if row["expected_min_boundary_margin_cm_approx"] not in ("", None)
    ]
    summary = {
        "status": "SOURCE_COORDINATE_CONTAINMENT_STATIC_PASS" if failing_rows == 0 else "SOURCE_COORDINATE_CONTAINMENT_STATIC_FAIL",
        "rows": len(audited),
        "pass_static_containment_rows": pass_rows,
        "failing_rows": failing_rows,
        "runtime_point_location_tested": False,
        "coordinate_transform_policy": "source-v2 coordinates are inverse-rotated by InstrumentFrame.Rotation 0 45 0 into the MEGAlib/FLUKA-translator local frame before static containment",
        "positions_csv": rel(positions_path),
        "positions_sha256": sha256_path(positions_path),
        "region_map_csv": str(region_map_path),
        "region_map_sha256": sha256_path(region_map_path),
        "geometry_geo": str(geom.GEO),
        "geometry_geo_sha256": sha256_path(geom.GEO),
        "geometry_intro": str(geom.INTRO),
        "geometry_intro_sha256": sha256_path(geom.INTRO),
        "audit_csv": rel(audit_csv),
        "audit_sha256": sha256_path(audit_csv),
        "status_summary_csv": rel(status_csv),
        "status_summary_sha256": sha256_path(status_csv),
        "resolved_material_summary_csv": rel(resolved_material_csv),
        "resolved_material_summary_sha256": sha256_path(resolved_material_csv),
        "status_summary": status_rows,
        "resolved_material_summary": resolved_material_rows,
        "min_expected_boundary_margin_cm_approx": min(finite_margins) if finite_margins else None,
        "boundary": "static translator containment only; runtime Geant4/FLUKA point location remains open",
    }
    write_json(out_dir / "source_coordinate_containment_audit.json", summary)
    write_summary_md(out_dir, summary)
    print(json.dumps({"status": summary["status"], "rows": len(audited), "failing_rows": failing_rows, "out_dir": rel(out_dir)}, sort_keys=True))
    return 0 if failing_rows == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
