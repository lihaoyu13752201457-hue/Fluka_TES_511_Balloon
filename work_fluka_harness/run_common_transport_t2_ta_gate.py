#!/usr/bin/env python3
"""Run the Phase-2 T2 minimal Cu+Ta absorber transport smoke.

The geometry is deliberately simple: the common source starts inside a 1 cm
copper sphere, and a single idealized tantalum absorber slab sits downstream.
This smoke checks whether both engines can run the same explicit source list
through a Cu+Ta toy and produce comparable Ta deposited-energy summaries.  It
is not a substitute for the production T2/TES closure.
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
from run_common_transport_t0_source_gate import COSIMA, PRIMARY_FIELDS, rel, sha256_path, write_fluka_primaries, write_megalib_eventlist
from run_common_transport_t1_cu_gate import SOURCE_FORTRAN, load_or_build_primaries, rows_from_csv
from run_eplus_raw_mvp import env, run, write_json


ROOT = Path(__file__).resolve().parents[1]
T0_SOURCE_CSV = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "02_common_em_transport/t0_source_bookkeeping_smoke/common_primaries.csv"
)
DEFAULT_OUT = (
    ROOT
    / "engineering/crosscode_delayed_closure_20260625"
    / "02_common_em_transport/t2_cu_ta_absorber_transport_smoke"
)
PROJECT_MATERIALS = (
    Path("/home/ubuntu/TES_511_Balloon")
    / "outputs/geometry/DEMO2_DR_v3p5_user_cylmag_redesign_multiholeW_fix5_20260621_megalib_proxy"
    / "Materials_DEMO2_DR_v3p5.geo"
)

CU_RADIUS_CM = 1.0
TA_HALF_X_CM = 2.0
TA_HALF_Y_CM = 2.0
TA_HALF_Z_CM = 0.05
TA_CENTER_Z_CM = 3.0
WORLD_HALF_WIDTH_CM = 100.0


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


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


def write_megalib_geometry(path: Path) -> None:
    text = "\n".join(
        [
            "Name T2CuTaAbsorberTransportSmoke",
            "Version 2.0",
            "",
            f"SurroundingSphere {WORLD_HALF_WIDTH_CM} 0.0 0.0 0.0 {WORLD_HALF_WIDTH_CM}",
            f"Include {PROJECT_MATERIALS}",
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
            "Volume TaAbsorber",
            "TaAbsorber.Material Ta",
            "TaAbsorber.Visibility 1",
            "TaAbsorber.Color 2",
            f"TaAbsorber.Shape BRIK {TA_HALF_X_CM} {TA_HALF_Y_CM} {TA_HALF_Z_CM}",
            f"TaAbsorber.Position 0.0 0.0 {TA_CENTER_Z_CM}",
            "TaAbsorber.Mother WorldVolume",
            "",
            "MDStrip3D TaDetector",
            "TaDetector.DetectorVolume TaAbsorber",
            "TaDetector.SensitiveVolume TaAbsorber",
            "TaDetector.Offset 0.0 0.0",
            "TaDetector.StripNumber 1 1",
            "TaDetector.NoiseThreshold 0.0001",
            "TaDetector.TriggerThreshold 0.0001",
            "TaDetector.EnergyResolution Ideal",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def write_megalib_source(path: Path, geometry: Path, eventlist: Path, out_prefix: Path, n_events: int) -> None:
    run_name = "T2CuTaAbsorber"
    source_name = "CommonPrimaryList"
    text = "\n".join(
        [
            "Version 1",
            f"Geometry {geometry}",
            "PhysicsListEM LivermorePol",
            "StoreSimulationInfo all",
            "StoreSimulationInfoIonization false",
            "StoreCalibrated true",
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


def parse_htsim(line: str, event_id: int) -> dict[str, Any] | None:
    if not line.startswith("HTsim"):
        return None
    fields = [field.strip() for field in line[len("HTsim") :].split(";")]
    if len(fields) < 5:
        return None
    try:
        return {
            "event_id": event_id,
            "detector": fields[0],
            "x_cm": float(fields[1]),
            "y_cm": float(fields[2]),
            "z_cm": float(fields[3]),
            "deposit_keV": float(fields[4]),
            "time_s": float(fields[5]) if len(fields) > 5 else 0.0,
        }
    except ValueError:
        return None


def parse_megalib_ta_hits(sim_path: Path) -> tuple[dict[int, float], list[dict[str, Any]], int]:
    totals: dict[int, float] = defaultdict(float)
    sample: list[dict[str, Any]] = []
    event_id = 0
    event_count = 0
    if not sim_path.exists():
        return {}, [], 0
    for raw in open_sim(sim_path):
        line = raw.strip()
        if line.startswith("ID "):
            event_count += 1
            parts = line.split()
            if len(parts) >= 2:
                try:
                    event_id = int(parts[1])
                except ValueError:
                    event_id = event_count
        elif line.startswith("HTsim"):
            hit = parse_htsim(line, event_id)
            if hit is None:
                continue
            totals[event_id] += float(hit["deposit_keV"])
            if len(sample) < 500:
                sample.append(hit)
    return dict(totals), sample, event_count


def run_megalib(out_dir: Path, primaries: list[dict[str, Any]], seed: int, keep_run_products: bool) -> dict[str, Any]:
    run_dir = out_dir / "cosima_run"
    input_dir = out_dir / "megalib_inputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    geometry = input_dir / "t2_cu_ta_absorber.geo.setup"
    eventlist = input_dir / "common_eventlist.dat"
    source = input_dir / "t2_cu_ta_absorber.source"
    out_prefix = run_dir / "t2_cu_ta_absorber"
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
    totals, sample, event_count = parse_megalib_ta_hits(sim_file)
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
        "sim_event_count": event_count,
        "run_products_retained": keep_run_products,
        "cosima_log": rel(log_path),
        "ta_deposits": totals,
        "ta_hit_sample": sample,
    }


MGDRAW_FORTRAN = """*
* Tantalum absorber deposit scorer for the T2 common-primary smoke.
*
      SUBROUTINE MGDRAW ( ICODE, MREG )
      INCLUDE 'dblprc.inc'
      INCLUDE 'dimpar.inc'
      INCLUDE 'iounit.inc'
      INCLUDE 'caslim.inc'
      INCLUDE 'trackr.inc'
      CHARACTER*8 NAMREG
      INTEGER IERR, I
      DOUBLE PRECISION DEPKEV
      DOUBLE PRECISION TADEP
      LOGICAL LFOPEN
      SAVE LFOPEN, TADEP
      DATA LFOPEN / .FALSE. /
      DATA TADEP / 0.0D0 /

      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=87, FILE='ta_event_totals_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (87,'(A)') 'event_id,ta_deposit_keV'
         LFOPEN = .TRUE.
      END IF

      CALL GEOR2N ( MREG, NAMREG, IERR )
      IF ( IERR .EQ. 0 .AND. NAMREG .EQ. 'TAREG' ) THEN
         IF ( MTRACK .GT. 0 ) THEN
            DEPKEV = 0.0D0
            DO I = 1, MTRACK
               IF ( DTRACK(I) .GT. 0.0D0 ) THEN
                  DEPKEV = DEPKEV + DBLE(DTRACK(I)) * 1.0D6
               END IF
            END DO
            TADEP = TADEP + DEPKEV
         END IF
      END IF
      RETURN

      ENTRY BXDRAW ( ICODE, MREG, NEWREG, XSCO, YSCO, ZSCO )
      RETURN

      ENTRY EEDRAW ( ICODE )
      IF ( LFOPEN ) THEN
         WRITE (87,1010) NCASE, TADEP
      END IF
      TADEP = 0.0D0
      RETURN

      ENTRY ENDRAW ( ICODE, MREG, RULL, XSCO, YSCO, ZSCO )
      CALL GEOR2N ( MREG, NAMREG, IERR )
      IF ( IERR .EQ. 0 .AND. NAMREG .EQ. 'TAREG' .AND.
     &     RULL .GT. 0.0D0 ) THEN
         TADEP = TADEP + DBLE(RULL) * 1.0D6
      END IF
      RETURN

      ENTRY SODRAW
      RETURN

      ENTRY USDRAW ( ICODE, MREG, XSCO, YSCO, ZSCO )
      RETURN

 1010 FORMAT(I12,',',1PE16.8)
      END
