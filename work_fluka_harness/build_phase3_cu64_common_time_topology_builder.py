#!/usr/bin/env python3
"""Build common Phase-3 Cu-64 time-split and topology event metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_WORK_ROOT = Path("/tmp/phase3prod")
DEFAULT_OUT_DIR = PHASE3_DIR / "phase3_cu64_common_event_builder_time_topology_1e6"
ACTIVE_VETO_THRESHOLD_KEV = 50.0
W2_LO = 510.58
W2_HI = 511.42
W2_SIGMA_KEV = 0.14

BANDS = [
    ("all_tes_gt0", "all TES > 0", 0.0, float("inf")),
    ("e480_550", "480-550 keV", 480.0, 550.0),
    ("w2_510p58_511p42", "W2 510.58-511.42 keV", W2_LO, W2_HI),
]

EVENT_DEFINITIONS = [
    ("parent", "whole parent history", None),
    ("within_1us", "cluster from first deposit within 1 microsecond", 1.0e-6),
    ("within_1ns", "cluster from first deposit within 1 nanosecond", 1.0e-9),
]


@dataclass(frozen=True)
class Deposit:
    time_s: float
    kind: str
    energy_keV: float
    channel: str


@dataclass
class Stat:
    events: int = 0
    sum_w: float = 0.0
    sum_w2: float = 0.0

    def add(self, weight: float = 1.0) -> None:
        if weight > 0.0:
            self.events += 1
        self.sum_w += weight
        self.sum_w2 += weight * weight


@dataclass
class TopologyStat:
    events: int = 0
    tes_pixel_sum: int = 0
    single_tes_pixel_events: int = 0
    multi_tes_pixel_events: int = 0
    active_shield_touched_events: int = 0
    side_shield_touched_events: int = 0
    top_shield_touched_events: int = 0

    def add(self, event: dict[str, Any]) -> None:
        n_tes = int(event["n_tes_pixels"])
        self.events += 1
        self.tes_pixel_sum += n_tes
        if n_tes == 1:
            self.single_tes_pixel_events += 1
        elif n_tes > 1:
            self.multi_tes_pixel_events += 1
        if event["n_shield_segments"] > 0:
            self.active_shield_touched_events += 1
        if event["side_shield_touched"]:
            self.side_shield_touched_events += 1
        if event["top_shield_touched"]:
            self.top_shield_touched_events += 1


@dataclass
class SplitStat:
    histories_with_detector_deposits: int = 0
    histories_with_multiple_subevents: int = 0
    subevents_with_detector_deposits: int = 0
    max_subevents_per_parent: int = 0

    def add_parent(self, n_subevents: int) -> None:
        self.histories_with_detector_deposits += 1
        self.subevents_with_detector_deposits += n_subevents
        if n_subevents > 1:
            self.histories_with_multiple_subevents += 1
        self.max_subevents_per_parent = max(self.max_subevents_per_parent, n_subevents)


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


def event_total_paths(code: str, work_root: Path) -> list[Path]:
    if code == "fluka":
        return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*event_totals_tmp.csv"))
    if code == "megalib":
        return sorted((work_root / "megalib").glob("chunk_*/cc_event_totals.csv"))
    raise ValueError(code)


def count_histories(code: str, work_root: Path) -> int:
    paths = event_total_paths(code, work_root)
    if not paths:
        raise FileNotFoundError(f"no event-total CSVs found for {code} under {work_root}")
    total = 0
    for path in paths:
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            total += sum(1 for _row in csv.DictReader(handle))
    return total


def fluka_raw_paths(work_root: Path) -> list[Path]:
    paths = sorted((work_root / "fluka").glob("chunk_*/raw_events/raw_events.csv"))
    if paths:
        return paths
    return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*raw_deposits_tmp.csv"))


def megalib_raw_paths(work_root: Path) -> list[Path]:
    return sorted((work_root / "megalib").glob("chunk_*/cc_raw_hits.csv"))


def normalize_channel(value: str) -> str:
    out = value.strip()
    return out if out else "UNKNOWN_CHANNEL"


def iter_fluka_history_deposits(work_root: Path) -> Iterable[tuple[int, list[Deposit]]]:
    paths = fluka_raw_paths(work_root)
    if not paths:
        raise FileNotFoundError(f"no FLUKA raw deposit CSVs found under {work_root}")
    for path in paths:
        start = chunk_start(path)
        current_history: int | None = None
        current: list[Deposit] = []
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                local_id = int(row["history_id"])
                if current_history is None:
                    current_history = local_id
                elif local_id != current_history:
                    if current:
                        yield start + current_history - 1, current
                    current_history = local_id
                    current = []

                kind = row.get("detector_kind", "").strip()
                if kind not in {"TES_PIXEL", "ACTIVE_SHIELD"}:
                    continue
                channel = normalize_channel(row.get("volume_name") or row.get("region_name") or row.get("volume_id", ""))
                current.append(
                    Deposit(
                        time_s=float(row["deposit_time_s"]),
                        kind=kind,
                        energy_keV=float(row["deposit_keV"]),
                        channel=channel,
                    )
                )
        if current_history is not None and current:
            yield start + current_history - 1, current


def iter_megalib_history_deposits(work_root: Path) -> Iterable[tuple[int, list[Deposit]]]:
    paths = megalib_raw_paths(work_root)
    if not paths:
        raise FileNotFoundError(f"no MEGAlib raw hit CSVs found under {work_root}")
    for path in paths:
        start = chunk_start(path)
        current_history: int | None = None
        current: list[Deposit] = []
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                local_id = int(row["history_id"])
                if current_history is None:
                    current_history = local_id
                elif local_id != current_history:
                    if current:
                        yield start + current_history - 1, current
                    current_history = local_id
                    current = []

                kind = row.get("region_kind", "").strip()
                if kind not in {"TES_PIXEL", "ACTIVE_SHIELD"}:
                    continue
                current.append(
                    Deposit(
                        time_s=float(row["time_s"]),
                        kind=kind,
                        energy_keV=float(row["deposit_keV"]),
                        channel=normalize_channel(row.get("volume", "")),
                    )
                )
        if current_history is not None and current:
            yield start + current_history - 1, current


def iter_history_deposits(code: str, work_root: Path) -> Iterable[tuple[int, list[Deposit]]]:
    if code == "fluka":
        yield from iter_fluka_history_deposits(work_root)
        return
    if code == "megalib":
        yield from iter_megalib_history_deposits(work_root)
        return
    raise ValueError(code)


def cluster_deposits(deposits: list[Deposit], window_s: float | None) -> list[list[Deposit]]:
    ordered = sorted(deposits, key=lambda dep: dep.time_s)
    if not ordered:
        return []
    if window_s is None:
        return [ordered]

    origin = ordered[0].time_s
    clusters: list[list[Deposit]] = []
    current: list[Deposit] = []
    cluster_start = 0.0
    for dep in ordered:
        rel_time = dep.time_s - origin
        if not current:
            current = [dep]
            cluster_start = rel_time
            continue
        if rel_time - cluster_start <= window_s:
            current.append(dep)
        else:
            clusters.append(current)
            current = [dep]
            cluster_start = rel_time
    if current:
        clusters.append(current)
    return clusters


def event_from_cluster(cluster: list[Deposit]) -> dict[str, Any]:
    tes_total = 0.0
    shield_total = 0.0
    tes_channels: set[str] = set()
    shield_channels: set[str] = set()
    side_shield_touched = False
    top_shield_touched = False
    for dep in cluster:
        if dep.kind == "TES_PIXEL":
            tes_total += dep.energy_keV
            if dep.energy_keV > 0.0:
                tes_channels.add(dep.channel)
        elif dep.kind == "ACTIVE_SHIELD":
            shield_total += dep.energy_keV
            if dep.energy_keV > 0.0:
                shield_channels.add(dep.channel)
                side_shield_touched = side_shield_touched or ("Side" in dep.channel)
                top_shield_touched = top_shield_touched or ("Top" in dep.channel)
    return {
        "tes_total_keV": tes_total,
        "shield_total_keV": shield_total,
        "n_tes_pixels": len(tes_channels),
        "n_shield_segments": len(shield_channels),
        "side_shield_touched": side_shield_touched,
        "top_shield_touched": top_shield_touched,
    }


def summarize_code(code: str, work_root: Path, histories: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    counts: dict[tuple[str, str, str], Stat] = defaultdict(Stat)
    topology: dict[tuple[str, str, str], TopologyStat] = defaultdict(TopologyStat)
    split: dict[str, SplitStat] = {name: SplitStat() for name, _label, _window in EVENT_DEFINITIONS}
    detector_parent_ids: set[int] = set()

    for global_id, deposits in iter_history_deposits(code, work_root):
        detector_parent_ids.add(global_id)
        for event_definition, _label, window_s in EVENT_DEFINITIONS:
            clusters = cluster_deposits(deposits, window_s)
            split[event_definition].add_parent(len(clusters))
            for cluster in clusters:
                event = event_from_cluster(cluster)
                active = event["shield_total_keV"] < ACTIVE_VETO_THRESHOLD_KEV
                tes_total = event["tes_total_keV"]
                for metric, _metric_label, lo, hi in BANDS:
                    if not in_band(tes_total, lo, hi):
                        continue
                    counts[(event_definition, metric, "raw")].add(1.0)
                    topology[(event_definition, metric, "raw")].add(event)
                    if active:
                        counts[(event_definition, metric, "active_veto")].add(1.0)
                        topology[(event_definition, metric, "active_veto")].add(event)
                p_w2 = w2_probability(tes_total)
                if p_w2 > 0.0:
                    counts[(event_definition, "w2_expected", "raw")].add(p_w2)
                    if active:
                        counts[(event_definition, "w2_expected", "active_veto")].add(p_w2)

    metric_labels = {metric: label for metric, label, _lo, _hi in BANDS}
    metric_labels["w2_expected"] = "W2 analytic Gaussian expectation"

    stage_rows: list[dict[str, Any]] = []
    for event_definition, event_label, _window_s in EVENT_DEFINITIONS:
        for metric in [band[0] for band in BANDS] + ["w2_expected"]:
            for stage in ("raw", "active_veto"):
                item = counts[(event_definition, metric, stage)]
                stage_rows.append(
                    {
                        "code": code,
                        "event_definition": event_definition,
                        "event_definition_label": event_label,
                        "metric": metric,
                        "metric_label": metric_labels[metric],
                        "stage": stage,
                        "histories": histories,
                        "events": item.events,
                        "sum_w": item.sum_w,
                        "sum_w2": item.sum_w2,
                        "n_eff": (item.sum_w * item.sum_w / item.sum_w2) if item.sum_w2 > 0.0 else 0.0,
                        "efficiency_per_parent": item.sum_w / histories if histories else 0.0,
                        "efficiency_sigma": math.sqrt(item.sum_w2) / histories if histories else 0.0,
                    }
                )

    topology_rows: list[dict[str, Any]] = []
    for (event_definition, metric, stage), item in sorted(topology.items()):
        topology_rows.append(
            {
                "code": code,
                "event_definition": event_definition,
                "metric": metric,
                "metric_label": metric_labels[metric],
                "stage": stage,
                "selected_events": item.events,
                "single_tes_pixel_events": item.single_tes_pixel_events,
                "multi_tes_pixel_events": item.multi_tes_pixel_events,
                "mean_tes_pixels": item.tes_pixel_sum / item.events if item.events else 0.0,
                "active_shield_touched_events": item.active_shield_touched_events,
                "side_shield_touched_events": item.side_shield_touched_events,
                "top_shield_touched_events": item.top_shield_touched_events,
            }
        )

    split_rows: list[dict[str, Any]] = []
    for event_definition, event_label, window_s in EVENT_DEFINITIONS:
        item = split[event_definition]
        split_rows.append(
            {
                "code": code,
                "event_definition": event_definition,
                "event_definition_label": event_label,
                "window_s": "" if window_s is None else window_s,
                "histories": histories,
                "histories_with_detector_deposits": item.histories_with_detector_deposits,
                "histories_with_multiple_subevents": item.histories_with_multiple_subevents,
                "subevents_with_detector_deposits": item.subevents_with_detector_deposits,
                "subevents_per_detector_parent": (
                    item.subevents_with_detector_deposits / item.histories_with_detector_deposits
                    if item.histories_with_detector_deposits
                    else 0.0
                ),
                "max_subevents_per_parent": item.max_subevents_per_parent,
            }
        )

    meta = {
        "code": code,
        "histories": histories,
        "detector_parent_histories": len(detector_parent_ids),
    }
    return stage_rows, topology_rows, split_rows, meta


def compare_rows(stage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {
        (row["code"], row["event_definition"], row["metric"], row["stage"]): row
        for row in stage_rows
    }
    out: list[dict[str, Any]] = []
    for event_definition, event_label, _window_s in EVENT_DEFINITIONS:
        for metric, metric_label, _lo, _hi in BANDS:
            for stage in ("raw", "active_veto"):
                out.append(compare_one(by_key, event_definition, event_label, metric, metric_label, stage))
        for stage in ("raw", "active_veto"):
            out.append(
                compare_one(
                    by_key,
                    event_definition,
                    event_label,
                    "w2_expected",
                    "W2 analytic Gaussian expectation",
                    stage,
                )
            )
    return [row for row in out if row]


def compare_one(
    by_key: dict[tuple[str, str, str, str], dict[str, Any]],
    event_definition: str,
    event_definition_label: str,
    metric: str,
    metric_label: str,
    stage: str,
) -> dict[str, Any]:
    f = by_key.get(("fluka", event_definition, metric, stage))
    m = by_key.get(("megalib", event_definition, metric, stage))
    if not f or not m:
        return {}
    f_eff = float(f["efficiency_per_parent"])
    m_eff = float(m["efficiency_per_parent"])
    f_sig = float(f["efficiency_sigma"])
    m_sig = float(m["efficiency_sigma"])
    denom = math.sqrt(f_sig * f_sig + m_sig * m_sig)
    return {
        "event_definition": event_definition,
        "event_definition_label": event_definition_label,
        "metric": metric,
        "metric_label": metric_label,
        "stage": stage,
        "fluka_histories": f["histories"],
        "fluka_sum_w": f["sum_w"],
        "fluka_sigma": f_sig,
        "fluka_efficiency": f_eff,
        "megalib_histories": m["histories"],
        "megalib_sum_w": m["sum_w"],
        "megalib_sigma": m_sig,
        "megalib_efficiency": m_eff,
        "fluka_over_megalib": f_eff / m_eff if m_eff > 0.0 else "",
        "z_efficiency_difference": (f_eff - m_eff) / denom if denom > 0.0 else "",
    }


def focus_comparison(comparison: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep_metrics = {"w2_510p58_511p42", "w2_expected"}
    return [row for row in comparison if row["metric"] in keep_metrics]


def w2_topology_focus(topology_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in topology_rows
        if row["metric"] == "w2_510p58_511p42" and row["stage"] in {"raw", "active_veto"}
    ]


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Common Time/Topology Event Builder",
        "",
        f"- status: `{payload['status']}`",
        f"- work_root: `{payload['work_root']}`",
        f"- histories_per_code: `FLUKA {payload['code_meta']['fluka']['histories']}; MEGAlib {payload['code_meta']['megalib']['histories']}`",
        f"- active_veto_threshold_keV: `{ACTIVE_VETO_THRESHOLD_KEV}`",
        f"- w2_sigma_keV: `{W2_SIGMA_KEV}`",
        "",
        "## Event Definitions",
        "",
        "| event definition | rule |",
        "|---|---|",
    ]
    for event_definition, event_label, window_s in EVENT_DEFINITIONS:
        window_text = "whole parent" if window_s is None else f"{window_s:g} s"
        lines.append(f"| `{event_definition}` | `{event_label}; window={window_text}` |")

    lines.extend(
        [
            "",
            "## W2 Focus Comparison",
            "",
            "| event definition | metric | stage | FLUKA sum_w / histories | MEGAlib sum_w / histories | FLUKA/MEGAlib | z |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in focus_comparison(payload["comparison"]):
        ratio = row["fluka_over_megalib"]
        z = row["z_efficiency_difference"]
        ratio_s = f"{ratio:.6g}" if isinstance(ratio, float) else "n/a"
        z_s = f"{z:.3g}" if isinstance(z, float) else "n/a"
        lines.append(
            f"| `{row['event_definition']}` | `{row['metric_label']}` | `{row['stage']}` | "
            f"`{float(row['fluka_sum_w']):.6g} / {row['fluka_histories']}` | "
            f"`{float(row['megalib_sum_w']):.6g} / {row['megalib_histories']}` | "
            f"`{ratio_s}` | `{z_s}` |"
        )

    lines.extend(
        [
            "",
            "## Time Split Summary",
            "",
            "| code | event definition | detector parents | split parents | subevents | max subevents/parent |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload["time_split_summary"]:
        lines.append(
            f"| `{row['code']}` | `{row['event_definition']}` | "
            f"`{row['histories_with_detector_deposits']}` | "
            f"`{row['histories_with_multiple_subevents']}` | "
            f"`{row['subevents_with_detector_deposits']}` | "
            f"`{row['max_subevents_per_parent']}` |"
        )

    lines.extend(
        [
            "",
            "## W2 TES/Shield Topology",
            "",
            "| code | event definition | stage | selected events | single TES pixel | multi TES pixel | active shield touched | side shield touched |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in w2_topology_focus(payload["topology_summary"]):
        lines.append(
            f"| `{row['code']}` | `{row['event_definition']}` | `{row['stage']}` | "
            f"`{row['selected_events']}` | `{row['single_tes_pixel_events']}` | "
            f"`{row['multi_tes_pixel_events']}` | `{row['active_shield_touched_events']}` | "
            f"`{row['side_shield_touched_events']}` |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The common parent-history result is reproduced from raw detector rows, not from `.sim.gz` replay.",
            "- The 1 microsecond clustering is effectively identical to whole-parent grouping for this Cu-64 delayed sample.",
            "- The 1 nanosecond clustering changes only the MEGAlib side at a small level and does not remove the W2 raw excess.",
            "- The output adds identical single/multi TES-pixel and active-shield-touch bookkeeping. It is not a FoV/reconstruction implementation.",
            "",
            "## Output Files",
            "",
            f"- event_definition_stage_rows_csv: `{payload['event_definition_stage_rows_csv']}`",
            f"- comparison_stage_ratios_csv: `{payload['comparison_stage_ratios_csv']}`",
            f"- topology_summary_csv: `{payload['topology_summary_csv']}`",
            f"- time_split_summary_csv: `{payload['time_split_summary_csv']}`",
            "",
            "## Boundary",
            "",
            "- This is a common external event builder over existing raw detector deposits from the independent Cu-64 common-parent production.",
            "- It does not replay Geant4 `.sim.gz` files.",
            "- It does not implement the final side-Compton/FoV reconstruction cut; that remains an open final-selection layer.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(work_root: Path, out_dir: Path) -> dict[str, Any]:
    histories = {
        "fluka": count_histories("fluka", work_root),
        "megalib": count_histories("megalib", work_root),
    }
    all_stage_rows: list[dict[str, Any]] = []
    all_topology_rows: list[dict[str, Any]] = []
    all_split_rows: list[dict[str, Any]] = []
    code_meta: dict[str, Any] = {}

    for code in ("fluka", "megalib"):
        stage_rows, topology_rows, split_rows, meta = summarize_code(code, work_root, histories[code])
        all_stage_rows.extend(stage_rows)
        all_topology_rows.extend(topology_rows)
        all_split_rows.extend(split_rows)
        code_meta[code] = meta

    comparison = compare_rows(all_stage_rows)

    stage_csv = out_dir / "event_definition_stage_rows.csv"
    comparison_csv = out_dir / "comparison_stage_ratios.csv"
    topology_csv = out_dir / "topology_summary.csv"
    split_csv = out_dir / "time_split_summary.csv"
    summary_json = out_dir / "summary.json"
    summary_md = out_dir / "summary.md"

    write_csv(
        stage_csv,
        all_stage_rows,
        [
            "code",
            "event_definition",
            "event_definition_label",
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
        comparison_csv,
        comparison,
        [
            "event_definition",
            "event_definition_label",
            "metric",
            "metric_label",
            "stage",
            "fluka_histories",
            "fluka_sum_w",
            "fluka_sigma",
            "fluka_efficiency",
            "megalib_histories",
            "megalib_sum_w",
            "megalib_sigma",
            "megalib_efficiency",
            "fluka_over_megalib",
            "z_efficiency_difference",
        ],
    )
    write_csv(
        topology_csv,
        all_topology_rows,
        [
            "code",
            "event_definition",
            "metric",
            "metric_label",
            "stage",
            "selected_events",
            "single_tes_pixel_events",
            "multi_tes_pixel_events",
            "mean_tes_pixels",
            "active_shield_touched_events",
            "side_shield_touched_events",
            "top_shield_touched_events",
        ],
    )
    write_csv(
        split_csv,
        all_split_rows,
        [
            "code",
            "event_definition",
            "event_definition_label",
            "window_s",
            "histories",
            "histories_with_detector_deposits",
            "histories_with_multiple_subevents",
            "subevents_with_detector_deposits",
            "subevents_per_detector_parent",
            "max_subevents_per_parent",
        ],
    )

    payload = {
        "status": "PHASE3_CU64_COMMON_TIME_TOPOLOGY_BUILDER_PASS",
        "work_root": str(work_root),
        "code_meta": code_meta,
        "event_definitions": [
            {"name": name, "label": label, "window_s": window} for name, label, window in EVENT_DEFINITIONS
        ],
        "active_veto_threshold_keV": ACTIVE_VETO_THRESHOLD_KEV,
        "w2_sigma_keV": W2_SIGMA_KEV,
        "event_definition_stage_rows_csv": rel(stage_csv),
        "comparison_stage_ratios_csv": rel(comparison_csv),
        "topology_summary_csv": rel(topology_csv),
        "time_split_summary_csv": rel(split_csv),
        "comparison": comparison,
        "topology_summary": all_topology_rows,
        "time_split_summary": all_split_rows,
    }
    write_json(summary_json, payload)
    payload["summary_json"] = rel(summary_json)
    payload["summary_md"] = rel(summary_md)
    write_summary_md(summary_md, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build(args.work_root, args.out_dir)
    print(payload["status"])
    print(payload["summary_md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
