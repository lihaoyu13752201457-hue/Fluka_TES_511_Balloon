#!/usr/bin/env python3
"""Run the Phase-2 T1 common Cu-sphere transport smoke.

This follows the completed T0 source-bookkeeping gate, using the same explicit
primary table.  The toy geometry is a 1 cm radius copper sphere in vacuum.  The
tracked observable is escaped-particle response, especially escaped photons and
511-like photons from the positron rows.  FLUKA also writes per-history copper
energy deposition totals.  MEGAlib detector-hit/deposit truth is intentionally
left for the later T1/T2 production gate.
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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import build_raw_scoring_smoke as scoring
from run_common_transport_t0_source_gate import (
    COSIMA,
    PRIMARY_FIELDS,
    build_common_primaries,
    rel,
    sha256_path,
    write_fluka_primaries,
    write_megalib_eventlist,
)
from run_eplus_raw_mvp import env, run, write_csv, write_json


ROOT = Path(__file__).resolve().parents[1]
T0_OUT = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "02_common_em_transport/t0_source_bookkeeping_smoke"
)
DEFAULT_SOURCE_CSV = T0_OUT / "common_primaries.csv"
DEFAULT_OUT = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "02_common_em_transport/t1_cu_sphere_transport_smoke"
)

CU_RADIUS_CM = 1.0
WORLD_HALF_WIDTH_CM = 100.0

PARTICLE_NAME = {
    "FLUKA": {4: "POSITRON", 7: "PHOTON", 3: "ELECTRON", 211: "EM_BELOW_THRESHOLD"},
    "MEGAlib": {1: "PHOTON", 2: "POSITRON", 3: "ELECTRON"},
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def load_or_build_primaries(path: Path, seed: int) -> list[dict[str, Any]]:
    if path.exists():
        rows = rows_from_csv(path)
        return [coerce_primary(row) for row in rows]
    return build_common_primaries(
        seed=seed,
        mono511=512,
        pair511=256,
        high_gamma_each=256,
        positrons=512,
    )


def coerce_primary(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    for key in (
        "primary_id",
        "source_event_id",
        "pair_member",
        "fluka_particle_code",
        "megalib_particle_code",
        "concurrent_with_previous",
        "seed",
    ):
        out[key] = int(float(str(row.get(key, 0) or 0)))
    for key in (
        "kinetic_energy_keV",
        "x_cm",
        "y_cm",
        "z_cm",
        "dir_x",
        "dir_y",
        "dir_z",
        "pol_x",
        "pol_y",
        "pol_z",
        "weight",
    ):
        out[key] = float(row.get(key, 0.0) or 0.0)
    return out


def write_megalib_geometry(path: Path) -> None:
    text = "\n".join(
        [
            "Name T1CuSphereTransportSmoke",
            "Version 2.0",
            "",
            f"SurroundingSphere {WORLD_HALF_WIDTH_CM} 0.0 0.0 0.0 {WORLD_HALF_WIDTH_CM}",
            "Include $(MEGALIB)/resource/examples/geomega/materials/Materials.geo",
            "",
            "Volume WorldVolume",
            "WorldVolume.Material Vacuum",
            "WorldVolume.Visibility 0",
            f"WorldVolume.Shape BRIK {WORLD_HALF_WIDTH_CM}. {WORLD_HALF_WIDTH_CM}. {WORLD_HALF_WIDTH_CM}.",
            "WorldVolume.Mother 0",
            "",
            "Volume CuSphere",
            "CuSphere.Material Copper",
            "CuSphere.Visibility 1",
            "CuSphere.Color 4",
            f"CuSphere.Shape SPHE 0.0 {CU_RADIUS_CM} 0.0 180.0 0.0 360.0",
            "CuSphere.Position 0.0 0.0 0.0",
            "CuSphere.Mother WorldVolume",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def write_megalib_source(path: Path, geometry: Path, eventlist: Path, out_prefix: Path, n_events: int) -> None:
    run_name = "T1CuSphere"
    source_name = "CommonPrimaryList"
    text = "\n".join(
        [
            "Version 1",
            f"Geometry {geometry}",
            "PhysicsListEM LivermorePol",
            "StoreSimulationInfo all",
            "StoreSimulationInfoIonization false",
            "DiscretizeHits true",
            "DetectorTimeConstant 1e-9",
            "",
            f"Run {run_name}",
            f"{run_name}.FileName {out_prefix}",
            f"{run_name}.Triggers {n_events}",
            f"{run_name}.Source {source_name}",
            "",
            f"{source_name}.EventList {eventlist}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


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


def parse_megalib_escape_line(line: str, current_event: int) -> dict[str, Any] | None:
    parts = [part.strip() for part in line.split("IA ESCP", 1)[1].split(";")]
    if len(parts) < 15:
        return None
    try:
        return {
            "code": "MEGAlib",
            "event_id": current_event,
            "interaction_id": int(parts[0].strip().split()[-1]),
            "parent_track_id": int(parts[1]),
            "particle_code": int(parts[7]),
            "particle": PARTICLE_NAME["MEGAlib"].get(int(parts[7]), f"MEGALIB_{int(parts[7])}"),
            "kinetic_energy_keV": float(parts[14]),
            "time_s": float(parts[3]),
            "dir_x": float(parts[8]),
            "dir_y": float(parts[9]),
            "dir_z": float(parts[10]),
            "x_cm": float(parts[4]),
            "y_cm": float(parts[5]),
            "z_cm": float(parts[6]),
            "weight": 1.0,
        }
    except ValueError:
        return None


def parse_megalib_escape(sim_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    current_event = 0
    if not sim_path.exists():
        return out
    for raw in open_sim(sim_path):
        line = raw.strip()
        if line.startswith("ID "):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    current_event = int(parts[1])
                except ValueError:
                    current_event = 0
        elif line.startswith("IA ESCP"):
            row = parse_megalib_escape_line(line, current_event)
            if row is not None:
                out.append(row)
    return out


def run_megalib(
    out_dir: Path,
    primaries: list[dict[str, Any]],
    seed: int,
    keep_run_products: bool,
) -> dict[str, Any]:
    run_dir = out_dir / "cosima_run"
    input_dir = out_dir / "megalib_inputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    geometry = input_dir / "t1_cu_sphere.geo.setup"
    eventlist = input_dir / "common_eventlist.dat"
    source = input_dir / "t1_cu_sphere.source"
    out_prefix = run_dir / "t1_cu_sphere"
    write_megalib_geometry(geometry)
    write_megalib_eventlist(eventlist, primaries)
    write_megalib_source(source, geometry, eventlist, out_prefix, len(primaries))

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
    sim_file_generated = sim_file.exists()
    escaped = parse_megalib_escape(sim_file)
    if not keep_run_products and run_dir.exists():
        shutil.rmtree(run_dir)
    return {
        "code": "MEGAlib",
        "returncode": proc.returncode,
        "started_utc": started,
        "finished_utc": finished,
        "elapsed_s": elapsed_s,
        "source": rel(source),
        "source_sha256": sha256_path(source),
        "eventlist": rel(eventlist),
        "eventlist_sha256": sha256_path(eventlist),
        "geometry": rel(geometry),
        "geometry_sha256": sha256_path(geometry),
        "sim_file": rel(sim_file),
        "sim_file_generated": sim_file_generated,
        "run_products_retained": keep_run_products,
        "cosima_log": rel(log_path),
        "escaped": escaped,
        "cu_deposits": {},
    }


SOURCE_FORTRAN = """*
* Common-primary T1 Cu-sphere source.
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
      integer, save :: unit = 77
      integer ios
      double precision egev, x, y, z, u, v, w, wei

      nomore = 0
      call initialization()

      if ( first_run ) then
         open(unit=unit, file='primaries.dat', status='old',
     &        action='read', iostat=ios)
         if ( ios .ne. 0 ) then
            open(unit=unit, file='../primaries.dat', status='old',
     &           action='read', iostat=ios)
         end if
         if ( ios .ne. 0 ) call FLABRT('SOURCE','cannot open primaries.dat')
         first_run = .false.
      end if

      read(unit,*,iostat=ios) particle_code, egev, x, y, z, u, v, w, wei
      if ( ios .ne. 0 ) then
         nomore = 1
         return
      end if

      momentum_energy = egev
      energy_logical_flag = .true.
      coordinate_x = x
      coordinate_y = y
      coordinate_z = z
      direction_cosx = u
      direction_cosy = v
      direction_cosz = w
      direction_flag = 0
      particle_weight = wei
      particle_age = 0.0D0

      call set_primary()
      return
      end