"""


def compile_fluka_executable(run_dir: Path) -> Path:
    routine_dir = run_dir / "scoring_routines"
    routine_dir.mkdir(parents=True, exist_ok=True)
    source_path = routine_dir / "source_t2_ta.f"
    mgdraw_path = routine_dir / "mgdraw_t2_ta.f"
    source_path.write_text(SOURCE_FORTRAN, encoding="ascii")
    mgdraw_path.write_text(MGDRAW_FORTRAN, encoding="ascii")
    subprocess.run(
        [str(scoring.FFF), source_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_source_t2_ta.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.FFF), mgdraw_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_mgdraw_t2_ta.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.LDPMQMD), "-m", "fluka", "-o", "fluka_t2_ta", "source_t2_ta.o", "mgdraw_t2_ta.o"],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "link_fluka_t2_ta.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    return routine_dir / "fluka_t2_ta"


def t2_fluka_input(histories: int, seed: int, beam_gev: float) -> str:
    fluka_seed = int(seed) % 900000
    if fluka_seed <= 0:
        fluka_seed = 1
    z_min = TA_CENTER_Z_CM - TA_HALF_Z_CM
    z_max = TA_CENTER_Z_CM + TA_HALF_Z_CM
    return (
        "GLOBAL         20000         0         1         0         0         0\n"
        "TITLE\n"
        "TES511 common-primary T2 Cu-Ta absorber smoke\n"
        "DEFAULTS                                                              EM-CASCA\n"
        f"BEAM      {beam_gev:10.6g}                                                  PHOTON\n"
        "SOURCE\n"
        "GEOBEGIN                                                              COMBNAME\n"
        "  0 0                       Common-primary T2 Cu-Ta absorber\n"
        "RPP BIGBOX -1000000.0 +1000000.0 -1000000.0 +1000000.0 -1000000.0 +1000000.0\n"
        f"RPP WORLD  -{WORLD_HALF_WIDTH_CM:.1f} +{WORLD_HALF_WIDTH_CM:.1f} -{WORLD_HALF_WIDTH_CM:.1f} +{WORLD_HALF_WIDTH_CM:.1f} -{WORLD_HALF_WIDTH_CM:.1f} +{WORLD_HALF_WIDTH_CM:.1f}\n"
        f"SPH CUSPH 0.0 0.0 0.0 {CU_RADIUS_CM:.6f}\n"
        f"RPP TASLAB -{TA_HALF_X_CM:.6f} +{TA_HALF_X_CM:.6f} -{TA_HALF_Y_CM:.6f} +{TA_HALF_Y_CM:.6f} {z_min:.6f} {z_max:.6f}\n"
        "END\n"
        "BLKHOLE 5 +BIGBOX -WORLD\n"
        "TAREG    5 +TASLAB\n"
        "CU       5 +CUSPH\n"
        "OUTER    5 +WORLD -CUSPH -TASLAB\n"
        "END\n"
        "GEOEND\n"
        "ASSIGNMAT  BLCKHOLE  BLKHOLE\n"
        "ASSIGNMAT    VACUUM    OUTER\n"
        "ASSIGNMAT    COPPER       CU\n"
        "ASSIGNMAT  TANTALUM    TAREG\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0        CU\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0     TAREG\n"
        "EMFCUT      -1.0E-05   1.0E-05       0.0     OUTER\n"
        + f"{'USERDUMP':<10}{100.0:10.1f}{99.0:10.1f}{6.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}RAWDUMP\n"
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def parse_fluka_ta_totals(path: Path) -> dict[int, float]:
    out: dict[int, float] = {}
    if not path.exists():
        return out
    for row in rows_from_csv(path):
        out[int(row["event_id"])] = float(row["ta_deposit_keV"])
    return out


def run_fluka(out_dir: Path, primaries: list[dict[str, Any]], seed: int, keep_run_products: bool) -> dict[str, Any]:
    run_dir = out_dir / "fluka_run"
    input_dir = out_dir / "fluka_inputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    tracked_primaries = input_dir / "primaries.dat"
    tracked_input = input_dir / "t2_cu_ta_absorber.inp"
    write_fluka_primaries(tracked_primaries, primaries)
    max_gev = max(float(row["kinetic_energy_keV"]) / 1.0e6 for row in primaries)
    tracked_input.write_text(t2_fluka_input(len(primaries), seed, max(0.001, max_gev * 1.05)), encoding="ascii")
    shutil.copyfile(tracked_primaries, run_dir / "primaries.dat")
    shutil.copyfile(tracked_input, run_dir / "t2_cu_ta_absorber.inp")

    exe = compile_fluka_executable(run_dir)
    started = now_utc()
    t0 = time.time()
    returncode = run([str(scoring.RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", "t2_cu_ta_absorber"], run_dir, run_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()
    candidates = sorted(run_dir.glob("*ta_event_totals_tmp.csv"))
    total_path = candidates[-1] if candidates else run_dir / "ta_event_totals_tmp.csv"
    totals = parse_fluka_ta_totals(total_path)
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
        "ta_deposits": totals,
    }


def family_summary(code: str, primaries: list[dict[str, Any]], deposits: dict[int, float]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in primaries:
        by_family[str(row["family"])].append(row)
    out: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        event_ids = [int(row["primary_id"]) for row in rows]
        values = [deposits.get(event_id, 0.0) for event_id in event_ids]
        nonzero = [v for v in values if v > 0.0]
        broad = [v for v in values if 480.0 <= v <= 550.0]
        w2 = [v for v in values if 510.58 <= v <= 511.42]
        n = len(values)
        out.append(
            {
                "code": code,
                "family": family,
                "particle": rows[0]["particle"],
                "histories": n,
                "events_with_ta_deposit": len(nonzero),
                "ta_deposit_efficiency": len(nonzero) / n if n else 0.0,
                "events_480_550_keV": len(broad),
                "eff_480_550": len(broad) / n if n else 0.0,
                "events_w2_510p58_511p42": len(w2),
                "eff_w2_510p58_511p42": len(w2) / n if n else 0.0,
                "mean_ta_deposit_keV_all": sum(values) / n if n else 0.0,
                "mean_ta_deposit_keV_nonzero": sum(nonzero) / len(nonzero) if nonzero else 0.0,
            }
        )
    return out


def comparison_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["code"], row["family"]): row for row in summary_rows}
    metrics = {
        "ta_deposit_efficiency": "events_with_ta_deposit",
        "eff_480_550": "events_480_550_keV",
        "eff_w2_510p58_511p42": "events_w2_510p58_511p42",
    }
    out: list[dict[str, Any]] = []
    for family in sorted({row["family"] for row in summary_rows}):
        f = by_key.get(("FLUKA", family))
        g = by_key.get(("MEGAlib", family))
        if not f or not g:
            continue
        for metric, count_key in metrics.items():
            fval = float(f[metric])
            gval = float(g[metric])
            fcount = float(f[count_key])
            gcount = float(g[count_key])
            sigma = math.sqrt(max(fcount + gcount, 0.0))
            z = (fcount - gcount) / sigma if sigma > 0 else 0.0
            if gval == 0.0:
                ratio: float | str = 0.0 if fval == 0.0 else "n/a"
                rel_delta: float | str = 0.0 if fval == 0.0 else "n/a"
            else:
                ratio = fval / gval
                rel_delta = (fval - gval) / gval
            out.append(
                {
                    "family": family,
                    "metric": metric,
                    "fluka_count": fcount,
                    "megalib_count": gcount,
                    "fluka": fval,
                    "megalib": gval,
                    "fluka_minus_megalib": fval - gval,
                    "fluka_over_megalib": ratio,
                    "relative_delta_vs_megalib": rel_delta,
                    "poisson_z_approx": z,
                }
            )
    return out


def deposit_sample(deposits_by_code: dict[str, dict[int, float]], primaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_primary = {int(row["primary_id"]): row for row in primaries}
    sample: list[dict[str, Any]] = []
    for code, deposits in deposits_by_code.items():
        kept = 0
        for event_id, deposit in sorted(deposits.items()):
            if deposit <= 0.0:
                continue
            primary = by_primary.get(event_id, {})
            sample.append(
                {
                    "code": code,
                    "event_id": event_id,
                    "family": primary.get("family", ""),
                    "primary_particle": primary.get("particle", ""),
                    "ta_deposit_keV": deposit,
                }
            )
            kept += 1
            if kept >= 500:
                break
    return sample


def write_summary_md(out_dir: Path, summary: dict[str, Any], comparison: list[dict[str, Any]]) -> None:
    def fmt(value: Any) -> str:
        if isinstance(value, str):
            return value
        return f"{float(value):.6g}"

    md = [
        "# Phase-2 T2 Cu+Ta Absorber Transport Smoke",
        "",
        f"- status: `{summary['status']}`",
        f"- primary_count: `{summary['primary_count']}`",
        f"- geometry: `Cu sphere radius {CU_RADIUS_CM} cm + Ta slab {2*TA_HALF_X_CM} x {2*TA_HALF_Y_CM} x {2*TA_HALF_Z_CM} cm at z={TA_CENTER_Z_CM} cm`",
        f"- family_summary_csv: `{summary['family_summary_csv']}`",
        f"- comparison_csv: `{summary['comparison_csv']}`",
        "",
        "## Key Ta Deposit Efficiencies",
        "",
        "| family | metric | FLUKA | MEGAlib | FLUKA/MEGAlib | z approx |",
        "|---|---|---:|---:|---:|---:|",
    ]
    key_metrics = {"eff_480_550", "eff_w2_510p58_511p42"}
    for row in comparison:
        if row["metric"] not in key_metrics:
            continue
        md.append(
            f"| {row['family']} | {row['metric']} | `{fmt(row['fluka'])}` | "
            f"`{fmt(row['megalib'])}` | `{fmt(row['fluka_over_megalib'])}` | "
            f"`{float(row['poisson_z_approx']):.3g}` |"
        )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a T2 smoke, not the final production T2 closure.",
            "- The Ta slab is intentionally larger than a physical TES pixel to get smoke statistics from the 2048-row common source.",
            "- Detector smearing is disabled on the MEGAlib side with `EnergyResolution Ideal`; FLUKA records raw deposited energy.",
            "- The final production gate still needs higher statistics, exact agreed Ta/TES dimensions, common ancestry/stopping observables, and deterministic analytic W2 response.",
            "",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--source-csv", type=Path, default=T0_SOURCE_CSV)
    ap.add_argument("--seed", type=int, default=24066701)
    ap.add_argument("--keep-run-products", action="store_true")
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

    family_rows = family_summary("FLUKA", primaries, dict(fluka_run["ta_deposits"]))
    family_rows += family_summary("MEGAlib", primaries, dict(megalib_run["ta_deposits"]))
    compare = comparison_rows(family_rows)
    sample = deposit_sample({"FLUKA": dict(fluka_run["ta_deposits"]), "MEGAlib": dict(megalib_run["ta_deposits"])}, primaries)

    family_csv = out_dir / "family_ta_deposit_summary.csv"
    comparison_csv = out_dir / "ta_deposit_efficiency_comparison.csv"
    sample_csv = out_dir / "ta_deposit_sample.csv"
    hit_sample_csv = out_dir / "megalib_htsim_sample.csv"
    write_csv(family_csv, family_rows, list(family_rows[0].keys()) if family_rows else [])
    write_csv(comparison_csv, compare, list(compare[0].keys()) if compare else [])
    if sample:
        write_csv(sample_csv, sample, list(sample[0].keys()))
    if megalib_run["ta_hit_sample"]:
        write_csv(hit_sample_csv, list(megalib_run["ta_hit_sample"]), list(megalib_run["ta_hit_sample"][0].keys()))

    run_ok = fluka_run["returncode"] == 0 and megalib_run["returncode"] == 0
    deposit_ok = bool(fluka_run["ta_deposits"]) and bool(megalib_run["ta_deposits"])
    status = "T2_CU_TA_ABSORBER_TRANSPORT_SMOKE_COMPLETE" if run_ok and deposit_ok else "T2_CU_TA_ABSORBER_TRANSPORT_SMOKE_INCOMPLETE"
    summary = {
        "status": status,
        "run_type": "phase2_t2_cu_ta_absorber_transport_smoke",
        "created_utc": now_utc(),
        "seed": args.seed,
        "source_csv": rel(args.source_csv),
        "common_primaries_csv": rel(common_csv),
        "common_primaries_sha256": sha256_path(common_csv),
        "primary_count": len(primaries),
        "geometry": {
            "cu_radius_cm": CU_RADIUS_CM,
            "ta_half_x_cm": TA_HALF_X_CM,
            "ta_half_y_cm": TA_HALF_Y_CM,
            "ta_half_z_cm": TA_HALF_Z_CM,
            "ta_center_z_cm": TA_CENTER_Z_CM,
            "world_half_width_cm": WORLD_HALF_WIDTH_CM,
        },
        "family_summary_csv": rel(family_csv),
        "family_summary_sha256": sha256_path(family_csv),
        "comparison_csv": rel(comparison_csv),
        "comparison_sha256": sha256_path(comparison_csv),
        "ta_deposit_sample_csv": rel(sample_csv) if sample else "",
        "megalib_htsim_sample_csv": rel(hit_sample_csv) if megalib_run["ta_hit_sample"] else "",
        "runs": {
            "FLUKA": {key: value for key, value in fluka_run.items() if key != "ta_deposits"},
            "MEGAlib": {key: value for key, value in megalib_run.items() if key not in {"ta_deposits", "ta_hit_sample"}},
        },
        "notes": [
            "This is a smoke gate for Ta deposited-energy response, not final Phase-2 closure.",
            "The Ta slab is intentionally larger than a physical TES pixel for smoke statistics.",
        ],
    }
    write_json(out_dir / "summary.json", summary)
    write_summary_md(out_dir, summary, compare)
    print(json.dumps({"status": status, "primary_count": len(primaries), "out_dir": rel(out_dir)}, sort_keys=True))
    return 0 if status.endswith("COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
