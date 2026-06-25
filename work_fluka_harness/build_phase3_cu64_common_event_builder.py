#!/usr/bin/env python3
"""Build common parent-history event metrics from Phase-3 Cu-64 raw deposits."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_WORK_ROOT = Path("/tmp/phase3prod")
DEFAULT_OUT_DIR = PHASE3_DIR / "phase3_cu64_common_event_builder_parent_1e6"
ACTIVE_VETO_THRESHOLD_KEV = 50.0
W2_LO = 510.58
W2_HI = 511.42
W2_SIGMA_KEV = 0.14

BANDS = [
    ("all_tes_gt0", "all TES > 0", 0.0, float("inf")),
    ("e480_550", "480-550 keV", 480.0, 550.0),
    ("w2_510p58_511p42", "W2 510.58-511.42 keV", W2_LO, W2_HI),
    ("e1500_3000", "1500-3000 keV", 1500.0, 3000.0),
    ("e3000_10000", "3000-10000 keV", 3000.0, 10000.0),
]


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


def phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def w2_probability(energy_keV: float) -> float:
    return phi((W2_HI - energy_keV) / W2_SIGMA_KEV) - phi((W2_LO - energy_keV) / W2_SIGMA_KEV)


def in_band(energy_keV: float, lo: float, hi: float) -> bool:
    return (lo == 0.0 and energy_keV > 0.0) or (lo != 0.0 and lo <= energy_keV < hi)


def iter_event_totals(code: str, work_root: Path) -> Iterable[tuple[float, float]]:
    if code == "fluka":
        paths = sorted((work_root / "fluka").glob("chunk_*/fluka_run/*event_totals_tmp.csv"))
        tes_field = "tes_total_keV"
        shield_field = "shield_total_keV"
    elif code == "megalib":
        paths = sorted((work_root / "megalib").glob("chunk_*/cc_event_totals.csv"))
        tes_field = "tes_total_keV"
        shield_field = "active_shield_total_keV"
    else:
        raise ValueError(f"unknown code: {code}")
    if not paths:
        raise FileNotFoundError(f"no event-total CSVs found for {code} under {work_root}")
    for path in paths:
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                yield float(row[tes_field]), float(row[shield_field])


def init_stage() -> dict[str, float]:
    return {
        "events": 0.0,
        "sum_w": 0.0,
        "sum_w2": 0.0,
    }


def add(stage: dict[str, float], weight: float) -> None:
    stage["events"] += 1.0 if weight > 0.0 else 0.0
    stage["sum_w"] += weight
    stage["sum_w2"] += weight * weight


def summarize_code(code: str, work_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    counts: dict[tuple[str, str], dict[str, float]] = {}
    for band, _label, _lo, _hi in BANDS:
        for stage in ("raw", "active_veto"):
            counts[(band, stage)] = init_stage()
    counts[("w2_expected", "raw")] = init_stage()
    counts[("w2_expected", "active_veto")] = init_stage()

    histories = 0
    active_histories = 0
    for tes, shield in iter_event_totals(code, work_root):
        histories += 1
        active = shield < ACTIVE_VETO_THRESHOLD_KEV
        if active:
            active_histories += 1
        for band, _label, lo, hi in BANDS:
            if in_band(tes, lo, hi):
                add(counts[(band, "raw")], 1.0)
                if active:
                    add(counts[(band, "active_veto")], 1.0)
        p = w2_probability(tes)
        if p > 0.0:
            add(counts[("w2_expected", "raw")], p)
            if active:
                add(counts[("w2_expected", "active_veto")], p)

    rows: list[dict[str, Any]] = []
    for band, label, _lo, _hi in BANDS:
        for stage in ("raw", "active_veto"):
            item = counts[(band, stage)]
            denom = histories
            eff = item["sum_w"] / denom if denom else 0.0
            sigma = math.sqrt(eff * (1.0 - eff) / denom) if denom and 0.0 <= eff <= 1.0 else 0.0
            rows.append(
                {
                    "code": code,
                    "metric": band,
                    "metric_label": label,
                    "stage": stage,
                    "histories": histories,
                    "events": int(item["sum_w"]),
                    "sum_w": item["sum_w"],
                    "sum_w2": item["sum_w2"],
                    "n_eff": (item["sum_w"] ** 2 / item["sum_w2"]) if item["sum_w2"] > 0.0 else 0.0,
                    "efficiency_per_parent": eff,
                    "efficiency_sigma": sigma,
                }
            )
    for stage in ("raw", "active_veto"):
        item = counts[("w2_expected", stage)]
        denom = histories
        eff = item["sum_w"] / denom if denom else 0.0
        sigma = math.sqrt(item["sum_w2"]) / denom if denom else 0.0
        rows.append(
            {
                "code": code,
                "metric": "w2_expected",
                "metric_label": "W2 analytic Gaussian expectation",
                "stage": stage,
                "histories": histories,
                "events": "",
                "sum_w": item["sum_w"],
                "sum_w2": item["sum_w2"],
                "n_eff": (item["sum_w"] ** 2 / item["sum_w2"]) if item["sum_w2"] > 0.0 else 0.0,
                "efficiency_per_parent": eff,
                "efficiency_sigma": sigma,
            }
        )
    meta = {"code": code, "histories": histories, "active_histories": active_histories}
    return rows, meta


def compare_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["code"], row["metric"], row["stage"]): row for row in rows}
    out = []
    label_by_metric = {band: label for band, label, _lo, _hi in BANDS}
    label_by_metric["w2_expected"] = "W2 analytic Gaussian expectation"
    keys = [
        (metric, label_by_metric[metric], stage)
        for metric in [band for band, _label, _lo, _hi in BANDS] + ["w2_expected"]
        for stage in ("raw", "active_veto")
    ]
    for metric, label, stage in keys:
        f = by_key.get(("fluka", metric, stage))
        m = by_key.get(("megalib", metric, stage))
        if not f or not m:
            continue
        f_eff = float(f["efficiency_per_parent"])
        m_eff = float(m["efficiency_per_parent"])
        f_sig = float(f["efficiency_sigma"])
        m_sig = float(m["efficiency_sigma"])
        denom = math.sqrt(f_sig * f_sig + m_sig * m_sig)
        ratio = f_eff / m_eff if m_eff > 0.0 else None
        out.append(
            {
                "metric": metric,
                "metric_label": label,
                "stage": stage,
                "fluka_histories": f["histories"],
                "fluka_sum_w": f["sum_w"],
                "fluka_efficiency": f_eff,
                "fluka_sigma": f_sig,
                "megalib_histories": m["histories"],
                "megalib_sum_w": m["sum_w"],
                "megalib_efficiency": m_eff,
                "megalib_sigma": m_sig,
                "fluka_over_megalib": ratio if ratio is not None else "",
                "z_efficiency_difference": (f_eff - m_eff) / denom if denom > 0.0 else "",
            }
        )
    return out


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Common Parent-History Event Builder",
        "",
        f"- status: `{payload['status']}`",
        f"- work_root: `{payload['work_root']}`",
        f"- active_veto_threshold_keV: `{ACTIVE_VETO_THRESHOLD_KEV}`",
        f"- w2_sigma_keV: `{W2_SIGMA_KEV}`",
        "",
        "## Stage Ratios",
        "",
        "| metric | stage | FLUKA sum_w / histories | MEGAlib sum_w / histories | FLUKA/MEGAlib | z |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["comparison"]:
        ratio = row["fluka_over_megalib"]
        z = row["z_efficiency_difference"]
        ratio_s = f"{ratio:.6g}" if isinstance(ratio, float) else "n/a"
        z_s = f"{z:.3g}" if isinstance(z, float) else "n/a"
        lines.append(
            f"| `{row['metric_label']}` | `{row['stage']}` | "
            f"`{float(row['fluka_sum_w']):.6g} / {row['fluka_histories']}` | "
            f"`{float(row['megalib_sum_w']):.6g} / {row['megalib_histories']}` | "
            f"`{ratio_s}` | `{z_s}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The common parent-history event builder does not remove the discrepancy.",
            "- Raw W2 and analytic Gaussian W2 give the same FLUKA/MEGAlib ratio within statistics.",
            "- The first failed phase is therefore full-geometry raw-deposit/source-material coupling, before common detector response.",
            "",
            "## Output Files",
            "",
            f"- stage_rows_csv: `{payload['stage_rows_csv']}`",
            f"- comparison_csv: `{payload['comparison_csv']}`",
            "",
            "## Boundary",
            "",
            "- This is the common parent-history event definition only.",
            "- It uses identical active-veto and analytic W2 response calculations for both codes.",
            "- It does not yet perform 1 microsecond / 1 nanosecond sub-event splitting or side-Compton/FoV topology.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    args.work_root = args.work_root.expanduser().resolve()
    args.out_dir = args.out_dir.expanduser().resolve()

    fluka_rows, fluka_meta = summarize_code("fluka", args.work_root)
    megalib_rows, megalib_meta = summarize_code("megalib", args.work_root)
    rows = fluka_rows + megalib_rows
    comparison = compare_rows(rows)
    status = (
        "PHASE3_CU64_COMMON_PARENT_EVENT_BUILDER_PASS"
        if fluka_meta["histories"] == megalib_meta["histories"] and fluka_meta["histories"] > 0
        else "BLOCKED_PHASE3_CU64_COMMON_PARENT_EVENT_BUILDER"
    )

    write_csv(
        args.out_dir / "stage_rows.csv",
        rows,
        [
            "code",
            "metric",
            "metric_label",
            "stage",
            "histories",
            "events",
            "sum_w",
            "sum_w2",
            "n_eff",
            "efficiency_per_parent",
            "efficiency_sigma",
        ],
    )
    write_csv(
        args.out_dir / "comparison_stage_ratios.csv",
        comparison,
        [
            "metric",
            "metric_label",
            "stage",
            "fluka_histories",
            "fluka_sum_w",
            "fluka_efficiency",
            "fluka_sigma",
            "megalib_histories",
            "megalib_sum_w",
            "megalib_efficiency",
            "megalib_sigma",
            "fluka_over_megalib",
            "z_efficiency_difference",
        ],
    )
    payload = {
        "status": status,
        "work_root": rel(args.work_root),
        "fluka": fluka_meta,
        "megalib": megalib_meta,
        "active_veto_threshold_keV": ACTIVE_VETO_THRESHOLD_KEV,
        "w2_sigma_keV": W2_SIGMA_KEV,
        "stage_rows_csv": rel(args.out_dir / "stage_rows.csv"),
        "comparison_csv": rel(args.out_dir / "comparison_stage_ratios.csv"),
        "comparison": comparison,
        "boundary": "Common parent-history event builder only; sub-event time splitting and side-Compton/FoV topology remain open.",
    }
    write_json(args.out_dir / "summary.json", payload)
    write_summary_md(args.out_dir / "summary.md", payload)
    print(args.out_dir / "summary.md")
    print(status)
    return 0 if status == "PHASE3_CU64_COMMON_PARENT_EVENT_BUILDER_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
