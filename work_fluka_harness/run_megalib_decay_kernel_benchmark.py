#!/usr/bin/env python3
"""Run a MEGAlib/Cosima radioactive-decay kernel benchmark.

This is the Geant4/MEGAlib side of the independent-source cross-code check.
It builds fresh EventList sources for a small isotope set, runs Cosima with
MEGAlib's radioactive-decay path, parses the emitted-particle `IA DECA`
records, and keeps only compact summaries plus bounded samples.  The raw
temporary Cosima run products are written under ignored `cosima_run`
directories and are deleted by default after parsing.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
COSIMA = Path("/home/ubuntu/MEGAlib_Install/megalib-main/bin/cosima")
FIX5_GEOMETRY = (
    TES_ROOT
    / "outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy"
    / "DEMO2_DR_v3p5_minpatch_centerfinger_megalib_proxy.geo.setup"
)
DEFAULT_OUT = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/geant4_megalib_vacuum_smoke"
)

TARGETS = [
    {"nuclide": "Cu-64", "Z": 29, "A": 64, "exc_keV": 0},
    {"nuclide": "Na-24", "Z": 11, "A": 24, "exc_keV": 0},
    {"nuclide": "Al-28", "Z": 13, "A": 28, "exc_keV": 0},
    {"nuclide": "I-128", "Z": 53, "A": 128, "exc_keV": 0},
]

PARTICLE_BY_CODE = {
    1: "PHOTON",
    2: "POSITRON",
    3: "ELECTRON",
    12: "NEUTRINO_OR_ANTINEUTRINO",
    13: "NEUTRINO_OR_ANTINEUTRINO",
}

GAMMA_LINE_WINDOWS = {
    "Cu-64": [(1345.0, 1346.5, "Cu-64 1346 keV")],
    "Na-24": [(1368.1, 1369.1, "Na-24 1369 keV"), (2753.5, 2754.5, "Na-24 2754 keV")],
    "Al-28": [(1778.5, 1779.5, "Al-28 1779 keV")],
    "I-128": [],
}


@dataclass(frozen=True)
class Target:
    nuclide: str
    z: int
    a: int
    exc_keV: int

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Target":
        return cls(str(row["nuclide"]), int(row["Z"]), int(row["A"]), int(row["exc_keV"]))

    @property
    def za(self) -> int:
        return self.z * 1000 + self.a

    @property
    def tag(self) -> str:
        return self.nuclide.lower().replace("-", "")


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
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def particle_name(code: int) -> str:
    if code >= 1000:
        return f"ION_ZA_{code}"
    return PARTICLE_BY_CODE.get(code, f"MEGALIB_{code}")


def open_sim(path: Path) -> Iterable[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            yield from handle
    else:
        with path.open(encoding="utf-8", errors="replace") as handle:
            yield from handle


def build_eventlist(path: Path, target: Target, histories: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as handle:
        for idx in range(histories):
            handle.write(
                f"{idx} 0 {target.za} {target.exc_keV} {idx * 1.0e-9:.12E} "
                "0 0 0 0 0 1 0 0 0 0\n"
            )


def build_source(path: Path, target: Target, eventlist: Path, out_prefix: Path, histories: int) -> None:
    run_name = f"DecayKernel{target.tag}"
    source_name = f"{run_name}_EventList"
    text = "\n".join(
        [
            "Version 1",
            f"Geometry {FIX5_GEOMETRY}",
            "PhysicsListEM LivermorePol",
            "PhysicsListRadioactiveDecay true",
            "DecayMode ActivationDelayedDecay",
            "StoreSimulationInfo all",
            "StoreIsotopes true",
            "DetectorTimeConstant 1e-9",
            "",
            f"Run {run_name}",
            f"{run_name}.FileName {out_prefix}",
            f"{run_name}.Triggers {histories}",
            f"{run_name}.Source {source_name}",
            "",
            f"{source_name}.EventList {eventlist}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def find_sim_file(out_prefix: Path) -> Path:
    candidates = sorted(out_prefix.parent.glob(out_prefix.name + "*.sim.gz"))
    if candidates:
        return candidates[-1]
    candidates = sorted(out_prefix.parent.glob(out_prefix.name + "*.sim"))
    if candidates:
        return candidates[-1]
    return out_prefix.with_suffix(".inc1.id1.sim.gz")


def run_target(
    target: Target,
    out_dir: Path,
    histories: int,
    seed: int,
    keep_run_products: bool,
) -> dict[str, Any]:
    run_dir = out_dir / "cosima_run" / target.tag
    run_dir.mkdir(parents=True, exist_ok=True)
    eventlist = run_dir / f"{target.tag}_eventlist.dat"
    source = run_dir / f"{target.tag}_decay_kernel.source"
    out_prefix = run_dir / f"{target.tag}_decay_kernel"

    build_eventlist(eventlist, target, histories)
    build_source(source, target, eventlist, out_prefix, histories)

    log_path = run_dir / "cosima.log"
    started = now_utc()
    t0 = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            [str(COSIMA), "-s", str(seed), str(source)],
            cwd=str(ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed_s = time.time() - t0
    finished = now_utc()
    sim_file = find_sim_file(out_prefix)

    record = {
        "nuclide": target.nuclide,
        "Z": target.z,
        "A": target.a,
        "exc_keV": target.exc_keV,
        "histories": histories,
        "seed": seed,
        "returncode": proc.returncode,
        "started_utc": started,
        "finished_utc": finished,
        "elapsed_s": elapsed_s,
        "run_dir": rel(run_dir),
        "source": rel(source),
        "source_sha256": sha256_path(source) if source.exists() else "",
        "eventlist": rel(eventlist),
        "eventlist_sha256": sha256_path(eventlist) if eventlist.exists() else "",
        "sim_file": rel(sim_file),
        "sim_file_generated": sim_file.exists(),
        "run_products_retained": bool(keep_run_products),
        "cosima_log": rel(log_path),
        "geometry": str(FIX5_GEOMETRY),
    }
    return record


def parse_deca_line(line: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in line.split(";")]
    if len(parts) < 23:
        return None
    head = parts[0].split()
    if len(head) < 3:
        return None
    try:
        return {
            "interaction_id": int(head[-1]),
            "parent_track_id": int(parts[1]),
            "interaction_type": int(parts[2]),
            "time_s": float(parts[3]),
            "x_cm": float(parts[4]),
            "y_cm": float(parts[5]),
            "z_cm": float(parts[6]),
            "particle_in_code": int(parts[7]),
            "particle_out_code": int(parts[15]),
            "dir_x": float(parts[16]),
            "dir_y": float(parts[17]),
            "dir_z": float(parts[18]),
            "kinetic_energy_keV": float(parts[22]),
        }
    except ValueError:
        return None


def summarize_target(target: Target, sim_path: Path, histories: int, out_dir: Path, sample_rows: int) -> dict[str, Any]:
    by_particle: Counter[int] = Counter()
    energy_sum_by_particle: defaultdict[int, float] = defaultdict(float)
    event_particle_counts: dict[int, Counter[int]] = defaultdict(Counter)
    photon_hist_counts: Counter[int] = Counter()
    line_defs = GAMMA_LINE_WINDOWS.get(target.nuclide, [])
    line_counts = [0 for _ in line_defs]
    line_event_ids = [set() for _ in line_defs]
    na24_1369_events: set[int] = set()
    na24_2754_events: set[int] = set()
    sample: list[dict[str, Any]] = []
    rows_read = 0
    event_count = 0
    id_count = 0
    current_event = 0
    geometry = ""
    te_s: float | None = None

    if sim_path.exists():
        for raw in open_sim(sim_path):
            if raw.startswith("Geometry "):
                geometry = raw.strip().split(" ", 1)[1]
            elif raw.startswith("SE"):
                event_count += 1
            elif raw.startswith("ID "):
                id_count += 1
                parts = raw.split()
                if len(parts) >= 2:
                    try:
                        current_event = int(parts[1])
                    except ValueError:
                        current_event = 0
            elif raw.startswith("TE "):
                parts = raw.split()
                if len(parts) >= 2:
                    try:
                        te_s = float(parts[1])
                    except ValueError:
                        te_s = None
            elif raw.startswith("IA DECA"):
                parsed = parse_deca_line(raw)
                if parsed is None:
                    continue
                parsed["event_id"] = current_event
                parsed["nuclide"] = target.nuclide
                rows_read += 1
                if len(sample) < sample_rows:
                    sample.append(parsed)
                event_id = int(parsed["event_id"])
                pcode = int(parsed["particle_out_code"])
                energy = float(parsed["kinetic_energy_keV"])
                by_particle[pcode] += 1
                event_particle_counts[event_id][pcode] += 1
                energy_sum_by_particle[pcode] += energy
                if pcode == 1:
                    if 0.0 <= energy < 4000.0:
                        photon_hist_counts[int(math.floor(energy))] += 1
                    for idx, (low, high, _label) in enumerate(line_defs):
                        if low <= energy <= high:
                            line_counts[idx] += 1
                            line_event_ids[idx].add(event_id)
                    if target.nuclide == "Na-24":
                        if 1368.1 <= energy <= 1369.1:
                            na24_1369_events.add(event_id)
                        if 2753.5 <= energy <= 2754.5:
                            na24_2754_events.add(event_id)

    particle_rows = []
    for pcode, count in sorted(by_particle.items(), key=lambda item: (-item[1], item[0])):
        particle_rows.append(
            {
                "nuclide": target.nuclide,
                "particle_code": pcode,
                "particle": particle_name(pcode),
                "count": count,
                "yield_per_parent": count / histories,
                "mean_kinetic_energy_keV": energy_sum_by_particle[pcode] / count if count else 0.0,
            }
        )

    event_mult_rows = []
    for pcode in sorted(by_particle):
        dist: Counter[int] = Counter()
        for event_id in range(1, histories + 1):
            dist[event_particle_counts.get(event_id, Counter()).get(pcode, 0)] += 1
        for multiplicity, events in sorted(dist.items()):
            event_mult_rows.append(
                {
                    "nuclide": target.nuclide,
                    "particle_code": pcode,
                    "particle": particle_name(pcode),
                    "multiplicity": multiplicity,
                    "events": events,
                    "fraction": events / histories,
                }
            )

    line_rows = []
    for idx, (low, high, label) in enumerate(line_defs):
        count = line_counts[idx]
        event_with_line = len(line_event_ids[idx])
        line_rows.append(
            {
                "nuclide": target.nuclide,
                "line": label,
                "window_low_keV": low,
                "window_high_keV": high,
                "photon_count": count,
                "photon_yield_per_parent": count / histories,
                "events_with_line": event_with_line,
                "event_fraction": event_with_line / histories,
            }
        )
    if target.nuclide == "Na-24":
        both = len(na24_1369_events & na24_2754_events)
        line_rows.append(
            {
                "nuclide": target.nuclide,
                "line": "Na-24 1369+2754 same-parent coincidence",
                "window_low_keV": "",
                "window_high_keV": "",
                "photon_count": "",
                "photon_yield_per_parent": "",
                "events_with_line": both,
                "event_fraction": both / histories,
            }
        )

    hist_rows = [
        {"e_low_keV": idx, "e_high_keV": idx + 1, "photon_count": count}
        for idx, count in sorted(photon_hist_counts.items())
        if count > 0
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        out_dir / f"{target.tag}_particle_yields.csv",
        particle_rows,
        ["nuclide", "particle_code", "particle", "count", "yield_per_parent", "mean_kinetic_energy_keV"],
    )
    write_csv(
        out_dir / f"{target.tag}_multiplicity_distribution.csv",
        event_mult_rows,
        ["nuclide", "particle_code", "particle", "multiplicity", "events", "fraction"],
    )
    if line_rows:
        write_csv(
            out_dir / f"{target.tag}_gamma_line_yields.csv",
            line_rows,
            [
                "nuclide",
                "line",
                "window_low_keV",
                "window_high_keV",
                "photon_count",
                "photon_yield_per_parent",
                "events_with_line",
                "event_fraction",
            ],
        )
    write_csv(out_dir / f"{target.tag}_photon_hist_1keV.csv", hist_rows, ["e_low_keV", "e_high_keV", "photon_count"])
    if sample:
        sample_fields = [
            "nuclide",
            "event_id",
            "interaction_id",
            "parent_track_id",
            "interaction_type",
            "time_s",
            "x_cm",
            "y_cm",
            "z_cm",
            "particle_in_code",
            "particle_out_code",
            "dir_x",
            "dir_y",
            "dir_z",
            "kinetic_energy_keV",
        ]
        write_csv(out_dir / f"{target.tag}_deca_sample.csv", sample, sample_fields)

    return {
        "nuclide": target.nuclide,
        "histories": histories,
        "sim_events": event_count,
        "sim_id_records": id_count,
        "sim_te_s": te_s,
        "geometry": geometry,
        "deca_rows": rows_read,
        "particle_yields_csv": rel(out_dir / f"{target.tag}_particle_yields.csv"),
        "multiplicity_distribution_csv": rel(out_dir / f"{target.tag}_multiplicity_distribution.csv"),
        "gamma_line_yields_csv": rel(out_dir / f"{target.tag}_gamma_line_yields.csv") if line_rows else "",
        "photon_hist_1keV_csv": rel(out_dir / f"{target.tag}_photon_hist_1keV.csv"),
        "sample_csv": rel(out_dir / f"{target.tag}_deca_sample.csv") if sample else "",
        "particle_yields": particle_rows,
        "gamma_line_yields": line_rows,
    }


def delete_run_products(run_record: dict[str, Any]) -> None:
    run_dir = ROOT / str(run_record["run_dir"])
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_record["run_products_retained"] = False


def write_summary_md(out_dir: Path, summary: dict[str, Any], line_rows: list[dict[str, Any]]) -> None:
    run_type = str(summary["run_type"])
    md = [
        f"# Geant4/MEGAlib Decay-Kernel {run_type.title()}",
        "",
        f"- status: `{summary['status']}`",
        f"- histories_per_isotope: `{summary['histories_per_isotope']}`",
        f"- targets: `{', '.join(summary['targets'])}`",
        f"- particle_yields_csv: `{summary['particle_yields_csv']}`",
        f"- gamma_line_yields_csv: `{summary['gamma_line_yields_csv']}`",
        f"- geometry: `{summary['geometry']}`",
        "",
        "## Key Line Checks",
        "",
    ]
    if line_rows:
        md.extend(["| nuclide | line | event fraction | photon yield per parent |", "|---|---|---:|---:|"])
        for row in line_rows:
            yld = row["photon_yield_per_parent"]
            yld_text = "" if yld == "" else f"{float(yld):.6g}"
            md.append(f"| {row['nuclide']} | {row['line']} | `{float(row['event_fraction']):.6g}` | `{yld_text}` |")
    else:
        md.append("No configured gamma line windows were populated.")
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is an independent EventList source run, not a replay of a prior `.sim.gz`.",
            "- The parsed records are `IA DECA` decay-emission records; detector selected-rate logic is not applied here.",
            "- The run uses the installed MEGAlib/Geant4 decay implementation and the TES fix5 geometry only as a valid simulation world.",
            "- Raw Cosima simulation products are excluded from the public handoff; tracked outputs are summaries and bounded samples.",
            "- Smoke statistics are sufficient for high-yield line sanity checks but not final production closure.",
            "",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--histories", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=24066401)
    ap.add_argument("--sample-rows", type=int, default=500)
    ap.add_argument("--targets", default="Cu-64,Na-24,Al-28,I-128")
    ap.add_argument("--keep-run-products", action="store_true")
    args = ap.parse_args()

    if args.histories < 1:
        raise SystemExit("histories must be positive")
    if not COSIMA.exists():
        raise SystemExit(f"missing Cosima binary: {COSIMA}")
    if not FIX5_GEOMETRY.exists():
        raise SystemExit(f"missing fix5 geometry: {FIX5_GEOMETRY}")

    wanted = {item.strip() for item in args.targets.split(",") if item.strip()}
    targets = [Target.from_dict(row) for row in TARGETS if row["nuclide"] in wanted]
    if not targets:
        raise SystemExit("no targets selected")

    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_type = "production" if args.histories >= 1_000_000 else "smoke"
    pass_status = (
        "GEANT4_MEGALIB_DECAY_KERNEL_PRODUCTION_PASS"
        if run_type == "production"
        else "GEANT4_MEGALIB_DECAY_KERNEL_SMOKE_PASS"
    )
    fail_status = (
        "GEANT4_MEGALIB_DECAY_KERNEL_PRODUCTION_FAILED"
        if run_type == "production"
        else "GEANT4_MEGALIB_DECAY_KERNEL_SMOKE_FAILED"
    )

    run_records = []
    summaries = []
    status = pass_status
    for offset, target in enumerate(targets):
        record = run_target(target, out_dir, args.histories, args.seed + offset * 101, args.keep_run_products)
        run_records.append(record)
        sim_path = Path(record["sim_file"])
        if not sim_path.is_absolute():
            sim_path = ROOT / sim_path
        if record["returncode"] != 0 or not sim_path.exists():
            status = fail_status
            continue
        summaries.append(summarize_target(target, sim_path, args.histories, out_dir, args.sample_rows))
        if not args.keep_run_products:
            delete_run_products(record)

    all_particle_rows: list[dict[str, Any]] = []
    all_line_rows: list[dict[str, Any]] = []
    for target_summary in summaries:
        all_particle_rows.extend(target_summary["particle_yields"])
        all_line_rows.extend(target_summary["gamma_line_yields"])

    if all_particle_rows:
        write_csv(
            out_dir / "particle_yields.csv",
            all_particle_rows,
            ["nuclide", "particle_code", "particle", "count", "yield_per_parent", "mean_kinetic_energy_keV"],
        )
    if all_line_rows:
        write_csv(
            out_dir / "gamma_line_yields.csv",
            all_line_rows,
            [
                "nuclide",
                "line",
                "window_low_keV",
                "window_high_keV",
                "photon_count",
                "photon_yield_per_parent",
                "events_with_line",
                "event_fraction",
            ],
        )
    write_csv(
        out_dir / "run_manifest.csv",
        run_records,
        [
            "nuclide",
            "Z",
            "A",
            "exc_keV",
            "histories",
            "seed",
            "returncode",
            "started_utc",
            "finished_utc",
            "elapsed_s",
            "run_dir",
            "source",
            "source_sha256",
            "eventlist",
            "eventlist_sha256",
            "sim_file",
            "sim_file_generated",
            "run_products_retained",
            "cosima_log",
            "geometry",
        ],
    )

    summary = {
        "status": status,
        "created_utc": now_utc(),
        "mode": f"Geant4/MEGAlib decay-kernel `IA DECA` {run_type}",
        "run_type": run_type,
        "histories_per_isotope": args.histories,
        "targets": [target.nuclide for target in targets],
        "cosima": str(COSIMA),
        "cosima_sha256": sha256_path(COSIMA),
        "geometry": str(FIX5_GEOMETRY),
        "geometry_sha256": sha256_path(FIX5_GEOMETRY),
        "run_manifest": rel(out_dir / "run_manifest.csv"),
        "particle_yields_csv": rel(out_dir / "particle_yields.csv") if all_particle_rows else "",
        "gamma_line_yields_csv": rel(out_dir / "gamma_line_yields.csv") if all_line_rows else "",
        "target_summaries": summaries,
        "limitations": [
            "This is an independent EventList source run, not replay of any prior sim.gz.",
            "It parses decay-emission `IA DECA` records, not detector-selected event rates.",
            "The TES fix5 geometry is used as a valid MEGAlib world; this gate is not a full transport-response comparison.",
            "Raw Cosima products are generated in ignored cosima_run directories and deleted by default after parsing.",
        ],
    }
    write_json(out_dir / "summary.json", summary)
    write_summary_md(out_dir, summary, all_line_rows)
    print(out_dir / "summary.md")
    print(status)
    return 0 if status == pass_status else 1


if __name__ == "__main__":
    raise SystemExit(main())
