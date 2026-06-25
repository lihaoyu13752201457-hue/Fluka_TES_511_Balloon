#!/usr/bin/env python3
"""Run MEGAlib raw hit summaries from the Phase-3 common Cu-64 parent list."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
COSIMA = Path("/home/ubuntu/MEGAlib_Install/megalib-main/bin/cosima")
GEOM_DIR = (
    TES_ROOT
    / "outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy"
)
FIX5_GEOMETRY = GEOM_DIR / "DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo.setup"
FIX5_DETECTORS = GEOM_DIR / "DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.det"
REGION_MAP = TES_ROOT / "engineering/fluka_crosscode_validation_20260624/02_geometry_translation/region_map.csv"
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_PARENT_LIST = PHASE3_DIR / "full_untracked/cu64_parent_resampling_1e6.csv"
DEFAULT_PARENT_SAMPLE = PHASE3_DIR / "cu64_parent_resampling_sample.csv"
DEFAULT_OUT = PHASE3_DIR / "megalib_cu64_common_raw_smoke"

BANDS = [
    ("all_tes_gt0", "all TES > 0", 0.0, float("inf")),
    ("e480_550", "480-550 keV", 480.0, 550.0),
    ("w2_510p58_511p42", "W2 510.58-511.42 keV", 510.58, 511.42),
    ("e1500_3000", "1500-3000 keV", 1500.0, 3000.0),
    ("e3000_10000", "3000-10000 keV", 3000.0, 10000.0),
]

MEGALIB_DETECTOR_TYPE_NAMES = {
    0: "NoDetectorType",
    1: "Strip2D",
    2: "Calorimeter",
    3: "Strip3D",
    4: "Scintillator",
    5: "DriftChamber",
    6: "Strip3DDirectional",
    7: "AngerCamera",
    8: "Voxel3D",
    9: "GuardRing",
}
CC_HIT_RE = re.compile(r"^CC HIT\s+(?P<volume>\S+)\s+(?P<kv>.*)$")
KV_RE = re.compile(r"(\w+)=([^\s]+)")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def open_sim(path: Path) -> Iterable[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            yield from handle
    else:
        with path.open(encoding="utf-8", errors="replace") as handle:
            yield from handle


def find_sim_file(out_prefix: Path) -> Path:
    candidates = sorted(out_prefix.parent.glob(out_prefix.name + "*.sim.gz"))
    if candidates:
        return candidates[-1]
    candidates = sorted(out_prefix.parent.glob(out_prefix.name + "*.sim"))
    if candidates:
        return candidates[-1]
    return out_prefix.with_suffix(".inc1.id1.sim.gz")


def source_rows_from_parent_list(path: Path, max_events: int | None, start_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv(path):
        parent_history_id = int(row["resampled_history_id"])
        if parent_history_id < start_index:
            continue
        rows.append(
            {
                **row,
                "history_id": len(rows) + 1,
                "parent_resampled_history_id": parent_history_id,
                "event_id": row["common_event_id"],
                "nuclide": "Cu-64",
                "source_name": f"phase3_cu64_common_parent_{parent_history_id:09d}",
                "isotope_Z": 29,
                "isotope_A": 64,
                "za": 29064,
                "exc_keV": 0,
                "time_s": 0.0,
                "history_weight": 1.0,
                "event_weight_Bq": row.get("original_activity_weight_Bq", ""),
            }
        )
        if max_events is not None and len(rows) >= max_events:
            break
    if not rows:
        raise ValueError("no Phase-3 Cu-64 parent rows selected")
    return rows


def source_csv_fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "history_id",
        "parent_resampled_history_id",
        "selected_position_row_index",
        "common_event_id",
        "source_event_id",
        "source_name",
        "production_tag",
        "source_volume",
        "resolved_static_material",
        "nuclide",
        "isotope_Z",
        "isotope_A",
        "za",
        "exc_keV",
        "x_cm",
        "y_cm",
        "z_cm",
        "time_s",
        "history_weight",
        "event_weight_Bq",
        "sampling_probability",
        "selection_u64",
    ]
    rest = sorted(set().union(*(row.keys() for row in rows)) - set(preferred))
    return preferred + rest


def write_eventlist(path: Path, sources: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as handle:
        for row in sources:
            handle.write(
                f"{int(row['history_id'])} 0 {int(row['za'])} {int(row['exc_keV'])} "
                f"{float(row['time_s']):.12E} "
                f"{float(row['x_cm']):.12g} {float(row['y_cm']):.12g} {float(row['z_cm']):.12g} "
                "0 0 1 0 0 0 0\n"
            )


def write_source(path: Path, eventlist: Path, out_prefix: Path, histories: int) -> None:
    run_name = "Phase3Cu64CommonMEGAlibRaw"
    source_name = "Phase3Cu64CommonEventList"
    text = "\n".join(
        [
            "Version 1",
            f"Geometry {FIX5_GEOMETRY}",
            "PhysicsListEM LivermorePol",
            "PhysicsListRadioactiveDecay true",
            "DecayMode ActivationDelayedDecay",
            "StoreSimulationInfo all",
            "StoreIsotopes true",
            "PreTriggerMode Everything",
            "DiscretizeHits true",
            "DetectorTimeConstant 1e-9",
            "",
            f"Run {run_name}",
            f"{run_name}.FileName {out_prefix}",
            f"{run_name}.Events {histories}",
            f"{run_name}.Source {source_name}",
            "",
            f"{source_name}.EventList {eventlist}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def region_kind_by_volume() -> dict[str, str]:
    out: dict[str, str] = {}
    for row in read_csv(REGION_MAP):
        kind = row.get("detector_kind", "")
        for key in ("source_volume_name", "logical_volume_name"):
            name = row.get(key, "")
            if name:
                out[name] = kind
    return out


def detector_instance_kind(detector_name: str, detector_volume: str, sensitive_volume: str, region_kind: dict[str, str]) -> str:
    if detector_name in {"D1", "D2", "D3", "D4", "D5", "D6"}:
        return "TES_PIXEL"
    for name in (detector_volume, sensitive_volume):
        if region_kind.get(name) == "TES_PIXEL" or name.startswith("TES_") or name.startswith("TES_Pixel"):
            return "TES_PIXEL"
        if region_kind.get(name) == "ACTIVE_SHIELD":
            return "ACTIVE_SHIELD"
    return "OTHER"


def detector_instance_map() -> dict[int, dict[str, Any]]:
    region_kind = region_kind_by_volume()
    out: dict[int, dict[str, Any]] = {}
    current_id = 0
    current_name = ""
    current_type = ""
    for raw in FIX5_DETECTORS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        parts = line.split()
        if len(parts) == 2 and parts[0] in {"MDCalorimeter", "Scintillator", "MDStrip3D"}:
            current_id += 1
            current_type = parts[0]
            current_name = parts[1]
            out[current_id] = {
                "detector_id": current_id,
                "detector_type": current_type,
                "detector_name": current_name,
                "detector_volume": "",
                "sensitive_volume": "",
                "detector_kind": "OTHER",
            }
            continue
        if "." not in line or current_id == 0:
            continue
        key, value = line.split(None, 1)
        prop = key.split(".", 1)[1]
        if prop == "DetectorVolume":
            out[current_id]["detector_volume"] = value.strip()
        elif prop == "SensitiveVolume":
            out[current_id]["sensitive_volume"] = value.strip()
        out[current_id]["detector_kind"] = detector_instance_kind(
            str(out[current_id]["detector_name"]),
            str(out[current_id]["detector_volume"]),
            str(out[current_id]["sensitive_volume"]),
            region_kind,
        )
    return out


def detector_type_name(detector_type: int) -> str:
    return MEGALIB_DETECTOR_TYPE_NAMES.get(detector_type, f"UnknownDetectorType{detector_type}")


def cc_volume_kind(volume: str, region_kind: dict[str, str]) -> str:
    mapped = region_kind.get(volume, "")
    if mapped == "TES_PIXEL":
        return "TES_PIXEL"
    if volume.startswith("TP_L") or volume.startswith("TES_Pixel"):
        return "TES_PIXEL"
    if mapped == "ACTIVE_SHIELD":
        return "ACTIVE_SHIELD"
    return "OTHER"


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_htsim(line: str, history_id: int) -> dict[str, Any] | None:
    fields = [field.strip() for field in line[len("HTsim") :].split(";")]
    if len(fields) < 5:
        return None
    try:
        detector_type = int(fields[0])
        return {
            "history_id": history_id,
            "megalib_detector_type": detector_type,
            "megalib_detector_type_name": detector_type_name(detector_type),
            "x_cm": float(fields[1]),
            "y_cm": float(fields[2]),
            "z_cm": float(fields[3]),
            "deposit_keV": float(fields[4]),
            "time_s": float(fields[5]) if len(fields) > 5 else 0.0,
            "origin_ids": ";".join(fields[6:]) if len(fields) > 6 else "",
        }
    except ValueError:
        return None


def parse_cc_hit(line: str, history_id: int, region_kind: dict[str, str]) -> dict[str, Any] | None:
    match = CC_HIT_RE.match(line)
    if match is None:
        return None
    volume = match.group("volume")
    kv = {key: value for key, value in KV_RE.findall(match.group("kv"))}
    return {
        "history_id": history_id,
        "volume": volume,
        "region_kind": cc_volume_kind(volume, region_kind),
        "x_cm": parse_float(kv.get("x", "")),
        "y_cm": parse_float(kv.get("y", "")),
        "z_cm": parse_float(kv.get("z", "")),
        "deposit_keV": parse_float(kv.get("edep_keV", "")),
        "time_s": parse_float(kv.get("t", "")),
        "secondary": kv.get("sec", ""),
        "track_id": parse_int(kv.get("tid", "")),
        "parent_track_id": parse_int(kv.get("pid", "")),
        "step_process": kv.get("sproc", ""),
        "primary": kv.get("prim", ""),
        "parent": kv.get("par", ""),
        "creator_process": kv.get("cproc", ""),
        "primary_id": parse_int(kv.get("primid", "")),
    }


def parse_megalib_hits(
    sim_path: Path,
    region_kind: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, dict[str, float]], int]:
    htsim_hits: list[dict[str, Any]] = []
    cc_hits: list[dict[str, Any]] = []
    totals: dict[int, dict[str, float]] = defaultdict(
        lambda: {
            "tes_total_keV": 0.0,
            "active_shield_total_keV": 0.0,
            "other_total_keV": 0.0,
            "all_total_keV": 0.0,
            "cc_hit_rows": 0.0,
        }
    )
    history_id = 0
    event_count = 0
    if not sim_path.exists():
        return htsim_hits, cc_hits, {}, 0
    for raw in open_sim(sim_path):
        line = raw.strip()
        if line.startswith("ID "):
            event_count += 1
            parts = line.split()
            if len(parts) >= 2:
                try:
                    history_id = int(parts[1])
                except ValueError:
                    history_id = event_count
        elif line.startswith("CC HIT"):
            hit = parse_cc_hit(line, history_id, region_kind)
            if hit is None:
                continue
            cc_hits.append(hit)
            deposit = float(hit["deposit_keV"])
            totals[history_id]["all_total_keV"] += deposit
            totals[history_id]["cc_hit_rows"] += 1.0
            kind = str(hit["region_kind"])
            if kind == "TES_PIXEL":
                totals[history_id]["tes_total_keV"] += deposit
            elif kind == "ACTIVE_SHIELD":
                totals[history_id]["active_shield_total_keV"] += deposit
            else:
                totals[history_id]["other_total_keV"] += deposit
        elif line.startswith("HTsim"):
            hit = parse_htsim(line, history_id)
            if hit is None:
                continue
            htsim_hits.append(hit)
    return htsim_hits, cc_hits, dict(totals), event_count


def event_total_rows(sources: list[dict[str, Any]], totals: dict[int, dict[str, float]]) -> list[dict[str, Any]]:
    out = []
    for row in sources:
        history_id = int(row["history_id"])
        vals = totals.get(
            history_id,
            {
                "tes_total_keV": 0.0,
                "active_shield_total_keV": 0.0,
                "other_total_keV": 0.0,
                "all_total_keV": 0.0,
                "cc_hit_rows": 0.0,
            },
        )
        out.append(
            {
                "history_id": history_id,
                "tes_total_keV": vals["tes_total_keV"],
                "active_shield_total_keV": vals["active_shield_total_keV"],
                "other_total_keV": vals["other_total_keV"],
                "all_total_keV": vals["all_total_keV"],
                "cc_hit_rows": int(vals["cc_hit_rows"]),
            }
        )
    return out


def band_summary(sources: list[dict[str, Any]], totals: dict[int, dict[str, float]]) -> list[dict[str, Any]]:
    src_by_history = {int(row["history_id"]): row for row in sources}
    out = []
    for band, label, lo, hi in BANDS:
        matched = []
        material_counts: Counter[str] = Counter()
        volume_counts: Counter[str] = Counter()
        for row in sources:
            history_id = int(row["history_id"])
            tes = totals.get(history_id, {"tes_total_keV": 0.0})["tes_total_keV"]
            if (lo == 0.0 and tes > 0.0) or (lo != 0.0 and lo <= tes < hi):
                matched.append(history_id)
                src = src_by_history[history_id]
                material_counts[str(src["resolved_static_material"])] += 1
                volume_counts[str(src["source_volume"])] += 1
        out.append(
            {
                "band": band,
                "band_label": label,
                "histories": len(sources),
                "events": len(matched),
                "efficiency_per_parent": len(matched) / len(sources) if sources else 0.0,
                "top_material_counts": json.dumps(dict(material_counts.most_common(5)), sort_keys=True),
                "top_source_volume_counts": json.dumps(dict(volume_counts.most_common(5)), sort_keys=True),
            }
        )
    return out


def sample_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(0, limit)]


def htsim_detector_type_summary(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    histories_by_type: dict[int, set[int]] = defaultdict(set)
    for hit in hits:
        detector_type = int(hit["megalib_detector_type"])
        if detector_type not in grouped:
            grouped[detector_type] = {
                "megalib_detector_type": detector_type,
                "megalib_detector_type_name": hit["megalib_detector_type_name"],
                "hit_rows": 0,
                "histories_with_hit": 0,
                "deposit_keV_sum": 0.0,
            }
        grouped[detector_type]["hit_rows"] += 1
        grouped[detector_type]["deposit_keV_sum"] += float(hit["deposit_keV"])
        histories_by_type[detector_type].add(int(hit["history_id"]))
    out = []
    for detector_type, row in grouped.items():
        row["histories_with_hit"] = len(histories_by_type[detector_type])
        out.append(row)
    return sorted(out, key=lambda row: (-float(row["deposit_keV_sum"]), int(row["megalib_detector_type"])))


def cc_volume_summary(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    histories_by_volume: dict[str, set[int]] = defaultdict(set)
    for hit in hits:
        volume = str(hit["volume"])
        if volume not in grouped:
            grouped[volume] = {
                "volume": volume,
                "region_kind": hit["region_kind"],
                "hit_rows": 0,
                "histories_with_hit": 0,
                "deposit_keV_sum": 0.0,
            }
        grouped[volume]["hit_rows"] += 1
        grouped[volume]["deposit_keV_sum"] += float(hit["deposit_keV"])
        histories_by_volume[volume].add(int(hit["history_id"]))
    out = []
    for volume, row in grouped.items():
        row["histories_with_hit"] = len(histories_by_volume[volume])
        out.append(row)
    return sorted(out, key=lambda row: (-float(row["deposit_keV_sum"]), str(row["volume"])))


def cc_particle_summary(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    histories_by_group: dict[tuple[str, str, str, str, str], set[int]] = defaultdict(set)
    for hit in hits:
        key = (
            str(hit["region_kind"]),
            str(hit["secondary"]),
            str(hit["parent"]),
            str(hit["creator_process"]),
            str(hit["step_process"]),
        )
        if key not in grouped:
            grouped[key] = {
                "region_kind": key[0],
                "secondary": key[1],
                "parent": key[2],
                "creator_process": key[3],
                "step_process": key[4],
                "hit_rows": 0,
                "histories_with_hit": 0,
                "deposit_keV_sum": 0.0,
            }
        grouped[key]["hit_rows"] += 1
        grouped[key]["deposit_keV_sum"] += float(hit["deposit_keV"])
        histories_by_group[key].add(int(hit["history_id"]))
    out = []
    for key, row in grouped.items():
        row["histories_with_hit"] = len(histories_by_group[key])
        out.append(row)
    return sorted(out, key=lambda row: (str(row["region_kind"]), -float(row["deposit_keV_sum"]), str(row["secondary"])))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-list", type=Path, default=DEFAULT_PARENT_LIST)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=24066900)
    ap.add_argument("--max-events", type=int, default=1000)
    ap.add_argument("--start-index", type=int, default=1)
    ap.add_argument("--sample-rows", type=int, default=50)
    ap.add_argument("--keep-run-products", action="store_true")
    args = ap.parse_args()

    parent_list = args.parent_list.expanduser().resolve()
    if not parent_list.exists() and parent_list == DEFAULT_PARENT_LIST.resolve():
        parent_list = DEFAULT_PARENT_SAMPLE.resolve()
    if not parent_list.exists():
        raise SystemExit(f"parent list does not exist: {parent_list}")
    if args.max_events is not None and args.max_events < 1:
        raise SystemExit("max-events must be positive")
    if args.start_index < 1:
        raise SystemExit("start-index must be >= 1")

    out_dir = args.out_dir.expanduser().resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    input_dir = out_dir / "megalib_inputs"
    run_dir = out_dir / "cosima_run"
    input_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    sources = source_rows_from_parent_list(parent_list, args.max_events, args.start_index)
    write_csv(input_dir / "phase3_cu64_common_sources.csv", sources, source_csv_fields(sources))

    eventlist = input_dir / "phase3_cu64_common_eventlist.dat"
    source = input_dir / "phase3_cu64_common_megalib_raw.source"
    out_prefix = run_dir / "phase3_cu64_common_megalib_raw"
    write_eventlist(eventlist, sources)
    write_source(source, eventlist, out_prefix, len(sources))

    log_path = run_dir / "cosima.log"
    started = now_utc()
    t0 = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            [str(COSIMA), "-s", str(args.seed), str(source)],
            cwd=str(ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed_s = time.time() - t0
    finished = now_utc()

    sim_file = find_sim_file(out_prefix)
    sim_file_generated = sim_file.exists()
    region_kind = region_kind_by_volume()
    detector_instances = detector_instance_map()
    htsim_hits, cc_hits, totals, event_count = parse_megalib_hits(sim_file, region_kind)
    bands = band_summary(sources, totals)
    htsim_type_summary = htsim_detector_type_summary(htsim_hits)
    volume_summary = cc_volume_summary(cc_hits)
    tes_hits = [hit for hit in cc_hits if hit["region_kind"] == "TES_PIXEL"]
    particle_summary = cc_particle_summary(cc_hits)
    tes_particle_summary = cc_particle_summary(tes_hits)

    write_csv(
        out_dir / "cc_band_summary.csv",
        bands,
        ["band", "band_label", "histories", "events", "efficiency_per_parent", "top_material_counts", "top_source_volume_counts"],
    )
    write_csv(
        out_dir / "cc_volume_summary.csv",
        volume_summary,
        ["volume", "region_kind", "hit_rows", "histories_with_hit", "deposit_keV_sum"],
    )
    write_csv(
        out_dir / "cc_particle_summary.csv",
        particle_summary,
        ["region_kind", "secondary", "parent", "creator_process", "step_process", "hit_rows", "histories_with_hit", "deposit_keV_sum"],
    )
    write_csv(
        out_dir / "cc_tes_hit_sample.csv",
        sample_rows(tes_hits, args.sample_rows),
        [
            "history_id",
            "volume",
            "region_kind",
            "x_cm",
            "y_cm",
            "z_cm",
            "deposit_keV",
            "time_s",
            "secondary",
            "track_id",
            "parent_track_id",
            "step_process",
            "primary",
            "parent",
            "creator_process",
            "primary_id",
        ],
    )
    write_csv(
        out_dir / "cc_tes_particle_summary.csv",
        tes_particle_summary,
        ["region_kind", "secondary", "parent", "creator_process", "step_process", "hit_rows", "histories_with_hit", "deposit_keV_sum"],
    )
    write_csv(
        out_dir / "htsim_detector_type_summary.csv",
        htsim_type_summary,
        ["megalib_detector_type", "megalib_detector_type_name", "hit_rows", "histories_with_hit", "deposit_keV_sum"],
    )
    detector_rows = [
        {
            "detector_id": key,
            "detector_type": value["detector_type"],
            "detector_name": value["detector_name"],
            "detector_volume": value["detector_volume"],
            "sensitive_volume": value["sensitive_volume"],
            "detector_kind": value["detector_kind"],
        }
        for key, value in sorted(detector_instances.items())
    ]
    write_csv(
        out_dir / "detector_instance_summary.csv",
        detector_rows,
        ["detector_id", "detector_type", "detector_name", "detector_volume", "sensitive_volume", "detector_kind"],
    )

    manifest = {
        "histories": len(sources),
        "seed": args.seed,
        "returncode": proc.returncode,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "elapsed_s": elapsed_s,
        "source_mode": "phase3_cu64_common_parent_resampling",
        "stop_condition": "Events",
        "pre_trigger_mode": "Everything",
        "parent_list": str(parent_list),
        "parent_list_sha256": sha256_path(parent_list),
        "geometry": str(FIX5_GEOMETRY),
        "geometry_sha256": sha256_path(FIX5_GEOMETRY),
        "detectors": str(FIX5_DETECTORS),
        "detectors_sha256": sha256_path(FIX5_DETECTORS),
        "eventlist": str(eventlist),
        "eventlist_sha256": sha256_path(eventlist),
        "source": str(source),
        "source_sha256": sha256_path(source),
        "sim_file": str(sim_file),
        "sim_file_generated": sim_file_generated,
        "sim_event_count": event_count,
        "raw_schema": "CC HIT volume energy deposits",
        "raw_hit_rows": len(cc_hits),
        "cc_hit_rows": len(cc_hits),
        "cc_tes_hit_rows": len(tes_hits),
        "htsim_hit_rows": len(htsim_hits),
        "htsim_first_field": "MEGAlib detector type, not .det detector instance id",
        "run_products_retained": bool(args.keep_run_products),
        "cosima_log": str(log_path),
        "no_sim_gz_replay": True,
    }
    write_csv(out_dir / "run_manifest.csv", [manifest], list(manifest.keys()))

    if not args.keep_run_products and proc.returncode == 0 and run_dir.exists():
        shutil.rmtree(run_dir)

    status = (
        "PHASE3_CU64_COMMON_MEGALIB_RAW_PASS"
        if proc.returncode == 0 and sim_file_generated and event_count == len(sources)
        else "BLOCKED_PHASE3_CU64_COMMON_MEGALIB_RAW"
    )
    summary = {
        "status": status,
        "source_mode": "phase3_cu64_common_parent_resampling",
        "stop_condition": "Events",
        "pre_trigger_mode": "Everything",
        "no_sim_gz_replay": True,
        "transport_code": "MEGAlib",
        "histories": len(sources),
        "seed": args.seed,
        "returncode": proc.returncode,
        "parent_list": rel(parent_list),
        "parent_list_sha256": sha256_path(parent_list),
        "geometry": str(FIX5_GEOMETRY),
        "geometry_sha256": sha256_path(FIX5_GEOMETRY),
        "sim_event_count": event_count,
        "raw_schema": "CC HIT volume energy deposits",
        "raw_hit_rows": len(cc_hits),
        "cc_hit_rows": len(cc_hits),
        "cc_tes_hit_rows": len(tes_hits),
        "htsim_hit_rows": len(htsim_hits),
        "htsim_first_field": "MEGAlib detector type, not .det detector instance id",
        "run_products_retained": bool(args.keep_run_products),
        "run_manifest": rel(out_dir / "run_manifest.csv"),
        "cc_band_summary_csv": rel(out_dir / "cc_band_summary.csv"),
        "cc_volume_summary_csv": rel(out_dir / "cc_volume_summary.csv"),
        "cc_particle_summary_csv": rel(out_dir / "cc_particle_summary.csv"),
        "cc_tes_hit_sample_csv": rel(out_dir / "cc_tes_hit_sample.csv"),
        "cc_tes_particle_summary_csv": rel(out_dir / "cc_tes_particle_summary.csv"),
        "htsim_detector_type_summary_csv": rel(out_dir / "htsim_detector_type_summary.csv"),
        "detector_instance_summary_csv": rel(out_dir / "detector_instance_summary.csv"),
        "htsim_detector_type_summary": htsim_type_summary,
        "cc_volume_summary": volume_summary[:20],
        "cc_tes_particle_summary": tes_particle_summary,
        "cc_band_summary": bands,
        "boundary": "MEGAlib-only Phase-3 common Cu-64 raw-hit smoke; CC HIT volume deposits now provide the common raw-deposit schema, while native HTsim is retained only as a MEGAlib detector-type/readout summary. FLUKA production comparison, common event building, and production-statistics closure remain open.",
    }
    write_json(out_dir / "summary.json", summary)

    band_lines = [
        "## CC HIT Volume-Truth Band Counts",
        "",
        "| band | events / histories | efficiency_per_parent | top_material_counts |",
        "|---|---:|---:|---|",
    ]
    for row in bands:
        band_lines.append(
            f"| `{row['band_label']}` | `{row['events']} / {row['histories']}` | "
            f"`{row['efficiency_per_parent']:.6g}` | `{row['top_material_counts']}` |"
        )
    volume_lines = [
        "## CC HIT Volume Summary",
        "",
        "| volume | region_kind | histories_with_hit | hit_rows | deposit_keV_sum |",
        "|---|---|---:|---:|---:|",
    ]
    for row in volume_summary[:10]:
        volume_lines.append(
            f"| `{row['volume']}` | `{row['region_kind']}` | "
            f"`{row['histories_with_hit']}` | `{row['hit_rows']}` | "
            f"`{float(row['deposit_keV_sum']):.6g}` |"
        )
    htsim_lines = [
        "## Native HTsim Detector-Type Summary",
        "",
        "| detector_type | type_name | histories_with_hit | hit_rows | deposit_keV_sum |",
        "|---:|---|---:|---:|---:|",
    ]
    for row in htsim_type_summary[:10]:
        htsim_lines.append(
            f"| `{row['megalib_detector_type']}` | `{row['megalib_detector_type_name']}` | "
            f"`{row['histories_with_hit']}` | `{row['hit_rows']}` | "
            f"`{float(row['deposit_keV_sum']):.6g}` |"
        )
    tes_particle_lines = [
        "## CC HIT TES Particle/Ancestry Summary",
        "",
        "| secondary | parent | creator_process | step_process | histories_with_hit | hit_rows | deposit_keV_sum |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for row in tes_particle_summary:
        tes_particle_lines.append(
            f"| `{row['secondary']}` | `{row['parent']}` | `{row['creator_process']}` | `{row['step_process']}` | "
            f"`{row['histories_with_hit']}` | `{row['hit_rows']}` | `{float(row['deposit_keV_sum']):.6g}` |"
        )
    (out_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Phase-3 Cu-64 Common MEGAlib Raw-Hit Run",
                "",
                f"- status: `{status}`",
                "- source_mode: `phase3_cu64_common_parent_resampling`",
                "- stop_condition: `Events`",
                "- pre_trigger_mode: `Everything`",
                "- no `.sim.gz` replay: `True`",
                f"- histories: `{len(sources)}`",
                f"- sim_event_count: `{event_count}`",
                "- raw_schema: `CC HIT volume energy deposits`",
                f"- cc_hit_rows: `{len(cc_hits)}`",
                f"- cc_tes_hit_rows: `{len(tes_hits)}`",
                f"- htsim_hit_rows: `{len(htsim_hits)}`",
                "- htsim_first_field: `MEGAlib detector type, not .det detector instance id`",
                f"- run_products_retained: `{bool(args.keep_run_products)}`",
                f"- elapsed_s: `{elapsed_s:.3f}`",
                f"- cc_band_summary_csv: `{rel(out_dir / 'cc_band_summary.csv')}`",
                f"- cc_tes_hit_sample_csv: `{rel(out_dir / 'cc_tes_hit_sample.csv')}`",
                f"- cc_tes_particle_summary_csv: `{rel(out_dir / 'cc_tes_particle_summary.csv')}`",
                "",
                *band_lines,
                "",
                *volume_lines,
                "",
                *tes_particle_lines,
                "",
                *htsim_lines,
                "",
                "## Boundary",
                "",
                "- This is the MEGAlib side only.",
                "- It validates full-geometry raw-hit plumbing for the Phase-3 common Cu-64 parent stream without `.sim.gz` replay.",
                "- `CC HIT` comments provide the common volume-deposit schema for TES/W2 band counts.",
                "- Native `HTsim` is retained only as a MEGAlib detector-type/readout summary; its first field is not a `.det` detector-instance id.",
                "- Cosima `.sim.gz` run products are deleted by default after parsing.",
                "- FLUKA production comparison, common event building, and production-statistics closure remain open.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(out_dir / "summary.md")
    print(status)
    return 0 if status == "PHASE3_CU64_COMMON_MEGALIB_RAW_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
