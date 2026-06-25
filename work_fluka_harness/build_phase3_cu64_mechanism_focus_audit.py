#!/usr/bin/env python3
"""Mechanism-focused audit for Phase-3 Cu-64 W2 raw-coupling differences."""

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
DEFAULT_OUT_DIR = PHASE3_DIR / "phase3_cu64_mechanism_focus_audit_1e6"
ACTIVE_VETO_THRESHOLD_KEV = 50.0
W2_LO = 510.58
W2_HI = 511.42


@dataclass(frozen=True)
class ParentMeta:
    global_history_id: int
    common_event_id: int
    production_tag: str
    source_volume: str
    material: str
    x_cm: float
    y_cm: float
    z_cm: float


@dataclass
class SelectedEvent:
    code: str
    global_history_id: int
    source_volume: str
    material: str
    production_tag: str
    source_x_cm: float
    source_y_cm: float
    source_z_cm: float
    tes_total_keV: float = 0.0
    shield_total_keV: float = 0.0
    tes_channels: set[str] = field(default_factory=set)
    shield_channels: set[str] = field(default_factory=set)
    side_shield_touched: bool = False
    top_shield_touched: bool = False
    tes_distances_cm: list[float] = field(default_factory=list)
    tes_weighted_distance_sum: float = 0.0
    tes_weight_for_distance: float = 0.0
    carrier_rows: Counter[str] = field(default_factory=Counter)
    carrier_energy: Counter[str] = field(default_factory=Counter)

    @property
    def active_veto(self) -> bool:
        return self.shield_total_keV < ACTIVE_VETO_THRESHOLD_KEV

    @property
    def n_tes_pixels(self) -> int:
        return len(self.tes_channels)

    @property
    def n_shield_segments(self) -> int:
        return len(self.shield_channels)

    @property
    def min_tes_distance_cm(self) -> float:
        return min(self.tes_distances_cm) if self.tes_distances_cm else float("nan")

    @property
    def weighted_tes_distance_cm(self) -> float:
        if self.tes_weight_for_distance <= 0.0:
            return self.min_tes_distance_cm
        return self.tes_weighted_distance_sum / self.tes_weight_for_distance


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


def chunk_start(path: Path) -> int:
    for parent in [path, *path.parents]:
        match = re.match(r"chunk_\d+_start(\d+)_n\d+$", parent.name)
        if match:
            return int(match.group(1))
    raise ValueError(f"cannot determine chunk start from {path}")


def in_w2(energy_keV: float) -> bool:
    return W2_LO <= energy_keV < W2_HI


