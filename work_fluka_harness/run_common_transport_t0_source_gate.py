#!/usr/bin/env python3
"""Run the Phase-2 T0 common-source bookkeeping gate.

This is intentionally smaller than a transport benchmark.  It builds one
code-neutral primary table, feeds that table to FLUKA and MEGAlib/EventList,
and checks that each engine starts the same particle type, kinetic energy,
direction, count, and weight before any detector response or post-processing.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import build_raw_scoring_smoke as scoring
from run_eplus_raw_mvp import env, run, write_csv, write_json


ROOT = Path(__file__).resolve().parents[1]
COSIMA = Path("/home/ubuntu/MEGAlib_Install/megalib-main/bin/cosima")
DEFAULT_OUT = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "02_common_em_transport/t0_source_bookkeeping_smoke"
)

ME_KEV = 511.0
CU64_BETA_PLUS_ENDPOINT_KEV = 653.0

PRIMARY_FIELDS = [
    "primary_id",
    "source_event_id",
    "pair_id",
    "pair_member",
    "family",
    "particle",
    "fluka_particle_code",
    "megalib_particle_code",
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
    "concurrent_with_previous",
    "seed",
    "source_note",
]

CLOSURE_FIELDS = [
    "code",
    "primary_id",
    "family",
    "particle",
    "expected_particle_code",
    "observed_particle_code",
    "expected_energy_keV",
    "observed_energy_keV",
    "energy_delta_keV",
    "energy_rel_delta",
    "expected_dir_x",
    "expected_dir_y",
    "expected_dir_z",
    "observed_dir_x",
    "observed_dir_y",
    "observed_dir_z",
    "direction_dot",
    "expected_weight",
    "observed_weight",
    "status",
]


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


def unit_vector(rng: random.Random) -> tuple[float, float, float]:
    z = 2.0 * rng.random() - 1.0
    phi = 2.0 * math.pi * rng.random()
    r = math.sqrt(max(0.0, 1.0 - z * z))
    return r * math.cos(phi), r * math.sin(phi), z


def normalized(x: float, y: float, z: float) -> tuple[float, float, float]:
    norm = math.sqrt(x * x + y * y + z * z)
    if norm <= 0.0:
        raise ValueError("zero-length vector")
    return x / norm, y / norm, z / norm


def polarization_for_direction(u: float, v: float, w: float) -> tuple[float, float, float]:
    if abs(w) < 0.9:
        return normalized(-v, u, 0.0)
    return normalized(0.0, -w, v)


def beta_plus_weight(energy_keV: float, endpoint_keV: float) -> float:
    if energy_keV <= 0.0 or energy_keV >= endpoint_keV:
        return 0.0
    total_e = energy_keV + ME_KEV
    momentum = math.sqrt(max(0.0, energy_keV * (energy_keV + 2.0 * ME_KEV)))
    return momentum * total_e * (endpoint_keV - energy_keV) ** 2


def beta_plus_max_weight(endpoint_keV: float) -> float:
    return max(beta_plus_weight(endpoint_keV * i / 1000.0, endpoint_keV) for i in range(1, 1000))


def sample_cu64_beta_plus_energy(rng: random.Random, endpoint_keV: float = CU64_BETA_PLUS_ENDPOINT_KEV) -> float:
    max_w = beta_plus_max_weight(endpoint_keV)
    while True:
        e = endpoint_keV * rng.random()
        if rng.random() * max_w <= beta_plus_weight(e, endpoint_keV):
            return e


def add_primary(
    rows: list[dict[str, Any]],
    *,
    rng: random.Random,
    seed: int,
    family: str,
    particle: str,
    energy_keV: float,
    direction: tuple[float, float, float] | None = None,
    pair_id: str = "",
    pair_member: int = 0,
    note: str = "",
) -> None:
    if direction is None:
        direction = unit_vector(rng)
    u, v, w = normalized(*direction)
    px, py, pz = polarization_for_direction(u, v, w)
    primary_id = len(rows) + 1
    if particle == "gamma":
        fluka_code = 7
        megalib_code = 1
    elif particle == "eplus":
        fluka_code = 4
        megalib_code = 2
    else:
        raise ValueError(f"unsupported particle: {particle}")
    rows.append(
        {
            "primary_id": primary_id,
            "source_event_id": primary_id,
            "pair_id": pair_id,
            "pair_member": pair_member,
            "family": family,
            "particle": particle,
            "fluka_particle_code": fluka_code,
            "megalib_particle_code": megalib_code,
            "kinetic_energy_keV": energy_keV,
            "x_cm": 0.0,
            "y_cm": 0.0,
            "z_cm": 0.0,
            "dir_x": u,
            "dir_y": v,
            "dir_z": w,
            "pol_x": px,
            "pol_y": py,
            "pol_z": pz,
            "weight": 1.0,
            "concurrent_with_previous": 0,
            "seed": seed,
            "source_note": note,
        }
    )


def build_common_primaries(
    *,
    seed: int,
    mono511: int,
    pair511: int,
    high_gamma_each: int,
    positrons: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for _ in range(mono511):
        add_primary(
            rows,
            rng=rng,
            seed=seed,
            family="mono511_gamma",
            particle="gamma",
            energy_keV=511.0,
            note="T0 monoenergetic 511 keV photon",
        )
    for idx in range(pair511):
        u, v, w = unit_vector(rng)
        pair_id = f"pair511_{idx + 1:06d}"
        add_primary(
            rows,
            rng=rng,
            seed=seed,
            family="pair511_gamma",
            particle="gamma",
            energy_keV=511.0,
            direction=(u, v, w),
            pair_id=pair_id,
            pair_member=1,
            note="Back-to-back pair row; T0 transports rows independently",
        )
        add_primary(
            rows,
            rng=rng,
            seed=seed,
            family="pair511_gamma",
            particle="gamma",
            energy_keV=511.0,
            direction=(-u, -v, -w),
            pair_id=pair_id,
            pair_member=2,
            note="Back-to-back pair row; T0 transports rows independently",
        )
    for energy_keV, family in ((1779.0, "mono1779_gamma"), (2754.0, "mono2754_gamma")):
        for _ in range(high_gamma_each):
            add_primary(
                rows,
                rng=rng,
                seed=seed,
                family=family,
                particle="gamma",
                energy_keV=energy_keV,
                note="High-energy mono-gamma transport sentinel",
            )
    for _ in range(positrons):
        add_primary(
            rows,
            rng=rng,
            seed=seed,
            family="cu64_eplus_smoke",
            particle="eplus",
            energy_keV=sample_cu64_beta_plus_energy(rng),
            note=(
                "Frozen allowed-spectrum smoke sampler; production T1/T2 should "
                "replace this with the evaluated/reference Cu-64 beta+ generator"
            ),
        )
    return rows


def write_megalib_geometry(path: Path) -> None:
    text = "\n".join(
        [
            "Name T0VacuumSourceGate",
            "Version 2.0",
            "",
            "SurroundingSphere 100 0.0 0.0 0.0 100",
            "Include $(MEGALIB)/resource/examples/geomega/materials/Materials.geo",
            "",
            "Volume WorldVolume",
            "WorldVolume.Material Vacuum",
            "WorldVolume.Visibility 0",
            "WorldVolume.Shape BRIK 100. 100. 100.",
            "WorldVolume.Mother 0",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def write_megalib_eventlist(path: Path, primaries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as handle:
        for row in primaries:
            handle.write(
                f"{int(row['primary_id'])} {int(row['concurrent_with_previous'])} "
                f"{int(row['megalib_particle_code'])} 0 "
                f"{int(row['primary_id']) * 1.0e-9:.12E} "
                f"{float(row['x_cm']):.12g} {float(row['y_cm']):.12g} {float(row['z_cm']):.12g} "
                f"{float(row['dir_x']):.12g} {float(row['dir_y']):.12g} {float(row['dir_z']):.12g} "
                f"{float(row['pol_x']):.12g} {float(row['pol_y']):.12g} {float(row['pol_z']):.12g} "
                f"{float(row['kinetic_energy_keV']):.12g}\n"
            )


def write_megalib_source(path: Path, geometry: Path, eventlist: Path, out_prefix: Path, n_events: int) -> None:
    run_name = "T0SourceGate"
    source_name = "CommonPrimaryList"
    text = "\n".join(
        [
            "Version 1",
            f"Geometry {geometry}",
            "PhysicsListEM LivermorePol",
            "StoreSimulationInfo all",
            "StoreSimulationInfoIonization false",
            "DiscretizeHits true",
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


def parse_megalib_init(sim_path: Path) -> list[dict[str, Any]]:
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
        if not line.startswith("IA INIT"):
            continue
        parts = [part.strip() for part in line.split("IA INIT", 1)[1].split(";")]
        if len(parts) < 23:
            continue
        try:
            out.append(
                {
                    "event_id": current_event,
                    "particle_code": int(parts[15]),
                    "kinetic_energy_keV": float(parts[22]),
                    "dir_x": float(parts[16]),
                    "dir_y": float(parts[17]),
                    "dir_z": float(parts[18]),
                    "x_cm": float(parts[4]),
                    "y_cm": float(parts[5]),
                    "z_cm": float(parts[6]),
                    "weight": 1.0,
                }
            )
        except ValueError:
            continue
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
    geometry = input_dir / "t0_vacuum_source_gate.geo.setup"
    eventlist = input_dir / "common_eventlist.dat"
    source = input_dir / "t0_source_gate.source"
    out_prefix = run_dir / "t0_source_gate"
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
    observed = parse_megalib_init(sim_file)
    sim_file_generated = sim_file.exists()
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
        "sim_file_generated": sim_file_generated,
        "sim_file": rel(sim_file),
        "run_products_retained": keep_run_products,
        "cosima_log": rel(log_path),
        "observed": observed,
    }


SOURCE_FORTRAN = """*
* Common-primary T0 source gate.
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
* Source-boundary scorer for the T0 common-primary gate.
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
      DOUBLE PRECISION KINKEV
      LOGICAL LFOPEN
      SAVE LFOPEN
      DATA LFOPEN / .FALSE. /

      RETURN

      ENTRY BXDRAW ( ICODE, MREG, NEWREG, XSCO, YSCO, ZSCO )
      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=88, FILE='source_boundary_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (88,'(A)') 'event_id,particle_code,kinetic_energy_keV,'//
     &        'time_s,dir_x,dir_y,dir_z,x_cm,y_cm,z_cm,weight,'//
     &        'track_generation'
         LFOPEN = .TRUE.
      END IF

      CALL GEOR2N ( MREG, NAMREG, IERR )
      CALL GEOR2N ( NEWREG, NEWNAM, JERR )
      IF ( IERR .EQ. 0 .AND. JERR .EQ. 0 .AND.
     &     NAMREG .EQ. 'INNER' .AND. NEWNAM .EQ. 'OUTER' ) THEN
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
      RETURN

      ENTRY ENDRAW ( ICODE, MREG, RULL, XSCO, YSCO, ZSCO )
      RETURN

      ENTRY SODRAW
      RETURN

      ENTRY USDRAW ( ICODE, MREG, XSCO, YSCO, ZSCO )
      RETURN

 1000 FORMAT(I12,',',I8,',',1PE16.8,',',1PE16.8,
     & ',',1PE16.8,',',1PE16.8,',',1PE16.8,',',1PE16.8,
     & ',',1PE16.8,',',1PE16.8,',',1PE16.8,',',I8)
      END
