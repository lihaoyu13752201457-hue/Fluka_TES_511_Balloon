#!/usr/bin/env python3
"""Run Phase-3 common Cu-64 raw-deposit chunks in FLUKA and MEGAlib."""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import math
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PHASE3_DIR = ROOT / "engineering/crosscode_delayed_closure_20260625/03_full_geometry_same_source"
DEFAULT_PARENT_LIST = PHASE3_DIR / "full_untracked/cu64_parent_resampling_1e6.csv"
DEFAULT_WORK_ROOT = PHASE3_DIR / "full_untracked/phase3_cu64_common_raw_production_work"
DEFAULT_OUT_DIR = PHASE3_DIR / "phase3_cu64_common_raw_production_1e6"
FLUKA_RUNNER = ROOT / "work_fluka_harness/run_phase3_cu64_common_fluka_raw.py"
MEGALIB_RUNNER = ROOT / "work_fluka_harness/run_phase3_cu64_common_megalib_raw.py"

BANDS = [
    ("all_tes_gt0", "all TES > 0"),
    ("e480_550", "480-550 keV"),
    ("w2_510p58_511p42", "W2 510.58-511.42 keV"),
    ("e1500_3000", "1500-3000 keV"),
    ("e3000_10000", "3000-10000 keV"),
]

PASS_STATUS = {
    "fluka": "PHASE3_CU64_COMMON_FLUKA_RAW_PASS",
    "megalib": "PHASE3_CU64_COMMON_MEGALIB_RAW_PASS",
}
BASE_SEED = {"fluka": 24067000, "megalib": 24068000}
CPU_COUNT = os.cpu_count() or 1
DEFAULT_MAX_PARALLEL = max(1, min(8, CPU_COUNT - 4 if CPU_COUNT > 4 else 1))


@dataclass
class Job:
    code: str
    idx: int
    start_index: int
    histories: int
    out_dir: Path
    cmd: list[str]
    log_path: Path


@dataclass
class ActiveJob:
    job: Job
    proc: subprocess.Popen[str]
    log_handle: object
    started_at: float


class DriverLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def __enter__(self) -> "DriverLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w", encoding="utf-8")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            self.handle = None
            raise SystemExit(f"another Phase-3 production driver is already running for {self.path.parent}") from exc
        self.handle.write(f"pid={os.getpid()}\n")
        self.handle.flush()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        if self.handle is None:
            return
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def chunk_sizes(total: int, chunks: int) -> list[int]:
    base, rem = divmod(total, chunks)
    return [base + (1 if i < rem else 0) for i in range(chunks)]


def parse_count_json(value: str) -> Counter[str]:
    if not value:
        return Counter()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return Counter()
    return Counter({str(key): int(val) for key, val in payload.items()})


def count_json(counter: Counter[str], limit: int = 8) -> str:
    return json.dumps(dict(counter.most_common(limit)), sort_keys=True)


def summary_path(out_dir: Path) -> Path:
    return out_dir / "summary.json"


def is_valid_chunk(code: str, out_dir: Path, histories: int) -> bool:
    path = summary_path(out_dir)
    if not path.exists():
        return False
    try:
        summary = load_json(path)
    except Exception:
        return False
    if summary.get("status") != PASS_STATUS[code]:
        return False
    if int(summary.get("histories", -1)) != histories:
        return False
    if code == "fluka":
        return summary.get("scoring_closure", {}).get("status") == "PASS"
    return int(summary.get("sim_event_count", -1)) == histories


def terminate(active: ActiveJob, sig: int = signal.SIGTERM) -> None:
    try:
        os.killpg(active.proc.pid, sig)
    except ProcessLookupError:
        return
    except PermissionError:
        active.proc.terminate()


def build_jobs(args: argparse.Namespace, codes: list[str]) -> list[Job]:
    sizes = chunk_sizes(args.histories, args.chunks)
    jobs: list[Job] = []
    for code in codes:
        start = 1
        runner = FLUKA_RUNNER if code == "fluka" else MEGALIB_RUNNER
        for idx, n_hist in enumerate(sizes, start=1):
            out_dir = args.work_root / code / f"chunk_{idx:03d}_start{start:07d}_n{n_hist}"
            log_path = args.work_root / code / f"chunk_{idx:03d}.driver.log"
            seed = BASE_SEED[code] + idx - 1
            cmd = [
                sys.executable,
                str(runner),
                "--parent-list",
                str(args.parent_list),
                "--out-dir",
                str(out_dir),
                "--seed",
                str(seed),
                "--start-index",
                str(start),
                "--max-events",
                str(n_hist),
                "--sample-rows",
                str(args.sample_rows),
            ]
            if code == "megalib" and args.write_full_truth:
                cmd.append("--write-full-truth")
            jobs.append(
                Job(
                    code=code,
                    idx=idx,
                    start_index=start,
                    histories=n_hist,
                    out_dir=out_dir,
                    cmd=cmd,
                    log_path=log_path,
                )
            )
            start += n_hist
    return jobs


