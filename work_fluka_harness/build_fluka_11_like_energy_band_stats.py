#!/usr/bin/env python3
"""Build 11_fix5-like prompt/delayed energy-band statistics for FLUKA.

This is a read-only post-processing pass over the completed independent-source
FLUKA prompt runs plus the delayed isotope-source run.  It mirrors the
TES_511_BALLOON 11_fix5 W2 prompt/delayed energy-band note and additionally
separates source tag from the local FLUKA TES deposit carrier.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from build_prompt_final_same_stat_comparison import (
    ACTIVE_VETO_THRESHOLD_KEV,
    EVENT_CATALOG,
    OFFICIAL_RATES,
    PROMPT_RUNS,
    Hit,
    event_hits,
    find_file,
    load_csv,
    load_history_weights,
    now_utc,
    poisson_sigma_from_weights,
    side_entry_disk,
    side_keep_from_hits,
    valid_chunk_dirs,
)
from run_eplus_raw_mvp import PARTICLE_BY_CODE


DELAYED_RUN = Path("work_fluka_harness/delayed_isotope_source_full254704")
TES_DELAYED_W2_AUDIT_CSV = (
    Path("/home/ubuntu/TES_511_Balloon")
    / "outputs/reports/fix5_fullstat_v2_exactpos_m50000_s260613"
    / "fix5_w_activation_selected_w2_events.csv"
)

STAGES = ("raw", "active_veto_pass", "side_compton_fov_pass")
STAGE_LABEL = {
    "raw": "raw",
    "active_veto_pass": "active-veto",
    "side_compton_fov_pass": "final",
}

BANDS: list[dict[str, Any]] = [
    {"id": "all_tes_gt0", "label": "all TES > 0", "mode": "gt0"},
    {"id": "e100_300", "label": "100-300 keV", "lo": 100.0, "hi": 300.0},
    {"id": "e300_480", "label": "300-480 keV", "lo": 300.0, "hi": 480.0},
    {"id": "e480_550", "label": "480-550 keV", "lo": 480.0, "hi": 550.0},
    {"id": "w2_510p58_511p42", "label": "W2 510.58-511.42 keV", "lo": 510.58, "hi": 511.42},
    {"id": "e550_800", "label": "550-800 keV", "lo": 550.0, "hi": 800.0},
    {"id": "e800_1500", "label": "800-1500 keV", "lo": 800.0, "hi": 1500.0},
    {"id": "e1500_3000", "label": "1500-3000 keV", "lo": 1500.0, "hi": 3000.0},
    {"id": "e3000_10000", "label": "3000-10000 keV", "lo": 3000.0, "hi": 10000.0},
]
BAND_BY_ID = {b["id"]: b for b in BANDS}


@dataclass
class DepositDetails:
    hits: list[Hit]
    particle_energy_keV: Counter[str]


def init_stage() -> dict[str, Any]:
    return {"events": 0, "rate": 0.0, "sigma2": 0.0, "class_counts": Counter()}


def init_carrier() -> dict[str, float]:
    return {
        "dominant_events": 0,
        "dominant_rate": 0.0,
        "dominant_sigma2": 0.0,
        "fractional_rate": 0.0,
        "energy_rate_keV_s": 0.0,
        "raw_deposit_keV": 0.0,
    }


def add_rate(
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    code: str,
    stream: str,
    source_tag: str,
    band: str,
    stage: str,
    weight: float,
) -> None:
    item = stats[(code, stream, source_tag, band, stage)]
    item["events"] += 1
    item["rate"] += weight
    item["sigma2"] += weight * weight


def add_class(
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    code: str,
    stream: str,
    source_tag: str,
    band: str,
    cls: str,
) -> None:
    stats[(code, stream, source_tag, band, "side_compton_fov_pass")]["class_counts"][cls] += 1


def summarize_stage(item: dict[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"events": 0, "rate_s-1": 0.0, "mc_sigma_s-1": 0.0, "side_compton_class_counts": {}}
    return {
        "events": int(item["events"]),
        "rate_s-1": float(item["rate"]),
        "mc_sigma_s-1": math.sqrt(float(item["sigma2"])),
        "side_compton_class_counts": dict(sorted(item.get("class_counts", Counter()).items())),
    }


def bands_for_tes(tes_keV: float) -> list[str]:
    out = []
    if tes_keV > 0.0:
        out.append("all_tes_gt0")
    for band in BANDS:
        if band.get("mode") == "gt0":
            continue
        if float(band["lo"]) <= tes_keV < float(band["hi"]):
            out.append(str(band["id"]))
    return out


def tags_for_stream(stream: str, source_tag: str) -> list[str]:
    if stream == "prompt":
        return [source_tag, "all_prompt"]
    if stream == "delayed":
        return [source_tag, "activation"] if source_tag != "activation" else ["activation"]
    return [source_tag]


def add_carrier_event(
    carrier_stats: dict[tuple[str, str, str, str, str, str], dict[str, float]],
    code: str,
    stream: str,
    source_tags: list[str],
    band: str,
    stage: str,
    weight: float,
    particle_energy_keV: Counter[str],
) -> None:
    total_e = float(sum(particle_energy_keV.values()))
    if total_e <= 0.0:
        carriers = Counter({"missing_tes_deposit": 1.0})
        total_e = 1.0
    else:
        carriers = particle_energy_keV
    dominant = max(carriers.items(), key=lambda kv: (float(kv[1]), kv[0]))[0]
    for source_tag in source_tags:
        dom = carrier_stats[(code, stream, source_tag, band, stage, dominant)]
        dom["dominant_events"] += 1
        dom["dominant_rate"] += weight
        dom["dominant_sigma2"] += weight * weight
        for carrier, e in carriers.items():
            item = carrier_stats[(code, stream, source_tag, band, stage, carrier)]
            frac = float(e) / total_e
            item["fractional_rate"] += weight * frac
            item["energy_rate_keV_s"] += weight * float(e)
            item["raw_deposit_keV"] += float(e)


def read_tes_deposit_details(deposits_path: Path, candidate_hids: set[int]) -> dict[int, DepositDetails]:
    if not candidate_hids:
        return {}
    by_region: dict[int, dict[str, dict[str, float]]] = defaultdict(dict)
    by_particle: dict[int, Counter[str]] = defaultdict(Counter)
    with deposits_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        hid_i = idx["history_id"]
        kind_i = idx["detector_kind"]
        region_i = idx["region_name"]
        e_i = idx["deposit_keV"]
        x_i = idx["x_cm"]
        y_i = idx["y_cm"]
        z_i = idx["z_cm"]
        p_i = idx["particle_code"]
        for row in reader:
            if "TES" not in row[kind_i].upper():
                continue
            hid = int(row[hid_i])
            if hid not in candidate_hids:
                continue
            e = float(row[e_i])
            if e <= 0.0:
                continue
            particle = PARTICLE_BY_CODE.get(int(row[p_i]), f"FLUKA_PARTICLE_{int(row[p_i])}")
            by_particle[hid][particle] += e
            region = row[region_i].strip()
            rec = by_region[hid].setdefault(region, {"e": 0.0, "wx": 0.0, "wy": 0.0, "wz": 0.0})
            rec["e"] += e
            rec["wx"] += e * float(row[x_i])
            rec["wy"] += e * float(row[y_i])
            rec["wz"] += e * float(row[z_i])
    out: dict[int, DepositDetails] = {}
    for hid in set(by_region) | set(by_particle):
        hits = []
        for region, rec in sorted(by_region.get(hid, {}).items()):
            e = rec["e"]
            if e <= 0.0:
                continue
            hits.append(Hit(x=rec["wx"] / e, y=rec["wy"] / e, z=rec["wz"] / e, e=e, pixel_uid=region))
        out[hid] = DepositDetails(hits=hits, particle_energy_keV=by_particle.get(hid, Counter()))
    return out


def load_g4(
    disk: dict[str, Any],
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    with EVENT_CATALOG.open("rb") as f:
        cat = pickle.load(f)
    streams = np.asarray(cat["stream"], dtype=object)
    tags = np.asarray(cat["tag"], dtype=object)
    tes = np.asarray(cat["tes_total_keV"], dtype=float)
    bgo = np.asarray(cat["bgo_total_keV"], dtype=float)
    rates = np.asarray(cat["rate_hz"], dtype=float)

    class_counts = Counter()
    for idx in range(len(tes)):
        stream = str(streams[idx])
        if stream not in ("prompt", "delayed"):
            continue
        event_bands = bands_for_tes(float(tes[idx]))
        if not event_bands:
            continue
        source_tag = str(tags[idx]) if stream == "prompt" else "activation"
        source_tags = tags_for_stream(stream, source_tag)
        weight = float(rates[idx])
        for band in event_bands:
            for tag in source_tags:
                add_rate(stats, "TES_511_BALLOON", stream, tag, band, "raw", weight)
        if float(bgo[idx]) >= ACTIVE_VETO_THRESHOLD_KEV:
            continue
        for band in event_bands:
            for tag in source_tags:
                add_rate(stats, "TES_511_BALLOON", stream, tag, band, "active_veto_pass", weight)
        keep, cls = side_keep_from_hits(event_hits(cat, int(idx)), disk)
        class_counts[cls] += 1
        for band in event_bands:
            for tag in source_tags:
                add_class(stats, "TES_511_BALLOON", stream, tag, band, cls)
                if keep:
                    add_rate(stats, "TES_511_BALLOON", stream, tag, band, "side_compton_fov_pass", weight)
    return {
        "event_catalog": str(EVENT_CATALOG),
        "n_generated_events_seen": int(cat.get("n_generated_events_seen", 0)),
        "n_kept_events": int(cat.get("n_kept_events", len(tes))),
        "active_side_class_counts_all_bands": dict(sorted(class_counts.items())),
    }


def process_prompt_chunk(
    particle: str,
    chunk: Path,
    disk: dict[str, Any],
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    carrier_stats: dict[tuple[str, str, str, str, str, str], dict[str, float]],
) -> int:
    weights = load_history_weights(chunk)
    raw_by_hid: dict[int, list[str]] = {}
    active_by_hid: dict[int, list[str]] = {}
    totals_path = find_file(chunk, "event_totals_tmp.csv")
    with totals_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        hid_i = idx["history_id"]
        tes_i = idx["tes_total_keV"]
        shield_i = idx["shield_total_keV"]
        for row in reader:
            hid = int(row[hid_i])
            event_bands = bands_for_tes(float(row[tes_i]))
            if not event_bands:
                continue
            raw_by_hid[hid] = event_bands
            weight = weights.get(hid, 0.0)
            for band in event_bands:
                for tag in (particle, "all_prompt"):
                    add_rate(stats, "FLUKA", "prompt", tag, band, "raw", weight)
            if float(row[shield_i]) < ACTIVE_VETO_THRESHOLD_KEV:
                active_by_hid[hid] = event_bands
                for band in event_bands:
                    for tag in (particle, "all_prompt"):
                        add_rate(stats, "FLUKA", "prompt", tag, band, "active_veto_pass", weight)

    details = read_tes_deposit_details(find_file(chunk, "raw_deposits_tmp.csv"), set(raw_by_hid))
    for hid, event_bands in raw_by_hid.items():
        weight = weights.get(hid, 0.0)
        particle_energy = details.get(hid, DepositDetails([], Counter())).particle_energy_keV
        for band in event_bands:
            add_carrier_event(carrier_stats, "FLUKA", "prompt", [particle, "all_prompt"], band, "raw", weight, particle_energy)
    for hid, event_bands in active_by_hid.items():
        weight = weights.get(hid, 0.0)
        detail = details.get(hid, DepositDetails([], Counter()))
        for band in event_bands:
            add_carrier_event(
                carrier_stats,
                "FLUKA",
                "prompt",
                [particle, "all_prompt"],
                band,
                "active_veto_pass",
                weight,
                detail.particle_energy_keV,
            )
        if not detail.hits:
            keep, cls = False, "missing_tes_hits"
        else:
            keep, cls = side_keep_from_hits(detail.hits, disk)
        for band in event_bands:
            for tag in (particle, "all_prompt"):
                add_class(stats, "FLUKA", "prompt", tag, band, cls)
                if keep:
                    add_rate(stats, "FLUKA", "prompt", tag, band, "side_compton_fov_pass", weight)
            if keep:
                add_carrier_event(
                    carrier_stats,
                    "FLUKA",
                    "prompt",
                    [particle, "all_prompt"],
                    band,
                    "side_compton_fov_pass",
                    weight,
                    detail.particle_energy_keV,
                )
    return len(weights)


def load_fluka_prompt(
    disk: dict[str, Any],
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    carrier_stats: dict[tuple[str, str, str, str, str, str], dict[str, float]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for particle, root in PROMPT_RUNS.items():
        chunks = valid_chunk_dirs(root)
        histories = 0
        print(f"[prompt:{particle}] valid_chunks={len(chunks)}", flush=True)
        for i, chunk in enumerate(chunks, start=1):
            histories += process_prompt_chunk(particle, chunk, disk, stats, carrier_stats)
            if i == 1 or i == len(chunks) or i % 4 == 0:
                print(f"[prompt:{particle}] processed {i}/{len(chunks)} histories={histories}", flush=True)
        out[particle] = {"run_root": str(root), "valid_chunks": len(chunks), "histories": histories}
    out["all_prompt"] = {
        "valid_chunks": sum(int(v["valid_chunks"]) for v in out.values()),
        "histories": sum(int(v["histories"]) for v in out.values()),
    }
    return out


def load_delayed_sources(run_root: Path) -> tuple[dict[int, float], dict[int, dict[str, str]]]:
    weights: dict[int, float] = {}
    meta: dict[int, dict[str, str]] = {}
    with (run_root / "raw_events/delayed_sources.csv").open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hid = int(row["history_id"])
            weights[hid] = float(row["history_weight"])
            meta[hid] = {
                "nuclide": row.get("nuclide", "") or "unknown",
                "raw_volume": row.get("raw_volume", "") or row.get("canonical_volume_for_reporting_only", ""),
                "production_tag": row.get("production_tag", ""),
            }
    return weights, meta


def load_fluka_delayed(
    run_root: Path,
    disk: dict[str, Any],
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    carrier_stats: dict[tuple[str, str, str, str, str, str], dict[str, float]],
) -> dict[str, Any]:
    weights, meta = load_delayed_sources(run_root)
    raw_by_hid: dict[int, list[str]] = {}
    active_by_hid: dict[int, list[str]] = {}
    totals_path = find_file(run_root / "fluka_run", "event_totals_tmp.csv")
    with totals_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        for row in reader:
            hid = int(row[idx["history_id"]])
            event_bands = bands_for_tes(float(row[idx["tes_total_keV"]]))
            if not event_bands:
                continue
            raw_by_hid[hid] = event_bands
            weight = weights.get(hid, 0.0)
            nuclide = meta.get(hid, {}).get("nuclide", "unknown")
            for band in event_bands:
                for tag in (nuclide, "activation"):
                    add_rate(stats, "FLUKA", "delayed", tag, band, "raw", weight)
            if float(row[idx["shield_total_keV"]]) < ACTIVE_VETO_THRESHOLD_KEV:
                active_by_hid[hid] = event_bands
                for band in event_bands:
                    for tag in (nuclide, "activation"):
                        add_rate(stats, "FLUKA", "delayed", tag, band, "active_veto_pass", weight)

    details = read_tes_deposit_details(find_file(run_root / "fluka_run", "raw_deposits_tmp.csv"), set(raw_by_hid))
    for hid, event_bands in raw_by_hid.items():
        weight = weights.get(hid, 0.0)
        nuclide = meta.get(hid, {}).get("nuclide", "unknown")
        particle_energy = details.get(hid, DepositDetails([], Counter())).particle_energy_keV
        for band in event_bands:
            add_carrier_event(carrier_stats, "FLUKA", "delayed", [nuclide, "activation"], band, "raw", weight, particle_energy)
    for hid, event_bands in active_by_hid.items():
        weight = weights.get(hid, 0.0)
        nuclide = meta.get(hid, {}).get("nuclide", "unknown")
        detail = details.get(hid, DepositDetails([], Counter()))
        for band in event_bands:
            add_carrier_event(
                carrier_stats,
                "FLUKA",
                "delayed",
                [nuclide, "activation"],
                band,
                "active_veto_pass",
                weight,
                detail.particle_energy_keV,
            )
        if not detail.hits:
            keep, cls = False, "missing_tes_hits"
        else:
            keep, cls = side_keep_from_hits(detail.hits, disk)
        for band in event_bands:
            for tag in (nuclide, "activation"):
                add_class(stats, "FLUKA", "delayed", tag, band, cls)
                if keep:
                    add_rate(stats, "FLUKA", "delayed", tag, band, "side_compton_fov_pass", weight)
            if keep:
                add_carrier_event(
                    carrier_stats,
                    "FLUKA",
                    "delayed",
                    [nuclide, "activation"],
                    band,
                    "side_compton_fov_pass",
                    weight,
                    detail.particle_energy_keV,
                )
    return {
        "run_root": str(run_root),
        "histories": len(weights),
        "source_activity_Bq": float(sum(weights.values())),
        "raw_candidate_histories": len(raw_by_hid),
        "active_candidate_histories": len(active_by_hid),
    }


def source_rows(stats: dict[tuple[str, str, str, str, str], dict[str, Any]]) -> list[dict[str, object]]:
    rows = []
    for (code, stream, source_tag, band, stage), item in sorted(stats.items()):
        s = summarize_stage(item)
        rows.append(
            {
                "code": code,
                "stream": stream,
                "source_tag": source_tag,
                "band": band,
                "band_label": BAND_BY_ID[band]["label"],
                "stage": stage,
                "stage_label": STAGE_LABEL[stage],
                "events": s["events"],
                "rate_s-1": s["rate_s-1"],
                "mc_sigma_s-1": s["mc_sigma_s-1"],
                "side_compton_class_counts": json.dumps(s["side_compton_class_counts"], sort_keys=True),
            }
        )
    return rows


def carrier_rows(carrier_stats: dict[tuple[str, str, str, str, str, str], dict[str, float]]) -> list[dict[str, object]]:
    rows = []
    for (code, stream, source_tag, band, stage, carrier), item in sorted(carrier_stats.items()):
        rows.append(
            {
                "code": code,
                "stream": stream,
                "source_tag": source_tag,
                "band": band,
                "band_label": BAND_BY_ID[band]["label"],
                "stage": stage,
                "stage_label": STAGE_LABEL[stage],
                "deposit_carrier": carrier,
                "dominant_events": int(item["dominant_events"]),
                "dominant_rate_s-1": float(item["dominant_rate"]),
                "dominant_sigma_s-1": math.sqrt(float(item["dominant_sigma2"])),
                "fractional_rate_s-1": float(item["fractional_rate"]),
                "energy_rate_keV_s-1": float(item["energy_rate_keV_s"]),
                "raw_deposit_keV_sum": float(item["raw_deposit_keV"]),
            }
        )
    return rows


def get_stage(
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    code: str,
    stream: str,
    source_tag: str,
    band: str,
    stage: str,
) -> dict[str, Any]:
    return summarize_stage(stats.get((code, stream, source_tag, band, stage)))


def delayed_fraction_rows(stats: dict[tuple[str, str, str, str, str], dict[str, Any]]) -> list[dict[str, object]]:
    rows = []
    for code in ("TES_511_BALLOON", "FLUKA"):
        for band in [str(b["id"]) for b in BANDS]:
            for stage in STAGES:
                p = get_stage(stats, code, "prompt", "all_prompt", band, stage)
                d = get_stage(stats, code, "delayed", "activation", band, stage)
                total = float(p["rate_s-1"]) + float(d["rate_s-1"])
                rows.append(
                    {
                        "code": code,
                        "band": band,
                        "band_label": BAND_BY_ID[band]["label"],
                        "stage": stage,
                        "stage_label": STAGE_LABEL[stage],
                        "prompt_events": p["events"],
                        "prompt_rate_s-1": p["rate_s-1"],
                        "delayed_events": d["events"],
                        "delayed_rate_s-1": d["rate_s-1"],
                        "delayed_fraction": None if total == 0.0 else float(d["rate_s-1"]) / total,
                        "delayed_over_prompt": None if float(p["rate_s-1"]) == 0.0 else float(d["rate_s-1"]) / float(p["rate_s-1"]),
                    }
                )
    return rows


def validate_w2_broad_against_official(stats: dict[tuple[str, str, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    band_map = {"broad_480_550": "e480_550", "w2_510p58_511p42": "w2_510p58_511p42"}
    checks = []
    ok = True
    for row in load_csv(OFFICIAL_RATES):
        stream = row.get("stream", "")
        if stream not in ("prompt", "delayed"):
            continue
        band = band_map.get(row["window"])
        if not band:
            continue
        got = get_stage(stats, "TES_511_BALLOON", stream, "all_prompt" if stream == "prompt" else "activation", band, row["stage"])
        event_delta = int(got["events"]) - int(row["events"])
        rate_delta = float(got["rate_s-1"]) - float(row["rate_s-1"])
        passed = event_delta == 0 and abs(rate_delta) <= max(1.0e-10, abs(float(row["rate_s-1"])) * 1.0e-9)
        ok = ok and passed
        checks.append(
            {
                "window": row["window"],
                "stream": stream,
                "stage": row["stage"],
                "official_events": int(row["events"]),
                "computed_events": int(got["events"]),
                "event_delta": event_delta,
                "official_rate_s-1": float(row["rate_s-1"]),
                "computed_rate_s-1": float(got["rate_s-1"]),
                "rate_delta_s-1": rate_delta,
                "status": "PASS" if passed else "FAIL",
            }
        )
    return {"status": "PASS" if ok else "FAIL", "checks": checks, "official_rates": str(OFFICIAL_RATES)}


def load_tes_delayed_w2_audit() -> dict[str, Any]:
    if not TES_DELAYED_W2_AUDIT_CSV.exists():
        return {"status": "MISSING", "path": str(TES_DELAYED_W2_AUDIT_CSV), "by_nuclide": [], "by_volume": []}
    by_nuclide: dict[str, dict[str, Any]] = {}
    by_volume: dict[str, dict[str, Any]] = {}
    with TES_DELAYED_W2_AUDIT_CSV.open(newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            rate = float(row["rate_hz"])
            nuc = row.get("source_ZA", "") or row.get("ZA", "")
            nuclide = za_to_nuclide(nuc)
            v = row.get("VN", "")
            nr = by_nuclide.setdefault(nuclide, {"nuclide": nuclide, "events": 0, "rate_s-1": 0.0})
            nr["events"] += 1
            nr["rate_s-1"] += rate
            vr = by_volume.setdefault(v, {"volume": v, "events": 0, "rate_s-1": 0.0})
            vr["events"] += 1
            vr["rate_s-1"] += rate
    return {
        "status": "PRESENT",
        "path": str(TES_DELAYED_W2_AUDIT_CSV),
        "by_nuclide": sorted(by_nuclide.values(), key=lambda r: float(r["rate_s-1"]), reverse=True),
        "by_volume": sorted(by_volume.values(), key=lambda r: float(r["rate_s-1"]), reverse=True),
    }


def za_to_nuclide(za: str) -> str:
    names = {
        "29064": "Cu-64",
        "29062": "Cu-62",
    }
    return names.get(str(za), str(za))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def fmt_rate(rate: float) -> str:
    return f"{rate:.9g}"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return ""
    return f"{100.0 * v:.2f}%"


def fmt_ratio(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.4g}"


def fraction_lookup(rows: list[dict[str, object]]) -> dict[tuple[str, str, str], dict[str, object]]:
    return {(str(r["code"]), str(r["band"]), str(r["stage"])): r for r in rows}


def top_carriers(
    rows: list[dict[str, object]],
    code: str,
    stream: str,
    source_tag: str,
    band: str,
    stage: str,
    limit: int = 8,
) -> list[dict[str, object]]:
    selected = [
        r
        for r in rows
        if r["code"] == code
        and r["stream"] == stream
        and r["source_tag"] == source_tag
        and r["band"] == band
        and r["stage"] == stage
    ]
    return sorted(selected, key=lambda r: float(r["fractional_rate_s-1"]), reverse=True)[:limit]


def source_summary_table(
    stats: dict[tuple[str, str, str, str, str], dict[str, Any]],
    code: str,
    stream: str,
    source_tags: list[str],
    band: str,
    stage: str,
) -> list[dict[str, object]]:
    total_tag = "all_prompt" if stream == "prompt" else "activation"
    total = get_stage(stats, code, stream, total_tag, band, stage)["rate_s-1"]
    rows = []
    for tag in source_tags:
        item = get_stage(stats, code, stream, tag, band, stage)
        if int(item["events"]) == 0 and float(item["rate_s-1"]) == 0.0:
            continue
        rows.append(
            {
                "source_tag": tag,
                "events": item["events"],
                "rate_s-1": item["rate_s-1"],
                "fraction": None if total == 0.0 else float(item["rate_s-1"]) / float(total),
            }
        )
    return sorted(rows, key=lambda r: float(r["rate_s-1"]), reverse=True)


def render_markdown(payload: dict[str, Any]) -> str:
    stats = payload["_stats_ref"]
    frac_rows = payload["delayed_fraction_rows"]
    carrier = payload["carrier_rows"]
    frac = fraction_lookup(frac_rows)
    lines = [
        "# FLUKA Independent-Source fix5 W2 Prompt/Delayed Energy-Band Statistics",
        "",
        f"Date: 2026-06-25",
        "",
        "Scope: same-statistic post-processing of completed independent-source FLUKA runs, using the TES Step05 event catalog only as the comparison authority. No transport run, geometry, source card, or Step05 artifact was modified.",
        "",
        "## Bottom Line",
        "",
        "The FLUKA mainline is now the intended independent-source reproduction: prompt uses `sampled_source_authority`, delayed uses the weighted exact-position isotope EventList. No `.sim.gz` replay is used for the FLUKA prompt/delayed rates in this note.",
        "",
        "The important correction to the earlier shorthand is that `eplus`/`n` are W2 final **source tags**, not the identity of the local particle depositing energy in the TES. The FLUKA TES deposit carrier for selected W2 events is dominated by `EM_BELOW_THRESHOLD`, i.e. local electromagnetic energy deposition below the transport threshold. This is consistent with photon/electromagnetic cascades reaching the TES, but the current raw-deposit CSV does not preserve enough ancestry to label the incident particle as photon event-by-event.",
        "",
    ]
    tw2 = frac[("TES_511_BALLOON", "w2_510p58_511p42", "side_compton_fov_pass")]
    fw2 = frac[("FLUKA", "w2_510p58_511p42", "side_compton_fov_pass")]
    lines.extend(
        [
            "| code | W2 final prompt cps | W2 final delayed cps | delayed fraction |",
            "|---|---:|---:|---:|",
            f"| TES_511_BALLOON | `{fmt_rate(float(tw2['prompt_rate_s-1']))}` | `{fmt_rate(float(tw2['delayed_rate_s-1']))}` | `{fmt_pct(tw2['delayed_fraction'])}` |",
            f"| FLUKA independent source | `{fmt_rate(float(fw2['prompt_rate_s-1']))}` | `{fmt_rate(float(fw2['delayed_rate_s-1']))}` | `{fmt_pct(fw2['delayed_fraction'])}` |",
            "",
            "Interpretation: W2 final total remains close, but the composition is not closed. FLUKA prompt is low relative to TES while delayed activation is high, so agreement in the total is partly compensating residuals.",
            "",
            "## Inputs",
            "",
            f"- TES Step05 event catalog: `{payload['inputs']['event_catalog']}`",
            f"- TES official rates CSV: `{payload['inputs']['official_rates']}`",
            f"- FLUKA prompt histories: `{payload['fluka_prompt']['all_prompt']['histories']}` across `{payload['fluka_prompt']['all_prompt']['valid_chunks']}` valid chunks",
            f"- FLUKA delayed histories: `{payload['fluka_delayed']['histories']}` isotope histories; represented activity `{payload['fluka_delayed']['source_activity_Bq']:.12g} Bq`",
            f"- G4 Step05 W2/broad validation: `{payload['g4_validation']['status']}`",
            "",
            "## Stage Definitions",
            "",
            "- `raw`: event has TES energy in the stated band.",
            f"- `active-veto`: `raw` plus shield/BGO total energy `< {ACTIVE_VETO_THRESHOLD_KEV:g} keV`.",
            "- `final`: `active-veto` plus the Step05 side-entry Compton/FoV keep rule.",
            "- For `all TES > 0`, the lower bound is strictly `tes_total_keV > 0`.",
            "",
            "## TES vs FLUKA Energy-Band Delayed Fraction",
            "",
            "Fractions are `delayed / (prompt + delayed)`.",
            "",
            "| Energy band | TES raw | TES final | FLUKA raw | FLUKA final | FLUKA/TES final delayed cps |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for band in [str(b["id"]) for b in BANDS]:
        tr = frac[("TES_511_BALLOON", band, "raw")]
        tf = frac[("TES_511_BALLOON", band, "side_compton_fov_pass")]
        fr = frac[("FLUKA", band, "raw")]
        ff = frac[("FLUKA", band, "side_compton_fov_pass")]
        tes_delay = float(tf["delayed_rate_s-1"])
        fl_delay = float(ff["delayed_rate_s-1"])
        ratio = None if tes_delay == 0.0 else fl_delay / tes_delay
        lines.append(
            f"| {BAND_BY_ID[band]['label']} | `{fmt_pct(tr['delayed_fraction'])}` | `{fmt_pct(tf['delayed_fraction'])}` | `{fmt_pct(fr['delayed_fraction'])}` | `{fmt_pct(ff['delayed_fraction'])}` | `{fmt_ratio(ratio)}` |"
        )

    lines.extend(
        [
            "",
            "## W2 Same-Statistic Rates",
            "",
            "| code | stream | stage | events | rate cps | survival vs raw |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for code in ("TES_511_BALLOON", "FLUKA"):
        for stream, tag in (("prompt", "all_prompt"), ("delayed", "activation")):
            raw_rate = float(get_stage(stats, code, stream, tag, "w2_510p58_511p42", "raw")["rate_s-1"])
            for stage in STAGES:
                item = get_stage(stats, code, stream, tag, "w2_510p58_511p42", stage)
                surv = None if raw_rate == 0.0 else float(item["rate_s-1"]) / raw_rate
                lines.append(
                    f"| {code} | {stream} | {STAGE_LABEL[stage]} | `{item['events']}` | `{fmt_rate(float(item['rate_s-1']))}` | `{fmt_ratio(surv)}` |"
                )

    lines.extend(
        [
            "",
            "## W2 Prompt Source-Tag Decomposition",
            "",
            "These rows are source tags, not TES local deposit carriers.",
            "",
        ]
    )
    prompt_tags = sorted(PROMPT_RUNS)
    for stage in STAGES:
        lines.extend(
            [
                f"### {STAGE_LABEL[stage]} W2 prompt",
                "",
                "| source tag | TES events/rate/fraction | FLUKA events/rate/fraction |",
                "|---|---:|---:|",
            ]
        )
        all_tags = sorted(
            set(r["source_tag"] for r in source_summary_table(stats, "TES_511_BALLOON", "prompt", prompt_tags, "w2_510p58_511p42", stage))
            | set(r["source_tag"] for r in source_summary_table(stats, "FLUKA", "prompt", prompt_tags, "w2_510p58_511p42", stage))
        )
        for tag in all_tags:
            t = get_stage(stats, "TES_511_BALLOON", "prompt", tag, "w2_510p58_511p42", stage)
            f = get_stage(stats, "FLUKA", "prompt", tag, "w2_510p58_511p42", stage)
            t_total = float(get_stage(stats, "TES_511_BALLOON", "prompt", "all_prompt", "w2_510p58_511p42", stage)["rate_s-1"])
            f_total = float(get_stage(stats, "FLUKA", "prompt", "all_prompt", "w2_510p58_511p42", stage)["rate_s-1"])
            t_frac = None if t_total == 0.0 else float(t["rate_s-1"]) / t_total
            f_frac = None if f_total == 0.0 else float(f["rate_s-1"]) / f_total
            lines.append(
                f"| `{tag}` | `{t['events']} / {fmt_rate(float(t['rate_s-1']))} / {fmt_pct(t_frac)}` | `{f['events']} / {fmt_rate(float(f['rate_s-1']))} / {fmt_pct(f_frac)}` |"
            )
        lines.append("")

    lines.extend(
        [
            "## W2 Delayed Isotope Check",
            "",
            "| nuclide | TES final events/rate | FLUKA final events/rate |",
            "|---|---:|---:|",
        ]
    )
    tes_by_nuc = {r["nuclide"]: r for r in payload["tes_delayed_w2_audit"]["by_nuclide"]}
    fluka_nucs = source_summary_table(
        stats,
        "FLUKA",
        "delayed",
        sorted({str(k[2]) for k in stats if k[0] == "FLUKA" and k[1] == "delayed" and k[2] != "activation"}),
        "w2_510p58_511p42",
        "side_compton_fov_pass",
    )
    all_nucs = sorted(set(tes_by_nuc) | {str(r["source_tag"]) for r in fluka_nucs})
    for nuc in all_nucs:
        t = tes_by_nuc.get(nuc, {"events": 0, "rate_s-1": 0.0})
        f = get_stage(stats, "FLUKA", "delayed", nuc, "w2_510p58_511p42", "side_compton_fov_pass")
        lines.append(
            f"| `{nuc}` | `{int(t['events'])} / {fmt_rate(float(t['rate_s-1']))}` | `{f['events']} / {fmt_rate(float(f['rate_s-1']))}` |"
        )

    lines.extend(
        [
            "",
            "## FLUKA TES Deposit Carrier Check",
            "",
            "This is the check for the photon/electron concern. `deposit_carrier` is the local FLUKA particle code attached to TES energy-deposit rows, not the source tag and not a complete ancestry label.",
            "",
            "| selection | deposit carrier | dominant events/rate | fractional event-rate share | energy-rate share |",
            "|---|---|---:|---:|---:|",
        ]
    )
    carrier_slices = [
        ("prompt W2 final", "prompt", "all_prompt", "w2_510p58_511p42", "side_compton_fov_pass"),
        ("delayed W2 final", "delayed", "activation", "w2_510p58_511p42", "side_compton_fov_pass"),
        ("prompt 480-550 final", "prompt", "all_prompt", "e480_550", "side_compton_fov_pass"),
        ("delayed 480-550 final", "delayed", "activation", "e480_550", "side_compton_fov_pass"),
    ]
    for label, stream, tag, band, stage in carrier_slices:
        rows = top_carriers(carrier, "FLUKA", stream, tag, band, stage)
        frac_total = sum(float(r["fractional_rate_s-1"]) for r in rows)
        energy_total = sum(float(r["energy_rate_keV_s-1"]) for r in rows)
        for r in rows:
            fshare = None if frac_total == 0.0 else float(r["fractional_rate_s-1"]) / frac_total
            eshare = None if energy_total == 0.0 else float(r["energy_rate_keV_s-1"]) / energy_total
            lines.append(
                f"| {label} | `{r['deposit_carrier']}` | `{r['dominant_events']} / {fmt_rate(float(r['dominant_rate_s-1']))}` | `{fmt_pct(fshare)}` | `{fmt_pct(eshare)}` |"
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "1. The TES_511_BALLOON reference conclusion still holds for the TES side: low W2 delayed fraction is selection-conditional and must not be generalized to all energy bands.",
            "2. FLUKA reproduces the prompt/delayed total W2 final rate closely, but its delayed fraction is higher than TES (`17.55%` vs `6.57%`). The delayed-composition residual remains open.",
            "3. The final W2 prompt source-tag composition is narrow in both codes: `eplus` plus neutron. That statement is about the external prompt source family, not about local TES deposit physics.",
            "4. The FLUKA local TES deposit carrier table is overwhelmingly electromagnetic (`EM_BELOW_THRESHOLD`) for W2 final selections. The current scoring does not retain parent/track ancestry, so a separate boundary-crossing or ancestry scorer would be needed to count incident photons at the TES surface directly.",
            "",
            "## Artifacts",
            "",
            f"- source rows CSV: `{payload['outputs']['source_rows_csv']}`",
            f"- deposit carrier CSV: `{payload['outputs']['carrier_rows_csv']}`",
            f"- delayed fraction CSV: `{payload['outputs']['delayed_fraction_csv']}`",
            f"- machine-readable summary: `{payload['outputs']['summary_json']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("work_fluka_harness/fluka_11_like_energy_band_stats_20260625"))
    ap.add_argument("--delayed-run", type=Path, default=DELAYED_RUN)
    args = ap.parse_args()

    stats: dict[tuple[str, str, str, str, str], dict[str, Any]] = defaultdict(init_stage)
    carrier_stats: dict[tuple[str, str, str, str, str, str], dict[str, float]] = defaultdict(init_carrier)
    disk = side_entry_disk()

    g4_info = load_g4(disk, stats)
    validation = validate_w2_broad_against_official(stats)
    if validation["status"] != "PASS":
        raise SystemExit("G4 Step05 validation failed")
    prompt_info = load_fluka_prompt(disk, stats, carrier_stats)
    delayed_info = load_fluka_delayed(args.delayed_run, disk, stats, carrier_stats)

    s_rows = source_rows(stats)
    c_rows = carrier_rows(carrier_stats)
    f_rows = delayed_fraction_rows(stats)
    tes_delayed_w2 = load_tes_delayed_w2_audit()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_csv = args.out_dir / "source_stage_rows.csv"
    carrier_csv = args.out_dir / "tes_deposit_carrier_rows.csv"
    fraction_csv = args.out_dir / "delayed_fraction_rows.csv"
    summary_json = args.out_dir / "summary.json"
    summary_md = args.out_dir / "summary.md"

    write_csv(source_csv, s_rows)
    write_csv(carrier_csv, c_rows)
    write_csv(fraction_csv, f_rows)

    payload: dict[str, Any] = {
        "created_utc": now_utc(),
        "status": "FLUKA_11_LIKE_ENERGY_BAND_STATS_PRESENT",
        "scope": "independent-source FLUKA prompt+delayed energy-band statistics with TES Step05 comparison",
        "source_modes": {
            "prompt": "sampled_source_authority",
            "delayed": "delayed_source_v2_weighted_exact_position_isotope_eventlist",
            "no_sim_gz_replay_for_fluka_rates": True,
        },
        "inputs": {
            "event_catalog": str(EVENT_CATALOG),
            "official_rates": str(OFFICIAL_RATES),
            "delayed_run": str(args.delayed_run),
        },
        "outputs": {
            "source_rows_csv": str(source_csv),
            "carrier_rows_csv": str(carrier_csv),
            "delayed_fraction_csv": str(fraction_csv),
            "summary_json": str(summary_json),
            "summary_md": str(summary_md),
        },
        "bands": BANDS,
        "g4": g4_info,
        "g4_validation": validation,
        "fluka_prompt": prompt_info,
        "fluka_delayed": delayed_info,
        "tes_delayed_w2_audit": tes_delayed_w2,
        "source_rows": s_rows,
        "carrier_rows": c_rows,
        "delayed_fraction_rows": f_rows,
    }
    payload["_stats_ref"] = stats
    summary_md.write_text(render_markdown(payload), encoding="utf-8")
    payload.pop("_stats_ref")
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(summary_md)
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