"""


def compile_fluka_executable(run_dir: Path) -> Path:
    routine_dir = run_dir / "scoring_routines"
    routine_dir.mkdir(parents=True, exist_ok=True)
    source_path = routine_dir / "source_t0_common.f"
    mgdraw_path = routine_dir / "mgdraw_t0_common.f"
    source_path.write_text(SOURCE_FORTRAN, encoding="ascii")
    mgdraw_path.write_text(MGDRAW_FORTRAN, encoding="ascii")
    subprocess.run(
        [str(scoring.FFF), source_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_source_t0_common.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.FFF), mgdraw_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_mgdraw_t0_common.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.LDPMQMD), "-m", "fluka", "-o", "fluka_t0_common", "source_t0_common.o", "mgdraw_t0_common.o"],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "link_fluka_t0_common.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    return routine_dir / "fluka_t0_common"


def t0_fluka_input(histories: int, seed: int, beam_gev: float) -> str:
    fluka_seed = int(seed) % 900000
    if fluka_seed <= 0:
        fluka_seed = 1
    return (
        "GLOBAL         20000         0         1         0         0         0\n"
        "TITLE\n"
        "TES511 common-primary T0 source gate\n"
        "DEFAULTS                                                              EM-CASCA\n"
        f"BEAM      {beam_gev:10.6g}                                                  PHOTON\n"
        "SOURCE\n"
        "GEOBEGIN                                                              COMBNAME\n"
        "  0 0                       Common-primary T0 vacuum sphere\n"
        "RPP BIGBOX -1000000.0 +1000000.0 -1000000.0 +1000000.0 -1000000.0 +1000000.0\n"
        "RPP WORLD  -100.0 +100.0 -100.0 +100.0 -100.0 +100.0\n"
        "SPH SPHIN 0.0 0.0 0.0 1.0\n"
        "END\n"
        "BLKHOLE 5 +BIGBOX -WORLD\n"
        "OUTER    5 +WORLD -SPHIN\n"
        "INNER    5 +SPHIN\n"
        "END\n"
        "GEOEND\n"
        "ASSIGNMAT  BLCKHOLE  BLKHOLE\n"
        "ASSIGNMAT    VACUUM    INNER\n"
        "ASSIGNMAT    VACUUM    OUTER\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0     INNER\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0     OUTER\n"
        + f"{'USERDUMP':<10}{100.0:10.1f}{99.0:10.1f}{6.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}RAWDUMP\n"
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def write_fluka_primaries(path: Path, primaries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as handle:
        for row in primaries:
            handle.write(
                f"{int(row['fluka_particle_code']):d} {float(row['kinetic_energy_keV']) / 1.0e6:.10e} "
                f"{float(row['x_cm']):.8e} {float(row['y_cm']):.8e} {float(row['z_cm']):.8e} "
                f"{float(row['dir_x']):.8e} {float(row['dir_y']):.8e} {float(row['dir_z']):.8e} "
                f"{float(row['weight']):.8e}\n"
            )


def rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def parse_fluka_boundary(path: Path) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    if not path.exists():
        return observed
    for row in rows_from_csv(path):
        observed.append(
            {
                "event_id": int(row["event_id"]),
                "particle_code": int(row["particle_code"]),
                "kinetic_energy_keV": float(row["kinetic_energy_keV"]),
                "dir_x": float(row["dir_x"]),
                "dir_y": float(row["dir_y"]),
                "dir_z": float(row["dir_z"]),
                "x_cm": float(row["x_cm"]),
                "y_cm": float(row["y_cm"]),
                "z_cm": float(row["z_cm"]),
                "weight": float(row["weight"]),
            }
        )
    observed.sort(key=lambda item: int(item["event_id"]))
    return observed


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
    tracked_input = input_dir / "t0_source_gate.inp"
    write_fluka_primaries(tracked_primaries, primaries)
    max_gev = max(float(row["kinetic_energy_keV"]) / 1.0e6 for row in primaries)
    tracked_input.write_text(t0_fluka_input(len(primaries), seed, max(0.001, max_gev * 1.05)), encoding="ascii")
    shutil.copyfile(tracked_primaries, run_dir / "primaries.dat")
    shutil.copyfile(tracked_input, run_dir / "t0_source_gate.inp")

    exe = compile_fluka_executable(run_dir)
    started = now_utc()
    t0 = time.time()
    returncode = run([str(scoring.RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", "t0_source_gate"], run_dir, run_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()
    candidates = sorted(run_dir.glob("*source_boundary_tmp.csv"))
    raw_path = candidates[-1] if candidates else run_dir / "source_boundary_tmp.csv"
    observed = parse_fluka_boundary(raw_path)
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
        "observed": observed,
    }


def closure_rows(
    code: str,
    primaries: list[dict[str, Any]],
    observed: list[dict[str, Any]],
    particle_code_field: str,
    energy_rel_tolerance: float,
    direction_dot_tolerance: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, expected in enumerate(primaries):
        obs = observed[idx] if idx < len(observed) else None
        expected_energy = float(expected["kinetic_energy_keV"])
        expected_code = int(expected[particle_code_field])
        expected_dir = (
            float(expected["dir_x"]),
            float(expected["dir_y"]),
            float(expected["dir_z"]),
        )
        if obs is None:
            rows.append(
                {
                    "code": code,
                    "primary_id": expected["primary_id"],
                    "family": expected["family"],
                    "particle": expected["particle"],
                    "expected_particle_code": expected_code,
                    "observed_particle_code": "",
                    "expected_energy_keV": expected_energy,
                    "observed_energy_keV": "",
                    "energy_delta_keV": "",
                    "energy_rel_delta": "",
                    "expected_dir_x": expected_dir[0],
                    "expected_dir_y": expected_dir[1],
                    "expected_dir_z": expected_dir[2],
                    "observed_dir_x": "",
                    "observed_dir_y": "",
                    "observed_dir_z": "",
                    "direction_dot": "",
                    "expected_weight": expected["weight"],
                    "observed_weight": "",
                    "status": "MISSING",
                }
            )
            continue
        observed_energy = float(obs["kinetic_energy_keV"])
        energy_delta = observed_energy - expected_energy
        energy_rel = abs(energy_delta) / max(abs(expected_energy), 1.0e-30)
        observed_dir = normalized(float(obs["dir_x"]), float(obs["dir_y"]), float(obs["dir_z"]))
        direction_dot = sum(a * b for a, b in zip(expected_dir, observed_dir))
        p_ok = int(obs["particle_code"]) == expected_code
        e_ok = energy_rel <= energy_rel_tolerance
        d_ok = 1.0 - direction_dot <= direction_dot_tolerance
        w_ok = abs(float(obs.get("weight", 1.0)) - float(expected["weight"])) <= 1.0e-9
        rows.append(
            {
                "code": code,
                "primary_id": expected["primary_id"],
                "family": expected["family"],
                "particle": expected["particle"],
                "expected_particle_code": expected_code,
                "observed_particle_code": int(obs["particle_code"]),
                "expected_energy_keV": expected_energy,
                "observed_energy_keV": observed_energy,
                "energy_delta_keV": energy_delta,
                "energy_rel_delta": energy_rel,
                "expected_dir_x": expected_dir[0],
                "expected_dir_y": expected_dir[1],
                "expected_dir_z": expected_dir[2],
                "observed_dir_x": observed_dir[0],
                "observed_dir_y": observed_dir[1],
                "observed_dir_z": observed_dir[2],
                "direction_dot": direction_dot,
                "expected_weight": expected["weight"],
                "observed_weight": float(obs.get("weight", 1.0)),
                "status": "PASS" if p_ok and e_ok and d_ok and w_ok else "FAIL",
            }
        )
    if len(observed) > len(primaries):
        for extra_idx, obs in enumerate(observed[len(primaries) :], start=len(primaries) + 1):
            rows.append(
                {
                    "code": code,
                    "primary_id": extra_idx,
                    "family": "EXTRA",
                    "particle": "",
                    "expected_particle_code": "",
                    "observed_particle_code": int(obs["particle_code"]),
                    "expected_energy_keV": "",
                    "observed_energy_keV": float(obs["kinetic_energy_keV"]),
                    "energy_delta_keV": "",
                    "energy_rel_delta": "",
                    "expected_dir_x": "",
                    "expected_dir_y": "",
                    "expected_dir_z": "",
                    "observed_dir_x": float(obs["dir_x"]),
                    "observed_dir_y": float(obs["dir_y"]),
                    "observed_dir_z": float(obs["dir_z"]),
                    "direction_dot": "",
                    "expected_weight": "",
                    "observed_weight": float(obs.get("weight", 1.0)),
                    "status": "EXTRA",
                }
            )
    return rows


def summarize_closure(rows: list[dict[str, Any]], expected_count: int) -> dict[str, Any]:
    observed_rows = [row for row in rows if row["status"] != "MISSING"]
    pass_rows = [row for row in rows if row["status"] == "PASS"]
    fail_rows = [row for row in rows if row["status"] in {"FAIL", "MISSING", "EXTRA"}]
    energy_rels = [float(row["energy_rel_delta"]) for row in rows if row["energy_rel_delta"] != ""]
    direction_gaps = [1.0 - float(row["direction_dot"]) for row in rows if row["direction_dot"] != ""]
    count_rel_delta = abs(len(observed_rows) - expected_count) / max(expected_count, 1)
    status = "PASS" if not fail_rows and count_rel_delta <= 1.0e-3 else "FAIL"
    return {
        "status": status,
        "expected_count": expected_count,
        "observed_count": len(observed_rows),
        "pass_count": len(pass_rows),
        "fail_or_missing_count": len(fail_rows),
        "count_rel_delta": count_rel_delta,
        "max_energy_rel_delta": max(energy_rels) if energy_rels else "",
        "max_direction_1_minus_dot": max(direction_gaps) if direction_gaps else "",
    }


def family_counts(primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for row in primaries:
        key = (str(row["family"]), str(row["particle"]))
        counts[key] = counts.get(key, 0) + 1
    return [
        {"family": family, "particle": particle, "count": count}
        for (family, particle), count in sorted(counts.items())
    ]


def write_summary_md(out_dir: Path, summary: dict[str, Any]) -> None:
    md = [
        "# Phase-2 T0 Common-Source Bookkeeping Gate",
        "",
        f"- status: `{summary['status']}`",
        f"- primary_count: `{summary['primary_count']}`",
        f"- seed: `{summary['seed']}`",
        f"- common_primaries_csv: `{summary['common_primaries_csv']}`",
        f"- closure_comparison_csv: `{summary['closure_comparison_csv']}`",
        "",
        "## Source Mix",
        "",
        "| family | particle | count |",
        "|---|---|---:|",
    ]
    for row in summary["family_counts"]:
        md.append(f"| {row['family']} | {row['particle']} | `{row['count']}` |")
    md.extend(["", "## Engine Closure", "", "| code | status | observed / expected | max energy rel delta | max direction 1-dot |", "|---|---|---:|---:|---:|"])
    for code in ("FLUKA", "MEGAlib"):
        item = summary["engine_closure"][code]
        md.append(
            f"| {code} | `{item['status']}` | `{item['observed_count']} / {item['expected_count']}` | "
            f"`{item['max_energy_rel_delta']}` | `{item['max_direction_1_minus_dot']}` |"
        )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is not a detector-rate or W2-efficiency result.",
            "- Every primary row is explicit in the common CSV; neither code resamples source energy or direction.",
            "- Back-to-back 511 rows retain a `pair_id`, but T0 transports rows independently to test bookkeeping.",
            "- The Cu-64 positron rows use a frozen allowed-spectrum smoke sampler only; T1/T2 production should replace it with the evaluated/reference beta-plus generator.",
            "- Raw FLUKA and Cosima run products are ignored and deleted by default; tracked outputs are compact source and closure tables.",
            "",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=24066501)
    ap.add_argument("--mono511", type=int, default=512)
    ap.add_argument("--pair511", type=int, default=256)
    ap.add_argument("--high-gamma-each", type=int, default=256)
    ap.add_argument("--positrons", type=int, default=512)
    ap.add_argument("--energy-rel-tolerance", type=float, default=1.0e-3)
    ap.add_argument("--direction-dot-tolerance", type=float, default=1.0e-6)
    ap.add_argument("--keep-run-products", action="store_true")
    args = ap.parse_args()

    if min(args.mono511, args.pair511, args.high_gamma_each, args.positrons) < 0:
        raise SystemExit("source counts must be non-negative")

    out_dir = args.out_dir.expanduser().resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    primaries = build_common_primaries(
        seed=args.seed,
        mono511=args.mono511,
        pair511=args.pair511,
        high_gamma_each=args.high_gamma_each,
        positrons=args.positrons,
    )
    primary_csv = out_dir / "common_primaries.csv"
    write_csv(primary_csv, primaries, PRIMARY_FIELDS)

    megalib_run = run_megalib(out_dir, primaries, args.seed + 100, args.keep_run_products)
    fluka_run = run_fluka(out_dir, primaries, args.seed + 200, args.keep_run_products)

    megalib_closure = closure_rows(
        "MEGAlib",
        primaries,
        list(megalib_run["observed"]),
        "megalib_particle_code",
        args.energy_rel_tolerance,
        args.direction_dot_tolerance,
    )
    fluka_closure = closure_rows(
        "FLUKA",
        primaries,
        list(fluka_run["observed"]),
        "fluka_particle_code",
        args.energy_rel_tolerance,
        args.direction_dot_tolerance,
    )
    combined = fluka_closure + megalib_closure
    closure_csv = out_dir / "closure_comparison.csv"
    write_csv(closure_csv, combined, CLOSURE_FIELDS)

    engine_closure = {
        "FLUKA": summarize_closure(fluka_closure, len(primaries)),
        "MEGAlib": summarize_closure(megalib_closure, len(primaries)),
    }
    status = "PASS" if all(item["status"] == "PASS" for item in engine_closure.values()) else "FAIL"
    summary = {
        "status": "T0_COMMON_SOURCE_GATE_" + status,
        "run_type": "phase2_t0_common_source_bookkeeping_smoke",
        "created_utc": now_utc(),
        "seed": args.seed,
        "primary_count": len(primaries),
        "source_counts": {
            "mono511": args.mono511,
            "pair511_pairs": args.pair511,
            "high_gamma_each": args.high_gamma_each,
            "positrons": args.positrons,
        },
        "acceptance": {
            "count_rel_delta_max": 1.0e-3,
            "energy_rel_tolerance": args.energy_rel_tolerance,
            "direction_1_minus_dot_tolerance": args.direction_dot_tolerance,
        },
        "common_primaries_csv": rel(primary_csv),
        "common_primaries_sha256": sha256_path(primary_csv),
        "closure_comparison_csv": rel(closure_csv),
        "closure_comparison_sha256": sha256_path(closure_csv),
        "family_counts": family_counts(primaries),
        "engine_closure": engine_closure,
        "runs": {
            "FLUKA": {key: value for key, value in fluka_run.items() if key != "observed"},
            "MEGAlib": {key: value for key, value in megalib_run.items() if key != "observed"},
        },
        "notes": [
            "This gate validates source bookkeeping only, not detector transport or W2 efficiency.",
            "The common CSV is the source of authority for both engines.",
            "Raw run products are deleted by default and ignored if retained.",
        ],
    }
    write_json(out_dir / "summary.json", summary)
    write_csv(out_dir / "source_family_counts.csv", family_counts(primaries), ["family", "particle", "count"])
    write_summary_md(out_dir, summary)

    print(json.dumps({"status": summary["status"], "primary_count": len(primaries), "out_dir": rel(out_dir)}, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
