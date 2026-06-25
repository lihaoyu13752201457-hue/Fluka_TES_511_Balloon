#!/usr/bin/env python3
"""Shared FLUKA raw-scoring helpers for TES511 delayed-source runs.

This reduced public handoff keeps only the helper functions required by the
independent-source runners. It intentionally does not include the old smoke-run
entry point or smoke outputs.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
RUN_ROOT = TES_ROOT / "engineering/fluka_crosscode_validation_20260624"
GEOM = RUN_ROOT / "02_geometry_translation"
REGION_MAP = GEOM / "region_map.csv"
SMOKE_DECK = GEOM / "fluka_geometry/fix5_geometry_smoke.inp"
FLUKA_HOME = Path("/home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka")
FFF = FLUKA_HOME / "bin/fff"
LDPMQMD = FLUKA_HOME / "bin/ldpmqmd"
RFLUKA = FLUKA_HOME / "bin/rfluka"


def read_region_rows() -> list[dict[str, str]]:
    with REGION_MAP.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def region_number(name: str) -> int:
    m = re.fullmatch(r"R(\d{7})", name)
    if not m:
        raise ValueError(f"unexpected FLUKA region name: {name}")
    return int(m.group(1))


def contiguous_ranges(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    vals = sorted(set(values))
    ranges = []
    start = prev = vals[0]
    for val in vals[1:]:
        if val == prev + 1:
            prev = val
            continue
        ranges.append((start, prev))
        start = prev = val
    ranges.append((start, prev))
    return ranges


def geometry_without_run_tail() -> str:
    lines = SMOKE_DECK.read_text(encoding="ascii").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("GEOBEGIN"))
    end = next(i for i, line in enumerate(lines) if line.startswith("RANDOMIZE"))
    return "\n".join(lines[start:end]) + "\n"


def _range_code(ranges: list[tuple[int, int]], kind: int) -> list[str]:
    lines: list[str] = []
    for lo, hi in ranges:
        if lo == hi:
            lines.extend(
                [
                    f"      IF ( RNUM .EQ. {lo} ) THEN",
                    f"         DETKIND = {kind}",
                    "         RETURN",
                    "      END IF",
                ]
            )
        else:
            lines.extend(
                [
                    f"      IF ( RNUM .GE. {lo} .AND. RNUM .LE. {hi} ) THEN",
                    f"         DETKIND = {kind}",
                    "         RETURN",
                    "      END IF",
                ]
            )
    return lines


def generate_mgdraw(tes_ranges: list[tuple[int, int]], shield_ranges: list[tuple[int, int]]) -> str:
    lookup = "\n".join(_range_code(tes_ranges, 1) + _range_code(shield_ranges, 2))
    return f"""*