"""


MGDRAW_FORTRAN = """*
* Cu-sphere escape and deposit scorer for the T1 common-primary smoke.
*
      SUBROUTINE MGDRAW ( ICODE, MREG )
      INCLUDE 'dblprc.inc'
      INCLUDE 'dimpar.inc'
      INCLUDE 'iounit.inc'
      INCLUDE 'caslim.inc'
      INCLUDE 'paprop.inc'
      INCLUDE 'trackr.inc'
      CHARACTER*8 NAMREG, NEWNAM
      INTEGER IERR, JERR
      DOUBLE PRECISION KINKEV, DEPKEV
      DOUBLE PRECISION CUDEP
      LOGICAL LFOPEN
      SAVE LFOPEN, CUDEP
      DATA LFOPEN / .FALSE. /
      DATA CUDEP / 0.0D0 /

      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=88, FILE='cu_escape_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         OPEN ( UNIT=87, FILE='cu_event_totals_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (88,'(A)') 'event_id,particle_code,kinetic_energy_keV,'//
     &        'time_s,dir_x,dir_y,dir_z,x_cm,y_cm,z_cm,weight,'//
     &        'track_generation'
         WRITE (87,'(A)') 'event_id,cu_deposit_keV'
         LFOPEN = .TRUE.
      END IF

      CALL GEOR2N ( MREG, NAMREG, IERR )
      IF ( IERR .EQ. 0 .AND. NAMREG .EQ. 'CU' ) THEN
         IF ( MTRACK .GT. 0 ) THEN
            DEPKEV = 0.0D0
            DO I = 1, MTRACK
               IF ( DTRACK(I) .GT. 0.0D0 ) THEN
                  DEPKEV = DEPKEV + DBLE(DTRACK(I)) * 1.0D6
               END IF
            END DO
            CUDEP = CUDEP + DEPKEV
         END IF
      END IF
      RETURN

      ENTRY BXDRAW ( ICODE, MREG, NEWREG, XSCO, YSCO, ZSCO )
      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=88, FILE='cu_escape_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         OPEN ( UNIT=87, FILE='cu_event_totals_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (88,'(A)') 'event_id,particle_code,kinetic_energy_keV,'//
     &        'time_s,dir_x,dir_y,dir_z,x_cm,y_cm,z_cm,weight,'//
     &        'track_generation'
         WRITE (87,'(A)') 'event_id,cu_deposit_keV'
         LFOPEN = .TRUE.
      END IF
      CALL GEOR2N ( MREG, NAMREG, IERR )
      CALL GEOR2N ( NEWREG, NEWNAM, JERR )
      IF ( IERR .EQ. 0 .AND. JERR .EQ. 0 .AND.
     &     NAMREG .EQ. 'CU' .AND. NEWNAM .EQ. 'OUTER' ) THEN
         KINKEV = ETRACK
         IF ( JTRACK .GE. -6 .AND. JTRACK .LE. NALLWP ) THEN
            KINKEV = ETRACK - AM(JTRACK)
         END IF
         IF ( KINKEV .LT. 0.0D0 ) KINKEV = 0.0D0
         KINKEV = KINKEV * 1.0D6
         WRITE (88,1000) NCASE, JTRACK, KINKEV, ATRACK,
     &        CXTRCK, CYTRCK, CZTRCK, XSCO, YSCO, ZSCO,
     &        WTRACK, LTRACK
      END IF
      RETURN

      ENTRY EEDRAW ( ICODE )
      IF ( LFOPEN ) THEN
         WRITE (87,1010) NCASE, CUDEP
      END IF
      CUDEP = 0.0D0
      RETURN

      ENTRY ENDRAW ( ICODE, MREG, RULL, XSCO, YSCO, ZSCO )
      CALL GEOR2N ( MREG, NAMREG, IERR )
      IF ( IERR .EQ. 0 .AND. NAMREG .EQ. 'CU' .AND.
     &     RULL .GT. 0.0D0 ) THEN
         CUDEP = CUDEP + DBLE(RULL) * 1.0D6
      END IF
      RETURN

      ENTRY SODRAW
      RETURN

      ENTRY USDRAW ( ICODE, MREG, XSCO, YSCO, ZSCO )
      RETURN

 1000 FORMAT(I12,',',I8,',',1PE16.8,',',1PE16.8,
     & ',',1PE16.8,',',1PE16.8,',',1PE16.8,',',1PE16.8,
     & ',',1PE16.8,',',1PE16.8,',',1PE16.8,',',I8)
 1010 FORMAT(I12,',',1PE16.8)
      END
