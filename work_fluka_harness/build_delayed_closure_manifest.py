#!/usr/bin/env python3
"""Create the first engineering manifest for delayed closure work."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TES_ROOT = Path("/home/ubuntu/TES_511_Balloon")
OUT = ROOT / "engineering/crosscode_delayed_closure_20260625/00_manifest"
DELAYED_AUTH = TES_ROOT / "engineering/delayed_source_authority_v2_20260624/04_custom_source_v2"
EVENTLIST = DELAYED_AUTH / "source_v2_eventlist.dat"
WEIGHTS = DELAYED_AUTH / "source_v2_event_weights.csv"
REGION_MAP = TES_ROOT / "engineering/fluka_crosscode_validation_20260624/02_geometry_translation/region_map.csv"
GEOMETRY_DECK = (
    TES_ROOT
    / "engineering/fluka_crosscode_validation_20260624/02_geometry_translation/fluka_geometry/fix5_geometry_smoke.inp"
)
FLUKA_HOME = Path("/home/ubuntu/fluka/fluka-4-5.1-local/usr/local/fluka")

TARGET_ZA = {
    29064: "Cu-64",
    29062: "Cu-62",
    11024: "Na-24",
    13028: "Al-28",
    53128: "I-128",
    11022: "Na-22",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_value(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def path_record(path: Path, label: str | None = None) -> dict[str, Any]:
    exists = path.exists()
    return {
        "label": label or path.name,
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        "sha256": sha256_path(path) if exists and path.is_file() else "",
    }


def source_authority_summary() -> dict[str, Any]:
    rows = 0
    heavy_rows = 0
    total_activity = 0.0
    target: dict[int, dict[str, Any]] = {
        za: {"ZA": za, "nuclide": nuc, "rows": 0, "activity_Bq": 0.0} for za, nuc in TARGET_ZA.items()
    }
    with WEIGHTS.open(newline="", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            rows += 1
            za = int(row["ZA"])
            z = za // 1000
            a = za % 1000
            if z <= 3 and a <= 4 and not (z == 1 and a == 3):
                continue
            heavy_rows += 1
            w = float(row["event_weight_Bq"])
            total_activity += w
            if za in target:
                target[za]["rows"] += 1
                target[za]["activity_Bq"] += w
    return {
        "eventlist": path_record(EVENTLIST, "source_v2_eventlist"),
        "weights": path_record(WEIGHTS, "source_v2_event_weights"),
        "weight_rows": rows,
        "heavy_isotope_rows": heavy_rows,
        "heavy_total_activity_Bq": total_activity,
        "target_isotopes": sorted(target.values(), key=lambda r: str(r["nuclide"])),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = [
        ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/engineering.md",
        ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.md",
        ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/summary.json",
        ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/source_stage_rows.csv",
        ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/delayed_fraction_rows.csv",
        ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/tes_deposit_carrier_rows.csv",
        ROOT / "work_fluka_harness/run_delayed_isotope_raw_mvp.py",
        ROOT / "work_fluka_harness/run_eplus_raw_mvp.py",
        ROOT / "work_fluka_harness/build_fluka_11_like_energy_band_stats.py",
        ROOT / "work_fluka_harness/build_raw_scoring_smoke.py",
        ROOT / "work_fluka_harness/run_fluka_delayed_source_identity_gate.py",
        EVENTLIST,
        WEIGHTS,
        REGION_MAP,
        GEOMETRY_DECK,
        FLUKA_HOME / "bin/fluka",
        FLUKA_HOME / "bin/rfluka",
        FLUKA_HOME / "bin/fff",
        FLUKA_HOME / "bin/ldpmqmd",
    ]
    records = [path_record(p) for p in files]
    (OUT / "file_hashes.sha256").write_text(
        "\n".join(f"{r['sha256']}  {r['path']}" for r in records if r["exists"] and r["sha256"]) + "\n",
        encoding="utf-8",
    )
    fluka_env = {
        "created_utc": now_utc(),
        "repo": str(ROOT),
        "repo_commit": git_value(ROOT, "rev-parse", "HEAD"),
        "repo_status_short": git_value(ROOT, "status", "--short"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "fluka_home": str(FLUKA_HOME),
        "fluka_executables": [path_record(FLUKA_HOME / f"bin/{name}", name) for name in ("fluka", "rfluka", "fff", "ldpmqmd")],
        "environment_subset": {k: os.environ.get(k, "") for k in ("FLUKA_HOME", "FLUKADATA", "PATH")},
    }
    g4_env = {
        "created_utc": now_utc(),
        "tes_root": str(TES_ROOT),
        "tes_repo_commit": git_value(TES_ROOT, "rev-parse", "HEAD"),
        "tes_repo_status_short": git_value(TES_ROOT, "status", "--short"),
        "note": "Read-only fingerprint from the FLUKA-side workspace; full Geant4/MEGAlib runtime fingerprint still must be generated on the TES side.",
        "authority_paths": [path_record(p) for p in (EVENTLIST, WEIGHTS, REGION_MAP, GEOMETRY_DECK)],
    }
    source = source_authority_summary()
    summary = {
        "created_utc": now_utc(),
        "status": "FIRST_30MIN_MANIFEST_PRESENT",
        "engineering_plan": str(ROOT / "work_fluka_harness/fluka_11_like_energy_band_stats_20260625/engineering.md"),
        "files_hashed": len([r for r in records if r["exists"] and r["sha256"]]),
        "fluka_repo_commit": fluka_env["repo_commit"],
        "tes_repo_commit": g4_env["tes_repo_commit"],
        "source_authority_target_isotopes": source["target_isotopes"],
        "next_gate": "run_fluka_delayed_source_identity_gate.py",
    }
    for name, data in (
        ("environment_fluka.json", fluka_env),
        ("environment_g4.json", g4_env),
        ("source_authority.json", source),
        ("summary.json", summary),
    ):
        (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "summary.md").write_text(
        "\n".join(
            [
                "# Delayed Closure First Manifest",
                "",
                f"- status: `{summary['status']}`",
                f"- created_utc: `{summary['created_utc']}`",
                f"- fluka_repo_commit: `{summary['fluka_repo_commit']}`",
                f"- tes_repo_commit: `{summary['tes_repo_commit'] or 'not_a_git_repo_or_unavailable'}`",
                f"- files_hashed: `{summary['files_hashed']}`",
                f"- source heavy isotope rows: `{source['heavy_isotope_rows']}`",
                f"- source heavy total activity_Bq: `{source['heavy_total_activity_Bq']:.12g}`",
                "- next gate: `run_fluka_delayed_source_identity_gate.py`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(OUT / "summary.md")
    print(summary["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
