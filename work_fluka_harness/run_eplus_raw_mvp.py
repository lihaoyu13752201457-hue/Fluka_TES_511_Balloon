#!/usr/bin/env python3
"""Run prompt-primary FLUKA raw data from the independent source authority."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
RUN_ROOT = TES_ROOT / "engineering/fluka_crosscode_validation_20260624"
GEOM = RUN_ROOT / "02_geometry_translation"
SRC = RUN_ROOT / "03_source_authority"
SCORING = RUN_ROOT / "04_raw_scoring"
DEFAULT_OUT = RUN_ROOT / "06_eplus_prompt_pilot"
OUT = DEFAULT_OUT
WP00 = RUN_ROOT / "00_manifest"
REGION_MAP = GEOM / "region_map.csv"
SMOKE_DECK = GEOM / "fluka_geometry/fix5_geometry_smoke.inp"
MEGALIB_SOURCE_DIR = TES_ROOT / "config/megalib_sources_fullsphere20_fix5_tilt45"
FLUKA_HOME = Path("/home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka")
RFLUKA = FLUKA_HOME / "bin/rfluka"

PROMPT_PRIMARY_TAGS = ("alpha", "eminus", "eplus", "gamma", "muminus", "muplus", "n", "p")
PARTICLE_CODE = {
    "alpha": -6,
    "eminus": 3,
    "eplus": 4,
    "gamma": 7,
    "muminus": 11,
    "muplus": 10,
    "n": 8,
    "p": 1,
}
BEAM_PARTICLE_NAME = {
    "alpha": "4-HELIUM",
    "eminus": "ELECTRON",
    "eplus": "POSITRON",
    "gamma": "PHOTON",
    "muminus": "MUON-",
    "muplus": "MUON+",
    "n": "NEUTRON",
    "p": "PROTON",
}
PARTICLE_BY_CODE = {
    -6: "4-HELIUM",
    1: "PROTON",
    3: "ELECTRON",
    4: "POSITRON",
    7: "PHOTON",
    8: "NEUTRON",
    10: "MUON+",
    11: "MUON-",
    208: "HEAVY_RECOIL",
    211: "EM_BELOW_THRESHOLD",
    308: "LOW_ENERGY_NEUTRON_KERMA",
}

RAW_EVENT_FIELDS = [
    "code",
    "run_id",
    "seed",
    "history_id",
    "stream",
    "primary_tag",
    "primary_energy_keV",
    "primary_x_cm",
    "primary_y_cm",
    "primary_z_cm",
    "primary_dx",
    "primary_dy",
    "primary_dz",
    "history_weight",
    "volume_id",
    "volume_name",
    "material_name",
    "detector_kind",
    "deposit_keV",
    "deposit_time_s",
    "track_id",
    "parent_track_id",
    "particle",
    "creator_process",
    "interaction_process",
    "x_cm",
    "y_cm",
    "z_cm",
    "tes_total_keV",
    "shield_total_keV",
    "fluka_region_name",
    "fluka_particle_code",
    "fluka_icode",
]

PRIMARY_FIELDS = [
    "run_id",
    "seed",
    "history_id",
    "stream",
    "primary_tag",
    "source_bin",
    "primary_energy_keV",
    "primary_energy_GeV",
    "source_start_area_center_x_cm",
    "source_start_area_center_y_cm",
    "source_start_area_center_z_cm",
    "primary_x_cm",
    "primary_y_cm",
    "primary_z_cm",
    "primary_dx",
    "primary_dy",
    "primary_dz",
    "history_weight",
    "fluka_transport_weight",
    "transport_primary_energy_keV",
    "transport_primary_energy_GeV",
    "transport_energy_policy",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def env() -> dict[str, str]:
    out = os.environ.copy()
    out["FLUKA_HOME"] = str(FLUKA_HOME)
    out["FLUKADATA"] = str(FLUKA_HOME / "data")
    out["PATH"] = str(FLUKA_HOME / "bin") + os.pathsep + out.get("PATH", "")
    return out


def run(cmd: list[str], cwd: Path, log: Path) -> int:
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env(), stdout=fh, stderr=subprocess.STDOUT)
    return proc.returncode


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]


def geometry_without_run_tail() -> str:
    lines = SMOKE_DECK.read_text(encoding="ascii").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("GEOBEGIN"))
    end = next(i for i, line in enumerate(lines) if line.startswith("RANDOMIZE"))
    return "\n".join(lines[start:end]) + "\n"


def default_out_for(primary_tag: str) -> Path:
    if primary_tag == "eplus":
        return DEFAULT_OUT
    return RUN_ROOT / f"06_{primary_tag}_prompt_pilot"


def megalib_source_path(primary_tag: str) -> Path:
    return MEGALIB_SOURCE_DIR / f"Background_{primary_tag}_fullsphere20.source"


def megalib_setup_path(primary_tag: str) -> Path:
    source_path = megalib_source_path(primary_tag)
    text = source_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("# geometry_setup="):
            rel = line.split("=", 1)[1].strip()
            return TES_ROOT / rel
    raise ValueError(f"missing geometry_setup header in {source_path}")


def load_surrounding_sphere_center(primary_tag: str) -> tuple[float, float, float]:
    setup = megalib_setup_path(primary_tag)
    for line in setup.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 6 and parts[0] == "SurroundingSphere":
            return float(parts[2]), float(parts[3]), float(parts[4])
    raise ValueError(f"missing SurroundingSphere line in {setup}")


def default_defaults_sdum(primary_tag: str) -> str:
    if primary_tag == "n":
        return "PRECISIO"
    return "EM-CASCA"


def transport_energy_for_fluka(primary_tag: str, energy_keV: float) -> tuple[float, float, str]:
    if primary_tag == "n" and energy_keV <= 0.0:
        return 1.0e-8, 0.0, "ZERO_ENERGY_NEUTRON_EPSILON_ZERO_WEIGHT"
    return energy_keV, 1.0, "PASS_THROUGH"


def userdump_settings(primary_tag: str, defaults_sdum: str) -> tuple[float, float]:
    if primary_tag == "n" and defaults_sdum == "PRECISIO":
        return 0.0, 1.0
    return 6.0, 0.0


def raw_input(
    title: str,
    histories: int,
    seed: int,
    beam_gev: float,
    beam_particle_name: str,
    defaults_sdum: str,
    primary_tag: str,
) -> str:
    fluka_seed = int(seed) % 900000
    if fluka_seed <= 0:
        fluka_seed = 1
    userdump_what3, userdump_what4 = userdump_settings(primary_tag, defaults_sdum)
    return (
        "GLOBAL         20000         0         1         0         0         0\n"
        "TITLE\n"
        f"{title}\n"
        f"DEFAULTS                                                              {defaults_sdum}\n"
        f"BEAM      {beam_gev:10.6g}                                                  {beam_particle_name}\n"
        "SOURCE\n"
        + geometry_without_run_tail()
        + "EMFCUT      -1.0E-05   1.0E-05       0.0  R0000001  @LASTREG\n"
        + "SCORE       ENERGY\n"
        + f"{'USERDUMP':<10}{100.0:10.1f}{99.0:10.1f}{userdump_what3:10.1f}{userdump_what4:10.1f}{0.0:10.1f}{0.0:10.1f}RAWDUMP\n"
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def load_angular_bins(primary_tag: str) -> list[dict[str, object]]:
    rows = [r for r in load_csv(SRC / "source_angular_bins.csv") if r["particle"] == primary_tag]
    rows.sort(key=lambda r: int(r["bin"]))
    if len(rows) != 20:
        raise ValueError(f"expected 20 {primary_tag} angular bins, got {len(rows)}")
    probs = [float(r["sampling_probability"]) for r in rows]
    total = sum(probs)
    running = 0.0
    for row, prob in zip(rows, probs):
        running += prob / total
        row["sampling_cdf"] = running
    rows[-1]["sampling_cdf"] = 1.0
    return rows


def load_energy_cdfs(primary_tag: str) -> dict[int, list[tuple[float, float]]]:
    authority = json.loads((SRC / "source_phase_space_authority.json").read_text(encoding="utf-8"))
    energy_axis_unit = str(authority.get("energy_axis_unit", ""))
    legacy_mev_label_is_source_axis_keV = energy_axis_unit.startswith("MeV in source CDF files")
    out: dict[int, list[tuple[float, float]]] = {}
    for row in load_csv(SRC / f"source_energy_cdf_{primary_tag}.csv"):
        b = int(row["bin"])
        if row.get("source_energy_axis_value"):
            energy_keV = float(row["energy_keV"])
        elif legacy_mev_label_is_source_axis_keV and row.get("energy_MeV"):
            energy_keV = float(row["energy_MeV"])
        else:
            energy_keV = float(row["energy_keV"])
        out.setdefault(b, []).append((float(row["cdf"]), energy_keV))
    for vals in out.values():
        vals.sort()
        vals[0] = (0.0, vals[0][1])
        vals[-1] = (1.0, vals[-1][1])
    return out


def source_energy_policy() -> str:
    authority = json.loads((SRC / "source_phase_space_authority.json").read_text(encoding="utf-8"))
    energy_axis_unit = str(authority.get("energy_axis_unit", ""))
    if energy_axis_unit.startswith("MeV in source CDF files"):
        return "LEGACY_CDF_ENERGY_MEV_COLUMN_USED_AS_KEV_TO_MATCH_TES_COSIMA_SOURCE"
    return "SOURCE_CDF_ENERGY_KEV"


def sample_energy_keV(rng: random.Random, cdf_rows: list[tuple[float, float]]) -> float:
    q = rng.random()
    cdfs = [c for c, _ in cdf_rows]
    idx = bisect.bisect_left(cdfs, q)
    if idx <= 0:
        return cdf_rows[0][1]
    if idx >= len(cdf_rows):
        return cdf_rows[-1][1]
    c0, e0 = cdf_rows[idx - 1]
    c1, e1 = cdf_rows[idx]
    if c1 <= c0:
        return e1
    t = (q - c0) / (c1 - c0)
    return e0 + t * (e1 - e0)


def rotate_y(x: float, y: float, z: float, angle_deg: float) -> tuple[float, float, float]:
    if abs(angle_deg) < 1.0e-15:
        return x, y, z
    a = math.radians(angle_deg)
    ca = math.cos(a)
    sa = math.sin(a)
    return ca * x + sa * z, y, -sa * x + ca * z


def sample_direction_and_position(
    rng: random.Random,
    row: dict[str, object],
    radius_cm: float,
    source_start_area_center_cm: tuple[float, float, float],
    source_rotation_y_deg: float,
) -> tuple[float, ...]:
    mu_min = float(row["mu_min"])
    mu_max = float(row["mu_max"])
    costh = mu_min + rng.random() * (mu_max - mu_min)
    sinth = math.sqrt(max(0.0, 1.0 - costh * costh))
    phi = rng.random() * 2.0 * math.pi
    # MEGAlib FarFieldAreaSource samples a spherical vector and then negates
    # the full momentum direction before placing the start disk.
    ux = -sinth * math.cos(phi)
    uy = -sinth * math.sin(phi)
    uz = -costh
    norm_xy = math.sqrt(ux * ux + uy * uy)
    if norm_xy > 1.0e-12:
        e1x = -uy / norm_xy
        e1y = ux / norm_xy
        e1z = 0.0
    else:
        e1x = 1.0
        e1y = 0.0
        e1z = 0.0
    e2x = uy * e1z - uz * e1y
    e2y = uz * e1x - ux * e1z
    e2z = ux * e1y - uy * e1x
    rho = radius_cm * math.sqrt(rng.random())
    alpha = rng.random() * 2.0 * math.pi
    ox = rho * math.cos(alpha)
    oy = rho * math.sin(alpha)
    x = -radius_cm * ux + ox * e1x + oy * e2x
    y = -radius_cm * uy + ox * e1y + oy * e2y
    z = -radius_cm * uz + ox * e1z + oy * e2z
    x += source_start_area_center_cm[0]
    y += source_start_area_center_cm[1]
    z += source_start_area_center_cm[2]
    x, y, z = rotate_y(x, y, z, source_rotation_y_deg)
    ux, uy, uz = rotate_y(ux, uy, uz, source_rotation_y_deg)
    return x, y, z, ux, uy, uz


def sample_primaries(
    histories: int,
    seed: int,
    run_id: str,
    primary_tag: str,
    source_start_area_center_cm: tuple[float, float, float],
    source_rotation_y_deg: float,
    normalization_histories: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    bins = load_angular_bins(primary_tag)
    cdfs = load_energy_cdfs(primary_tag)
    norm = json.loads((SRC / "source_normalization.json").read_text(encoding="utf-8"))
    rate_s = float(norm["particles"][primary_tag]["physical_rate_s"])
    radius_cm = float(norm["farfield_radius_cm"])
    norm_histories = normalization_histories or histories
    history_weight = rate_s / norm_histories
    rng = random.Random(seed)
    cdf_probs = [float(r["sampling_cdf"]) for r in bins]
    primaries: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    for history_id in range(1, histories + 1):
        q_bin = rng.random()
        bidx = bisect.bisect_left(cdf_probs, q_bin)
        if bidx >= len(bins):
            bidx = len(bins) - 1
        b = bins[bidx]
        energy_keV = sample_energy_keV(rng, cdfs[int(b["bin"])])
        transport_energy_keV, fluka_transport_weight, transport_policy = transport_energy_for_fluka(primary_tag, energy_keV)
        x, y, z, u, v, w = sample_direction_and_position(
            rng,
            b,
            radius_cm,
            source_start_area_center_cm,
            source_rotation_y_deg,
        )
        row = {
            "run_id": run_id,
            "seed": seed,
            "history_id": history_id,
            "stream": "prompt",
            "primary_tag": primary_tag,
            "source_bin": int(b["bin"]),
            "primary_energy_keV": energy_keV,
            "primary_energy_GeV": energy_keV / 1.0e6,
            "transport_primary_energy_keV": transport_energy_keV,
            "transport_primary_energy_GeV": transport_energy_keV / 1.0e6,
            "transport_energy_policy": transport_policy,
            "source_start_area_center_x_cm": source_start_area_center_cm[0],
            "source_start_area_center_y_cm": source_start_area_center_cm[1],
            "source_start_area_center_z_cm": source_start_area_center_cm[2],
            "primary_x_cm": x,
            "primary_y_cm": y,
            "primary_z_cm": z,
            "primary_dx": u,
            "primary_dy": v,
            "primary_dz": w,
            "history_weight": history_weight,
            "fluka_transport_weight": fluka_transport_weight,
        }
        primaries.append(row)
        audit.append(
            {
                "run_id": run_id,
                "seed": seed,
                "history_id": history_id,
                "particle": primary_tag,
                "source_bin": int(b["bin"]),
                "bin_sampling_probability": b["sampling_probability"],
                "mu_min": b["mu_min"],
                "mu_max": b["mu_max"],
                "theta_min_deg": b["theta_min_deg"],
                "theta_max_deg": b["theta_max_deg"],
                "farfield_radius_cm": radius_cm,
                "sampled_primary_energy_keV": energy_keV,
                "transport_primary_energy_keV": transport_energy_keV,
                "transport_energy_policy": transport_policy,
                "fluka_transport_weight": fluka_transport_weight,
                "source_start_area_center_x_cm": source_start_area_center_cm[0],
                "source_start_area_center_y_cm": source_start_area_center_cm[1],
                "source_start_area_center_z_cm": source_start_area_center_cm[2],
                "source_rotation_y_deg": source_rotation_y_deg,
                "status": "PASS",
            }
        )
    return primaries, audit


def write_primaries_dat(path: Path, primaries: list[dict[str, object]], primary_tag: str) -> None:
    with path.open("w", encoding="ascii") as f:
        for r in primaries:
            f.write(
                f"{PARTICLE_CODE[primary_tag]:d} {float(r.get('transport_primary_energy_GeV') or r['primary_energy_GeV']):.10e} "
                f"{float(r['primary_x_cm']):.8e} {float(r['primary_y_cm']):.8e} {float(r['primary_z_cm']):.8e} "
                f"{float(r['primary_dx']):.8e} {float(r['primary_dy']):.8e} {float(r['primary_dz']):.8e} "
                f"{float(r['fluka_transport_weight']):.8e}\n"
            )


def find_file(root: Path, name: str) -> Path:
    matches = sorted(
        [p for p in root.rglob("*") if p.is_file() and (p.name == name or p.name.endswith("_" + name))],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise FileNotFoundError(f"missing {name} below {root}")
    return matches[0]


def parse_score_energy(out_path: Path) -> dict[str, float]:
    scores: dict[str, float] = {}
    pat = re.compile(r"^\s*\d+\s+(R\d{7})\s+[-+0-9.DEdex]+\s+([-+0-9.DEdex]+)")
    for line in out_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.match(line)
        if m:
            scores[m.group(1)] = float(m.group(2).replace("D", "E").replace("d", "e"))
    return scores


def load_region_crosswalk() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    rows = load_csv(SCORING / "volume_name_crosswalk.csv")
    by_region = {r["fluka_region_name"]: r for r in rows}
    kind = {r["fluka_region_name"]: r["detector_kind"] for r in rows}
    return by_region, kind


def load_process_map() -> dict[str, str]:
    rows = load_csv(SCORING / "process_name_crosswalk.csv")
    return {r["fluka_icode"]: r["interaction_process"] for r in rows}


def parse_event_totals(path: Path) -> dict[int, dict[str, float]]:
    totals: dict[int, dict[str, float]] = {}
    for row in load_csv(path):
        hid = int(row["history_id"])
        totals[hid] = {
            "tes_total_keV": float(row["tes_total_keV"]),
            "shield_total_keV": float(row["shield_total_keV"]),
        }
    return totals


def build_raw_events(
    deposits_path: Path,
    totals_path: Path,
    primaries: list[dict[str, object]],
    run_id: str,
    seed: int,
    primary_tag: str,
) -> list[dict[str, object]]:
    by_region, _ = load_region_crosswalk()
    process_map = load_process_map()
    primary_by_history = {int(r["history_id"]): r for r in primaries}
    totals = parse_event_totals(totals_path)
    rows = []
    for dep in load_csv(deposits_path):
        history_id = int(dep["history_id"])
        primary = primary_by_history[history_id]
        region = dep["region_name"].strip()
        volume = by_region.get(region, {})
        pcode = int(dep["particle_code"])
        icode = str(int(dep["icode"]))
        etot = totals.get(history_id, {"tes_total_keV": 0.0, "shield_total_keV": 0.0})
        rows.append(
            {
                "code": "FLUKA",
                "run_id": run_id,
                "seed": seed,
                "history_id": history_id,
                "stream": "prompt",
                "primary_tag": primary_tag,
                "primary_energy_keV": primary["primary_energy_keV"],
                "primary_x_cm": primary["primary_x_cm"],
                "primary_y_cm": primary["primary_y_cm"],
                "primary_z_cm": primary["primary_z_cm"],
                "primary_dx": primary["primary_dx"],
                "primary_dy": primary["primary_dy"],
                "primary_dz": primary["primary_dz"],
                "history_weight": primary["history_weight"],
                "volume_id": region,
                "volume_name": volume.get("volume_name", region),
                "material_name": volume.get("material_name", "NOT_AVAILABLE"),
                "detector_kind": dep["detector_kind"].strip(),
                "deposit_keV": float(dep["deposit_keV"]),
                "deposit_time_s": float(dep["deposit_time_s"]),
                "track_id": "NOT_AVAILABLE",
                "parent_track_id": "NOT_AVAILABLE",
                "particle": PARTICLE_BY_CODE.get(pcode, f"FLUKA_PARTICLE_{pcode}"),
                "creator_process": "NOT_AVAILABLE",
                "interaction_process": process_map.get(icode, f"FLUKA_ICODE_{icode}"),
                "x_cm": float(dep["x_cm"]),
                "y_cm": float(dep["y_cm"]),
                "z_cm": float(dep["z_cm"]),
                "tes_total_keV": etot["tes_total_keV"],
                "shield_total_keV": etot["shield_total_keV"],
                "fluka_region_name": region,
                "fluka_particle_code": pcode,
                "fluka_icode": icode,
            }
        )
    return rows


def closure_from_outputs(
    run_dir: Path,
    raw_events: list[dict[str, object]],
    histories: int,
    score_weight_sum: float,
    region_kind: dict[str, str],
    input_stem: str,
) -> dict:
    out_file = find_file(run_dir, f"{input_stem}001.out")
    scores = parse_score_energy(out_file)
    raw_tes = sum(float(r["deposit_keV"]) for r in raw_events if r["detector_kind"] == "TES_PIXEL")
    raw_shield = sum(float(r["deposit_keV"]) for r in raw_events if r["detector_kind"] == "ACTIVE_SHIELD")
    score_tes = sum(v for k, v in scores.items() if region_kind.get(k) == "TES_PIXEL") * score_weight_sum * 1.0e6
    score_shield = sum(v for k, v in scores.items() if region_kind.get(k) == "ACTIVE_SHIELD") * score_weight_sum * 1.0e6

    def rel_delta(a: float, b: float) -> float:
        denom = max(abs(a), abs(b), 1.0e-30)
        return abs(a - b) / denom

    tes_rel = rel_delta(raw_tes, score_tes)
    shield_rel = rel_delta(raw_shield, score_shield)
    status = "PASS" if scores and tes_rel < 1.0e-6 and shield_rel < 1.0e-6 else "FAIL"
    return {
        "status": status,
        "histories": histories,
        "score_weight_sum": score_weight_sum,
        "raw_dump_tes_total_keV": raw_tes,
        "raw_dump_shield_total_keV": raw_shield,
        "score_tes_total_keV": score_tes,
        "score_shield_total_keV": score_shield,
        "tes_relative_delta": tes_rel,
        "shield_relative_delta": shield_rel,
        "score_rows_parsed": len(scores),
        "score_output": str(out_file),
        "normalization": "SCORE ENERGY output is per unit source weight and per region volume; no region volumes were supplied, so volume=1 and totals are multiplied by sum(fluka_transport_weight).",
    }


def write_parquet(path: Path, rows: list[dict[str, object]]) -> tuple[bool, str | None]:
    try:
        import pandas as pd  # type: ignore

        df = pd.DataFrame(rows, columns=RAW_EVENT_FIELDS)
        df.to_parquet(path, index=False)
        return False, None
    except Exception as exc:  # pragma: no cover - depends on optional environment packages.
        return True, str(exc)


def update_final_status() -> None:
    if OUT != DEFAULT_OUT:
        return
    final_path = WP00 / "FINAL_STATUS.md"
    if not final_path.exists():
        return
    text = final_path.read_text(encoding="utf-8")
    text = text.replace(
        "- [ ] Minimum eplus-only raw-data MVP produced: not run yet.",
        "- [x] Minimum eplus-only raw-data MVP produced.",
    )
    text = text.replace(
        "Raw FLUKA data status: NOT PRODUCED YET. WP04/WP06 raw event tables remain gated until G2-G4 pass.",
        "Raw FLUKA data status: PRODUCED_EPLUS_MVP. G2-G4M executor artifacts are present; terminal gatekeeper verdict remains null.",
    )
    text = text.replace(
        "Raw FLUKA data status: PRODUCED_EPLUS_MVP. WP04/WP06 raw event tables remain gated until G2-G4 pass.",
        "Raw FLUKA data status: PRODUCED_EPLUS_MVP. G2-G4M executor artifacts are present; terminal gatekeeper verdict remains null.",
    )
    final_path.write_text(text, encoding="utf-8")


def main() -> int:
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary-tag", choices=PROMPT_PRIMARY_TAGS, default="eplus")
    ap.add_argument("--histories", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=24062401)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for this run. Defaults to the WP06 authority MVP directory for the selected primary.",
    )
    ap.add_argument(
        "--source-rotation-y-deg",
        type=float,
        default=0.0,
        help="Rotate sampled source positions/directions about +Y before writing primaries.dat.",
    )
    ap.add_argument(
        "--source-start-area-center-cm",
        type=float,
        nargs=3,
        metavar=("X", "Y", "Z"),
        default=None,
        help="MEGAlib StartArea sphere center in global cm before source rotation. Defaults to SurroundingSphere from the source geometry setup.",
    )
    ap.add_argument(
        "--normalization-histories",
        type=int,
        default=None,
        help="Denominator for per-history physical weight. Use TES full generated count for full-stat prompt comparisons.",
    )
    ap.add_argument(
        "--defaults-sdum",
        default=None,
        help="FLUKA DEFAULTS SDUM. Defaults to PRECISIO for neutron and EM-CASCA otherwise.",
    )
    args = ap.parse_args()
    out_arg = args.out_dir if args.out_dir is not None else default_out_for(args.primary_tag)
    OUT = out_arg.expanduser().resolve()

    if args.histories < 1:
        raise SystemExit("histories must be positive")
    if args.normalization_histories is not None and args.normalization_histories < args.histories:
        raise SystemExit("normalization-histories must be >= histories")
    defaults_sdum = str(args.defaults_sdum or default_defaults_sdum(args.primary_tag)).upper()
    scoring_summary = json.loads((SCORING / "summary.json").read_text(encoding="utf-8"))
    if scoring_summary.get("claimed_status") != "RAW_SCORING_PASS":
        raise SystemExit("WP06 MVP blocked: WP04 raw scoring closure has not passed")

    run_id = f"{args.primary_tag}_prompt_seed{args.seed}_n{args.histories}"
    if OUT.exists():
        shutil.rmtree(OUT)
    raw_dir = OUT / "raw_events"
    fluka_dir = OUT / "fluka_run"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fluka_dir.mkdir(parents=True, exist_ok=True)

    primary_source_mode = "sampled_source_authority"
    primary_source_energy_policy = source_energy_policy()
    source_start_area_center_cm: tuple[float, float, float] | None = (
        tuple(float(v) for v in args.source_start_area_center_cm)
        if args.source_start_area_center_cm is not None
        else load_surrounding_sphere_center(args.primary_tag)
    )
    primaries, audit_rows = sample_primaries(
        args.histories,
        args.seed,
        run_id,
        args.primary_tag,
        source_start_area_center_cm,
        args.source_rotation_y_deg,
        args.normalization_histories,
    )
    write_csv(raw_dir / "primaries.csv", primaries, PRIMARY_FIELDS)
    write_csv(
        raw_dir / "source_sampling_audit.csv",
        audit_rows,
        [
            "run_id",
            "seed",
            "history_id",
            "particle",
            "source_bin",
            "bin_sampling_probability",
            "mu_min",
            "mu_max",
            "theta_min_deg",
            "theta_max_deg",
            "farfield_radius_cm",
            "sampled_primary_energy_keV",
            "transport_primary_energy_keV",
            "transport_energy_policy",
            "fluka_transport_weight",
            "source_start_area_center_x_cm",
            "source_start_area_center_y_cm",
            "source_start_area_center_z_cm",
            "source_rotation_y_deg",
            "sim_event_id",
            "sim_start_index",
            "status",
        ],
    )
    write_primaries_dat(fluka_dir / "primaries.dat", primaries, args.primary_tag)

    exe = SCORING / "scoring_routines/fluka_raw"
    if not exe.exists():
        raise SystemExit(f"missing FLUKA raw executable: {exe}")
    max_energy_gev = max(float(p.get("transport_primary_energy_GeV") or p["primary_energy_GeV"]) for p in primaries)
    beam_gev = max(0.001, max_energy_gev * 1.05)
    input_stem = f"{args.primary_tag}_raw_mvp"
    input_path = fluka_dir / f"{input_stem}.inp"
    input_path.write_text(
        raw_input(
            f"TES511 {args.primary_tag} prompt raw-data MVP",
            args.histories,
            args.seed,
            beam_gev,
            BEAM_PARTICLE_NAME[args.primary_tag],
            defaults_sdum,
            args.primary_tag,
        ),
        encoding="ascii",
    )

    started = now_utc()
    t0 = time.time()
    returncode = run(
        [str(RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", input_stem],
        fluka_dir,
        fluka_dir / "rfluka.log",
    )
    elapsed_s = time.time() - t0
    finished = now_utc()
    if returncode != 0:
        write_csv(
            OUT / "run_manifest.csv",
            [
                {
                    "run_id": run_id,
                    "particle": args.primary_tag,
                    "histories": args.histories,
                    "seed": args.seed,
                    "returncode": returncode,
                    "started_at_utc": started,
                    "finished_at_utc": finished,
                    "elapsed_s": elapsed_s,
                    "fluka_executable": str(exe),
                    "fluka_executable_sha256": sha256_path(exe),
                }
            ],
            [
                "run_id",
                "particle",
                "histories",
                "seed",
                "returncode",
                "started_at_utc",
                "finished_at_utc",
                "elapsed_s",
                "fluka_executable",
                "fluka_executable_sha256",
            ],
        )
        raise SystemExit(f"FLUKA {args.primary_tag} MVP failed with return code {returncode}")

    deposits_file = find_file(fluka_dir, "raw_deposits_tmp.csv")
    totals_file = find_file(fluka_dir, "event_totals_tmp.csv")
    raw_events = build_raw_events(deposits_file, totals_file, primaries, run_id, args.seed, args.primary_tag)
    write_csv(raw_dir / "raw_events.csv", raw_events, RAW_EVENT_FIELDS)
    parquet_unavailable, parquet_error = write_parquet(raw_dir / "raw_events.parquet", raw_events)

    _, region_kind = load_region_crosswalk()
    score_weight_sum = sum(float(p.get("fluka_transport_weight", 1.0)) for p in primaries)
    closure = closure_from_outputs(fluka_dir, raw_events, args.histories, score_weight_sum, region_kind, input_stem)
    closure.update(
        {
            "raw_deposits_file": str(deposits_file),
            "event_totals_file": str(totals_file),
            "raw_event_rows": len(raw_events),
            "created_at_utc": now_utc(),
        }
    )
    write_json(OUT / "scoring_closure.json", closure)

    source_summary = json.loads((SRC / "summary.json").read_text(encoding="utf-8"))
    source_authority_hash = source_summary.get("source_authority_sha256")
    geometry_hash = sha256_path(SMOKE_DECK)
    executable_hash = sha256_path(exe)
    source_status = "PASS" if all(str(r["status"]).startswith("PASS") for r in audit_rows) else "FAIL"
    totals_rows = len(load_csv(totals_file))
    status = (
        "RAW_DATA_MVP_PASS"
        if len(primaries) == args.histories
        and totals_rows == args.histories
        and source_status == "PASS"
        and closure["status"] == "PASS"
        else "BLOCKED_RAW_DATA_MVP"
    )
    verdict = {
        "status": status,
        "histories_generated": args.histories,
        "raw_event_rows": len(raw_events),
        "primaries_rows": len(primaries),
        "event_total_rows": totals_rows,
        "source_sampling_status": source_status,
        "geometry_hash": geometry_hash,
        "source_authority_hash": source_authority_hash,
        "fluka_executable_hash": executable_hash,
        "scoring_closure_status": closure["status"],
        "parquet_unavailable": parquet_unavailable,
        "parquet_error": parquet_error,
        "known_missing_optional_fields": ["track_id", "parent_track_id", "creator_process"],
        "normalization_histories": args.normalization_histories or args.histories,
        "normalization_note": f"FLUKA transport weight is 1.0. history_weight records {args.primary_tag} physical_rate_s / normalization_histories.",
        "primary_source_mode": primary_source_mode,
        "primary_source_energy_policy": primary_source_energy_policy,
        "source_start_area_center_cm": [] if source_start_area_center_cm is None else list(source_start_area_center_cm),
        "source_start_area_center_note": "MEGAlib adds the SurroundingSphere center after FarFieldAreaSource disk sampling; this runner adds it before optional global-to-local rotation.",
        "source_rotation_y_deg": args.source_rotation_y_deg,
        "primary_tag": args.primary_tag,
        "fluka_defaults_sdum": defaults_sdum,
        "raw_outputs": {
            "primaries_csv": str(raw_dir / "primaries.csv"),
            "source_sampling_audit_csv": str(raw_dir / "source_sampling_audit.csv"),
            "raw_events_csv": str(raw_dir / "raw_events.csv"),
            "raw_events_parquet": str(raw_dir / "raw_events.parquet"),
        },
    }
    write_json(OUT / "mvp_raw_data_verdict.json", verdict)

    manifest_row = {
        "run_id": run_id,
        "particle": args.primary_tag,
        "histories": args.histories,
        "seed": args.seed,
        "returncode": returncode,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "elapsed_s": elapsed_s,
        "fluka_executable": str(exe),
        "fluka_executable_sha256": executable_hash,
        "input": str(input_path),
        "input_sha256": sha256_path(input_path),
        "primaries_dat": str(fluka_dir / "primaries.dat"),
        "primaries_dat_sha256": sha256_path(fluka_dir / "primaries.dat"),
        "raw_deposits_file": str(deposits_file),
        "event_totals_file": str(totals_file),
        "mvp_status": status,
        "normalization_histories": args.normalization_histories or args.histories,
        "primary_source_mode": primary_source_mode,
        "primary_source_energy_policy": primary_source_energy_policy,
        "source_start_area_center_x_cm": "" if source_start_area_center_cm is None else source_start_area_center_cm[0],
        "source_start_area_center_y_cm": "" if source_start_area_center_cm is None else source_start_area_center_cm[1],
        "source_start_area_center_z_cm": "" if source_start_area_center_cm is None else source_start_area_center_cm[2],
        "source_rotation_y_deg": args.source_rotation_y_deg,
        "fluka_defaults_sdum": defaults_sdum,
    }
    write_csv(
        OUT / "run_manifest.csv",
        [manifest_row],
        [
            "run_id",
            "particle",
            "histories",
            "seed",
            "returncode",
            "started_at_utc",
            "finished_at_utc",
            "elapsed_s",
            "fluka_executable",
            "fluka_executable_sha256",
            "input",
            "input_sha256",
            "primaries_dat",
            "primaries_dat_sha256",
            "raw_deposits_file",
            "event_totals_file",
            "mvp_status",
            "normalization_histories",
            "primary_source_mode",
            "primary_source_energy_policy",
            "source_start_area_center_x_cm",
            "source_start_area_center_y_cm",
            "source_start_area_center_z_cm",
            "source_rotation_y_deg",
            "fluka_defaults_sdum",
        ],
    )
    summary = {
        "claimed_status": status,
        "terminal_status": None,
        "gate": "G4M",
        "run_manifest": str(OUT / "run_manifest.csv"),
        "raw_events_csv": str(raw_dir / "raw_events.csv"),
        "raw_events_parquet": str(raw_dir / "raw_events.parquet"),
        "mvp_raw_data_verdict": verdict,
        "scoring_closure": closure,
    }
    write_json(OUT / "summary.json", summary)
    md = [
        f"# WP06 {args.primary_tag} prompt raw-data MVP",
        "",
        f"- claimed_status: {status}",
        "- terminal_status: null",
        f"- histories: {args.histories}",
        f"- raw event rows: {len(raw_events)}",
        f"- primaries rows: {len(primaries)}",
        f"- source start-area center cm: {source_start_area_center_cm}",
        f"- source rotation y deg: {args.source_rotation_y_deg}",
        f"- FLUKA DEFAULTS: {defaults_sdum}",
        f"- primary source mode: {primary_source_mode}",
        f"- primary source energy policy: {primary_source_energy_policy}",
        f"- normalization histories: {args.normalization_histories or args.histories}",
        f"- scoring closure: {closure['status']}",
        f"- TES raw/SCORE delta: {closure['tes_relative_delta']:.3e}",
        f"- shield raw/SCORE delta: {closure['shield_relative_delta']:.3e}",
        f"- parquet_unavailable: {parquet_unavailable}",
        "",
        "This MVP is a raw-data plumbing and closure run only; it is not a physics comparison or paper result.",
        "",
    ]
    (OUT / "summary.md").write_text("\n".join(md), encoding="utf-8")

    if status == "RAW_DATA_MVP_PASS" and args.primary_tag == "eplus":
        update_final_status()
    return 0 if status == "RAW_DATA_MVP_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