"""


def compile_fluka_executable(run_dir: Path) -> Path:
    routine_dir = run_dir / "scoring_routines"
    routine_dir.mkdir(parents=True, exist_ok=True)
    source_path = routine_dir / "source_t1_cu.f"
    mgdraw_path = routine_dir / "mgdraw_t1_cu.f"
    source_path.write_text(SOURCE_FORTRAN, encoding="ascii")
    mgdraw_path.write_text(MGDRAW_FORTRAN, encoding="ascii")
    subprocess.run(
        [str(scoring.FFF), source_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_source_t1_cu.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.FFF), mgdraw_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_mgdraw_t1_cu.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.LDPMQMD), "-m", "fluka", "-o", "fluka_t1_cu", "source_t1_cu.o", "mgdraw_t1_cu.o"],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "link_fluka_t1_cu.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    return routine_dir / "fluka_t1_cu"


def t1_fluka_input(histories: int, seed: int, beam_gev: float) -> str:
    fluka_seed = int(seed) % 900000
    if fluka_seed <= 0:
        fluka_seed = 1
    return (
        "GLOBAL         20000         0         1         0         0         0\n"
        "TITLE\n"
        "TES511 common-primary T1 Cu sphere smoke\n"
        "DEFAULTS                                                              EM-CASCA\n"
        f"BEAM      {beam_gev:10.6g}                                                  PHOTON\n"
        "SOURCE\n"
        "GEOBEGIN                                                              COMBNAME\n"
        "  0 0                       Common-primary T1 Cu sphere\n"
        "RPP BIGBOX -1000000.0 +1000000.0 -1000000.0 +1000000.0 -1000000.0 +1000000.0\n"
        f"RPP WORLD  -{WORLD_HALF_WIDTH_CM:.1f} +{WORLD_HALF_WIDTH_CM:.1f} -{WORLD_HALF_WIDTH_CM:.1f} +{WORLD_HALF_WIDTH_CM:.1f} -{WORLD_HALF_WIDTH_CM:.1f} +{WORLD_HALF_WIDTH_CM:.1f}\n"
        f"SPH CUSPH 0.0 0.0 0.0 {CU_RADIUS_CM:.6f}\n"
        "END\n"
        "BLKHOLE 5 +BIGBOX -WORLD\n"
        "OUTER    5 +WORLD -CUSPH\n"
        "CU       5 +CUSPH\n"
        "END\n"
        "GEOEND\n"
        "ASSIGNMAT  BLCKHOLE  BLKHOLE\n"
        "ASSIGNMAT    VACUUM    OUTER\n"
        "ASSIGNMAT    COPPER       CU\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0        CU\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0     OUTER\n"
        + f"{'USERDUMP':<10}{100.0:10.1f}{99.0:10.1f}{6.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}RAWDUMP\n"
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def parse_fluka_escape(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for row in rows_from_csv(path):
        pcode = int(row["particle_code"])
        rows.append(
            {
                "code": "FLUKA",
                "event_id": int(row["event_id"]),
                "particle_code": pcode,
                "particle": PARTICLE_NAME["FLUKA"].get(pcode, f"FLUKA_{pcode}"),
                "kinetic_energy_keV": float(row["kinetic_energy_keV"]),
                "time_s": float(row["time_s"]),
                "dir_x": float(row["dir_x"]),
                "dir_y": float(row["dir_y"]),
                "dir_z": float(row["dir_z"]),
                "x_cm": float(row["x_cm"]),
                "y_cm": float(row["y_cm"]),
                "z_cm": float(row["z_cm"]),
                "weight": float(row["weight"]),
            }
        )
    rows.sort(key=lambda item: (int(item["event_id"]), int(item["particle_code"]), float(item["kinetic_energy_keV"])))
    return rows


def parse_fluka_deposits(path: Path) -> dict[int, float]:
    out: dict[int, float] = {}
    if not path.exists():
        return out
    for row in rows_from_csv(path):
        out[int(row["event_id"])] = float(row["cu_deposit_keV"])
    return out


def run_fluka(
    out_dir: Path,
    primaries: list[dict[str, Any]],
    seed: int,
    keep_run_products: bool,
) -> dict[str, Any]:
    run_dir = out_dir / "fluka_run"
    input_dir = out_dir / "fluka_inputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    tracked_primaries = input_dir / "primaries.dat"
    tracked_input = input_dir / "t1_cu_sphere.inp"
    write_fluka_primaries(tracked_primaries, primaries)
    max_gev = max(float(row["kinetic_energy_keV"]) / 1.0e6 for row in primaries)
    tracked_input.write_text(t1_fluka_input(len(primaries), seed, max(0.001, max_gev * 1.05)), encoding="ascii")
    shutil.copyfile(tracked_primaries, run_dir / "primaries.dat")
    shutil.copyfile(tracked_input, run_dir / "t1_cu_sphere.inp")

    exe = compile_fluka_executable(run_dir)
    started = now_utc()
    t0 = time.time()
    returncode = run([str(scoring.RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", "t1_cu_sphere"], run_dir, run_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()
    escape_candidates = sorted(run_dir.glob("*cu_escape_tmp.csv"))
    total_candidates = sorted(run_dir.glob("*cu_event_totals_tmp.csv"))
    escape_path = escape_candidates[-1] if escape_candidates else run_dir / "cu_escape_tmp.csv"
    total_path = total_candidates[-1] if total_candidates else run_dir / "cu_event_totals_tmp.csv"
    escaped = parse_fluka_escape(escape_path)
    cu_deposits = parse_fluka_deposits(total_path)
    if not keep_run_products and run_dir.exists():
        shutil.rmtree(run_dir)
    return {
        "code": "FLUKA",
        "returncode": returncode,
        "started_utc": started,
        "finished_utc": finished,
        "elapsed_s": elapsed_s,
        "input": rel(tracked_input),
        "input_sha256": sha256_path(tracked_input),
        "primaries_dat": rel(tracked_primaries),
        "primaries_dat_sha256": sha256_path(tracked_primaries),
        "run_products_retained": keep_run_products,
        "rfluka_log": rel(run_dir / "rfluka.log"),
        "escaped": escaped,
        "cu_deposits": cu_deposits,
    }


def is_photon(code: str, particle_code: int) -> bool:
    return (code == "MEGAlib" and particle_code == 1) or (code == "FLUKA" and particle_code == 7)


def family_summary(
    code: str,
    primaries: list[dict[str, Any]],
    escaped: list[dict[str, Any]],
    cu_deposits: dict[int, float],
) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in primaries:
        by_family[str(row["family"])].append(row)
    escaped_by_event: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in escaped:
        escaped_by_event[int(row["event_id"])].append(row)

    out: list[dict[str, Any]] = []
    for family, family_primaries in sorted(by_family.items()):
        event_ids = [int(row["primary_id"]) for row in family_primaries]
        escape_rows = [row for event_id in event_ids for row in escaped_by_event.get(event_id, [])]
        photon_rows = [row for row in escape_rows if is_photon(code, int(row["particle_code"]))]
        w2_rows = [row for row in photon_rows if 510.58 <= float(row["kinetic_energy_keV"]) <= 511.42]
        broad_rows = [row for row in photon_rows if 480.0 <= float(row["kinetic_energy_keV"]) <= 550.0]
        primary_escape = [
            row
            for row in escape_rows
            if int(row["particle_code"]) == int(family_primaries[0][f"{code.lower() if code == 'MEGAlib' else 'fluka'}_particle_code"])
        ]
        deposits = [cu_deposits.get(event_id, 0.0) for event_id in event_ids] if cu_deposits else []
        n = len(family_primaries)
        photon_energy_sum = sum(float(row["kinetic_energy_keV"]) for row in photon_rows)
        out.append(
            {
                "code": code,
                "family": family,
                "particle": family_primaries[0]["particle"],
                "histories": n,
                "escaped_rows": len(escape_rows),
                "escaped_primary_particle_count": len(primary_escape),
                "escaped_primary_particle_yield": len(primary_escape) / n if n else 0.0,
                "escaped_photon_count": len(photon_rows),
                "escaped_photon_yield": len(photon_rows) / n if n else 0.0,
                "escaped_480_550_photon_count": len(broad_rows),
                "escaped_480_550_photon_yield": len(broad_rows) / n if n else 0.0,
                "escaped_w2_photon_count": len(w2_rows),
                "escaped_w2_photon_yield": len(w2_rows) / n if n else 0.0,
                "mean_escaped_photon_energy_keV": photon_energy_sum / len(photon_rows) if photon_rows else 0.0,
                "mean_cu_deposit_keV": sum(deposits) / len(deposits) if deposits else "",
                "events_with_cu_deposit_rows": len(deposits) if deposits else "",
            }
        )
    return out


def comparison_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["code"], row["family"]): row for row in summary_rows}
    families = sorted({row["family"] for row in summary_rows})
    metrics = {
        "escaped_photon_yield": "escaped_photon_count",
        "escaped_480_550_photon_yield": "escaped_480_550_photon_count",
        "escaped_w2_photon_yield": "escaped_w2_photon_count",
        "escaped_primary_particle_yield": "escaped_primary_particle_count",
    }
    out: list[dict[str, Any]] = []
    for family in families:
        fluka = by_key.get(("FLUKA", family))
        mega = by_key.get(("MEGAlib", family))
        if not fluka or not mega:
            continue
        for metric, count_key in metrics.items():
            fval = float(fluka[metric])
            gval = float(mega[metric])
            fcount = float(fluka[count_key])
            gcount = float(mega[count_key])
            poisson_sigma = math.sqrt(max(fcount + gcount, 0.0))
            poisson_z = (fcount - gcount) / poisson_sigma if poisson_sigma > 0.0 else 0.0
            denom = max(abs(gval), 1.0e-30)
            out.append(
                {
                    "family": family,
                    "metric": metric,
                    "fluka_count": fcount,
                    "megalib_count": gcount,
                    "fluka": fval,
                    "megalib": gval,
                    "fluka_minus_megalib": fval - gval,
                    "fluka_over_megalib": fval / denom,
                    "relative_delta_vs_megalib": (fval - gval) / denom,
                    "poisson_z_approx": poisson_z,
                }
            )
    return out


def bounded_escape_sample(escaped: list[dict[str, Any]], primaries: list[dict[str, Any]], limit_per_code: int) -> list[dict[str, Any]]:
    by_primary = {int(row["primary_id"]): row for row in primaries}
    sample: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for row in escaped:
        code = str(row["code"])
        if counts[code] >= limit_per_code:
            continue
        primary = by_primary.get(int(row["event_id"]), {})
        sample.append(
            {
                "code": code,
                "event_id": row["event_id"],
                "family": primary.get("family", ""),
                "primary_particle": primary.get("particle", ""),
                "escaped_particle": row["particle"],
                "particle_code": row["particle_code"],
                "kinetic_energy_keV": row["kinetic_energy_keV"],
                "time_s": row["time_s"],
                "dir_x": row["dir_x"],
                "dir_y": row["dir_y"],
                "dir_z": row["dir_z"],
            }
        )
        counts[code] += 1
    return sample


def write_summary_md(out_dir: Path, summary: dict[str, Any], comparison: list[dict[str, Any]]) -> None:
    md = [
        "# Phase-2 T1 Cu-Sphere Transport Smoke",
        "",
        f"- status: `{summary['status']}`",
        f"- primary_count: `{summary['primary_count']}`",
        f"- geometry: `Copper sphere, radius {summary['geometry']['radius_cm']} cm, in vacuum`",
        f"- family_summary_csv: `{summary['family_summary_csv']}`",
        f"- comparison_csv: `{summary['comparison_csv']}`",
        "",
        "## Key Escape Yields",
        "",
        "| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib |",
        "|---|---|---:|---:|---:|",
    ]
    for row in comparison:
        if row["metric"] not in {"escaped_photon_yield", "escaped_w2_photon_yield"}:
            continue
        md.append(
            f"| {row['family']} | {row['metric']} | `{float(row['fluka']):.6g}` | "
            f"`{float(row['megalib']):.6g}` | `{float(row['fluka_over_megalib']):.6g}` |"
        )
    md.extend(
        [
            "",
            "Approximate Poisson z-scores are included in `escape_yield_comparison.csv`; low-count 511-like secondaries from the 1779/2754-keV photon rows should not be overinterpreted from ratios alone.",
        ]
    )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a T1 smoke, not the final Phase-2 transport closure.",
            "- The common T0 source table is reused; neither code resamples the source.",
            "- FLUKA escape is scored at the Cu-to-vacuum boundary; MEGAlib escape is parsed from `IA ESCP` at world escape after vacuum flight.",
            "- FLUKA copper deposit totals are included, but MEGAlib deposit-level truth is not yet part of this smoke output.",
            "- T1/T2 production closure still needs a common raw-deposit schema, annihilation-vertex/stopping observables, and deterministic W2 response.",
            "",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    ap.add_argument("--seed", type=int, default=24066601)
    ap.add_argument("--keep-run-products", action="store_true")
    ap.add_argument("--sample-rows-per-code", type=int, default=500)
    args = ap.parse_args()

    out_dir = args.out_dir.expanduser().resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    primaries = load_or_build_primaries(args.source_csv.expanduser().resolve(), args.seed)
    common_csv = out_dir / "common_primaries.csv"
    write_csv(common_csv, primaries, PRIMARY_FIELDS)

    megalib_run = run_megalib(out_dir, primaries, args.seed + 100, args.keep_run_products)
    fluka_run = run_fluka(out_dir, primaries, args.seed + 200, args.keep_run_products)
    all_escaped = list(fluka_run["escaped"]) + list(megalib_run["escaped"])
    escape_sample = bounded_escape_sample(all_escaped, primaries, args.sample_rows_per_code)

    family_rows = family_summary("FLUKA", primaries, list(fluka_run["escaped"]), dict(fluka_run["cu_deposits"]))
    family_rows += family_summary("MEGAlib", primaries, list(megalib_run["escaped"]), {})
    compare = comparison_rows(family_rows)

    family_csv = out_dir / "family_escape_summary.csv"
    comparison_csv = out_dir / "escape_yield_comparison.csv"
    sample_csv = out_dir / "escaped_particle_sample.csv"
    write_csv(family_csv, family_rows, list(family_rows[0].keys()) if family_rows else [])
    write_csv(comparison_csv, compare, list(compare[0].keys()) if compare else [])
    if escape_sample:
        write_csv(sample_csv, escape_sample, list(escape_sample[0].keys()))

    run_ok = fluka_run["returncode"] == 0 and megalib_run["returncode"] == 0
    escaped_ok = bool(fluka_run["escaped"]) and bool(megalib_run["escaped"])
    status = "T1_CU_SPHERE_TRANSPORT_SMOKE_COMPLETE" if run_ok and escaped_ok else "T1_CU_SPHERE_TRANSPORT_SMOKE_INCOMPLETE"
    summary = {
        "status": status,
        "run_type": "phase2_t1_cu_sphere_transport_smoke",
        "created_utc": now_utc(),
        "seed": args.seed,
        "source_csv": rel(args.source_csv),
        "common_primaries_csv": rel(common_csv),
        "common_primaries_sha256": sha256_path(common_csv),
        "primary_count": len(primaries),
        "geometry": {
            "shape": "sphere",
            "material": "Copper",
            "radius_cm": CU_RADIUS_CM,
            "world_half_width_cm": WORLD_HALF_WIDTH_CM,
        },
        "family_summary_csv": rel(family_csv),
        "family_summary_sha256": sha256_path(family_csv),
        "comparison_csv": rel(comparison_csv),
        "comparison_sha256": sha256_path(comparison_csv),
        "escaped_particle_sample_csv": rel(sample_csv) if escape_sample else "",
        "escaped_counts": {
            "FLUKA": len(fluka_run["escaped"]),
            "MEGAlib": len(megalib_run["escaped"]),
        },
        "runs": {
            "FLUKA": {key: value for key, value in fluka_run.items() if key not in {"escaped", "cu_deposits"}},
            "MEGAlib": {key: value for key, value in megalib_run.items() if key not in {"escaped", "cu_deposits"}},
        },
        "notes": [
            "This is a smoke gate for T1 escaped-particle response, not final Phase-2 closure.",
            "FLUKA copper deposit totals are summarized; MEGAlib deposit-level truth is deferred to the production T1/T2 gate.",
        ],
    }
    write_json(out_dir / "summary.json", summary)
    write_summary_md(out_dir, summary, compare)

    print(json.dumps({"status": status, "primary_count": len(primaries), "out_dir": rel(out_dir)}, sort_keys=True))
    return 0 if status.endswith("COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