def run_jobs(args: argparse.Namespace, jobs: list[Job]) -> int:
    pending: list[Job] = []
    skipped: list[Job] = []
    for job in jobs:
        if is_valid_chunk(job.code, job.out_dir, job.histories):
            skipped.append(job)
        else:
            pending.append(job)

    if skipped:
        print(
            "skipping valid chunks: "
            + ", ".join(f"{job.code}:{job.idx:03d}" for job in skipped),
            flush=True,
        )

    active: list[ActiveJob] = []
    completed: list[tuple[Job, int]] = []
    last_report = 0.0
    total_to_run = len(pending)

    while pending or active:
        while pending and len(active) < args.max_parallel:
            job = pending.pop(0)
            job.log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = job.log_path.open("w", encoding="utf-8")
            proc = subprocess.Popen(
                job.cmd,
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            active.append(ActiveJob(job=job, proc=proc, log_handle=fh, started_at=time.time()))
            print(
                f"started {job.code} chunk {job.idx:03d}: start={job.start_index} "
                f"histories={job.histories} out={rel(job.out_dir)}",
                flush=True,
            )

        now = time.time()
        failed: list[tuple[Job, int]] = []
        for item in list(active):
            if (
                args.chunk_timeout_s > 0
                and item.proc.poll() is None
                and now - item.started_at > args.chunk_timeout_s
            ):
                terminate(item, signal.SIGTERM)
                try:
                    item.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    terminate(item, signal.SIGKILL)
                    item.proc.wait(timeout=10)
            if item.proc.poll() is None:
                continue
            rc = int(item.proc.returncode)
            item.log_handle.close()
            active.remove(item)
            completed.append((item.job, rc))
            print(f"finished {item.job.code} chunk {item.job.idx:03d}: returncode={rc}", flush=True)
            if rc != 0 or not is_valid_chunk(item.job.code, item.job.out_dir, item.job.histories):
                failed.append((item.job, rc))

        if now - last_report >= 30.0:
            done = len(completed)
            valid_now = sum(1 for job in jobs if is_valid_chunk(job.code, job.out_dir, job.histories))
            print(
                f"progress: newly_done={done}/{total_to_run} valid={valid_now}/{len(jobs)} "
                f"active={len(active)} pending={len(pending)}",
                flush=True,
            )
            last_report = now

        if failed and not args.keep_going:
            for item in active:
                if item.proc.poll() is None:
                    terminate(item, signal.SIGTERM)
                item.log_handle.close()
            print(
                "failed chunks: " + ", ".join(f"{job.code}:{job.idx:03d}:rc={rc}" for job, rc in failed),
                flush=True,
            )
            return 2

        if active or pending:
            time.sleep(args.poll_interval_s)

    return 0


def band_file_for(code: str, out_dir: Path) -> Path:
    return out_dir / ("band_summary.csv" if code == "fluka" else "cc_band_summary.csv")


def aggregate_code(code: str, jobs: list[Job]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_by_band: dict[str, dict[str, Any]] = {
        band: {
            "code": code,
            "band": band,
            "band_label": label,
            "histories": 0,
            "events": 0,
            "top_material_counts": Counter(),
            "top_source_volume_counts": Counter(),
        }
        for band, label in BANDS
    }
    chunk_rows: list[dict[str, Any]] = []
    total_elapsed = 0.0
    raw_rows = 0
    cc_rows = 0
    cc_tes_rows = 0
    htsim_rows = 0

    for job in jobs:
        if job.code != code or not is_valid_chunk(job.code, job.out_dir, job.histories):
            continue
        summary = load_json(summary_path(job.out_dir))
        total_elapsed += float(summary.get("elapsed_s", 0.0))
        raw_rows += int(summary.get("raw_event_rows", 0) or 0)
        cc_rows += int(summary.get("cc_hit_rows", 0) or 0)
        cc_tes_rows += int(summary.get("cc_tes_hit_rows", 0) or 0)
        htsim_rows += int(summary.get("htsim_hit_rows", 0) or 0)
        chunk_rows.append(
            {
                "code": code,
                "chunk": job.idx,
                "start_index": job.start_index,
                "histories": job.histories,
                "status": summary.get("status", ""),
                "elapsed_s": summary.get("elapsed_s", ""),
                "out_dir": rel(job.out_dir),
                "summary_json": rel(summary_path(job.out_dir)),
                "raw_truth_local": bool(
                    code == "fluka"
                    or summary.get("cc_raw_hits_csv")
                    or summary.get("cc_event_totals_csv")
                ),
            }
        )
        for row in read_csv(band_file_for(code, job.out_dir)):
            band = row["band"]
            item = rows_by_band[band]
            item["histories"] += int(row["histories"])
            item["events"] += int(row["events"])
            item["top_material_counts"].update(parse_count_json(row.get("top_material_counts", "")))
            item["top_source_volume_counts"].update(parse_count_json(row.get("top_source_volume_counts", "")))

    out_rows: list[dict[str, Any]] = []
    for band, _label in BANDS:
        item = rows_by_band[band]
        histories = int(item["histories"])
        events = int(item["events"])
        efficiency = events / histories if histories else 0.0
        sigma = math.sqrt(efficiency * (1.0 - efficiency) / histories) if histories else 0.0
        out_rows.append(
            {
                "code": code,
                "band": band,
                "band_label": item["band_label"],
                "histories": histories,
                "events": events,
                "efficiency_per_parent": efficiency,
                "efficiency_sigma_binomial": sigma,
                "sum_w": float(events),
                "sum_w2": float(events),
                "n_eff": float(events) if events else 0.0,
                "top_material_counts": count_json(item["top_material_counts"]),
                "top_source_volume_counts": count_json(item["top_source_volume_counts"]),
            }
        )

    meta = {
        "code": code,
        "valid_chunks": len(chunk_rows),
        "histories": sum(int(row["histories"]) for row in chunk_rows),
        "chunk_elapsed_s_sum": total_elapsed,
        "raw_event_rows": raw_rows,
        "cc_hit_rows": cc_rows,
        "cc_tes_hit_rows": cc_tes_rows,
        "htsim_hit_rows": htsim_rows,
        "raw_truth_local": all(bool(row["raw_truth_local"]) for row in chunk_rows) if chunk_rows else False,
        "chunks": chunk_rows,
    }
    return out_rows, meta


def compare_bands(fluka: list[dict[str, Any]], megalib: list[dict[str, Any]]) -> list[dict[str, Any]]:
    f_by_band = {row["band"]: row for row in fluka}
    m_by_band = {row["band"]: row for row in megalib}
    out = []
    for band, label in BANDS:
        f = f_by_band.get(band, {})
        m = m_by_band.get(band, {})
        f_hist = int(f.get("histories", 0) or 0)
        m_hist = int(m.get("histories", 0) or 0)
        f_events = int(f.get("events", 0) or 0)
        m_events = int(m.get("events", 0) or 0)
        f_eff = float(f.get("efficiency_per_parent", 0.0) or 0.0)
        m_eff = float(m.get("efficiency_per_parent", 0.0) or 0.0)
        f_sig = float(f.get("efficiency_sigma_binomial", 0.0) or 0.0)
        m_sig = float(m.get("efficiency_sigma_binomial", 0.0) or 0.0)
        denom = math.sqrt(f_sig * f_sig + m_sig * m_sig)
        ratio = f_eff / m_eff if m_eff > 0 else None
        ratio_sigma = ratio * math.sqrt(1.0 / f_events + 1.0 / m_events) if ratio and f_events > 0 and m_events > 0 else None
        out.append(
            {
                "band": band,
                "band_label": label,
                "fluka_histories": f_hist,
                "fluka_events": f_events,
                "fluka_efficiency": f_eff,
                "fluka_sigma": f_sig,
                "megalib_histories": m_hist,
                "megalib_events": m_events,
                "megalib_efficiency": m_eff,
                "megalib_sigma": m_sig,
                "fluka_over_megalib": ratio if ratio is not None else "",
                "ratio_sigma_approx": ratio_sigma if ratio_sigma is not None else "",
                "z_efficiency_difference": (f_eff - m_eff) / denom if denom > 0 else "",
            }
        )
    return out


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase-3 Cu-64 Common Raw-Deposit Production",
        "",
        f"- status: `{payload['status']}`",
        f"- histories_requested_per_code: `{payload['histories_requested_per_code']}`",
        f"- chunks: `{payload['chunks']}`",
        f"- max_parallel: `{payload['max_parallel']}`",
        f"- parent_list_sha256: `{payload['parent_list_sha256']}`",
        f"- work_root_untracked: `{payload['work_root']}`",
        f"- raw_truth_retained_locally: `{payload['raw_truth_retained_locally']}`",
        f"- started_at_utc: `{payload['started_at_utc']}`",
        f"- finished_at_utc: `{payload['finished_at_utc']}`",
        f"- wall_elapsed_s: `{payload['wall_elapsed_s']:.3f}`",
    ]
    if payload.get("aggregated_at_utc"):
        lines.append(f"- aggregated_at_utc: `{payload['aggregated_at_utc']}`")
        lines.append(f"- aggregation_wall_elapsed_s: `{payload['aggregation_wall_elapsed_s']:.3f}`")
    lines.extend(
        [
            "",
            "## Band Comparison",
            "",
            "| band | FLUKA events / histories | MEGAlib events / histories | FLUKA/MEGAlib | z |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in payload.get("comparison", []):
        ratio = row["fluka_over_megalib"]
        z = row["z_efficiency_difference"]
        ratio_s = f"{ratio:.6g}" if isinstance(ratio, float) else "n/a"
        z_s = f"{z:.3g}" if isinstance(z, float) else "n/a"
        lines.append(
            f"| `{row['band_label']}` | `{row['fluka_events']} / {row['fluka_histories']}` | "
            f"`{row['megalib_events']} / {row['megalib_histories']}` | "
            f"`{ratio_s}` | `{z_s}` |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- chunk_manifest_csv: `{payload['chunk_manifest_csv']}`",
            f"- fluka_band_summary_csv: `{payload['fluka_band_summary_csv']}`",
            f"- megalib_band_summary_csv: `{payload['megalib_band_summary_csv']}`",
            f"- comparison_csv: `{payload['comparison_csv']}`",
            "",
            "## Boundary",
            "",
            "- This is a production-statistics raw-deposit comparison for the common Cu-64 parent stream.",
            "- Full raw truth is retained only under the ignored local work root.",
            "- This does not yet apply the common active-veto/topology/FoV event builder or analytic W2 response.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", nargs="+", choices=("fluka", "megalib", "both"), default=["both"])
    ap.add_argument("--histories", type=int, default=1_000_000)
    ap.add_argument("--chunks", type=int, default=20)
    ap.add_argument("--max-parallel", type=int, default=DEFAULT_MAX_PARALLEL)
    ap.add_argument("--chunk-timeout-s", type=float, default=0.0)
    ap.add_argument("--poll-interval-s", type=float, default=5.0)
    ap.add_argument("--parent-list", type=Path, default=DEFAULT_PARENT_LIST)
    ap.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--sample-rows", type=int, default=20)
    ap.add_argument("--write-full-truth", action="store_true")
    ap.add_argument("--keep-going", action="store_true")
    args = ap.parse_args()

    if "both" in args.codes:
        codes = ["fluka", "megalib"]
    else:
        codes = list(dict.fromkeys(args.codes))
    if args.histories < 1 or args.chunks < 1 or args.max_parallel < 1:
        raise SystemExit("histories, chunks, and max-parallel must be positive")
    if args.chunk_timeout_s < 0 or args.poll_interval_s <= 0:
        raise SystemExit("chunk-timeout-s must be non-negative and poll-interval-s must be positive")
    args.parent_list = args.parent_list.expanduser().resolve()
    args.work_root = args.work_root.expanduser().resolve()
    args.out_dir = args.out_dir.expanduser().resolve()
    if not args.parent_list.exists():
        raise SystemExit(f"parent list does not exist: {args.parent_list}")

    jobs = build_jobs(args, codes)
    all_chunks_preexisting = all(is_valid_chunk(job.code, job.out_dir, job.histories) for job in jobs)
    summary_json_path = args.out_dir / "summary.json"
    existing_summary = load_json(summary_json_path) if summary_json_path.exists() else {}
    started = now_utc()
    t0 = time.time()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with DriverLock(args.work_root / ".driver.lock"):
        rc = run_jobs(args, jobs)
    finished = now_utc()
    wall_elapsed = time.time() - t0

    valid_jobs = [job for job in jobs if is_valid_chunk(job.code, job.out_dir, job.histories)]
    chunk_manifest: list[dict[str, Any]] = []
    code_payload: dict[str, Any] = {}
    for code in codes:
        band_rows, meta = aggregate_code(code, valid_jobs)
        code_payload[code] = meta
        if band_rows:
            out_csv = args.out_dir / f"{code}_band_summary.csv"
            write_csv(
                out_csv,
                band_rows,
                [
                    "code",
                    "band",
                    "band_label",
                    "histories",
                    "events",
                    "efficiency_per_parent",
                    "efficiency_sigma_binomial",
                    "sum_w",
                    "sum_w2",
                    "n_eff",
                    "top_material_counts",
                    "top_source_volume_counts",
                ],
            )
        chunk_manifest.extend(meta.get("chunks", []))

    comparison: list[dict[str, Any]] = []
    if "fluka" in code_payload and "megalib" in code_payload:
        fluka_rows, _ = aggregate_code("fluka", valid_jobs)
        megalib_rows, _ = aggregate_code("megalib", valid_jobs)
        comparison = compare_bands(fluka_rows, megalib_rows)
        write_csv(
            args.out_dir / "comparison_band_summary.csv",
            comparison,
            [
                "band",
                "band_label",
                "fluka_histories",
                "fluka_events",
                "fluka_efficiency",
                "fluka_sigma",
                "megalib_histories",
                "megalib_events",
                "megalib_efficiency",
                "megalib_sigma",
                "fluka_over_megalib",
                "ratio_sigma_approx",
                "z_efficiency_difference",
            ],
        )

    write_csv(
        args.out_dir / "chunk_manifest.csv",
        chunk_manifest,
        [
            "code",
            "chunk",
            "start_index",
            "histories",
            "status",
            "elapsed_s",
            "out_dir",
            "summary_json",
            "raw_truth_local",
        ],
    )

    all_requested_valid = all(is_valid_chunk(job.code, job.out_dir, job.histories) for job in jobs)
    status = "PHASE3_CU64_COMMON_RAW_PRODUCTION_PASS" if rc == 0 and all_requested_valid else "BLOCKED_PHASE3_CU64_COMMON_RAW_PRODUCTION"
    production_started = started
    production_finished = finished
    production_wall_elapsed = wall_elapsed
    aggregation_started = ""
    aggregation_finished = ""
    aggregation_wall_elapsed = 0.0
    if (
        all_chunks_preexisting
        and existing_summary.get("status") == "PHASE3_CU64_COMMON_RAW_PRODUCTION_PASS"
    ):
        production_started = existing_summary.get("started_at_utc", started)
        production_finished = existing_summary.get("finished_at_utc", finished)
        production_wall_elapsed = float(existing_summary.get("wall_elapsed_s", wall_elapsed))
        aggregation_started = started
        aggregation_finished = finished
        aggregation_wall_elapsed = wall_elapsed
    payload = {
        "status": status,
        "codes": codes,
        "histories_requested_per_code": args.histories,
        "chunks": args.chunks,
        "max_parallel": args.max_parallel,
        "parent_list": rel(args.parent_list),
        "parent_list_sha256": file_sha256(args.parent_list),
        "work_root": rel(args.work_root),
        "out_dir": rel(args.out_dir),
        "write_full_truth": bool(args.write_full_truth),
        "raw_truth_retained_locally": all(
            bool(meta.get("raw_truth_local")) for meta in code_payload.values()
        )
        if code_payload
        else False,
        "started_at_utc": production_started,
        "finished_at_utc": production_finished,
        "wall_elapsed_s": production_wall_elapsed,
        "aggregated_at_utc": aggregation_finished,
        "aggregation_started_at_utc": aggregation_started,
        "aggregation_wall_elapsed_s": aggregation_wall_elapsed,
        "driver_returncode": rc,
        "chunk_manifest_csv": rel(args.out_dir / "chunk_manifest.csv"),
        "fluka_band_summary_csv": rel(args.out_dir / "fluka_band_summary.csv"),
        "megalib_band_summary_csv": rel(args.out_dir / "megalib_band_summary.csv"),
        "comparison_csv": rel(args.out_dir / "comparison_band_summary.csv"),
        "codes_summary": code_payload,
        "comparison": comparison,
        "boundary": "Production raw-deposit gate only; common active-veto/topology/FoV event builder and analytic W2 response remain separate steps.",
    }
    write_json(args.out_dir / "summary.json", payload)
    write_summary_md(args.out_dir / "summary.md", payload)
    print(args.out_dir / "summary.md")
    print(status)
    return 0 if status == "PHASE3_CU64_COMMON_RAW_PRODUCTION_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