* Raw TES/shield deposition dump for current TES511 translated regions.
*
      SUBROUTINE MGDRAW ( ICODE, MREG )
      INCLUDE 'dblprc.inc'
      INCLUDE 'dimpar.inc'
      INCLUDE 'iounit.inc'
      INCLUDE 'caslim.inc'
      INCLUDE 'trackr.inc'
      INTEGER MAXRAW
      PARAMETER ( MAXRAW = 3110 )
      CHARACTER*8 NAMREG, OUTREG
      CHARACTER*16 KNAME
      INTEGER IERR, I, RNUM, IOS, KIND, DETKIND
      INTEGER RPCODE(MAXRAW), RICODE(MAXRAW)
      DOUBLE PRECISION TESTOT, SHDTOT, DEPKEV, XPOS, YPOS, ZPOS
      DOUBLE PRECISION EDEP(MAXRAW), RTIME(MAXRAW)
      DOUBLE PRECISION RXPOS(MAXRAW), RYPOS(MAXRAW), RZPOS(MAXRAW)
      LOGICAL LFOPEN
      SAVE TESTOT, SHDTOT, LFOPEN, EDEP, RTIME, RXPOS, RYPOS, RZPOS
      SAVE RPCODE, RICODE
      DATA TESTOT / 0.0D0 /
      DATA SHDTOT / 0.0D0 /
      DATA LFOPEN / .FALSE. /

      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=98, FILE='raw_deposits_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         OPEN ( UNIT=97, FILE='event_totals_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (98,'(A)') 'history_id,region_name,detector_kind,'//
     &        'deposit_keV,deposit_time_s,particle_code,icode,'//
     &        'x_cm,y_cm,z_cm'
         WRITE (97,'(A)') 'history_id,tes_total_keV,shield_total_keV'
         DO I = 1, MAXRAW
            EDEP(I) = 0.0D0
            RTIME(I) = 0.0D0
            RXPOS(I) = 0.0D0
            RYPOS(I) = 0.0D0
            RZPOS(I) = 0.0D0
            RPCODE(I) = 0
            RICODE(I) = 0
         END DO
         LFOPEN = .TRUE.
      END IF

      CALL GEOR2N ( MREG, NAMREG, IERR )
      RNUM = -1
      IF ( IERR .EQ. 0 .AND. NAMREG(1:1) .EQ. 'R' ) THEN
         READ (NAMREG(2:8),'(I7)',IOSTAT=IOS) RNUM
      END IF
      KIND = DETKIND(RNUM)
      IF ( KIND .GT. 0 .AND. RNUM .GE. 1 .AND.
     &     RNUM .LE. MAXRAW ) THEN
         IF ( NTRACK .GT. 0 ) THEN
            XPOS = XTRACK(NTRACK)
            YPOS = YTRACK(NTRACK)
            ZPOS = ZTRACK(NTRACK)
         ELSE
            XPOS = XTRACK(0)
            YPOS = YTRACK(0)
            ZPOS = ZTRACK(0)
         END IF
         DO I = 1, MTRACK
            IF ( DTRACK(I) .GT. 0.0D0 ) THEN
               DEPKEV = DBLE(DTRACK(I)) * 1.0D6
               IF ( EDEP(RNUM) .LE. 0.0D0 ) THEN
                  RTIME(RNUM) = ATRACK
                  RXPOS(RNUM) = XPOS
                  RYPOS(RNUM) = YPOS
                  RZPOS(RNUM) = ZPOS
                  RPCODE(RNUM) = JTRACK
                  RICODE(RNUM) = ICODE
               END IF
               EDEP(RNUM) = EDEP(RNUM) + DEPKEV
               IF ( KIND .EQ. 1 ) TESTOT = TESTOT + DEPKEV
               IF ( KIND .EQ. 2 ) SHDTOT = SHDTOT + DEPKEV
            END IF
         END DO
      END IF
      RETURN

      ENTRY BXDRAW ( ICODE, MREG, NEWREG, XSCO, YSCO, ZSCO )
      RETURN

      ENTRY EEDRAW ( ICODE )
      IF ( .NOT. LFOPEN ) THEN
         OPEN ( UNIT=98, FILE='raw_deposits_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         OPEN ( UNIT=97, FILE='event_totals_tmp.csv',
     &          STATUS='UNKNOWN', FORM='FORMATTED' )
         WRITE (98,'(A)') 'history_id,region_name,detector_kind,'//
     &        'deposit_keV,deposit_time_s,particle_code,icode,'//
     &        'x_cm,y_cm,z_cm'
         WRITE (97,'(A)') 'history_id,tes_total_keV,shield_total_keV'
         LFOPEN = .TRUE.
      END IF
      DO I = 1, MAXRAW
         KIND = DETKIND(I)
         IF ( KIND .GT. 0 .AND. EDEP(I) .GT. 0.0D0 ) THEN
            IF ( KIND .EQ. 1 ) KNAME = 'TES_PIXEL'
            IF ( KIND .EQ. 2 ) KNAME = 'ACTIVE_SHIELD'
            WRITE (OUTREG,'(''R'',I7.7)') I
            WRITE (98,1000) NCASE, OUTREG, KNAME, EDEP(I), RTIME(I),
     &           RPCODE(I), RICODE(I), RXPOS(I), RYPOS(I), RZPOS(I)
         END IF
         EDEP(I) = 0.0D0
         RTIME(I) = 0.0D0
         RXPOS(I) = 0.0D0
         RYPOS(I) = 0.0D0
         RZPOS(I) = 0.0D0
         RPCODE(I) = 0
         RICODE(I) = 0
      END DO
      WRITE (97,1010) NCASE, TESTOT, SHDTOT
      TESTOT = 0.0D0
      SHDTOT = 0.0D0
      RETURN

      ENTRY ENDRAW ( ICODE, MREG, RULL, XSCO, YSCO, ZSCO )
      CALL GEOR2N ( MREG, NAMREG, IERR )
      RNUM = -1
      IF ( IERR .EQ. 0 .AND. NAMREG(1:1) .EQ. 'R' ) THEN
         READ (NAMREG(2:8),'(I7)',IOSTAT=IOS) RNUM
      END IF
      KIND = DETKIND(RNUM)
      IF ( KIND .GT. 0 .AND. RULL .GT. 0.0D0 .AND.
     &     RNUM .GE. 1 .AND. RNUM .LE. MAXRAW ) THEN
         DEPKEV = DBLE(RULL) * 1.0D6
         IF ( EDEP(RNUM) .LE. 0.0D0 ) THEN
            RTIME(RNUM) = ATRACK
            RXPOS(RNUM) = DBLE(XSCO)
            RYPOS(RNUM) = DBLE(YSCO)
            RZPOS(RNUM) = DBLE(ZSCO)
            RPCODE(RNUM) = JTRACK
            RICODE(RNUM) = ICODE
         END IF
         EDEP(RNUM) = EDEP(RNUM) + DEPKEV
         IF ( KIND .EQ. 1 ) TESTOT = TESTOT + DEPKEV
         IF ( KIND .EQ. 2 ) SHDTOT = SHDTOT + DEPKEV
      END IF
      RETURN

      ENTRY SODRAW
      RETURN

      ENTRY USDRAW ( ICODE, MREG, XSCO, YSCO, ZSCO )
      RETURN

 1000 FORMAT(I12,',',A8,',',A16,',',1PE16.8,',',1PE16.8,
     & ',',I8,',',I8,',',1PE16.8,',',1PE16.8,',',1PE16.8)
 1010 FORMAT(I12,',',1PE16.8,',',1PE16.8)
      END

      INTEGER FUNCTION DETKIND ( RNUM )
      INTEGER RNUM
      DETKIND = 0
{lookup}
      RETURN
      END
"""
