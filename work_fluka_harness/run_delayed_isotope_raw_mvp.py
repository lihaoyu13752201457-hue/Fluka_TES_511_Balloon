#!/usr/bin/env python3
"""Run delayed isotope-source FLUKA raw transport from the TES v2 authority.

This runner is the delayed analogue of ``run_eplus_raw_mvp.py``.  It does not
read or replay a MEGAlib ``.sim.gz``.  Its source authority is the deterministic
v2 EventList plus event-weight ledger built under TES_511_Balloon.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_raw_scoring_smoke as scoring
from run_eplus_raw_mvp import (
    PARTICLE_BY_CODE,
    RAW_EVENT_FIELDS,
    build_raw_events,
    closure_from_outputs,
    env,
    find_file,
    load_process_map,
    load_region_crosswalk,
    parse_event_totals,
    run,
    sha256_path,
    write_csv,
    write_json,
)


TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
DELAYED_AUTH = TES_ROOT / "engineering/delayed_source_authority_v2_20260624/04_custom_source_v2"
DEFAULT_EVENTLIST = DELAYED_AUTH / "source_v2_eventlist.dat"
DEFAULT_WEIGHTS = DELAYED_AUTH / "source_v2_event_weights.csv"
DEFAULT_OUT = Path("work_fluka_harness/delayed_isotope_source_mvp")
FLUKA_HOME = scoring.FLUKA_HOME
RFLUKA = scoring.RFLUKA
ACTIVE_VETO_THRESHOLD_KEV = 50.0


DELAYED_SOURCE_FORTRAN = """*
* Exact-position delayed isotope source for TES511 source-v2 EventList.
*
      module source_variables
         implicit none
         integer, save :: particle_code
         integer, save :: heavyion_atomic_number, heavyion_mass_number, heavyion_isomer
         double precision, save :: momentum_energy, particle_weight
         logical, save :: energy_logical_flag
         double precision, save :: divergence_x, divergence_y
         logical, save :: gaussian_divergence_logical_flag
         double precision, save :: coordinate_x, coordinate_y, coordinate_z
         integer, save :: direction_flag
         double precision, save :: direction_cosx, direction_cosy, direction_cosz
         double precision, save :: polarization_cosx, polarization_cosy, polarization_cosz
         double precision, save :: particle_age
         double precision, save :: kshort_component
         double precision, save :: delayed_radioactive_decay
      end module source_variables

      include 'source_library.inc'

      subroutine SOURCE ( nomore )
      use source_library
      use source_variables
      implicit none
      integer nomore
      logical, save :: first_run = .true.
      integer, save :: unit = 78
      integer ios, znum, anum, isom
      double precision x, y, z, u, v, w, delay

      nomore = 0
      call initialization()

      if ( first_run ) then
         open(unit=unit, file='isotopes.dat', status='old',
     &        action='read', iostat=ios)
         if ( ios .ne. 0 ) then
            open(unit=unit, file='../isotopes.dat', status='old',
     &           action='read', iostat=ios)
         end if
         if ( ios .ne. 0 ) call FLABRT('SOURCE','cannot open isotopes.dat')
         first_run = .false.
      end if

      read(unit,*,iostat=ios) znum, anum, isom, x, y, z, u, v, w, delay
      if ( ios .ne. 0 ) then
         nomore = 1
         return
      end if

      particle_code = -2
      heavyion_atomic_number = znum
      heavyion_mass_number = anum
      heavyion_isomer = isom
      coordinate_x = x
      coordinate_y = y
      coordinate_z = z
      direction_cosx = u
      direction_cosy = v
      direction_cosz = w
      direction_flag = 0
      particle_weight = 1.0D0
      particle_age = 0.0D0
      delayed_radioactive_decay = delay

      call set_primary()
      return
      end
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def parse_eventlist(path: Path) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8", errors="ignore") as f:
        for raw in f:
            parts = raw.split()
            if not parts:
                continue
            if len(parts) != 15:
                raise ValueError(f"unexpected EventList field count in {path}: {raw.rstrip()}")
            eid = int(parts[0])
            za = int(parts[2])
            out[eid] = {
                "event_id": parts[0],
                "ZA": parts[2],
                "Z": str(za // 1000),
                "A": str(za % 1000),
                "isomer": parts[3],
                "time_s": parts[4],
                "x_cm": parts[5],
                "y_cm": parts[6],
                "z_cm": parts[7],
                "dx": parts[8],
                "dy": parts[9],
                "dz": parts[10],
            }
    return out


def source_rows(eventlist: Path, weights: Path, max_events: int | None, start_index: int) -> list[dict[str, Any]]:
    events = parse_eventlist(eventlist)
    weight_rows = rows_from_csv(weights)
    out: list[dict[str, Any]] = []
    for row in weight_rows:
        event_id = int(row["event_id"])
        if event_id < start_index:
            continue
        ev = events.get(event_id)
        if ev is None:
            raise KeyError(f"weight row has no EventList row: event_id={event_id}")
        z = int(ev["Z"])
        a = int(ev["A"])
        if z <= 3 and a <= 4 and not (z == 1 and a == 3):
            continue
        merged: dict[str, Any] = {**row, **ev}
        merged["history_id"] = len(out) + 1
        merged["history_weight"] = float(row["event_weight_Bq"])
        merged["isotope_Z"] = z
        merged["isotope_A"] = a
        merged["isomer"] = int(float(ev["isomer"]))
        out.append(merged)
        if max_events is not None and len(out) >= max_events:
            break
    if not out:
        raise ValueError("no delayed isotope rows selected")
    return out


def write_isotopes_dat(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="ascii") as f:
        for row in rows:
            dx = float(row.get("dx") or 0.0)
            dy = float(row.get("dy") or 0.0)
            dz = float(row.get("dz") or 1.0)
            norm = math.sqrt(dx * dx + dy * dy + dz * dz)
            if norm <= 0.0:
                dx, dy, dz = 0.0, 0.0, 1.0
            else:
                dx, dy, dz = dx / norm, dy / norm, dz / norm
            f.write(
                f"{int(row['isotope_Z'])} {int(row['isotope_A'])} {int(row['isomer'])} "
                f"{float(row['x_cm']):.8e} {float(row['y_cm']):.8e} {float(row['z_cm']):.8e} "
                f"{dx:.8e} {dy:.8e} {dz:.8e} {float(row['time_s']):.12e}\n"
            )


def delayed_input(title: str, histories: int, seed: int) -> str:
    fluka_seed = int(seed) % 900000
    if fluka_seed <= 0:
        fluka_seed = 1
    return (
        "GLOBAL         20000         0         1         0         0         0\n"
        "TITLE\n"
        f"{title}\n"
        "DEFAULTS                                                              EM-CASCA\n"
        + f"{'BEAM':<10}{0.001:10.6g}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}ISOTOPE\n"
        + f"{'HI-PROPE':<10}{53.0:10.1f}{128.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}\n"
        + f"{'RADDECAY':<10}{2.0:10.1f}\n"
        + f"{'DCYSCORE':<10}{-1.0:10.1f}\n"
        "SOURCE\n"
        + scoring.geometry_without_run_tail()
        + "EMFCUT      -1.0E-05   1.0E-05       0.0  R0000001  @LASTREG\n"
        + "SCORE       ENERGY\n"
        + "USERDUMP       100.0      99.0       6.0       0.0       0.0       0.0RAWDUMP\n"
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def compile_delayed_executable(out_dir: Path) -> Path:
    rows = scoring.read_region_rows()
    tes_nums = [scoring.region_number(r["fluka_region_name"]) for r in rows if r["detector_kind"] == "TES_PIXEL"]
    shield_nums = [scoring.region_number(r["fluka_region_name"]) for r in rows if r["detector_kind"] == "ACTIVE_SHIELD"]
    routine_dir = out_dir / "scoring_routines"
    routine_dir.mkdir(parents=True, exist_ok=True)
    source_path = routine_dir / "source_delayed_isotope.f"
    mgdraw_path = routine_dir / "mgdraw_raw.f"
    source_path.write_text(DELAYED_SOURCE_FORTRAN, encoding="ascii")
    mgdraw_path.write_text(
        scoring.generate_mgdraw(scoring.contiguous_ranges(tes_nums), scoring.contiguous_ranges(shield_nums)),
        encoding="ascii",
    )
    subprocess.run([str(scoring.FFF), source_path.name], cwd=str(routine_dir), env=env(), check=True, stdout=(routine_dir / "compile_source_delayed.log").open("w"), stderr=subprocess.STDOUT)
    subprocess.run([str(scoring.FFF), mgdraw_path.name], cwd=str(routine_dir), env=env(), check=True, stdout=(routine_dir / "compile_mgdraw_raw.log").open("w"), stderr=subprocess.STDOUT)
    subprocess.run(
        [str(scoring.LDPMQMD), "-m", "fluka", "-o", "fluka_delayed_raw", "source_delayed_isotope.o", "mgdraw_raw.o"],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "link_fluka_delayed_raw.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    return routine_dir / "fluka_delayed_raw"


def build_delayed_raw_events(
    deposits_path: Path,
    totals_path: Path,
    sources: list[dict[str, Any]],
    run_id: str,
    seed: int,
) -> list[dict[str, object]]:
    by_region, _ = load_region_crosswalk()
    process_map = load_process_map()
    source_by_history = {int(r["history_id"]): r for r in sources}
    totals = parse_event_totals(totals_path)
    rows: list[dict[str, object]] = []
    for dep in rows_from_csv(deposits_path):
        history_id = int(dep["history_id"])
        src = source_by_history[history_id]
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
                "stream": "delayed",
                "primary_tag": str(src.get("nuclide", "delayed_isotope")),
                "primary_energy_keV": 0.0,
                "primary_x_cm": src["x_cm"],
                "primary_y_cm": src["y_cm"],
                "primary_z_cm": src["z_cm"],
                "primary_dx": src.get("dx", 0.0),
                "primary_dy": src.get("dy", 0.0),
                "primary_dz": src.get("dz", 1.0),
                "history_weight": src["history_weight"],
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


def source_csv_fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "history_id",
        "event_id",
        "source_name",
        "production_tag",
        "raw_volume",
        "ZA",
        "nuclide",
        "isotope_Z",
        "isotope_A",
        "isomer",
        "x_cm",
        "y_cm",
        "z_cm",
        "time_s",
        "history_weight",
        "event_weight_Bq",
        "key_activity_Bq",
        "key_rpip_count",
    ]
    rest = sorted(set().union(*(row.keys() for row in rows)) - set(preferred))
    return preferred + rest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eventlist", type=Path, default=DEFAULT_EVENTLIST)
    ap.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=24066200)
    ap.add_argument("--max-events", type=int, default=None)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--reuse-executable", action="store_true")
    args = ap.parse_args()

    if args.max_events is not None and args.max_events < 1:
        raise SystemExit("max-events must be positive")
    if args.start_index < 0:
        raise SystemExit("start-index must be non-negative")

    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    raw_dir = out_dir / "raw_events"
    fluka_dir = out_dir / "fluka_run"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fluka_dir.mkdir(parents=True, exist_ok=True)

    sources = source_rows(args.eventlist, args.weights, args.max_events, args.start_index)
    run_id = f"delayed_isotope_seed{args.seed}_n{len(sources)}"
    write_csv(raw_dir / "delayed_sources.csv", sources, source_csv_fields(sources))
    write_isotopes_dat(fluka_dir / "isotopes.dat", sources)

    exe = out_dir / "scoring_routines/fluka_delayed_raw"
    if not (args.reuse_executable and exe.exists()):
        exe = compile_delayed_executable(out_dir)

    input_stem = "delayed_isotope_raw"
    input_path = fluka_dir / f"{input_stem}.inp"
    input_path.write_text(delayed_input("TES511 delayed isotope raw MVP", len(sources), args.seed), encoding="ascii")

    started = now_utc()
    t0 = time.time()
    returncode = run([str(RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", input_stem], fluka_dir, fluka_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()
    if returncode != 0:
        write_json(
            out_dir / "summary.json",
            {
                "status": "FLUKA_DELAYED_ISOTOPE_RUN_FAILED",
                "returncode": returncode,
                "rfluka_log": str(fluka_dir / "rfluka.log"),
                "histories": len(sources),
            },
        )
        return 2

    deposits_file = find_file(fluka_dir, "raw_deposits_tmp.csv")
    totals_file = find_file(fluka_dir, "event_totals_tmp.csv")
    raw_events = build_delayed_raw_events(deposits_file, totals_file, sources, run_id, args.seed)
    write_csv(raw_dir / "raw_events.csv", raw_events, RAW_EVENT_FIELDS)

    _, region_kind = load_region_crosswalk()
    closure = closure_from_outputs(fluka_dir, raw_events, len(sources), float(len(sources)), region_kind, input_stem)
    closure.update(
        {
            "raw_deposits_file": str(deposits_file),
            "event_totals_file": str(totals_file),
            "raw_event_rows": len(raw_events),
            "created_at_utc": now_utc(),
        }
    )
    write_json(out_dir / "scoring_closure.json", closure)

    manifest = {
        "run_id": run_id,
        "histories": len(sources),
        "seed": args.seed,
        "returncode": returncode,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "elapsed_s": elapsed_s,
        "fluka_executable": str(exe),
        "fluka_executable_sha256": sha256_path(exe),
        "input": str(input_path),
        "input_sha256": sha256_path(input_path),
        "source_mode": "delayed_source_v2_weighted_exact_position_isotope_eventlist",
        "eventlist": str(args.eventlist.resolve()),
        "weights": str(args.weights.resolve()),
        "selected_activity_Bq": sum(float(r["history_weight"]) for r in sources),
        "raw_deposits_file": str(deposits_file),
        "event_totals_file": str(totals_file),
        "scoring_closure_status": closure["status"],
    }
    write_csv(out_dir / "run_manifest.csv", [manifest], list(manifest.keys()))
    status = "DELAYED_ISOTOPE_RAW_MVP_PASS" if closure["status"] == "PASS" else "BLOCKED_DELAYED_SCORING_CLOSURE"
    summary = {
        "status": status,
        "source_mode": "delayed_source_v2_weighted_exact_position_isotope_eventlist",
        "no_sim_gz_replay": True,
        "histories": len(sources),
        "selected_activity_Bq": manifest["selected_activity_Bq"],
        "raw_event_rows": len(raw_events),
        "raw_events_csv": str(raw_dir / "raw_events.csv"),
        "sources_csv": str(raw_dir / "delayed_sources.csv"),
        "run_manifest": str(out_dir / "run_manifest.csv"),
        "scoring_closure": closure,
    }
    write_json(out_dir / "summary.json", summary)
    (out_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Delayed Isotope Source Raw MVP",
                "",
                f"- status: `{status}`",
                "- source_mode: delayed_source_v2_weighted_exact_position_isotope_eventlist",
                "- no `.sim.gz` replay: true",
                f"- histories: `{len(sources)}`",
                f"- selected_activity_Bq: `{manifest['selected_activity_Bq']:.12g}`",
                f"- raw_event_rows: `{len(raw_events)}`",
                f"- scoring_closure: `{closure['status']}`",
                f"- elapsed_s: `{elapsed_s:.3f}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(out_dir / "summary.md")
    print(status)
    return 0 if status == "DELAYED_ISOTOPE_RAW_MVP_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
