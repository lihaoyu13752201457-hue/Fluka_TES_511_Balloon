#!/usr/bin/env python3
"""Verify FLUKA delayed source identity at runtime.

This is the first discriminating gate from the delayed closure engineering
plan: keep the same dummy ``HI-PROPE 53 128`` card used by the production
delayed input, override it from source-v2 EventList rows, and record the
Z/A/isomer that the FLUKA source routine passes to ``set_primary``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_raw_scoring_smoke as scoring
from run_eplus_raw_mvp import env, run, write_csv, write_json


ROOT = Path(__file__).resolve().parents[1]
TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
DELAYED_AUTH = TES_ROOT / "engineering/delayed_source_authority_v2_20260624/04_custom_source_v2"
DEFAULT_EVENTLIST = DELAYED_AUTH / "source_v2_eventlist.dat"
DEFAULT_WEIGHTS = DELAYED_AUTH / "source_v2_event_weights.csv"
DEFAULT_OUT = ROOT / "engineering/crosscode_delayed_closure_20260625/00_manifest/fluka_source_identity_gate"

TARGET_ORDER = [
    (29064, "Cu-64", "W2 beta-plus anchor"),
    (29062, "Cu-62", "W2 secondary copper isotope"),
    (53128, "I-128", "dominant total delayed activity"),
    (11022, "Na-22", "long-lived positron emitter sanity check"),
    (11024, "Na-24", "high-energy cascade probe"),
    (13028, "Al-28", "high-energy gamma probe"),
]


SOURCE_IDENTITY_FORTRAN = """*
* Runtime isotope identity gate for delayed source-v2 EventList rows.
*
      module source_variables
         implicit none
         integer, save :: particle_code
         integer, save :: heavyion_atomic_number, heavyion_mass_number
         integer, save :: heavyion_isomer
         double precision, save :: momentum_energy, particle_weight
         logical, save :: energy_logical_flag
         double precision, save :: divergence_x, divergence_y
         logical, save :: gaussian_divergence_logical_flag
         double precision, save :: coordinate_x, coordinate_y, coordinate_z
         integer, save :: direction_flag
         double precision, save :: direction_cosx, direction_cosy
         double precision, save :: direction_cosz
         double precision, save :: polarization_cosx, polarization_cosy
         double precision, save :: polarization_cosz
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
      integer, save :: logunit = 81
      integer, save :: seq = 0
      integer ios, source_index, event_id, za, znum, anum, isom
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
         open(unit=logunit, file='source_identity_runtime.csv',
     &        status='unknown', form='formatted')
         write(logunit,'(A)') 'seq,source_index,event_id,ZA,input_Z,'//
     &        'input_A,input_isomer,runtime_Z,runtime_A,'//
     &        'runtime_isomer,IJHION,ILOFLK,IRDAZM,RADDLY_s'
         first_run = .false.
      end if

      read(unit,*,iostat=ios) source_index, event_id, za, znum, anum,
     &     isom, x, y, z, u, v, w, delay
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
      seq = seq + 1
      write(logunit,1000) seq, source_index, event_id, za, znum, anum,
     &     isom, heavyion_atomic_number, heavyion_mass_number,
     &     heavyion_isomer, IJHION, ILOFLK(NPFLKA), IRDAZM(NPFLKA),
     &     RADDLY(NPFLKA)
      call flush(logunit)
      return

 1000 FORMAT(I8,',',I8,',',I12,',',I8,',',I4,',',I4,',',I4,
     & ',',I4,',',I4,',',I4,',',I12,',',I12,',',I12,',',
     & 1PE16.8)
      end
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def target_summary(weights: Path) -> dict[int, dict[str, Any]]:
    out = {
        za: {"ZA": za, "nuclide": name, "purpose": purpose, "rows": 0, "activity_Bq": 0.0, "first_event_id": None}
        for za, name, purpose in TARGET_ORDER
    }
    with weights.open(newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            za = int(row["ZA"])
            rec = out.get(za)
            if rec is None:
                continue
            rec["rows"] += 1
            rec["activity_Bq"] += float(row["event_weight_Bq"])
            if rec["first_event_id"] is None:
                rec["first_event_id"] = int(row["event_id"])
    return out


def select_target_rows(eventlist: Path, weights: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = parse_eventlist(eventlist)
    selected_by_za: dict[int, dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    weights_rows = rows_from_csv(weights)
    for row in weights_rows:
        za = int(row["ZA"])
        if za not in {target[0] for target in TARGET_ORDER} or za in selected_by_za:
            continue
        event_id = int(row["event_id"])
        ev = events.get(event_id)
        if ev is None:
            raise KeyError(f"weight row has no EventList row: event_id={event_id}")
        merged: dict[str, Any] = {**row, **ev}
        merged["source_index"] = len(selected_by_za) + 1
        merged["selected_Z"] = int(ev["Z"])
        merged["selected_A"] = int(ev["A"])
        merged["selected_isomer"] = int(float(ev["isomer"]))
        selected_by_za[za] = merged
    rows: list[dict[str, Any]] = []
    for source_index, (za, name, purpose) in enumerate(TARGET_ORDER, start=1):
        row = selected_by_za.get(za)
        if row is None:
            missing.append({"ZA": za, "nuclide": name, "purpose": purpose})
            continue
        row["source_index"] = source_index
        row["target_nuclide"] = name
        row["purpose"] = purpose
        rows.append(row)
    return rows, missing


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
                f"{int(row['source_index'])} {int(row['event_id'])} {int(row['ZA'])} "
                f"{int(row['selected_Z'])} {int(row['selected_A'])} {int(row['selected_isomer'])} "
                f"{float(row['x_cm']):.8e} {float(row['y_cm']):.8e} {float(row['z_cm']):.8e} "
                f"{dx:.8e} {dy:.8e} {dz:.8e} {float(row['time_s']):.12e}\n"
            )


def identity_input(title: str, histories: int, seed: int) -> str:
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
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def compile_identity_executable(out_dir: Path) -> Path:
    routine_dir = out_dir / "scoring_routines"
    routine_dir.mkdir(parents=True, exist_ok=True)
    source_path = routine_dir / "source_identity_gate.f"
    source_path.write_text(SOURCE_IDENTITY_FORTRAN, encoding="ascii")
    subprocess.run(
        [str(scoring.FFF), source_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_source_identity_gate.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.LDPMQMD), "-m", "fluka", "-o", "fluka_identity_gate", "source_identity_gate.o"],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "link_fluka_identity_gate.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    return routine_dir / "fluka_identity_gate"


def validate_runtime(selected: list[dict[str, Any]], runtime_path: Path) -> tuple[str, list[dict[str, Any]], list[str]]:
    runtime = rows_from_csv(runtime_path)
    selected_by_source = {int(row["source_index"]): row for row in selected}
    validation: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in runtime:
        source_index = int(row["source_index"])
        expected = selected_by_source.get(source_index)
        if expected is None:
            errors.append(f"runtime row has unknown source_index={source_index}")
            continue
        rec = {
            "source_index": source_index,
            "event_id": int(row["event_id"]),
            "nuclide": expected["target_nuclide"],
            "expected_ZA": int(expected["ZA"]),
            "expected_Z": int(expected["selected_Z"]),
            "expected_A": int(expected["selected_A"]),
            "expected_isomer": int(expected["selected_isomer"]),
            "runtime_Z": int(row["runtime_Z"]),
            "runtime_A": int(row["runtime_A"]),
            "runtime_isomer": int(row["runtime_isomer"]),
            "IJHION": int(row["IJHION"]),
            "RADDLY_s": float(row["RADDLY_s"]),
        }
        rec["identity_match"] = (
            rec["expected_Z"] == rec["runtime_Z"]
            and rec["expected_A"] == rec["runtime_A"]
            and rec["expected_isomer"] == rec["runtime_isomer"]
        )
        if not rec["identity_match"]:
            errors.append(
                f"{rec['nuclide']} mismatch: expected "
                f"{rec['expected_Z']}/{rec['expected_A']}/{rec['expected_isomer']} got "
                f"{rec['runtime_Z']}/{rec['runtime_A']}/{rec['runtime_isomer']}"
            )
        validation.append(rec)
    if len(runtime) != len(selected):
        errors.append(f"runtime row count {len(runtime)} != selected row count {len(selected)}")
    status = "FLUKA_SOURCE_IDENTITY_GATE_PASS" if not errors else "FLUKA_SOURCE_IDENTITY_GATE_FAIL"
    return status, validation, errors


def selected_fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "source_index",
        "event_id",
        "target_nuclide",
        "purpose",
        "ZA",
        "nuclide",
        "selected_Z",
        "selected_A",
        "selected_isomer",
        "x_cm",
        "y_cm",
        "z_cm",
        "time_s",
        "event_weight_Bq",
        "source_name",
        "production_tag",
        "raw_volume",
        "canonical_volume_for_reporting_only",
    ]
    rest = sorted(set().union(*(row.keys() for row in rows)) - set(preferred))
    return preferred + rest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eventlist", type=Path, default=DEFAULT_EVENTLIST)
    ap.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=24066251)
    ap.add_argument("--reuse-executable", action="store_true")
    args = ap.parse_args()

    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    run_dir = out_dir / "fluka_run"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    selected, missing = select_target_rows(args.eventlist, args.weights)
    if not selected:
        raise SystemExit("no target isotope rows selected")
    write_csv(out_dir / "selected_source_rows.csv", selected, selected_fields(selected))
    write_isotopes_dat(run_dir / "isotopes.dat", selected)

    exe = out_dir / "scoring_routines/fluka_identity_gate"
    if not (args.reuse_executable and exe.exists()):
        exe = compile_identity_executable(out_dir)

    input_stem = "identity_gate"
    input_path = run_dir / f"{input_stem}.inp"
    input_path.write_text(identity_input("TES511 delayed source identity gate", len(selected), args.seed), encoding="ascii")

    started = now_utc()
    t0 = time.time()
    returncode = run([str(scoring.RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", input_stem], run_dir, run_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()

    runtime_path = run_dir / "source_identity_runtime.csv"
    runtime_candidates = sorted(run_dir.glob("*source_identity_runtime.csv"))
    if not runtime_path.exists() and runtime_candidates:
        runtime_path = runtime_candidates[-1]
    if returncode != 0 or not runtime_path.exists():
        status = "FLUKA_SOURCE_IDENTITY_GATE_RUN_FAILED"
        summary = {
            "status": status,
            "returncode": returncode,
            "selected_histories": len(selected),
            "missing_targets": missing,
            "rfluka_log": str(run_dir / "rfluka.log"),
            "runtime_csv_exists": runtime_path.exists(),
        }
        write_json(out_dir / "summary.json", summary)
        (out_dir / "summary.md").write_text(
            "\n".join(
                [
                    "# FLUKA Delayed Source Identity Gate",
                    "",
                    f"- status: `{status}`",
                    f"- returncode: `{returncode}`",
                    f"- selected_histories: `{len(selected)}`",
                    f"- runtime_csv_exists: `{runtime_path.exists()}`",
                    f"- rfluka_log: `{run_dir / 'rfluka.log'}`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(out_dir / "summary.md")
        print(status)
        return 2

    runtime_copy = out_dir / "runtime_source_identity.csv"
    shutil.copy2(runtime_path, runtime_copy)

    status, validation, errors = validate_runtime(selected, runtime_copy)
    write_csv(
        out_dir / "runtime_identity_validation.csv",
        validation,
        [
            "source_index",
            "event_id",
            "nuclide",
            "expected_ZA",
            "expected_Z",
            "expected_A",
            "expected_isomer",
            "runtime_Z",
            "runtime_A",
            "runtime_isomer",
            "IJHION",
            "RADDLY_s",
            "identity_match",
        ],
    )
    source_summary = target_summary(args.weights)
    summary = {
        "status": status,
        "created_utc": now_utc(),
        "started_utc": started,
        "finished_utc": finished,
        "elapsed_s": elapsed_s,
        "returncode": returncode,
        "dummy_hi_prope_ZA": 53128,
        "source_override_checked": True,
        "selected_histories": len(selected),
        "selected_targets": [row["target_nuclide"] for row in selected],
        "missing_targets": missing,
        "target_source_summary": list(source_summary.values()),
        "runtime_csv": str(runtime_copy),
        "rfluka_runtime_csv": str(runtime_path),
        "validation_csv": str(out_dir / "runtime_identity_validation.csv"),
        "selected_source_rows_csv": str(out_dir / "selected_source_rows.csv"),
        "fluka_executable": str(exe),
        "fluka_executable_sha256": sha256_path(exe),
        "input": str(input_path),
        "input_sha256": sha256_path(input_path),
        "errors": errors,
        "interpretation": (
            "The production-style dummy HI-PROPE 53/128 card is not the observed "
            "source identity for these histories; the source routine overrides it "
            "with the source-v2 isotope Z/A/isomer before set_primary."
            if status.endswith("_PASS")
            else "At least one runtime Z/A/isomer did not match the source-v2 row."
        ),
    }
    write_json(out_dir / "summary.json", summary)
    (out_dir / "summary.md").write_text(
        "\n".join(
            [
                "# FLUKA Delayed Source Identity Gate",
                "",
                f"- status: `{status}`",
                f"- dummy `HI-PROPE` ZA: `53128`",
                "- source override checked: true",
                f"- selected histories: `{len(selected)}`",
                f"- selected targets: `{', '.join(summary['selected_targets'])}`",
                f"- elapsed_s: `{elapsed_s:.3f}`",
                f"- validation_csv: `{out_dir / 'runtime_identity_validation.csv'}`",
                "",
                "## Interpretation",
                "",
                summary["interpretation"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(out_dir / "summary.md")
    print(status)
    return 0 if status == "FLUKA_SOURCE_IDENTITY_GATE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
