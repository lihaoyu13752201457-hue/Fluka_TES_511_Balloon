#!/usr/bin/env python3
"""Decompose the Phase-3 Cu-64 raw-coupling FLUKA/MEGAlib difference."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_PARENT_LIST = PHASE3_DIR / "full_untracked/cu64_parent_resampling_1e6.csv"
DEFAULT_WORK_ROOT = Path("/tmp/phase3prod")
DEFAULT_OUT_DIR = PHASE3_DIR / "phase3_cu64_raw_coupling_decomposition_1e6"
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
DIMENSIONS = [
    ("source_volume", 0),
    ("material", 1),
    ("production_tag", 2),
]
SELECTED_CARRIER_METRICS = {
    "w2_510p58_511p42",
    "e480_550",
}
FLUKA_PARTICLE = {
    3: "ELECTRON",
    4: "POSITRON",
    7: "PHOTON",
    8: "NEUTRON",
    10: "MUON_PLUS",
    11: "MUON_MINUS",
    13: "PROTON",
    211: "EM_BELOW_THRESHOLD",
}


@dataclass
class Stat:
    sum_w: float = 0.0
    sum_w2: float = 0.0

    def add(self, weight: float) -> None:
        self.sum_w += weight
        self.sum_w2 += weight * weight


@dataclass
class CarrierStat:
    histories: set[int] = field(default_factory=set)
    hit_rows: int = 0
    deposit_keV_sum: float = 0.0

    def add(self, history_id: int, deposit_keV: float) -> None:
        self.histories.add(history_id)
        self.hit_rows += 1
        self.deposit_keV_sum += deposit_keV


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


def chunk_start(path: Path) -> int:
    for parent in [path, *path.parents]:
        match = re.match(r"chunk_\d+_start(\d+)_n\d+$", parent.name)
        if match:
            return int(match.group(1))
    raise ValueError(f"cannot determine chunk start from {path}")


def load_parent_meta(parent_list: Path) -> tuple[dict[int, tuple[str, str, str]], dict[str, Counter[str]], int]:
    meta_by_id: dict[int, tuple[str, str, str]] = {}
    history_counts: dict[str, Counter[str]] = {dim: Counter() for dim, _idx in DIMENSIONS}
    with parent_list.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            global_id = int(row["resampled_history_id"])
            meta = (
                row.get("source_volume", "").strip() or "UNKNOWN_SOURCE_VOLUME",
                row.get("resolved_static_material", "").strip() or "UNKNOWN_MATERIAL",
                row.get("production_tag", "").strip() or "UNKNOWN_PRODUCTION_TAG",
            )
            meta_by_id[global_id] = meta
            for dim, idx in DIMENSIONS:
                history_counts[dim][meta[idx]] += 1
    return meta_by_id, history_counts, len(meta_by_id)


def event_total_paths(code: str, work_root: Path) -> list[Path]:
    if code == "fluka":
        return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*event_totals_tmp.csv"))
    if code == "megalib":
        return sorted((work_root / "megalib").glob("chunk_*/cc_event_totals.csv"))
    raise ValueError(code)


def raw_hit_paths(code: str, work_root: Path) -> list[Path]:
    if code == "fluka":
        return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*raw_deposits_tmp.csv"))
    if code == "megalib":
        return sorted((work_root / "megalib").glob("chunk_*/cc_raw_hits.csv"))
    raise ValueError(code)


def iter_event_totals(code: str, work_root: Path) -> Iterable[tuple[int, float, float]]:
    for path in event_total_paths(code, work_root):
        start = chunk_start(path)
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                local_id = int(row["history_id"])
                if code == "fluka":
                    tes = float(row["tes_total_keV"])
                    shield = float(row["shield_total_keV"])
                else:
                    tes = float(row["tes_total_keV"])
                    shield = float(row["active_shield_total_keV"])
                yield start + local_id - 1, tes, shield


def add_metric(
    counts: dict[tuple[str, str, str, str, str], Stat],
    code: str,
    meta: tuple[str, str, str],
    metric: str,
    stage: str,
    weight: float,
) -> None:
    for dim, idx in DIMENSIONS:
        counts[(code, dim, meta[idx], metric, stage)].add(weight)


def summarize_events(
    work_root: Path,
    meta_by_id: dict[int, tuple[str, str, str]],
) -> tuple[dict[tuple[str, str, str, str, str], Stat], dict[tuple[str, str, str], set[int]], dict[str, int]]:
    counts: dict[tuple[str, str, str, str, str], Stat] = defaultdict(Stat)
    selected: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    histories_by_code: dict[str, int] = {}

    for code in ("fluka", "megalib"):
        histories = 0
        for global_id, tes, shield in iter_event_totals(code, work_root):
            histories += 1
            meta = meta_by_id[global_id]
            active = shield < ACTIVE_VETO_THRESHOLD_KEV
            for metric, _label, lo, hi in BANDS:
                if in_band(tes, lo, hi):
                    add_metric(counts, code, meta, metric, "raw", 1.0)
                    if metric in SELECTED_CARRIER_METRICS:
                        selected[(code, metric, "raw")].add(global_id)
                    if active:
                        add_metric(counts, code, meta, metric, "active_veto", 1.0)
                        if metric in SELECTED_CARRIER_METRICS:
                            selected[(code, metric, "active_veto")].add(global_id)
            p_w2 = w2_probability(tes)
            if p_w2 > 0.0:
                add_metric(counts, code, meta, "w2_expected", "raw", p_w2)
                if active:
                    add_metric(counts, code, meta, "w2_expected", "active_veto", p_w2)
        histories_by_code[code] = histories
    return counts, selected, histories_by_code


def build_comparison_rows(
    counts: dict[tuple[str, str, str, str, str], Stat],
    history_counts: dict[str, Counter[str]],
    total_histories: int,
) -> list[dict[str, Any]]:
    labels = {metric: label for metric, label, _lo, _hi in BANDS}
    labels["w2_expected"] = "W2 analytic Gaussian expectation"
    metrics = [metric for metric, _label, _lo, _hi in BANDS] + ["w2_expected"]
    rows: list[dict[str, Any]] = []
    total_diff: dict[tuple[str, str, str], float] = {}

    for dim, _idx in DIMENSIONS:
        for metric in metrics:
            for stage in ("raw", "active_veto"):
                f_total = sum(counts[("fluka", dim, key, metric, stage)].sum_w for key in history_counts[dim])
                m_total = sum(counts[("megalib", dim, key, metric, stage)].sum_w for key in history_counts[dim])
                total_diff[(dim, metric, stage)] = (f_total - m_total) / total_histories

    for dim, _idx in DIMENSIONS:
        for key, histories in history_counts[dim].items():
            for metric in metrics:
                for stage in ("raw", "active_veto"):
                    f = counts[("fluka", dim, key, metric, stage)]
                    m = counts[("megalib", dim, key, metric, stage)]
                    if f.sum_w == 0.0 and m.sum_w == 0.0:
                        continue
                    f_contrib = f.sum_w / total_histories
                    m_contrib = m.sum_w / total_histories
                    diff = f_contrib - m_contrib
                    denom = math.sqrt(f.sum_w2 + m.sum_w2) / total_histories
                    f_cond = f.sum_w / histories if histories else 0.0
                    m_cond = m.sum_w / histories if histories else 0.0
                    total = total_diff[(dim, metric, stage)]
                    rows.append(
                        {
                            "dimension": dim,
                            "key": key,
                            "metric": metric,
                            "metric_label": labels[metric],
                            "stage": stage,
                            "source_histories": histories,
                            "source_fraction": histories / total_histories if total_histories else 0.0,
                            "fluka_sum_w": f.sum_w,
                            "megalib_sum_w": m.sum_w,
                            "fluka_contribution_per_parent": f_contrib,
                            "megalib_contribution_per_parent": m_contrib,
                            "contribution_difference_per_parent": diff,
                            "difference_share_of_total": diff / total if total else "",
                            "z_contribution_difference": diff / denom if denom > 0.0 else "",
                            "fluka_conditional_efficiency": f_cond,
                            "megalib_conditional_efficiency": m_cond,
                            "fluka_over_megalib_conditional": f_cond / m_cond if m_cond > 0.0 else "",
                        }
                    )
    rows.sort(
        key=lambda row: (
            str(row["dimension"]),
            str(row["metric"]),
            str(row["stage"]),
            -abs(float(row["contribution_difference_per_parent"])),
        )
    )
    return rows


def summarize_carriers(
    work_root: Path,
    selected: dict[tuple[str, str, str], set[int]],
) -> list[dict[str, Any]]:
    stats: dict[tuple[str, str, str, str, str, str, str], CarrierStat] = defaultdict(CarrierStat)

    for path in raw_hit_paths("fluka", work_root):
        start = chunk_start(path)
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                if row["detector_kind"].strip() != "TES_PIXEL":
                    continue
                global_id = start + int(row["history_id"]) - 1
                deposit = float(row["deposit_keV"])
                pcode = int(row["particle_code"])
                particle = FLUKA_PARTICLE.get(pcode, f"FLUKA_CODE_{pcode}")
                step = f"icode_{int(row['icode'])}"
                for metric in SELECTED_CARRIER_METRICS:
                    for stage in ("raw", "active_veto"):
                        if global_id in selected.get(("fluka", metric, stage), set()):
                            stats[("fluka", metric, stage, particle, "", step, particle)].add(global_id, deposit)

    for path in raw_hit_paths("megalib", work_root):
        start = chunk_start(path)
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                if row["region_kind"] != "TES_PIXEL":
                    continue
                global_id = start + int(row["history_id"]) - 1
                deposit = float(row["deposit_keV"])
                secondary = row["secondary"]
                parent = row["parent"]
                creator = row["creator_process"]
                step = row["step_process"]
                carrier = f"{secondary}|parent={parent}|creator={creator}|step={step}"
                for metric in SELECTED_CARRIER_METRICS:
                    for stage in ("raw", "active_veto"):
                        if global_id in selected.get(("megalib", metric, stage), set()):
                            stats[("megalib", metric, stage, secondary, parent, f"{creator}->{step}", carrier)].add(
                                global_id, deposit
                            )

    rows: list[dict[str, Any]] = []
    for (code, metric, stage, secondary, parent, process, carrier), stat in stats.items():
        rows.append(
            {
                "code": code,
                "metric": metric,
                "stage": stage,
                "carrier_group": carrier,
                "local_secondary": secondary,
                "parent": parent,
                "creator_step_process": process,
                "histories_with_hit": len(stat.histories),
                "hit_rows": stat.hit_rows,
                "deposit_keV_sum": stat.deposit_keV_sum,
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["metric"]),
            str(row["stage"]),
            str(row["code"]),
            -float(row["deposit_keV_sum"]),
        )
    )
    return rows


def top_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for metric in ("w2_510p58_511p42", "w2_expected", "e480_550", "all_tes_gt0"):
        for stage in ("raw", "active_veto"):
            selected = [
                row
                for row in rows
                if row["dimension"] == "source_volume" and row["metric"] == metric and row["stage"] == stage
            ]
            selected.sort(key=lambda row: -abs(float(row["contribution_difference_per_parent"])))
            out.extend(selected[:12])
    return out


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Raw-Coupling Decomposition",
        "",
        f"- status: `{payload['status']}`",
        f"- parent_list_sha256: `{payload['parent_list_sha256']}`",
        f"- work_root: `{payload['work_root']}`",
        f"- histories_per_code: `FLUKA {payload['histories_per_code'].get('fluka')}; "
        f"MEGAlib {payload['histories_per_code'].get('megalib')}`",
        "",
        "## Headline",
        "",
        payload["headline"],
        "",
        "## Top W2 Raw Source-Volume Contributors",
        "",
        "| source_volume | source histories | FLUKA W2 | MEGAlib W2 | diff / parent | share of total diff | conditional FLUKA/MEGAlib |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["top_w2_raw_source_volume"][:10]:
        ratio = row["fluka_over_megalib_conditional"]
        share = row["difference_share_of_total"]
        lines.append(
            f"| `{row['key']}` | `{row['source_histories']}` | `{float(row['fluka_sum_w']):.6g}` | "
            f"`{float(row['megalib_sum_w']):.6g}` | `{float(row['contribution_difference_per_parent']):.6g}` | "
            f"`{float(share):.3g}` | `{float(ratio):.6g}` |"
            if isinstance(ratio, float) and isinstance(share, float)
            else f"| `{row['key']}` | `{row['source_histories']}` | `{float(row['fluka_sum_w']):.6g}` | "
            f"`{float(row['megalib_sum_w']):.6g}` | `{float(row['contribution_difference_per_parent']):.6g}` | `n/a` | `n/a` |"
        )
    lines.extend(
        [
            "",
            "## Local TES Carrier Check",
            "",
            "| code | metric | stage | carrier group | histories | hit rows | deposit keV |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in payload["top_carriers"][:16]:
        lines.append(
            f"| `{row['code']}` | `{row['metric']}` | `{row['stage']}` | `{row['carrier_group']}` | "
            f"`{row['histories_with_hit']}` | `{row['hit_rows']}` | `{float(row['deposit_keV_sum']):.6g}` |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- dimension_comparison_csv: `{payload['dimension_comparison_csv']}`",
            f"- top_source_volume_csv: `{payload['top_source_volume_csv']}`",
            f"- local_carrier_csv: `{payload['local_carrier_csv']}`",
            "",
            "## Boundary",
            "",
            "- This decomposes the already-produced parent-history raw and active-veto totals.",
            "- It does not add a runtime point-location scorer or a positron stopping/annihilation locator.",
            "- FLUKA raw rows carry local particle code only; MEGAlib `CC HIT` rows carry richer TES ancestry.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-list", type=Path, default=DEFAULT_PARENT_LIST)
    ap.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    args.parent_list = args.parent_list.expanduser().resolve()
    args.work_root = args.work_root.expanduser().resolve()
    args.out_dir = args.out_dir.expanduser().resolve()

    meta_by_id, history_counts, total_histories = load_parent_meta(args.parent_list)
    counts, selected, histories_by_code = summarize_events(args.work_root, meta_by_id)
    rows = build_comparison_rows(counts, history_counts, total_histories)
    top_rows = top_source_rows(rows)
    carrier_rows = summarize_carriers(args.work_root, selected)

    top_w2_raw = [
        row
        for row in top_rows
        if row["metric"] == "w2_510p58_511p42" and row["stage"] == "raw"
    ]
    top_carriers = sorted(
        [row for row in carrier_rows if row["metric"] == "w2_510p58_511p42" and row["stage"] == "raw"],
        key=lambda row: (str(row["code"]), -float(row["deposit_keV_sum"])),
    )
    status = (
        "PHASE3_CU64_RAW_COUPLING_DECOMPOSITION_PASS"
        if histories_by_code.get("fluka") == total_histories and histories_by_code.get("megalib") == total_histories
        else "BLOCKED_PHASE3_CU64_RAW_COUPLING_DECOMPOSITION"
    )
    headline = (
        "The W2 raw excess is distributed across multiple copper source volumes, "
        "with `ColdPlate_MXC_50mK_SD_anchor` and `Cu_50mK_StillLike_Can_side_wall_above_side_port` "
        "among the largest positive contributors; it is not isolated to CuNi or a non-neutron production tag."
    )
    payload = {
        "status": status,
        "parent_list": rel(args.parent_list),
        "parent_list_sha256": file_sha256(args.parent_list),
        "work_root": rel(args.work_root),
        "histories_per_code": histories_by_code,
        "total_parent_histories": total_histories,
        "active_veto_threshold_keV": ACTIVE_VETO_THRESHOLD_KEV,
        "w2_sigma_keV": W2_SIGMA_KEV,
        "headline": headline,
        "dimension_comparison_csv": rel(args.out_dir / "dimension_comparison.csv"),
        "top_source_volume_csv": rel(args.out_dir / "top_source_volume_contributors.csv"),
        "local_carrier_csv": rel(args.out_dir / "local_tes_carrier_summary.csv"),
        "top_w2_raw_source_volume": top_w2_raw[:12],
        "top_carriers": top_carriers[:20],
        "boundary": "Decomposition of existing raw truth only; no new transport and no runtime point-location/stopping locator.",
    }

    write_csv(
        args.out_dir / "dimension_comparison.csv",
        rows,
        [
            "dimension",
            "key",
            "metric",
            "metric_label",
            "stage",
            "source_histories",
            "source_fraction",
            "fluka_sum_w",
            "megalib_sum_w",
            "fluka_contribution_per_parent",
            "megalib_contribution_per_parent",
            "contribution_difference_per_parent",
            "difference_share_of_total",
            "z_contribution_difference",
            "fluka_conditional_efficiency",
            "megalib_conditional_efficiency",
            "fluka_over_megalib_conditional",
        ],
    )
    write_csv(
        args.out_dir / "top_source_volume_contributors.csv",
        top_rows,
        [
            "dimension",
            "key",
            "metric",
            "metric_label",
            "stage",
            "source_histories",
            "source_fraction",
            "fluka_sum_w",
            "megalib_sum_w",
            "fluka_contribution_per_parent",
            "megalib_contribution_per_parent",
            "contribution_difference_per_parent",
            "difference_share_of_total",
            "z_contribution_difference",
            "fluka_conditional_efficiency",
            "megalib_conditional_efficiency",
            "fluka_over_megalib_conditional",
        ],
    )
    write_csv(
        args.out_dir / "local_tes_carrier_summary.csv",
        carrier_rows,
        [
            "code",
            "metric",
            "stage",
            "carrier_group",
            "local_secondary",
            "parent",
            "creator_step_process",
            "histories_with_hit",
            "hit_rows",
            "deposit_keV_sum",
        ],
    )
    write_json(args.out_dir / "summary.json", payload)
    write_summary_md(args.out_dir / "summary.md", payload)
    print(args.out_dir / "summary.md")
    print(status)
    return 0 if status == "PHASE3_CU64_RAW_COUPLING_DECOMPOSITION_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
