#!/usr/bin/env python3
"""Run a FLUKA-side vacuum radioactive-decay kernel benchmark.

This implements the FLUKA half of Phase 1 in
``fluka_11_like_energy_band_stats_20260625/engineering.md``.  It launches one
radioactive parent at rest in the center of a small vacuum sphere and records
particles crossing from the inner source sphere into an outer vacuum region.

The tracked outputs are compact summaries and line-yield tables.  Full FLUKA
run products and raw crossing dumps remain in ignored run/build directories.
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
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_raw_scoring_smoke as scoring
from run_eplus_raw_mvp import env, run, write_csv, write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "engineering/crosscode_delayed_closure_20260625/01_cu64_decay_kernel/fluka_vacuum_smoke"

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

TARGETS = [
    {"nuclide": "Cu-64", "Z": 29, "A": 64, "isomer": 0},
    {"nuclide": "Na-24", "Z": 11, "A": 24, "isomer": 0},
    {"nuclide": "Al-28", "Z": 13, "A": 28, "isomer": 0},
    {"nuclide": "I-128", "Z": 53, "A": 128, "isomer": 0},
]

GAMMA_LINE_WINDOWS = {
    "Cu-64": [(1345.0, 1346.5, "Cu-64 1346 keV")],
    "Na-24": [(1368.1, 1369.1, "Na-24 1369 keV"), (2753.5, 2754.5, "Na-24 2754 keV")],
    "Al-28": [(1778.5, 1779.5, "Al-28 1779 keV")],
    "I-128": [],
}


SOURCE_FORTRAN = """*
* Vacuum decay-kernel source: one isotope at rest at the origin.
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
      integer, save :: znum = 0
      integer, save :: anum = 0
      integer, save :: isom = 0
      integer ios

      nomore = 0
      call initialization()

      if ( first_run ) then
         open(unit=78, file='parent.dat', status='old',
     &        action='read', iostat=ios)
         if ( ios .ne. 0 ) then
            open(unit=78, file='../parent.dat', status='old',
     &           action='read', iostat=ios)
         end if
         if ( ios .ne. 0 ) call FLABRT('SOURCE','cannot open parent.dat')
         read(78,*,iostat=ios) znum, anum, isom
         if ( ios .ne. 0 ) call FLABRT('SOURCE','bad parent.dat')
         close(78)
         first_run = .false.
      end if

      particle_code = -2
      heavyion_atomic_number = znum
      heavyion_mass_number = anum
      heavyion_isomer = isom
      coordinate_x = 0.0D0
      coordinate_y = 0.0D0
      coordinate_z = 0.0D0
      direction_cosx = 0.0D0
      direction_cosy = 0.0D0
      direction_cosz = 1.0D0
      direction_flag = 0
      particle_weight = 1.0D0
      particle_age = 0.0D0
      delayed_radioactive_decay = 0.0D0

      call set_primary()
      return
      end
"""


MGDRAW_FORTRAN = """*
* Boundary-crossing scorer for the vacuum decay-kernel benchmark.
*
      SUBROUTINE MGDRAW ( ICODE, MREG )
      INCLUDE 'dblprc.inc'
      INCLUDE 'dimpar.inc'
      INCLUDE 'iounit.inc'
      INCLUDE 'caslim.inc'
      INCLUDE 'paprop.inc'
      INCLUDE 'trackr.inc'
      CHARACTER*8 NAMREG, NEWNAM
      INTEGER IERR, JERR, IOS
      INTEGER PZ, PA, PISO
      DOUBLE PRECISION KINKEV
      LOGICAL LFOPEN
      SAVE LFOPEN, PZ, PA, PISO
      DATA LFOPEN / .FALSE. /
      DATA PZ / 0 /
      DATA PA / 0 /
      DATA PISO / 0 /

      RETURN

      ENTRY BXDRAW ( ICODE, MREG, NEWREG, XSCO, YSCO, ZSCO )
      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=88, FILE='boundary_crossings_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (88,'(A)') 'event_id,parent_Z,parent_A,parent_isomer,'//
     &        'particle_code,kinetic_energy_keV,time_s,dir_x,'//
     &        'dir_y,dir_z,x_cm,y_cm,z_cm,weight,track_generation,'//
     &        'iprod,iaztrk'
         OPEN(unit=79, file='parent.dat', status='old',
     &        action='read', iostat=IOS)
         IF ( IOS .NE. 0 ) THEN
            OPEN(unit=79, file='../parent.dat', status='old',
     &           action='read', iostat=IOS)
         END IF
         IF ( IOS .EQ. 0 ) THEN
            READ(79,*,IOSTAT=IOS) PZ, PA, PISO
            CLOSE(79)
         END IF
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
         WRITE (88,1000) NCASE, PZ, PA, PISO, JTRACK, KINKEV,
     &        ATRACK, CXTRCK, CYTRCK, CZTRCK, XSCO, YSCO, ZSCO,
     &        WTRACK, LTRACK, IPRODC, IAZTRK
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

 1000 FORMAT(I12,',',I4,',',I4,',',I4,',',I8,',',1PE16.8,
     & ',',1PE16.8,',',1PE16.8,',',1PE16.8,',',1PE16.8,
     & ',',1PE16.8,',',1PE16.8,',',1PE16.8,',',1PE16.8,
     & ',',I8,',',I8,',',I12)
      END
