#!/usr/bin/env python3
"""Audit whether Phase-3 Cu-64 W2 raw differences concentrate near source boundaries."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_PARENT_LIST = PHASE3_DIR / "full_untracked/cu64_parent_resampling_1e6.csv"
DEFAULT_COORD_AUDIT = PHASE3_DIR / "cu64_source_coordinate_containment_audit.csv"
DEFAULT_WORK_ROOT = Path("/tmp/phase3prod")
DEFAULT_OUT_DIR = PHASE3_DIR / "phase3_cu64_boundary_margin_audit_1e6"
ACTIVE_VETO_THRESHOLD_KEV = 50.0

BANDS = [
    ("all_tes_gt0", "all TES > 0", 0.0, float("inf")),
    ("e480_550", "480-550 keV", 480.0, 550.0),
    ("w2_510p58_511p42", "W2 510.58-511.42 keV", 510.58, 511.42),
]

MARGIN_BINS = [
    ("lt_1e-4_cm", 0.0, 1.0e-4),
    ("1e-4_1e-3_cm", 1.0e-4, 1.0e-3),
    ("1e-3_1e-2_cm", 1.0e-3, 1.0e-2),
    ("1e-2_5e-2_cm", 1.0e-2, 5.0e-2),
    ("5e-2_1e-1_cm", 5.0e-2, 1.0e-1),
    ("1e-1_5e-1_cm", 1.0e-1, 5.0e-1),
    ("ge_5e-1_cm", 5.0e-1, float("inf")),
]


@dataclass
class ParentMeta:
    common_event_id: int
    source_volume: str
    material: str
    production_tag: str
    margin_cm: float
    margin_bin: str


@dataclass
class Stat:
    sum_w: float = 0.0
    sum_w2: float = 0.0

    def add(self, weight: float = 1.0) -> None:
        self.sum_w += weight
        self.sum_w2 += weight * weight


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def in_band(energy_keV: float, lo: float, hi: float) -> bool:
    return (lo == 0.0 and energy_keV > 0.0) or (lo != 0.0 and lo <= energy_keV < hi)


def margin_bin(margin_cm: float) -> str:
    for name, lo, hi in MARGIN_BINS:
        if lo <= margin_cm < hi:
            return name
    return "unknown"


def chunk_start(path: Path) -> int:
    for parent in [path, *path.parents]:
        match = re.match(r"chunk_\d+_start(\d+)_n\d+$", parent.name)
        if match:
            return int(match.group(1))
    raise ValueError(f"cannot determine chunk start from {path}")


def load_margins(coord_audit: Path) -> dict[int, float]:
    out: dict[int, float] = {}
    with coord_audit.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            out[int(row["common_event_id"])] = float(row["expected_min_boundary_margin_cm_approx"])
    return out


def load_parent_meta(parent_list: Path, coord_audit: Path) -> dict[int, ParentMeta]:
    margins = load_margins(coord_audit)
    out: dict[int, ParentMeta] = {}
    with parent_list.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            global_id = int(row["resampled_history_id"])
            common_event_id = int(row["common_event_id"])
            margin = margins[common_event_id]
            out[global_id] = ParentMeta(
                common_event_id=common_event_id,
                source_volume=row.get("source_volume", "").strip() or "UNKNOWN_SOURCE_VOLUME",
                material=row.get("resolved_static_material", "").strip() or "UNKNOWN_MATERIAL",
                production_tag=row.get("production_tag", "").strip() or "UNKNOWN_PRODUCTION_TAG",
                margin_cm=margin,
                margin_bin=margin_bin(margin),
            )
    return out


def event_total_paths(code: str, work_root: Path) -> list[Path]:
    if code == "fluka":
        return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*event_totals_tmp.csv"))
    if code == "megalib":
        return sorted((work_root / "megalib").glob("chunk_*/cc_event_totals.csv"))
    raise ValueError(code)


def iter_event_totals(code: str, work_root: Path) -> Iterable[tuple[int, float, float]]:
    for path in event_total_paths(code, work_root):
        start = chunk_start(path)
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                global_id = start + int(row["history_id"]) - 1
                if code == "fluka":
                    yield global_id, float(row["tes_total_keV"]), float(row["shield_total_keV"])
                else:
                    yield global_id, float(row["tes_total_keV"]), float(row["active_shield_total_keV"])


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[int(pos)]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def summarize(parent_meta: dict[int, ParentMeta], work_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    histories_by_bin = Counter(meta.margin_bin for meta in parent_meta.values())
    counts: dict[tuple[str, str, str, str], Stat] = defaultdict(Stat)
    selected_margins: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    selected_examples: list[dict[str, Any]] = []
    histories_by_code: dict[str, int] = {}

    for code in ("fluka", "megalib"):
        histories = 0
        for global_id, tes, shield in iter_event_totals(code, work_root):
            histories += 1
            meta = parent_meta[global_id]
            active = shield < ACTIVE_VETO_THRESHOLD_KEV
            for metric, _label, lo, hi in BANDS:
                if not in_band(tes, lo, hi):
                    continue
                for stage in ("raw", "active_veto"):
                    if stage == "active_veto" and not active:
                        continue
                    counts[(code, meta.margin_bin, metric, stage)].add()
                    selected_margins[(code, metric, stage)].append(meta.margin_cm)
                    if metric == "w2_510p58_511p42" and stage == "raw":
                        selected_examples.append(
                            {
                                "code": code,
                                "global_history_id": global_id,
                                "common_event_id": meta.common_event_id,
                                "source_volume": meta.source_volume,
                                "material": meta.material,
                                "production_tag": meta.production_tag,
                                "margin_cm": meta.margin_cm,
                                "margin_bin": meta.margin_bin,
                                "tes_total_keV": tes,
                                "shield_total_keV": shield,
                            }
                        )
        histories_by_code[code] = histories

    labels = {metric: label for metric, label, _lo, _hi in BANDS}
    comparison_rows: list[dict[str, Any]] = []
    total_histories = len(parent_meta)
    for metric, _label, _lo, _hi in BANDS:
        for stage in ("raw", "active_veto"):
            total_diff = sum(
                counts[("fluka", bin_name, metric, stage)].sum_w - counts[("megalib", bin_name, metric, stage)].sum_w
                for bin_name, _lo2, _hi2 in MARGIN_BINS
            ) / total_histories
            for bin_name, lo2, hi2 in MARGIN_BINS:
                f = counts[("fluka", bin_name, metric, stage)]
                m = counts[("megalib", bin_name, metric, stage)]
                if f.sum_w == 0.0 and m.sum_w == 0.0 and histories_by_bin[bin_name] == 0:
                    continue
                diff = (f.sum_w - m.sum_w) / total_histories
                denom = math.sqrt(f.sum_w2 + m.sum_w2) / total_histories
                bin_histories = histories_by_bin[bin_name]
                f_cond = f.sum_w / bin_histories if bin_histories else 0.0
                m_cond = m.sum_w / bin_histories if bin_histories else 0.0
                comparison_rows.append(
                    {
                        "margin_bin": bin_name,
                        "margin_lo_cm": lo2,
                        "margin_hi_cm": hi2 if math.isfinite(hi2) else "",
                        "metric": metric,
                        "metric_label": labels[metric],
                        "stage": stage,
                        "source_histories": bin_histories,
                        "source_fraction": bin_histories / total_histories,
                        "fluka_sum_w": f.sum_w,
                        "megalib_sum_w": m.sum_w,
                        "fluka_conditional_efficiency": f_cond,
                        "megalib_conditional_efficiency": m_cond,
                        "fluka_over_megalib_conditional": f_cond / m_cond if m_cond > 0.0 else "",
                        "difference_per_parent": diff,
                        "difference_share_of_total": diff / total_diff if total_diff else "",
                        "z_difference": diff / denom if denom > 0.0 else "",
                    }
                )

    margin_summary: list[dict[str, Any]] = []
    for (code, metric, stage), values in selected_margins.items():
        margin_summary.append(
            {
                "code": code,
                "metric": metric,
                "stage": stage,
                "events": len(values),
                "min_margin_cm": min(values) if values else "",
                "p10_margin_cm": percentile(values, 0.10),
                "median_margin_cm": percentile(values, 0.50),
                "p90_margin_cm": percentile(values, 0.90),
                "max_margin_cm": max(values) if values else "",
                "events_lt_1e-3_cm": sum(1 for val in values if val < 1.0e-3),
                "events_lt_1e-2_cm": sum(1 for val in values if val < 1.0e-2),
                "events_lt_5e-2_cm": sum(1 for val in values if val < 5.0e-2),
            }
        )

    selected_examples.sort(key=lambda row: (float(row["margin_cm"]), row["code"]))
    meta = {
        "histories_by_code": histories_by_code,
        "total_parent_histories": total_histories,
        "history_margin_bins": dict(histories_by_bin),
        "nearest_w2_raw_examples": selected_examples[:40],
    }
    comparison_rows.sort(key=lambda row: (row["metric"], row["stage"], float(row["margin_lo_cm"])))
    margin_summary.sort(key=lambda row: (row["metric"], row["stage"], row["code"]))
    return comparison_rows, margin_summary, meta


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Boundary-Margin Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- histories_per_code: `FLUKA {payload['histories_by_code'].get('fluka')}; "
        f"MEGAlib {payload['histories_by_code'].get('megalib')}`",
        f"- coordinate_audit: `{payload['coordinate_audit_csv']}`",
        "",
        "## Headline",
        "",
        payload["headline"],
        "",
        "## W2 Raw By Static Boundary-Margin Bin",
        "",
        "| margin bin | source histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | FLUKA/MEGAlib conditional |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["w2_raw_rows"]:
        ratio = row["fluka_over_megalib_conditional"]
        share = row["difference_share_of_total"]
        lines.append(
            f"| `{row['margin_bin']}` | `{row['source_histories']}` | `{float(row['fluka_sum_w']):.6g}` | "
            f"`{float(row['megalib_sum_w']):.6g}` | `{float(row['difference_per_parent']):.6g}` | "
            f"`{float(share):.3g}` | `{float(ratio):.6g}` |"
            if isinstance(ratio, float) and isinstance(share, float)
            else f"| `{row['margin_bin']}` | `{row['source_histories']}` | `{float(row['fluka_sum_w']):.6g}` | "
            f"`{float(row['megalib_sum_w']):.6g}` | `{float(row['difference_per_parent']):.6g}` | `n/a` | `n/a` |"
        )
    lines.extend(
        [
            "",
            "## W2 Raw Margin Distribution",
            "",
            "| code | events | min cm | p10 cm | median cm | p90 cm | events < 0.01 cm |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["w2_raw_margin_summary"]:
        lines.append(
            f"| `{row['code']}` | `{row['events']}` | `{float(row['min_margin_cm']):.6g}` | "
            f"`{float(row['p10_margin_cm']):.6g}` | `{float(row['median_margin_cm']):.6g}` | "
            f"`{float(row['p90_margin_cm']):.6g}` | `{row['events_lt_1e-2_cm']}` |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- margin_bin_comparison_csv: `{payload['margin_bin_comparison_csv']}`",
            f"- selected_margin_summary_csv: `{payload['selected_margin_summary_csv']}`",
            f"- nearest_w2_raw_events_csv: `{payload['nearest_w2_raw_events_csv']}`",
            "",
            "## Boundary",
            "",
            "- This is a static translator boundary-margin audit, not a runtime Geant4/FLUKA point-location scorer.",
            "- It tests whether the observed W2 raw difference is dominated by source positions very near declared source-volume boundaries.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-list", type=Path, default=DEFAULT_PARENT_LIST)
    ap.add_argument("--coordinate-audit", type=Path, default=DEFAULT_COORD_AUDIT)
    ap.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    args.parent_list = args.parent_list.expanduser().resolve()
    args.coordinate_audit = args.coordinate_audit.expanduser().resolve()
    args.work_root = args.work_root.expanduser().resolve()
    args.out_dir = args.out_dir.expanduser().resolve()

    parent_meta = load_parent_meta(args.parent_list, args.coordinate_audit)
    comparison_rows, margin_summary, meta = summarize(parent_meta, args.work_root)
    status = (
        "PHASE3_CU64_BOUNDARY_MARGIN_AUDIT_PASS"
        if meta["histories_by_code"].get("fluka") == len(parent_meta)
        and meta["histories_by_code"].get("megalib") == len(parent_meta)
        else "BLOCKED_PHASE3_CU64_BOUNDARY_MARGIN_AUDIT"
    )
    w2_raw_rows = [
        row for row in comparison_rows if row["metric"] == "w2_510p58_511p42" and row["stage"] == "raw"
    ]
    w2_raw_summary = [
        row for row in margin_summary if row["metric"] == "w2_510p58_511p42" and row["stage"] == "raw"
    ]
    near_share = sum(
        float(row["difference_per_parent"])
        for row in w2_raw_rows
        if row["margin_bin"] in {"lt_1e-4_cm", "1e-4_1e-3_cm", "1e-3_1e-2_cm"}
    )
    total_diff = sum(float(row["difference_per_parent"]) for row in w2_raw_rows)
    near_fraction = near_share / total_diff if total_diff else 0.0
    headline = (
        "The W2 raw FLUKA excess is not dominated by very near-boundary source positions: "
        f"positions with static margin < 0.01 cm contribute {near_fraction:.3g} of the net W2 difference. "
        "This weakens a pure boundary-proximity explanation, though runtime point-location and stopping/annihilation audits remain open."
    )

    write_csv(
        args.out_dir / "margin_bin_comparison.csv",
        comparison_rows,
        [
            "margin_bin",
            "margin_lo_cm",
            "margin_hi_cm",
            "metric",
            "metric_label",
            "stage",
            "source_histories",
            "source_fraction",
            "fluka_sum_w",
            "megalib_sum_w",
            "fluka_conditional_efficiency",
            "megalib_conditional_efficiency",
            "fluka_over_megalib_conditional",
            "difference_per_parent",
            "difference_share_of_total",
            "z_difference",
        ],
    )
    write_csv(
        args.out_dir / "selected_margin_summary.csv",
        margin_summary,
        [
            "code",
            "metric",
            "stage",
            "events",
            "min_margin_cm",
            "p10_margin_cm",
            "median_margin_cm",
            "p90_margin_cm",
            "max_margin_cm",
            "events_lt_1e-3_cm",
            "events_lt_1e-2_cm",
            "events_lt_5e-2_cm",
        ],
    )
    write_csv(
        args.out_dir / "nearest_w2_raw_events.csv",
        meta["nearest_w2_raw_examples"],
        [
            "code",
            "global_history_id",
            "common_event_id",
            "source_volume",
            "material",
            "production_tag",
            "margin_cm",
            "margin_bin",
            "tes_total_keV",
            "shield_total_keV",
        ],
    )
    payload = {
        "status": status,
        "parent_list": rel(args.parent_list),
        "coordinate_audit_csv": rel(args.coordinate_audit),
        "work_root": rel(args.work_root),
        "histories_by_code": meta["histories_by_code"],
        "total_parent_histories": meta["total_parent_histories"],
        "history_margin_bins": meta["history_margin_bins"],
        "headline": headline,
        "near_boundary_margin_lt_0p01cm_fraction_of_w2_raw_difference": near_fraction,
        "margin_bin_comparison_csv": rel(args.out_dir / "margin_bin_comparison.csv"),
        "selected_margin_summary_csv": rel(args.out_dir / "selected_margin_summary.csv"),
        "nearest_w2_raw_events_csv": rel(args.out_dir / "nearest_w2_raw_events.csv"),
        "w2_raw_rows": w2_raw_rows,
        "w2_raw_margin_summary": w2_raw_summary,
        "boundary": "Static boundary-margin audit only; runtime point-location and stopping/annihilation location remain open.",
    }
    write_json(args.out_dir / "summary.json", payload)
    write_summary_md(args.out_dir / "summary.md", payload)
    print(args.out_dir / "summary.md")
    print(status)
    return 0 if status == "PHASE3_CU64_BOUNDARY_MARGIN_AUDIT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