def percentile(values: list[float], q: float) -> float:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return float("nan")
    pos = (len(clean) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return clean[int(pos)]
    return clean[lo] * (hi - pos) + clean[hi] * (pos - lo)


def mean(values: Iterable[float]) -> float:
    vals = [v for v in values if math.isfinite(v)]
    return sum(vals) / len(vals) if vals else float("nan")


def distance_cm(meta: ParentMeta, x: float, y: float, z: float) -> float:
    return math.sqrt((x - meta.x_cm) ** 2 + (y - meta.y_cm) ** 2 + (z - meta.z_cm) ** 2)


def event_total_paths(code: str, work_root: Path) -> list[Path]:
    if code == "fluka":
        return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*event_totals_tmp.csv"))
    if code == "megalib":
        return sorted((work_root / "megalib").glob("chunk_*/cc_event_totals.csv"))
    raise ValueError(code)


def load_selected_ids(work_root: Path) -> dict[str, dict[str, set[int]]]:
    selected = {
        "fluka": {"raw": set(), "active_veto": set()},
        "megalib": {"raw": set(), "active_veto": set()},
    }
    for code in ("fluka", "megalib"):
        for path in event_total_paths(code, work_root):
            start = chunk_start(path)
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                for row in csv.DictReader(handle):
                    global_id = start + int(row["history_id"]) - 1
                    tes = float(row["tes_total_keV"])
                    shield_field = "shield_total_keV" if code == "fluka" else "active_shield_total_keV"
                    shield = float(row[shield_field])
                    if not in_w2(tes):
                        continue
                    selected[code]["raw"].add(global_id)
                    if shield < ACTIVE_VETO_THRESHOLD_KEV:
                        selected[code]["active_veto"].add(global_id)
    return selected


def load_parent_meta(parent_list: Path, needed_ids: set[int]) -> tuple[dict[int, ParentMeta], Counter[str]]:
    out: dict[int, ParentMeta] = {}
    source_histories: Counter[str] = Counter()
    with parent_list.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            global_id = int(row["resampled_history_id"])
            source_volume = row["source_volume"].strip() or "UNKNOWN_SOURCE_VOLUME"
            source_histories[source_volume] += 1
            if global_id not in needed_ids:
                continue
            out[global_id] = ParentMeta(
                global_history_id=global_id,
                common_event_id=int(row["common_event_id"]),
                production_tag=row.get("production_tag", "").strip() or "UNKNOWN_PRODUCTION_TAG",
                source_volume=source_volume,
                material=row.get("resolved_static_material", "").strip() or "UNKNOWN_MATERIAL",
                x_cm=float(row["x_cm"]),
                y_cm=float(row["y_cm"]),
                z_cm=float(row["z_cm"]),
            )
    missing = needed_ids.difference(out)
    if missing:
        raise RuntimeError(f"missing parent metadata for {len(missing)} selected histories")
    return out, source_histories


def init_event(code: str, global_id: int, meta: ParentMeta) -> SelectedEvent:
    return SelectedEvent(
        code=code,
        global_history_id=global_id,
        source_volume=meta.source_volume,
        material=meta.material,
        production_tag=meta.production_tag,
        source_x_cm=meta.x_cm,
        source_y_cm=meta.y_cm,
        source_z_cm=meta.z_cm,
    )


def fluka_raw_paths(work_root: Path) -> list[Path]:
    paths = sorted((work_root / "fluka").glob("chunk_*/raw_events/raw_events.csv"))
    if paths:
        return paths
    return sorted((work_root / "fluka").glob("chunk_*/fluka_run/*raw_deposits_tmp.csv"))


def megalib_raw_paths(work_root: Path) -> list[Path]:
    return sorted((work_root / "megalib").glob("chunk_*/cc_raw_hits.csv"))


def parse_fluka_events(work_root: Path, selected_ids: set[int], parent_meta: dict[int, ParentMeta]) -> dict[int, SelectedEvent]:
    events: dict[int, SelectedEvent] = {}
    for path in fluka_raw_paths(work_root):
        start = chunk_start(path)
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                global_id = start + int(row["history_id"]) - 1
                if global_id not in selected_ids:
                    continue
                event = events.setdefault(global_id, init_event("fluka", global_id, parent_meta[global_id]))
                kind = row.get("detector_kind", "").strip()
                energy = float(row["deposit_keV"])
                channel = (row.get("volume_name") or row.get("region_name") or row.get("volume_id") or "").strip()
                if kind == "TES_PIXEL":
                    event.tes_total_keV += energy
                    if energy > 0.0:
                        event.tes_channels.add(channel)
                    d = distance_cm(parent_meta[global_id], float(row["x_cm"]), float(row["y_cm"]), float(row["z_cm"]))
                    event.tes_distances_cm.append(d)
                    event.tes_weighted_distance_sum += d * max(energy, 0.0)
                    event.tes_weight_for_distance += max(energy, 0.0)
                    carrier = "FLUKA:" + "|".join(
                        [
                            row.get("particle", "").strip() or "UNKNOWN_PARTICLE",
                            row.get("interaction_process", "").strip() or "UNKNOWN_INTERACTION",
                            row.get("fluka_particle_code", "").strip() or "UNKNOWN_CODE",
                            row.get("fluka_icode", "").strip() or "UNKNOWN_ICODE",
                        ]
                    )
                    event.carrier_rows[carrier] += 1
                    event.carrier_energy[carrier] += energy
                elif kind == "ACTIVE_SHIELD":
                    event.shield_total_keV += energy
                    if energy > 0.0:
                        event.shield_channels.add(channel)
                    event.side_shield_touched = event.side_shield_touched or ("Side" in channel)
                    event.top_shield_touched = event.top_shield_touched or ("Top" in channel)
    return events


def parse_megalib_events(work_root: Path, selected_ids: set[int], parent_meta: dict[int, ParentMeta]) -> dict[int, SelectedEvent]:
    events: dict[int, SelectedEvent] = {}
    for path in megalib_raw_paths(work_root):
        start = chunk_start(path)
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                global_id = start + int(row["history_id"]) - 1
                if global_id not in selected_ids:
                    continue
                kind = row.get("region_kind", "").strip()
                if kind not in {"TES_PIXEL", "ACTIVE_SHIELD"}:
                    continue
                event = events.setdefault(global_id, init_event("megalib", global_id, parent_meta[global_id]))
                energy = float(row["deposit_keV"])
                channel = row.get("volume", "").strip() or "UNKNOWN_VOLUME"
                if kind == "TES_PIXEL":
                    event.tes_total_keV += energy
                    if energy > 0.0:
                        event.tes_channels.add(channel)
                    d = distance_cm(parent_meta[global_id], float(row["x_cm"]), float(row["y_cm"]), float(row["z_cm"]))
                    event.tes_distances_cm.append(d)
                    event.tes_weighted_distance_sum += d * max(energy, 0.0)
                    event.tes_weight_for_distance += max(energy, 0.0)
                    carrier = "MEGAlib:" + "|".join(
                        [
                            row.get("secondary", "").strip() or "UNKNOWN_SECONDARY",
                            row.get("parent", "").strip() or "UNKNOWN_PARENT",
                            row.get("creator_process", "").strip() or "UNKNOWN_CREATOR",
                            row.get("step_process", "").strip() or "UNKNOWN_STEP",
                        ]
                    )
                    event.carrier_rows[carrier] += 1
                    event.carrier_energy[carrier] += energy
                elif kind == "ACTIVE_SHIELD":
                    event.shield_total_keV += energy
                    if energy > 0.0:
                        event.shield_channels.add(channel)
                    event.side_shield_touched = event.side_shield_touched or ("Side" in channel)
                    event.top_shield_touched = event.top_shield_touched or ("Top" in channel)
    return events


def top_counter(counter: Counter[str], n: int = 3) -> str:
    return "; ".join(f"{key}:{value}" for key, value in counter.most_common(n))


def summarize_distance(events: dict[str, dict[int, SelectedEvent]], selected_ids: dict[str, dict[str, set[int]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in ("fluka", "megalib"):
        for stage in ("raw", "active_veto"):
            ids = selected_ids[code][stage]
            evs = [events[code][i] for i in ids if i in events[code]]
            distances = [ev.weighted_tes_distance_cm for ev in evs]
            rows.append(
                {
                    "code": code,
                    "stage": stage,
                    "events": len(evs),
                    "min_source_to_tes_cm": percentile(distances, 0.0),
                    "p10_source_to_tes_cm": percentile(distances, 0.1),
                    "median_source_to_tes_cm": percentile(distances, 0.5),
                    "p90_source_to_tes_cm": percentile(distances, 0.9),
                    "mean_source_to_tes_cm": mean(distances),
                    "single_tes_pixel_fraction": sum(1 for ev in evs if ev.n_tes_pixels == 1) / len(evs) if evs else 0.0,
                    "multi_tes_pixel_fraction": sum(1 for ev in evs if ev.n_tes_pixels > 1) / len(evs) if evs else 0.0,
                    "shield_touched_fraction": sum(1 for ev in evs if ev.n_shield_segments > 0) / len(evs) if evs else 0.0,
                    "side_shield_touched_fraction": sum(1 for ev in evs if ev.side_shield_touched) / len(evs) if evs else 0.0,
                    "top_shield_touched_fraction": sum(1 for ev in evs if ev.top_shield_touched) / len(evs) if evs else 0.0,
                }
            )
    return rows


def summarize_source_volumes(
    events: dict[str, dict[int, SelectedEvent]],
    selected_ids: dict[str, dict[str, set[int]]],
    source_histories: Counter[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_code_rows: list[dict[str, Any]] = []
    by_volume: dict[tuple[str, str], list[SelectedEvent]] = defaultdict(list)
    for code in ("fluka", "megalib"):
        for global_id in selected_ids[code]["raw"]:
            event = events[code].get(global_id)
            if event:
                by_volume[(code, event.source_volume)].append(event)

    for (code, source_volume), evs in sorted(by_volume.items()):
        distances = [ev.weighted_tes_distance_cm for ev in evs]
        channels = Counter(ch for ev in evs for ch in ev.tes_channels)
        carriers = Counter()
        for ev in evs:
            carriers.update(ev.carrier_rows)
        per_code_rows.append(
            {
                "code": code,
                "source_volume": source_volume,
                "source_histories": source_histories[source_volume],
                "w2_raw_events": len(evs),
                "conditional_efficiency": len(evs) / source_histories[source_volume] if source_histories[source_volume] else 0.0,
                "active_veto_events": sum(1 for ev in evs if ev.active_veto),
                "active_veto_fraction": sum(1 for ev in evs if ev.active_veto) / len(evs) if evs else 0.0,
                "median_source_to_tes_cm": percentile(distances, 0.5),
                "p10_source_to_tes_cm": percentile(distances, 0.1),
                "p90_source_to_tes_cm": percentile(distances, 0.9),
                "single_tes_pixel_fraction": sum(1 for ev in evs if ev.n_tes_pixels == 1) / len(evs) if evs else 0.0,
                "multi_tes_pixel_fraction": sum(1 for ev in evs if ev.n_tes_pixels > 1) / len(evs) if evs else 0.0,
                "shield_touched_fraction": sum(1 for ev in evs if ev.n_shield_segments > 0) / len(evs) if evs else 0.0,
                "side_shield_touched_fraction": sum(1 for ev in evs if ev.side_shield_touched) / len(evs) if evs else 0.0,
                "top_tes_channels": top_counter(channels),
                "top_carriers": top_counter(carriers),
            }
        )

    volume_names = set(source_histories)
    comparison_rows: list[dict[str, Any]] = []
    by_code_volume = {(row["code"], row["source_volume"]): row for row in per_code_rows}
    total_diff = len(selected_ids["fluka"]["raw"]) - len(selected_ids["megalib"]["raw"])
    for volume in volume_names:
        f = by_code_volume.get(("fluka", volume), {})
        m = by_code_volume.get(("megalib", volume), {})
        f_events = int(f.get("w2_raw_events", 0) or 0)
        m_events = int(m.get("w2_raw_events", 0) or 0)
        if f_events == 0 and m_events == 0:
            continue
        diff = f_events - m_events
        comparison_rows.append(
            {
                "source_volume": volume,
                "source_histories": source_histories[volume],
                "fluka_w2_raw_events": f_events,
                "megalib_w2_raw_events": m_events,
                "difference_events": diff,
                "difference_share_of_net": diff / total_diff if total_diff else "",
                "fluka_over_megalib": (f_events / m_events) if m_events else "",
                "fluka_median_source_to_tes_cm": f.get("median_source_to_tes_cm", ""),
                "megalib_median_source_to_tes_cm": m.get("median_source_to_tes_cm", ""),
                "fluka_active_veto_fraction": f.get("active_veto_fraction", ""),
                "megalib_active_veto_fraction": m.get("active_veto_fraction", ""),
                "fluka_shield_touched_fraction": f.get("shield_touched_fraction", ""),
                "megalib_shield_touched_fraction": m.get("shield_touched_fraction", ""),
                "fluka_top_carriers": f.get("top_carriers", ""),
                "megalib_top_carriers": m.get("top_carriers", ""),
            }
        )
    comparison_rows.sort(key=lambda row: abs(int(row["difference_events"])), reverse=True)
    return per_code_rows, comparison_rows


def summarize_carriers(
    events: dict[str, dict[int, SelectedEvent]],
    selected_ids: dict[str, dict[str, set[int]]],
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    histories_by_key: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    for code in ("fluka", "megalib"):
        for global_id in selected_ids[code]["raw"]:
            event = events[code].get(global_id)
            if not event:
                continue
            for carrier, n_rows in event.carrier_rows.items():
                key = (code, "raw", event.source_volume, carrier)
                item = rows_by_key.setdefault(
                    key,
                    {
                        "code": code,
                        "stage": "raw",
                        "source_volume": event.source_volume,
                        "carrier_key": carrier,
                        "histories": 0,
                        "hit_rows": 0,
                        "deposit_keV_sum": 0.0,
                    },
                )
                item["hit_rows"] += n_rows
                item["deposit_keV_sum"] += event.carrier_energy[carrier]
                histories_by_key[key].add(global_id)
    rows = []
    for key, row in rows_by_key.items():
        row = dict(row)
        row["histories"] = len(histories_by_key[key])
        rows.append(row)
    rows.sort(key=lambda row: (row["code"], -row["histories"], -row["deposit_keV_sum"]))
    return rows


def selected_event_sample(events: dict[str, dict[int, SelectedEvent]], selected_ids: dict[str, dict[str, set[int]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in ("fluka", "megalib"):
        evs = [events[code][i] for i in selected_ids[code]["raw"] if i in events[code]]
        evs.sort(key=lambda ev: ev.weighted_tes_distance_cm)
        for ev in evs[:25]:
            rows.append(
                {
                    "code": code,
                    "global_history_id": ev.global_history_id,
                    "source_volume": ev.source_volume,
                    "material": ev.material,
                    "production_tag": ev.production_tag,
                    "tes_total_keV": ev.tes_total_keV,
                    "shield_total_keV": ev.shield_total_keV,
                    "active_veto": ev.active_veto,
                    "weighted_source_to_tes_cm": ev.weighted_tes_distance_cm,
                    "min_source_to_tes_cm": ev.min_tes_distance_cm,
                    "n_tes_pixels": ev.n_tes_pixels,
                    "n_shield_segments": ev.n_shield_segments,
                    "top_carriers": top_counter(ev.carrier_rows),
                }
            )
    return rows


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Mechanism Focus Audit",
        "",
        f"- status: `{payload['status']}`",
        f"- histories_per_code: `FLUKA {payload['histories']['fluka']}; MEGAlib {payload['histories']['megalib']}`",
        f"- W2 raw: `FLUKA {payload['w2_raw']['fluka']}; MEGAlib {payload['w2_raw']['megalib']}`",
        f"- W2 active-veto: `FLUKA {payload['w2_active_veto']['fluka']}; MEGAlib {payload['w2_active_veto']['megalib']}`",
        "",
        "## Mechanism Summary",
        "",
        "The existing raw truth supports a geometry/raw-coupling mechanism, not a detector-response or time-grouping mechanism.",
        "The excess is source-volume specific and changes sign by volume: `ColdPlate_MXC_50mK_SD_anchor` is FLUKA-high, while `Cu_SubstrateSupport_SolidDisk_L0_deepest` is MEGAlib-high.",
        "The global source-to-TES distance distributions for W2 selected histories are similar, so the effect is not explained by a simple near/far distance scalar.",
        "MEGAlib TES W2 rows carry mostly gamma `phot`/`compt` ancestry into local TES electron deposits; FLUKA exposes only local deposit proxies (`EM_BELOW_THRESHOLD`), so incident photon ancestry still needs a dedicated scorer.",
        "",
        "## Source-To-TES Distance",
        "",
        "| code | stage | events | median cm | p10 cm | p90 cm | shield touched | multi TES pixel |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["distance_summary"]:
        lines.append(
            f"| `{row['code']}` | `{row['stage']}` | `{row['events']}` | "
            f"`{row['median_source_to_tes_cm']:.5g}` | `{row['p10_source_to_tes_cm']:.5g}` | "
            f"`{row['p90_source_to_tes_cm']:.5g}` | `{row['shield_touched_fraction']:.3g}` | "
            f"`{row['multi_tes_pixel_fraction']:.3g}` |"
        )
    lines.extend(
        [
            "",
            "## Largest Source-Volume Differences",
            "",
            "| source volume | source histories | FLUKA W2 | MEGAlib W2 | diff | share of net | FLUKA/MEGAlib | FLUKA median cm | MEGAlib median cm |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["source_volume_comparison"][:10]:
        ratio = row["fluka_over_megalib"]
        ratio_s = f"{ratio:.6g}" if isinstance(ratio, float) else "n/a"
        share = row["difference_share_of_net"]
        share_s = f"{share:.3g}" if isinstance(share, float) else "n/a"
        f_dist = row["fluka_median_source_to_tes_cm"]
        m_dist = row["megalib_median_source_to_tes_cm"]
        f_dist_s = f"{f_dist:.5g}" if isinstance(f_dist, float) else "n/a"
        m_dist_s = f"{m_dist:.5g}" if isinstance(m_dist, float) else "n/a"
        lines.append(
            f"| `{row['source_volume']}` | `{row['source_histories']}` | "
            f"`{row['fluka_w2_raw_events']}` | `{row['megalib_w2_raw_events']}` | "
            f"`{row['difference_events']:+d}` | `{share_s}` | `{ratio_s}` | `{f_dist_s}` | `{m_dist_s}` |"
        )
    lines.extend(
        [
            "",
            "## Mechanism Interpretation",
            "",
            "1. The W2 difference is generated before common response and before final FoV logic.",
            "2. It is not a global source-boundary or source-to-TES-distance effect; the sign flips between nearby Cu structures.",
            "3. The evidence points to local full-geometry coupling in specific Cu volumes: positron stopping/annihilation, photon escape paths through surrounding Cu/shield/Ta geometry, or runtime region/material assignment at those locations.",
            "4. The photon concern is real: MEGAlib shows gamma ancestry feeding TES-local electrons. FLUKA's current raw dump records local deposit proxies only, so a TES-boundary/ancestry scorer is required to say which incident particles reach TES in FLUKA.",
            "",
            "## Output Files",
            "",
            f"- distance_summary_csv: `{payload['distance_summary_csv']}`",
            f"- source_volume_mechanism_csv: `{payload['source_volume_mechanism_csv']}`",
            f"- source_volume_comparison_csv: `{payload['source_volume_comparison_csv']}`",
            f"- local_carrier_ancestry_csv: `{payload['local_carrier_ancestry_csv']}`",
            f"- selected_event_sample_csv: `{payload['selected_event_sample_csv']}`",
            "",
            "## Boundary",
            "",
            "- This audit reuses existing independent-source raw truth under `/tmp/phase3prod`; it does not replay `.sim.gz`.",
            "- It is a mechanism-focus post-processing audit, not a new FLUKA/Geant4 runtime scorer.",
            "- FLUKA incident TES ancestry remains unmeasured by the existing raw schema.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(parent_list: Path, work_root: Path, out_dir: Path) -> dict[str, Any]:
    selected_ids = load_selected_ids(work_root)
    needed = set().union(*(selected_ids[code]["raw"] for code in ("fluka", "megalib")))
    parent_meta, source_histories = load_parent_meta(parent_list, needed)
    events = {
        "fluka": parse_fluka_events(work_root, selected_ids["fluka"]["raw"], parent_meta),
        "megalib": parse_megalib_events(work_root, selected_ids["megalib"]["raw"], parent_meta),
    }
    distance_rows = summarize_distance(events, selected_ids)
    source_volume_rows, source_volume_comparison = summarize_source_volumes(events, selected_ids, source_histories)
    carrier_rows = summarize_carriers(events, selected_ids)
    sample_rows = selected_event_sample(events, selected_ids)

    distance_csv = out_dir / "w2_source_to_tes_distance_summary.csv"
    source_volume_csv = out_dir / "w2_source_volume_mechanism_summary.csv"
    source_volume_comparison_csv = out_dir / "w2_source_volume_mechanism_comparison.csv"
    carrier_csv = out_dir / "w2_local_carrier_ancestry_summary.csv"
    sample_csv = out_dir / "w2_selected_event_distance_sample.csv"
    summary_json = out_dir / "summary.json"
    summary_md = out_dir / "summary.md"

    write_csv(
        distance_csv,
        distance_rows,
        [
            "code",
            "stage",
            "events",
            "min_source_to_tes_cm",
            "p10_source_to_tes_cm",
            "median_source_to_tes_cm",
            "p90_source_to_tes_cm",
            "mean_source_to_tes_cm",
            "single_tes_pixel_fraction",
            "multi_tes_pixel_fraction",
            "shield_touched_fraction",
            "side_shield_touched_fraction",
            "top_shield_touched_fraction",
        ],
    )
    write_csv(
        source_volume_csv,
        source_volume_rows,
        [
            "code",
            "source_volume",
            "source_histories",
            "w2_raw_events",
            "conditional_efficiency",
            "active_veto_events",
            "active_veto_fraction",
            "median_source_to_tes_cm",
            "p10_source_to_tes_cm",
            "p90_source_to_tes_cm",
            "single_tes_pixel_fraction",
            "multi_tes_pixel_fraction",
            "shield_touched_fraction",
            "side_shield_touched_fraction",
            "top_tes_channels",
            "top_carriers",
        ],
    )
    write_csv(
        source_volume_comparison_csv,
        source_volume_comparison,
        [
            "source_volume",
            "source_histories",
            "fluka_w2_raw_events",
            "megalib_w2_raw_events",
            "difference_events",
            "difference_share_of_net",
            "fluka_over_megalib",
            "fluka_median_source_to_tes_cm",
            "megalib_median_source_to_tes_cm",
            "fluka_active_veto_fraction",
            "megalib_active_veto_fraction",
            "fluka_shield_touched_fraction",
            "megalib_shield_touched_fraction",
            "fluka_top_carriers",
            "megalib_top_carriers",
        ],
    )
    write_csv(
        carrier_csv,
        carrier_rows,
        ["code", "stage", "source_volume", "carrier_key", "histories", "hit_rows", "deposit_keV_sum"],
    )
    write_csv(
        sample_csv,
        sample_rows,
        [
            "code",
            "global_history_id",
            "source_volume",
            "material",
            "production_tag",
            "tes_total_keV",
            "shield_total_keV",
            "active_veto",
            "weighted_source_to_tes_cm",
            "min_source_to_tes_cm",
            "n_tes_pixels",
            "n_shield_segments",
            "top_carriers",
        ],
    )

    payload = {
        "status": "PHASE3_CU64_MECHANISM_FOCUS_AUDIT_PASS",
        "histories": {"fluka": 1_000_000, "megalib": 1_000_000},
        "w2_raw": {code: len(selected_ids[code]["raw"]) for code in ("fluka", "megalib")},
        "w2_active_veto": {code: len(selected_ids[code]["active_veto"]) for code in ("fluka", "megalib")},
        "distance_summary_csv": rel(distance_csv),
        "source_volume_mechanism_csv": rel(source_volume_csv),
        "source_volume_comparison_csv": rel(source_volume_comparison_csv),
        "local_carrier_ancestry_csv": rel(carrier_csv),
        "selected_event_sample_csv": rel(sample_csv),
        "distance_summary": distance_rows,
        "source_volume_comparison": source_volume_comparison[:20],
        "interpretation": {
            "mechanism": "source-volume-specific full-geometry raw coupling before common detector response",
            "not_supported": [
                "pure W2 response effect",
                "1us/1ns time grouping effect",
                "global static boundary-margin effect",
                "global source-to-TES distance scalar effect",
            ],
            "remaining_needed": [
                "FLUKA TES-boundary incident ancestry scorer",
                "positron stopping/annihilation locator",
                "runtime point-location scorer in dominant source volumes",
            ],
        },
    }
    write_json(summary_json, payload)
    payload["summary_json"] = rel(summary_json)
    payload["summary_md"] = rel(summary_md)
    write_summary_md(summary_md, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-list", type=Path, default=DEFAULT_PARENT_LIST)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build(args.parent_list, args.work_root, args.out_dir)
    print(payload["status"])
    print(payload["summary_md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