"""


@dataclass(frozen=True)
class Target:
    nuclide: str
    z: int
    a: int
    isomer: int

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Target":
        return cls(str(row["nuclide"]), int(row["Z"]), int(row["A"]), int(row["isomer"]))

    @property
    def tag(self) -> str:
        return self.nuclide.lower().replace("-", "")


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


def compile_executable(out_dir: Path) -> Path:
    routine_dir = out_dir / "scoring_routines"
    routine_dir.mkdir(parents=True, exist_ok=True)
    source_path = routine_dir / "source_decay_kernel.f"
    mgdraw_path = routine_dir / "mgdraw_decay_kernel.f"
    source_path.write_text(SOURCE_FORTRAN, encoding="ascii")
    mgdraw_path.write_text(MGDRAW_FORTRAN, encoding="ascii")
    subprocess.run(
        [str(scoring.FFF), source_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_source_decay_kernel.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.FFF), mgdraw_path.name],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "compile_mgdraw_decay_kernel.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        [str(scoring.LDPMQMD), "-m", "fluka", "-o", "fluka_decay_kernel", "source_decay_kernel.o", "mgdraw_decay_kernel.o"],
        cwd=str(routine_dir),
        env=env(),
        check=True,
        stdout=(routine_dir / "link_fluka_decay_kernel.log").open("w"),
        stderr=subprocess.STDOUT,
    )
    return routine_dir / "fluka_decay_kernel"


def decay_kernel_input(target: Target, histories: int, seed: int) -> str:
    fluka_seed = int(seed) % 900000
    if fluka_seed <= 0:
        fluka_seed = 1
    return (
        "GLOBAL         20000         0         1         0         0         0\n"
        "TITLE\n"
        f"TES511 vacuum decay kernel {target.nuclide}\n"
        "DEFAULTS                                                              EM-CASCA\n"
        + f"{'BEAM':<10}{0.001:10.6g}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}ISOTOPE\n"
        + f"{'HI-PROPE':<10}{float(target.z):10.1f}{float(target.a):10.1f}{float(target.isomer):10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}\n"
        + f"{'RADDECAY':<10}{2.0:10.1f}\n"
        + f"{'DCYSCORE':<10}{-1.0:10.1f}\n"
        "SOURCE\n"
        "GEOBEGIN                                                              COMBNAME\n"
        "  0 0                       Vacuum decay kernel scoring sphere\n"
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
        "SCORE       ENERGY\n"
        + f"{'USERDUMP':<10}{100.0:10.1f}{99.0:10.1f}{6.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}RAWDUMP\n"
        + f"{'RANDOMIZE':<10}{1.0:10.1f}{float(fluka_seed):10.1f}\n"
        + f"{'START':<10}{float(histories):10.1f}\n"
        + "STOP\n"
    )


def run_target(target: Target, out_dir: Path, exe: Path, histories: int, seed: int) -> dict[str, Any]:
    run_dir = out_dir / "fluka_run" / target.tag
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "parent.dat").write_text(f"{target.z} {target.a} {target.isomer}\n", encoding="ascii")
    stem = f"decay_kernel_{target.tag}"
    inp = run_dir / f"{stem}.inp"
    inp.write_text(decay_kernel_input(target, histories, seed), encoding="ascii")
    started = now_utc()
    t0 = time.time()
    rc = run([str(scoring.RFLUKA), "-e", str(exe), "-N", "0", "-M", "1", stem], run_dir, run_dir / "rfluka.log")
    elapsed_s = time.time() - t0
    finished = now_utc()
    candidates = sorted(run_dir.glob("*boundary_crossings_tmp.csv"))
    raw_path = candidates[-1] if candidates else run_dir / "boundary_crossings_tmp.csv"
    return {
        "nuclide": target.nuclide,
        "Z": target.z,
        "A": target.a,
        "isomer": target.isomer,
        "histories": histories,
        "seed": seed,
        "returncode": rc,
        "started_utc": started,
        "finished_utc": finished,
        "elapsed_s": elapsed_s,
        "input": str(inp),
        "input_sha256": sha256_path(inp) if inp.exists() else "",
        "raw_boundary_crossings": str(raw_path),
        "raw_boundary_crossings_exists": raw_path.exists(),
        "raw_boundary_crossings_tracked": False,
        "rfluka_log": str(run_dir / "rfluka.log"),
    }


def photon_histogram(rows: list[dict[str, str]], bin_keV: float, max_keV: float) -> list[dict[str, Any]]:
    bins = int(math.ceil(max_keV / bin_keV))
    counts = [0] * bins
    for row in rows:
        if int(row["particle_code"]) != 7:
            continue
        e = float(row["kinetic_energy_keV"])
        if 0.0 <= e < max_keV:
            counts[int(e // bin_keV)] += 1
    return [
        {"e_low_keV": i * bin_keV, "e_high_keV": (i + 1) * bin_keV, "photon_count": count}
        for i, count in enumerate(counts)
        if count > 0
    ]


def summarize_target(target: Target, raw_path: Path, histories: int, out_dir: Path, sample_rows: int) -> dict[str, Any]:
    rows = rows_from_csv(raw_path) if raw_path.exists() else []
    by_particle: Counter[int] = Counter()
    event_particle_counts: dict[int, Counter[int]] = defaultdict(Counter)
    photon_energies_by_event: dict[int, list[float]] = defaultdict(list)
    energy_sum_by_particle: defaultdict[int, float] = defaultdict(float)
    for row in rows:
        event_id = int(row["event_id"])
        pcode = int(row["particle_code"])
        energy = float(row["kinetic_energy_keV"])
        by_particle[pcode] += 1
        event_particle_counts[event_id][pcode] += 1
        energy_sum_by_particle[pcode] += energy
        if pcode == 7:
            photon_energies_by_event[event_id].append(energy)

    particle_rows = []
    for pcode, count in sorted(by_particle.items(), key=lambda item: (-item[1], item[0])):
        particle_rows.append(
            {
                "nuclide": target.nuclide,
                "particle_code": pcode,
                "particle": PARTICLE_BY_CODE.get(pcode, f"FLUKA_{pcode}"),
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
                    "particle": PARTICLE_BY_CODE.get(pcode, f"FLUKA_{pcode}"),
                    "multiplicity": multiplicity,
                    "events": events,
                    "fraction": events / histories,
                }
            )

    line_rows = []
    for low, high, label in GAMMA_LINE_WINDOWS.get(target.nuclide, []):
        count = 0
        event_count = 0
        for event_id, energies in photon_energies_by_event.items():
            hits = sum(1 for energy in energies if low <= energy <= high)
            count += hits
            if hits:
                event_count += 1
        line_rows.append(
            {
                "nuclide": target.nuclide,
                "line": label,
                "window_low_keV": low,
                "window_high_keV": high,
                "photon_count": count,
                "photon_yield_per_parent": count / histories,
                "events_with_line": event_count,
                "event_fraction": event_count / histories,
            }
        )
    if target.nuclide == "Na-24":
        both = 0
        for energies in photon_energies_by_event.values():
            has_1369 = any(1368.1 <= energy <= 1369.1 for energy in energies)
            has_2754 = any(2753.5 <= energy <= 2754.5 for energy in energies)
            if has_1369 and has_2754:
                both += 1
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

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / f"{target.tag}_particle_yields.csv", particle_rows, list(particle_rows[0].keys()) if particle_rows else ["nuclide", "particle_code", "particle", "count", "yield_per_parent", "mean_kinetic_energy_keV"])
    write_csv(out_dir / f"{target.tag}_multiplicity_distribution.csv", event_mult_rows, list(event_mult_rows[0].keys()) if event_mult_rows else ["nuclide", "particle_code", "particle", "multiplicity", "events", "fraction"])
    if line_rows:
        write_csv(out_dir / f"{target.tag}_gamma_line_yields.csv", line_rows, list(line_rows[0].keys()))
    hist_rows = photon_histogram(rows, bin_keV=1.0, max_keV=4000.0)
    write_csv(out_dir / f"{target.tag}_photon_hist_1keV.csv", hist_rows, ["e_low_keV", "e_high_keV", "photon_count"])
    if rows:
        sample = rows[:sample_rows]
        write_csv(out_dir / f"{target.tag}_boundary_crossing_sample.csv", sample, list(sample[0].keys()))

    return {
        "nuclide": target.nuclide,
        "histories": histories,
        "boundary_crossings": len(rows),
        "particle_yields_csv": str(out_dir / f"{target.tag}_particle_yields.csv"),
        "multiplicity_distribution_csv": str(out_dir / f"{target.tag}_multiplicity_distribution.csv"),
        "gamma_line_yields_csv": str(out_dir / f"{target.tag}_gamma_line_yields.csv") if line_rows else "",
        "photon_hist_1keV_csv": str(out_dir / f"{target.tag}_photon_hist_1keV.csv"),
        "sample_csv": str(out_dir / f"{target.tag}_boundary_crossing_sample.csv") if rows else "",
        "particle_yields": particle_rows,
        "gamma_line_yields": line_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--histories", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=24066301)
    ap.add_argument("--sample-rows", type=int, default=500)
    ap.add_argument("--targets", default="Cu-64,Na-24,Al-28,I-128")
    ap.add_argument("--reuse-executable", action="store_true")
    args = ap.parse_args()

    if args.histories < 1:
        raise SystemExit("histories must be positive")

    wanted = {item.strip() for item in args.targets.split(",") if item.strip()}
    targets = [Target.from_dict(row) for row in TARGETS if row["nuclide"] in wanted]
    if not targets:
        raise SystemExit("no targets selected")

    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exe = out_dir / "scoring_routines/fluka_decay_kernel"
    if not (args.reuse_executable and exe.exists()):
        exe = compile_executable(out_dir)

    run_records = []
    summaries = []
    status = "FLUKA_DECAY_KERNEL_SMOKE_PASS"
    for offset, target in enumerate(targets):
        record = run_target(target, out_dir, exe, args.histories, args.seed + offset * 101)
        run_records.append(record)
        if record["returncode"] != 0 or not record["raw_boundary_crossings_exists"]:
            status = "FLUKA_DECAY_KERNEL_SMOKE_FAILED"
            continue
        summaries.append(summarize_target(target, Path(record["raw_boundary_crossings"]), args.histories, out_dir, args.sample_rows))

    all_particle_rows = []
    all_line_rows = []
    for summary in summaries:
        all_particle_rows.extend(summary["particle_yields"])
        all_line_rows.extend(summary["gamma_line_yields"])
    if all_particle_rows:
        write_csv(out_dir / "particle_yields.csv", all_particle_rows, list(all_particle_rows[0].keys()))
    if all_line_rows:
        write_csv(out_dir / "gamma_line_yields.csv", all_line_rows, list(all_line_rows[0].keys()))
    write_csv(out_dir / "run_manifest.csv", run_records, list(run_records[0].keys()) if run_records else [])

    summary = {
        "status": status,
        "created_utc": now_utc(),
        "mode": "FLUKA vacuum decay-kernel boundary-crossing smoke",
        "histories_per_isotope": args.histories,
        "targets": [target.nuclide for target in targets],
        "fluka_executable": str(exe),
        "fluka_executable_sha256": sha256_path(exe) if exe.exists() else "",
        "run_manifest": str(out_dir / "run_manifest.csv"),
        "particle_yields_csv": str(out_dir / "particle_yields.csv") if all_particle_rows else "",
        "gamma_line_yields_csv": str(out_dir / "gamma_line_yields.csv") if all_line_rows else "",
        "target_summaries": summaries,
        "limitations": [
            "This is a FLUKA-side smoke benchmark, not the required 1e6-per-isotope production run.",
            "It records boundary-crossing particles from an inner vacuum sphere; it is not a Geant4/MEGAlib comparison.",
            "Raw crossing dumps are generated in ignored fluka_run directories and are not part of the public handoff; tracked outputs are summaries and bounded samples.",
        ],
    }
    write_json(out_dir / "summary.json", summary)
    md_lines = [
        "# FLUKA Vacuum Decay-Kernel Smoke",
        "",
        f"- status: `{status}`",
        f"- histories_per_isotope: `{args.histories}`",
        f"- targets: `{', '.join(summary['targets'])}`",
        f"- particle_yields_csv: `{summary['particle_yields_csv']}`",
        f"- gamma_line_yields_csv: `{summary['gamma_line_yields_csv']}`",
        "",
        "## Key Line Checks",
        "",
    ]
    if all_line_rows:
        md_lines.extend(["| nuclide | line | event fraction | photon yield per parent |", "|---|---|---:|---:|"])
        for row in all_line_rows:
            yld = row["photon_yield_per_parent"]
            md_lines.append(
                f"| {row['nuclide']} | {row['line']} | `{float(row['event_fraction']):.6g}` | "
                f"`{float(yld):.6g}` |" if yld != "" else f"| {row['nuclide']} | {row['line']} | `{float(row['event_fraction']):.6g}` | `` |"
            )
    else:
        md_lines.append("No configured gamma line windows were populated.")
    md_lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- FLUKA side only; the Geant4/MEGAlib side remains open.",
            "- Smoke statistics only; the engineering plan still calls for `1e6` parents per isotope for a production gate.",
            "- Raw crossing dumps are excluded from the public handoff; use the bounded samples only to audit the schema.",
            "- Use this to validate scorer/runtime behavior and to choose the next production run, not as final closure.",
            "",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(out_dir / "summary.md")
    print(status)
    return 0 if status.endswith("_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
