#!/usr/bin/env python3
"""Build TES Step05-style prompt comparison including side-Compton/FoV.

This is a post-processing pass over the already completed independent-source
FLUKA prompt runs. It intentionally does not use .sim.gz replay as FLUKA input.
The Geant4/TES side is the Step05 event catalog, and the FLUKA side is the raw
event/deposit CSV output from the independent-source runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
STEP05 = TES_ROOT / "stepwise_maintenance/step05_veto_time_axis/outputs_fix5_fullstat_v2_exactpos_m50000_s260613_l1"
EVENT_CATALOG = STEP05 / "work/event_catalog.pkl"
OFFICIAL_RATES = STEP05 / "step05_fix5_fullstat_v2_exactpos_m50000_s260613_l1_rates.csv"
STEP09_FOCUS_SUMMARY = (
    TES_ROOT
    / "stepwise_maintenance/step09_optics_bridge/outputs_fix5_fullstat_v2_exactpos_m50000_s260613"
    / "step09_focus_summary.json"
)

ACTIVE_VETO_THRESHOLD_KEV = 50.0
ME_KEV = 511.0
PIX_HALF_X_CM = 0.075
PIX_HALF_Y_CM = 0.075
PIX_HALF_Z_CM = 0.150
N_CONE_SAMPLES = 24
MAX_ENUM_HITS = 6
REJECT_POLICY = "keep"

PROMPT_RUNS: dict[str, Path] = {
    "eplus": Path("work_fluka_harness/independent_source_runs/eplus_independent_fixed_seed24065420_n1949816_chunks24_parallel"),
    "muplus": Path("work_fluka_harness/independent_source_runs/muplus_independent_fixed_seed24065500_n92840_chunks8_parallel"),
    "muminus": Path("work_fluka_harness/independent_source_runs/muminus_independent_fixed_seed24065600_n82824_chunks8_parallel"),
    "alpha": Path("work_fluka_harness/independent_source_runs/alpha_independent_fixed_seed24065700_n191464_chunks8_parallel"),
    "p": Path("work_fluka_harness/independent_source_runs/p_independent_fixed_seed24065800_n1871808_chunks24_parallel"),
    "eminus": Path("work_fluka_harness/independent_source_runs/eminus_independent_fixed_seed24065900_n3316936_chunks32_parallel"),
    "gamma": Path("work_fluka_harness/independent_source_runs/gamma_independent_fixed_seed24066000_n10000000_chunks40_parallel"),
    "n": Path("work_fluka_harness/independent_source_runs/n_independent_fixed_seed24066100_n7704528_chunks32_parallel"),
}

WINDOWS = {
    "broad_480_550": (480.0, 550.0),
    "w2_510p58_511p42": (510.58, 511.42),
}


@dataclass
class Hit:
    x: float
    y: float
    z: float
    e: float
    pixel_uid: str = ""
    layer: int = 0


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def poisson_sigma_from_weights(weights: list[float] | np.ndarray) -> float:
    if len(weights) == 0:
        return 0.0
    arr = np.asarray(weights, dtype=float)
    return float(np.sqrt(np.square(arr).sum()))


def ratio(num: float, den: float) -> float | None:
    if den == 0.0:
        return None
    return num / den


def z_score(fluka: float, fluka_sigma: float, g4: float, g4_sigma: float) -> float | None:
    den = math.sqrt(fluka_sigma * fluka_sigma + g4_sigma * g4_sigma)
    if den == 0.0:
        return None
    return (fluka - g4) / den


def unit(v: np.ndarray) -> np.ndarray | None:
    n = float(np.linalg.norm(v))
    return None if n <= 0.0 else v / n


def rotate_y(values: tuple[float, float, float], angle_deg: float) -> np.ndarray:
    x, y, z = values
    a = math.radians(angle_deg)
    c = math.cos(a)
    s = math.sin(a)
    return np.asarray([c * x + s * z, y, -s * x + c * z], dtype=float)


def side_entry_disk() -> dict[str, Any]:
    summary = load_json(STEP09_FOCUS_SUMMARY)
    bridge = summary.get("base_bridge") or summary.get("bridge")
    if not isinstance(bridge, dict):
        raise KeyError(f"Cannot locate Step09 bridge in {STEP09_FOCUS_SUMMARY}")
    angle = float(bridge["instrument_rotation_y_deg"])
    local_center = (float(bridge["x_plane_cm"]), float(bridge["axis_y_cm"]), float(bridge["axis_z_cm"]))
    center = rotate_y(local_center, angle)
    normal = unit(rotate_y((1.0, 0.0, 0.0), angle))
    if normal is None:
        raise ValueError("bad side-entry disk normal")
    ref = np.asarray([0.0, 0.0, 1.0], dtype=float)
    if abs(float(np.dot(normal, ref))) > 0.9:
        ref = np.asarray([0.0, 1.0, 0.0], dtype=float)
    u = unit(np.cross(normal, ref))
    if u is None:
        raise ValueError("bad side-entry disk basis")
    v = unit(np.cross(normal, u))
    if v is None:
        raise ValueError("bad side-entry disk basis")
    return {
        "center_cm": center,
        "normal": normal,
        "basis_u": u,
        "basis_v": v,
        "radius_cm": float(bridge["be_radius_cm"]),
        "local_center_cm": local_center,
        "rotation_y_deg": angle,
        "side_window_look_elevation_deg": float(bridge["side_window_look_elevation_deg"]),
        "source": str(STEP09_FOCUS_SUMMARY),
    }


def representative_points_box(hit: Hit) -> np.ndarray:
    pts = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                pts.append([hit.x + sx * PIX_HALF_X_CM, hit.y + sy * PIX_HALF_Y_CM, hit.z + sz * PIX_HALF_Z_CM])
    pts.append([hit.x, hit.y, hit.z])
    return np.asarray(pts, dtype=float)


def orthonormal_basis_batch(axis_hat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ref = np.zeros_like(axis_hat)
    mask = np.abs(axis_hat[:, 2]) < 0.9
    ref[mask] = np.asarray([0.0, 0.0, 1.0])
    ref[~mask] = np.asarray([1.0, 0.0, 0.0])
    e1 = np.cross(axis_hat, ref)
    n1 = np.linalg.norm(e1, axis=1)
    valid1 = n1 > 1.0e-12
    e1[valid1] /= n1[valid1, None]
    e2 = np.cross(axis_hat, e1)
    n2 = np.linalg.norm(e2, axis=1)
    valid2 = n2 > 1.0e-12
    e2[valid2] /= n2[valid2, None]
    return e1, e2, valid1 & valid2


def compton_cos_theta(e_first: float, e_second: float) -> float:
    e0 = e_first + e_second
    ep = e_second
    if e0 <= 0 or ep <= 0:
        return float("nan")
    return 1.0 - ME_KEV * (1.0 / ep - 1.0 / e0)


def segments_intersect_disk_2d(segments: np.ndarray, radius: float) -> bool:
    if segments is None or len(segments) == 0:
        return False
    p0 = segments[:, 0, :]
    p1 = segments[:, 1, :]
    d = p1 - p0
    a = np.sum(d * d, axis=1)
    t = np.zeros(len(segments), dtype=float)
    nz = a > 1.0e-18
    if np.any(nz):
        t[nz] = -np.sum(p0[nz] * d[nz], axis=1) / a[nz]
        t[nz] = np.clip(t[nz], 0.0, 1.0)
    closest = p0 + t[:, None] * d
    r2 = np.sum(closest * closest, axis=1)
    return bool(np.any(r2 <= radius * radius))


def sample_cone_side_disk(hit1: Hit, hit2: Hit, e_first: float, e_second: float, disk: dict[str, Any]) -> tuple[bool, bool]:
    ctheta = compton_cos_theta(e_first, e_second)
    if (not np.isfinite(ctheta)) or ctheta < -1.0 or ctheta > 1.0:
        return False, False
    theta = math.acos(float(np.clip(ctheta, -1.0, 1.0)))
    reps1 = representative_points_box(hit1)
    reps2 = representative_points_box(hit2)
    p1 = np.repeat(reps1, len(reps2), axis=0)
    p2 = np.tile(reps2, (len(reps1), 1))
    axis_vec = p1 - p2
    norms = np.linalg.norm(axis_vec, axis=1)
    valid_norm = norms > 1.0e-12
    if not np.any(valid_norm):
        return True, False
    p1 = p1[valid_norm]
    axis_hat = axis_vec[valid_norm] / norms[valid_norm, None]
    e1, e2, valid_basis = orthonormal_basis_batch(axis_hat)
    if not np.any(valid_basis):
        return True, False
    p1 = p1[valid_basis]
    axis_hat = axis_hat[valid_basis]
    e1 = e1[valid_basis]
    e2 = e2[valid_basis]

    phis = np.linspace(0.0, 2.0 * math.pi, N_CONE_SAMPLES, endpoint=False)
    dirs = (
        math.cos(theta) * axis_hat[:, None, :]
        + math.sin(theta)
        * (np.cos(phis)[None, :, None] * e1[:, None, :] + np.sin(phis)[None, :, None] * e2[:, None, :])
    )
    center = np.asarray(disk["center_cm"], dtype=float)
    normal = np.asarray(disk["normal"], dtype=float)
    u = np.asarray(disk["basis_u"], dtype=float)
    v = np.asarray(disk["basis_v"], dtype=float)
    denom = np.tensordot(dirs, normal, axes=([2], [0]))
    numer = np.dot(center, normal) - np.dot(p1, normal)
    t = np.full(denom.shape, np.nan, dtype=float)
    valid_denom = np.abs(denom) > 1.0e-12
    numer_grid = np.broadcast_to(numer[:, None], denom.shape)
    t[valid_denom] = numer_grid[valid_denom] / denom[valid_denom]
    valid = valid_denom & (t > 0.0) & np.isfinite(t)
    if not np.any(valid):
        return True, False

    points = p1[:, None, :] + np.where(valid, t, 0.0)[:, :, None] * dirs
    relp = points - center
    coords = np.stack([np.tensordot(relp, u, axes=([2], [0])), np.tensordot(relp, v, axes=([2], [0]))], axis=2)
    r2 = np.sum(coords * coords, axis=2)
    if bool(np.any(valid & (r2 <= float(disk["radius_cm"]) ** 2))):
        return True, True

    segs = []
    for i in range(coords.shape[0]):
        valid_i = valid[i]
        seg_mask = valid_i & np.roll(valid_i, -1)
        idx = np.where(seg_mask)[0]
        if len(idx):
            segs.append(np.stack([coords[i, idx], coords[i, (idx + 1) % coords.shape[1]]], axis=1))
    flat_segments = np.concatenate(segs, axis=0) if segs else np.empty((0, 2, 2), dtype=float)
    return True, segments_intersect_disk_2d(flat_segments, float(disk["radius_cm"]))


def sequence_metrics(ordered: list[Hit]) -> dict[str, float] | None:
    n = len(ordered)
    energies = np.asarray([h.e for h in ordered], dtype=float)
    positions = np.asarray([[h.x, h.y, h.z] for h in ordered], dtype=float)
    if np.any(~np.isfinite(energies)) or np.any(energies <= 0):
        return None
    total_e = float(np.sum(energies))
    rem_after = total_e - np.cumsum(energies)
    cos_kin = []
    theta1 = None
    for i in range(n - 1):
        if rem_after[i] <= 0:
            return None
        c = compton_cos_theta(float(energies[i]), float(rem_after[i]))
        if (not np.isfinite(c)) or c < -1.0 or c > 1.0:
            return None
        cos_kin.append(float(c))
        if i == 0:
            theta1 = math.degrees(math.acos(float(np.clip(c, -1.0, 1.0))))
    qf_terms = []
    for i in range(1, n - 1):
        u_prev = unit(positions[i] - positions[i - 1])
        u_next = unit(positions[i + 1] - positions[i])
        if u_prev is None or u_next is None:
            return None
        qf_terms.append((cos_kin[i] - float(np.dot(u_prev, u_next))) ** 2)
    return {
        "qf": float(np.sum(qf_terms)) if qf_terms else 0.0,
        "first_lever_arm": float(np.linalg.norm(positions[1] - positions[0])),
        "e_first": float(energies[0]),
        "e_after1": float(rem_after[0]),
        "theta1": float(theta1) if theta1 is not None else float("nan"),
    }


def classify_side_compton(hits: list[Hit], disk: dict[str, Any], reject_policy: str = REJECT_POLICY) -> str:
    if len(hits) <= 1:
        return "single"
    if len(hits) == 2:
        decisions = []
        for a, b in ((hits[0], hits[1]), (hits[1], hits[0])):
            ok, intersects = sample_cone_side_disk(a, b, a.e, b.e, disk)
            if ok:
                decisions.append(intersects)
        cls = "reject" if not decisions else ("keep" if any(decisions) else "veto")
    else:
        import itertools

        if len(hits) > MAX_ENUM_HITS:
            cls = "reject"
        else:
            valid = []
            for perm in itertools.permutations(range(len(hits))):
                ordered = [hits[i] for i in perm]
                metrics = sequence_metrics(ordered)
                if metrics is None:
                    continue
                valid.append((metrics["qf"], -metrics["first_lever_arm"], ordered, metrics))
            if not valid:
                cls = "reject"
            else:
                _, _, ordered, metrics = sorted(valid, key=lambda x: (x[0], x[1]))[0]
                ok, intersects = sample_cone_side_disk(ordered[0], ordered[1], metrics["e_first"], metrics["e_after1"], disk)
                cls = "reject" if not ok else ("keep" if intersects else "veto")
    if cls == "reject" and reject_policy == "keep":
        return "reject_kept"
    return cls


def side_keep_from_hits(hits: list[Hit], disk: dict[str, Any]) -> tuple[bool, str]:
    cls = classify_side_compton(hits, disk, REJECT_POLICY)
    return cls in ("single", "keep", "reject_kept"), cls


def event_hits(cat: dict[str, Any], idx: int) -> list[Hit]:
    s = int(cat["pix_start"][idx])
    n = int(cat["pix_count"][idx])
    hits = []
    for j in range(s, s + n):
        hits.append(
            Hit(
                x=float(cat["pix_x"][j]),
                y=float(cat["pix_y"][j]),
                z=float(cat["pix_z"][j]),
                e=float(cat["pix_e"][j]),
                pixel_uid=str(cat["pix_uid"][j]),
                layer=int(cat["pix_layer"][j]),
            )
        )
    return hits


def init_stage() -> dict[str, Any]:
    return {"events": 0, "rate": 0.0, "sigma2": 0.0, "weights": [], "class_counts": Counter()}


def add_weight(stage: dict[str, Any], weight: float) -> None:
    stage["events"] += 1
    stage["rate"] += weight
    stage["sigma2"] += weight * weight
    stage["weights"].append(weight)


def summarize_stage(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "events": int(stage["events"]),
        "rate_s-1": float(stage["rate"]),
        "mc_sigma_s-1": math.sqrt(float(stage["sigma2"])),
        "side_compton_class_counts": dict(sorted(stage.get("class_counts", Counter()).items())),
    }


def load_g4_rows(disk: dict[str, Any]) -> tuple[list[dict[str, object]], dict[str, Any]]:
    with EVENT_CATALOG.open("rb") as f:
        cat = pickle.load(f)

    rows: list[dict[str, object]] = []
    details: dict[str, Any] = {}
    stream = np.asarray(cat["stream"], dtype=object)
    tags = np.asarray(cat["tag"], dtype=object)
    tes = np.asarray(cat["tes_total_keV"], dtype=float)
    bgo = np.asarray(cat["bgo_total_keV"], dtype=float)
    rate = np.asarray(cat["rate_hz"], dtype=float)

    particles = sorted(str(x) for x in set(tags[stream == "prompt"]))
    for particle in particles + ["all_prompt"]:
        if particle == "all_prompt":
            base = stream == "prompt"
        else:
            base = (stream == "prompt") & (tags == particle)
        details[particle] = {}
        for window, (lo, hi) in WINDOWS.items():
            raw_mask = base & (tes >= lo) & (tes < hi)
            active_mask = raw_mask & (bgo < ACTIVE_VETO_THRESHOLD_KEV)
            final = init_stage()
            for idx in np.flatnonzero(active_mask):
                keep, cls = side_keep_from_hits(event_hits(cat, int(idx)), disk)
                final["class_counts"][cls] += 1
                if keep:
                    add_weight(final, float(rate[idx]))
            stages = {
                "raw": {
                    "events": int(np.count_nonzero(raw_mask)),
                    "rate_s-1": float(np.sum(rate[raw_mask])),
                    "mc_sigma_s-1": poisson_sigma_from_weights(rate[raw_mask]),
                    "side_compton_class_counts": {},
                },
                "active_veto_pass": {
                    "events": int(np.count_nonzero(active_mask)),
                    "rate_s-1": float(np.sum(rate[active_mask])),
                    "mc_sigma_s-1": poisson_sigma_from_weights(rate[active_mask]),
                    "side_compton_class_counts": {},
                },
                "side_compton_fov_pass": summarize_stage(final),
            }
            details[particle][window] = stages
            for stage, item in stages.items():
                rows.append(
                    {
                        "code": "GEANT4_MEGALIB",
                        "particle": particle,
                        "window": window,
                        "stage": stage,
                        "events": item["events"],
                        "rate_s-1": item["rate_s-1"],
                        "mc_sigma_s-1": item["mc_sigma_s-1"],
                        "class_counts": json.dumps(item["side_compton_class_counts"], sort_keys=True),
                    }
                )
    return rows, details


def official_prompt_rates() -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    for row in load_csv(OFFICIAL_RATES):
        if row.get("stream") != "prompt":
            continue
        out[(row["window"], row["stage"])] = {"events": int(row["events"]), "rate_s-1": float(row["rate_s-1"])}
    return out


def validate_g4_against_official(g4_details: dict[str, Any]) -> dict[str, Any]:
    official = official_prompt_rates()
    checks = []
    ok = True
    for (window, stage), ref in official.items():
        got = g4_details["all_prompt"][window][stage]
        event_delta = int(got["events"]) - int(ref["events"])
        rate_delta = float(got["rate_s-1"]) - float(ref["rate_s-1"])
        passed = event_delta == 0 and abs(rate_delta) <= max(1.0e-10, abs(float(ref["rate_s-1"])) * 1.0e-9)
        ok = ok and passed
        checks.append(
            {
                "window": window,
                "stage": stage,
                "official_events": ref["events"],
                "computed_events": got["events"],
                "event_delta": event_delta,
                "official_rate_s-1": ref["rate_s-1"],
                "computed_rate_s-1": got["rate_s-1"],
                "rate_delta_s-1": rate_delta,
                "status": "PASS" if passed else "FAIL",
            }
        )
    return {"status": "PASS" if ok else "FAIL", "checks": checks, "official_rates": str(OFFICIAL_RATES)}


def find_file(root: Path, suffix: str) -> Path:
    matches = sorted(
        [p for p in root.rglob("*") if p.is_file() and (p.name == suffix or p.name.endswith("_" + suffix))],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise FileNotFoundError(f"missing {suffix} below {root}")
    return matches[0]


def valid_chunk_dirs(root: Path) -> list[Path]:
    out = []
    for d in sorted(p for p in root.glob("chunk_*_n*") if p.is_dir()):
        summary = d / "summary.json"
        if not summary.exists():
            continue
        data = load_json(summary)
        verdict = data.get("mvp_raw_data_verdict", {})
        closure = data.get("scoring_closure", {})
        if verdict.get("status") == "RAW_DATA_MVP_PASS" and closure.get("status") == "PASS":
            out.append(d)
    return out


def load_history_weights(chunk: Path) -> dict[int, float]:
    weights: dict[int, float] = {}
    with (chunk / "raw_events/primaries.csv").open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        hid_i = idx["history_id"]
        hw_i = idx["history_weight"]
        tw_i = idx.get("fluka_transport_weight")
        for row in reader:
            hid = int(row[hid_i])
            transport_weight = float(row[tw_i]) if tw_i is not None and row[tw_i] else 0.0
            weights[hid] = float(row[hw_i]) * transport_weight
    return weights


def candidate_windows(tes_keV: float, shield_keV: float) -> tuple[list[str], list[str]]:
    raw = []
    active = []
    for window, (lo, hi) in WINDOWS.items():
        if lo <= tes_keV < hi:
            raw.append(window)
            if shield_keV < ACTIVE_VETO_THRESHOLD_KEV:
                active.append(window)
    return raw, active


def fluka_hits_for_candidates(chunk: Path, candidates: set[int]) -> dict[int, list[Hit]]:
    if not candidates:
        return {}
    deposits_path = find_file(chunk, "raw_deposits_tmp.csv")
    by_history_region: dict[int, dict[str, dict[str, float]]] = defaultdict(dict)
    with deposits_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        hid_i = idx["history_id"]
        region_i = idx["region_name"]
        kind_i = idx["detector_kind"]
        e_i = idx["deposit_keV"]
        x_i = idx["x_cm"]
        y_i = idx["y_cm"]
        z_i = idx["z_cm"]
        for row in reader:
            kind = row[kind_i].strip().upper()
            if "TES" not in kind:
                continue
            hid = int(row[hid_i])
            if hid not in candidates:
                continue
            region = row[region_i].strip()
            e = float(row[e_i])
            if e <= 0.0:
                continue
            rec = by_history_region[hid].setdefault(region, {"e": 0.0, "wx": 0.0, "wy": 0.0, "wz": 0.0})
            rec["e"] += e
            rec["wx"] += e * float(row[x_i])
            rec["wy"] += e * float(row[y_i])
            rec["wz"] += e * float(row[z_i])
    hits_by_history: dict[int, list[Hit]] = {}
    for hid, by_region in by_history_region.items():
        hits = []
        for region, rec in sorted(by_region.items()):
            e = rec["e"]
            if e <= 0.0:
                continue
            hits.append(Hit(x=rec["wx"] / e, y=rec["wy"] / e, z=rec["wz"] / e, e=e, pixel_uid=region))
        hits_by_history[hid] = hits
    return hits_by_history


def load_fluka_particle(particle: str, root: Path, disk: dict[str, Any]) -> tuple[list[dict[str, object]], dict[str, Any]]:
    chunks = valid_chunk_dirs(root)
    print(f"[{particle}] valid chunks: {len(chunks)}", flush=True)
    stages: dict[str, dict[str, dict[str, Any]]] = {
        window: {"raw": init_stage(), "active_veto_pass": init_stage(), "side_compton_fov_pass": init_stage()} for window in WINDOWS
    }
    histories = 0
    candidate_by_chunk: dict[Path, dict[int, list[str]]] = {}
    weights_by_chunk: dict[Path, dict[int, float]] = {}

    for chunk_idx, chunk in enumerate(chunks, start=1):
        weights = load_history_weights(chunk)
        weights_by_chunk[chunk] = weights
        histories += len(weights)
        totals_path = find_file(chunk, "event_totals_tmp.csv")
        active_candidates: dict[int, list[str]] = {}
        with totals_path.open(newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader)
            idx = {name: i for i, name in enumerate(header)}
            hid_i = idx["history_id"]
            tes_i = idx["tes_total_keV"]
            shield_i = idx["shield_total_keV"]
            for row in reader:
                hid = int(row[hid_i])
                weight = weights.get(hid, 0.0)
                raw_windows, active_windows = candidate_windows(float(row[tes_i]), float(row[shield_i]))
                for window in raw_windows:
                    add_weight(stages[window]["raw"], weight)
                for window in active_windows:
                    add_weight(stages[window]["active_veto_pass"], weight)
                    active_candidates.setdefault(hid, []).append(window)
        candidate_by_chunk[chunk] = active_candidates
        if chunk_idx == 1 or chunk_idx == len(chunks) or chunk_idx % 4 == 0:
            n_candidates = sum(len(v) for v in active_candidates.values())
            print(
                f"[{particle}] totals {chunk_idx}/{len(chunks)} histories={histories} "
                f"active_candidate_entries={n_candidates}",
                flush=True,
            )

    missing_hits = Counter()
    for chunk_idx, (chunk, active_candidates) in enumerate(candidate_by_chunk.items(), start=1):
        weights = weights_by_chunk[chunk]
        hits_by_history = fluka_hits_for_candidates(chunk, set(active_candidates))
        for hid, windows in active_candidates.items():
            hits = hits_by_history.get(hid, [])
            if not hits:
                cls = "missing_tes_hits"
                keep = False
            else:
                keep, cls = side_keep_from_hits(hits, disk)
            for window in windows:
                stages[window]["side_compton_fov_pass"]["class_counts"][cls] += 1
                if keep:
                    add_weight(stages[window]["side_compton_fov_pass"], weights.get(hid, 0.0))
                elif cls == "missing_tes_hits":
                    missing_hits[window] += 1
        if chunk_idx == 1 or chunk_idx == len(chunks) or chunk_idx % 4 == 0:
            print(
                f"[{particle}] deposits {chunk_idx}/{len(chunks)} candidate_histories={len(active_candidates)}",
                flush=True,
            )

    rows = []
    details: dict[str, Any] = {"histories": histories, "valid_chunks": len(chunks), "windows": {}}
    for window in WINDOWS:
        details["windows"][window] = {}
        for stage in ("raw", "active_veto_pass", "side_compton_fov_pass"):
            item = summarize_stage(stages[window][stage])
            details["windows"][window][stage] = item
            rows.append(
                {
                    "code": "FLUKA",
                    "particle": particle,
                    "window": window,
                    "stage": stage,
                    "events": item["events"],
                    "rate_s-1": item["rate_s-1"],
                    "mc_sigma_s-1": item["mc_sigma_s-1"],
                    "class_counts": json.dumps(item["side_compton_class_counts"], sort_keys=True),
                }
            )
    if missing_hits:
        details["missing_hits_by_window"] = dict(missing_hits)
    return rows, details


def aggregate_particle_details(details: dict[str, Any]) -> dict[str, Any]:
    total = {window: {stage: init_stage() for stage in ("raw", "active_veto_pass", "side_compton_fov_pass")} for window in WINDOWS}
    histories = 0
    valid_chunks = 0
    for particle, pdata in details.items():
        histories += int(pdata.get("histories", 0))
        valid_chunks += int(pdata.get("valid_chunks", 0))
        for window in WINDOWS:
            for stage in ("raw", "active_veto_pass", "side_compton_fov_pass"):
                item = pdata["windows"][window][stage]
                total[window][stage]["events"] += int(item["events"])
                total[window][stage]["rate"] += float(item["rate_s-1"])
                total[window][stage]["sigma2"] += float(item["mc_sigma_s-1"]) ** 2
                total[window][stage]["class_counts"].update(item.get("side_compton_class_counts", {}))
    return {
        "histories": histories,
        "valid_chunks": valid_chunks,
        "windows": {window: {stage: summarize_stage(total[window][stage]) for stage in total[window]} for window in WINDOWS},
    }


def comparison_rows(g4_details: dict[str, Any], fluka_details: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    particles = sorted(PROMPT_RUNS) + ["all_prompt"]
    for particle in particles:
        fpart = fluka_details["all_prompt"] if particle == "all_prompt" else fluka_details[particle]
        gpart = g4_details[particle]
        for window in WINDOWS:
            for stage in ("raw", "active_veto_pass", "side_compton_fov_pass"):
                g = gpart[window][stage]
                f = fpart["windows"][window][stage] if particle != "all_prompt" else fpart["windows"][window][stage]
                rows.append(
                    {
                        "particle": particle,
                        "window": window,
                        "stage": stage,
                        "g4_events": g["events"],
                        "g4_rate_s-1": g["rate_s-1"],
                        "g4_sigma_s-1": g["mc_sigma_s-1"],
                        "fluka_events": f["events"],
                        "fluka_rate_s-1": f["rate_s-1"],
                        "fluka_sigma_s-1": f["mc_sigma_s-1"],
                        "fluka_over_g4": ratio(float(f["rate_s-1"]), float(g["rate_s-1"])),
                        "z": z_score(float(f["rate_s-1"]), float(f["mc_sigma_s-1"]), float(g["rate_s-1"]), float(g["mc_sigma_s-1"])),
                        "g4_class_counts": json.dumps(g.get("side_compton_class_counts", {}), sort_keys=True),
                        "fluka_class_counts": json.dumps(f.get("side_compton_class_counts", {}), sort_keys=True),
                    }
                )
    return rows


def fmt_rate(events: object, rate: object, sigma: object | None = None) -> str:
    if sigma is None:
        return f"{int(events)} / {float(rate):.7g}"
    return f"{int(events)} / {float(rate):.7g}+/-{float(sigma):.3g}"


def render_summary(payload: dict[str, Any], rows: list[dict[str, object]]) -> str:
    lines = [
        "# Prompt Independent-Source Step05 Same-Statistic Comparison",
        "",
        f"- created_utc: {payload['created_utc']}",
        f"- status: {payload['status']}",
        f"- fluka_histories: {payload['fluka']['all_prompt']['histories']}",
        f"- fluka_valid_chunks: {payload['fluka']['all_prompt']['valid_chunks']}",
        f"- g4_step05_validation: {payload['g4_validation']['status']}",
        f"- source_mode: sampled_source_authority; no .sim.gz replay",
        f"- active_veto_threshold_keV: {ACTIVE_VETO_THRESHOLD_KEV:g}",
        f"- reject_policy: {REJECT_POLICY}",
        "",
        "## Aggregate Prompt",
        "",
        "| window | stage | G4 events/rate | FLUKA events/rate | FLUKA/G4 | z |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["particle"] != "all_prompt":
            continue
        ratio_v = row["fluka_over_g4"]
        z = row["z"]
        lines.append(
            "| {window} | {stage} | {g4} | {fluka} | {ratio} | {z} |".format(
                window=row["window"],
                stage=row["stage"],
                g4=fmt_rate(row["g4_events"], row["g4_rate_s-1"], row["g4_sigma_s-1"]),
                fluka=fmt_rate(row["fluka_events"], row["fluka_rate_s-1"], row["fluka_sigma_s-1"]),
                ratio="" if ratio_v is None else f"{float(ratio_v):.4g}",
                z="" if z is None else f"{float(z):.3g}",
            )
        )
    lines.extend(["", "## W2 By Prompt Particle", "", "| particle | stage | G4 events/rate | FLUKA events/rate | FLUKA/G4 | z |", "|---|---|---:|---:|---:|---:|"])
    for row in rows:
        if row["window"] != "w2_510p58_511p42" or row["particle"] == "all_prompt":
            continue
        ratio_v = row["fluka_over_g4"]
        z = row["z"]
        lines.append(
            "| {particle} | {stage} | {g4} | {fluka} | {ratio} | {z} |".format(
                particle=row["particle"],
                stage=row["stage"],
                g4=fmt_rate(row["g4_events"], row["g4_rate_s-1"], row["g4_sigma_s-1"]),
                fluka=fmt_rate(row["fluka_events"], row["fluka_rate_s-1"], row["fluka_sigma_s-1"]),
                ratio="" if ratio_v is None else f"{float(ratio_v):.4g}",
                z="" if z is None else f"{float(z):.3g}",
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `side_compton_fov_pass` uses the TES Step05 side-entry Compton/FoV classifier ported from `build_v3p5_centerfinger_step05_l1_response.py`.",
            "- The Geant4 side is validated against the official Step05 prompt CSV before FLUKA comparison.",
            "- FLUKA TES deposits are aggregated by FLUKA TES pixel region name and energy-weighted deposit position before classification.",
            "- This remains prompt-only; delayed activation/source construction is not included.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("work_fluka_harness/prompt_final_same_stat_independent_source_20260625"))
    args = ap.parse_args()

    disk = side_entry_disk()
    g4_rows, g4_details = load_g4_rows(disk)
    validation = validate_g4_against_official(g4_details)
    if validation["status"] != "PASS":
        raise SystemExit("G4 Step05 validation failed; not comparing FLUKA")

    fluka_rows_all: list[dict[str, object]] = []
    fluka_details: dict[str, Any] = {}
    for particle, root in PROMPT_RUNS.items():
        rows, details = load_fluka_particle(particle, root, disk)
        fluka_rows_all.extend(rows)
        fluka_details[particle] = details
    fluka_details["all_prompt"] = aggregate_particle_details(fluka_details)

    rows = comparison_rows(g4_details, fluka_details)
    payload = {
        "created_utc": now_utc(),
        "status": "PROMPT_FINAL_SAME_STAT_PRESENT",
        "scope": "prompt independent-source FLUKA vs TES Step05 same statistics",
        "source_mode": "sampled_source_authority",
        "inputs": {
            "event_catalog": str(EVENT_CATALOG),
            "official_rates_csv": str(OFFICIAL_RATES),
            "step09_focus_summary": str(STEP09_FOCUS_SUMMARY),
            "fluka_runs": {k: str(v) for k, v in PROMPT_RUNS.items()},
        },
        "disk": {
            "center_cm": np.asarray(disk["center_cm"], dtype=float).tolist(),
            "normal": np.asarray(disk["normal"], dtype=float).tolist(),
            "basis_u": np.asarray(disk["basis_u"], dtype=float).tolist(),
            "basis_v": np.asarray(disk["basis_v"], dtype=float).tolist(),
            "radius_cm": disk["radius_cm"],
            "local_center_cm": list(disk["local_center_cm"]),
            "rotation_y_deg": disk["rotation_y_deg"],
            "side_window_look_elevation_deg": disk["side_window_look_elevation_deg"],
        },
        "g4_validation": validation,
        "g4": g4_details,
        "fluka": fluka_details,
        "comparison_rows": rows,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "summary.json", payload)
    fields = [
        "particle",
        "window",
        "stage",
        "g4_events",
        "g4_rate_s-1",
        "g4_sigma_s-1",
        "fluka_events",
        "fluka_rate_s-1",
        "fluka_sigma_s-1",
        "fluka_over_g4",
        "z",
        "g4_class_counts",
        "fluka_class_counts",
    ]
    write_csv(args.out_dir / "same_stat_comparison.csv", rows, fields)
    write_csv(
        args.out_dir / "g4_step05_validation.csv",
        validation["checks"],
        [
            "window",
            "stage",
            "official_events",
            "computed_events",
            "event_delta",
            "official_rate_s-1",
            "computed_rate_s-1",
            "rate_delta_s-1",
            "status",
        ],
    )
    (args.out_dir / "summary.md").write_text(render_summary(payload, rows), encoding="utf-8")
    print(args.out_dir / "summary.md")
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
