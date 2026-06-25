#!/usr/bin/env python3
"""Run eplus FLUKA histories in bounded chunks and build a combined comparison."""

from __future__ import annotations

import argparse
import fcntl
from dataclasses import dataclass
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


CPU_COUNT = os.cpu_count() or 1
DEFAULT_MAX_PARALLEL = max(1, min(20, CPU_COUNT - 4 if CPU_COUNT > 4 else 1))


@dataclass
class ChunkProc:
    idx: int
    n_hist: int
    out_dir: Path
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
            raise SystemExit(f"another chunk driver is already running for {self.path.parent}") from exc
        self.handle.write(f"pid={os.getpid()}\n")
        self.handle.flush()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        if self.handle is None:
            return
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


def chunk_sizes(total: int, chunks: int) -> list[int]:
    base, rem = divmod(total, chunks)
    return [base + (1 if i < rem else 0) for i in range(chunks)]


def line_count(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def is_valid_run(out_dir: Path) -> bool:
    summary_path = out_dir / "summary.json"
    if not summary_path.exists():
        return False
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    verdict = summary.get("mvp_raw_data_verdict", {})
    closure = summary.get("scoring_closure", {})
    return verdict.get("status") == "RAW_DATA_MVP_PASS" and closure.get("status") == "PASS"


def remove_flag(argv: list[str], flag: str) -> list[str]:
    return [item for item in argv if item != flag]


def launch_detached(args: argparse.Namespace) -> int:
    log_path = args.driver_log or (args.out_root / "driver.detached.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_root.mkdir(parents=True, exist_ok=True)
    child_argv = remove_flag(sys.argv[1:], "--detach")
    cmd = [sys.executable, str(Path(__file__).resolve()), *child_argv]
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path.cwd()),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            close_fds=True,
        )
    pid_path = args.out_root / "driver.pid"
    pid_path.write_text(f"{proc.pid}\n", encoding="utf-8")
    print(f"detached driver pid={proc.pid} log={log_path} pid_file={pid_path}", flush=True)
    return 0


def terminate_chunk(chunk: ChunkProc, sig: int = signal.SIGTERM) -> None:
    try:
        os.killpg(chunk.proc.pid, sig)
    except ProcessLookupError:
        return
    except PermissionError:
        chunk.proc.terminate()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary-tag", default="eplus")
    ap.add_argument("--histories", type=int, default=243727)
    ap.add_argument("--chunks", type=int, default=8)
    ap.add_argument("--seed", type=int, default=24062401)
    ap.add_argument("--out-root", type=Path, default=Path("work_fluka_harness/eplus_raw_runs/eplus_seed24062401_n243727_chunks"))
    ap.add_argument("--comparison-out", type=Path, default=Path("work_fluka_harness/eplus_crosscode_comparison_243727"))
    ap.add_argument("--source-rotation-y-deg", type=float, default=0.0)
    ap.add_argument("--source-start-area-center-cm", type=float, nargs=3, metavar=("X", "Y", "Z"), default=None)
    ap.add_argument("--normalization-histories", type=int, default=None)
    ap.add_argument("--primary-source-sim-gz", type=Path, default=None)
    ap.add_argument("--geant4-source-contains", default=None)
    ap.add_argument("--defaults-sdum", default=None)
    ap.add_argument("--keep-going", action="store_true", help="Continue other chunks if a chunk fails; compare only valid PASS chunks.")
    ap.add_argument(
        "--max-parallel",
        type=int,
        default=DEFAULT_MAX_PARALLEL,
        help=f"Maximum simultaneously running chunks. Default {DEFAULT_MAX_PARALLEL} keeps parallelism inside one driver.",
    )
    ap.add_argument(
        "--chunk-timeout-s",
        type=float,
        default=0.0,
        help="Per-chunk wall-time watchdog in seconds. Use 0 to disable.",
    )
    ap.add_argument("--poll-interval-s", type=float, default=5.0)
    ap.add_argument(
        "--detach",
        action="store_true",
        help="Start one background driver process and return immediately; use this to avoid repeated foreground terminal popups.",
    )
    ap.add_argument("--driver-log", type=Path, default=None)
    args = ap.parse_args()

    if args.histories < 1 or args.chunks < 1 or args.max_parallel < 1:
        raise SystemExit("histories, chunks, and max-parallel must be positive")
    if args.chunk_timeout_s < 0 or args.poll_interval_s <= 0:
        raise SystemExit("chunk-timeout-s must be non-negative and poll-interval-s must be positive")
    if args.normalization_histories is not None and args.normalization_histories < args.histories:
        raise SystemExit("normalization-histories must be >= histories")
    if args.detach:
        return launch_detached(args)

    script = Path("work_fluka_harness/run_eplus_raw_mvp.py")
    cmp_script = Path("work_fluka_harness/build_eplus_crosscode_comparison.py")
    sizes = chunk_sizes(args.histories, args.chunks)
    args.out_root.mkdir(parents=True, exist_ok=True)
    with DriverLock(args.out_root / ".driver.lock"):
        return run_chunks(args, script, cmp_script, sizes)


def run_chunks(args: argparse.Namespace, script: Path, cmp_script: Path, sizes: list[int]) -> int:

    jobs: list[tuple[int, int, Path, list[str], Path]] = []
    skipped_valid: list[tuple[int, int, Path]] = []
    sim_start_index = 1
    for idx, n_hist in enumerate(sizes, start=1):
        out_dir = args.out_root / f"chunk_{idx:02d}_n{n_hist}"
        if is_valid_run(out_dir):
            skipped_valid.append((idx, n_hist, out_dir))
            sim_start_index += n_hist
            continue
        seed = args.seed + idx - 1
        cmd = [
            sys.executable,
            str(script),
            "--primary-tag",
            str(args.primary_tag),
            "--histories",
            str(n_hist),
            "--seed",
            str(seed),
            "--out-dir",
            str(out_dir),
            "--source-rotation-y-deg",
            str(args.source_rotation_y_deg),
        ]
        cmd.extend(["--normalization-histories", str(args.normalization_histories or args.histories)])
        if args.defaults_sdum is not None:
            cmd.extend(["--defaults-sdum", str(args.defaults_sdum)])
        if args.source_start_area_center_cm is not None:
            cmd.extend(["--source-start-area-center-cm", *(str(v) for v in args.source_start_area_center_cm)])
        if args.primary_source_sim_gz is not None:
            cmd.extend(["--primary-source-sim-gz", str(args.primary_source_sim_gz)])
            cmd.extend(["--primary-source-sim-start-index", str(sim_start_index)])
            sim_start_index += n_hist
        log = out_dir.with_suffix(".driver.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        jobs.append((idx, n_hist, out_dir, cmd, log))

    if skipped_valid:
        print(
            "skipping existing valid chunks: "
            + ", ".join(f"{idx:02d}" for idx, _n_hist, _out_dir in skipped_valid),
            flush=True,
        )

    pending = list(jobs)
    active: list[ChunkProc] = []
    completed: list[tuple[int, int, Path, int]] = []
    started_dirs: list[Path] = []
    last_report = 0.0
    if not jobs:
        print("all chunks already valid; rebuilding combined comparison", flush=True)

    while jobs:
        while pending and len(active) < args.max_parallel:
            idx, n_hist, out_dir, cmd, log = pending.pop(0)
            fh = log.open("w", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            active.append(
                ChunkProc(
                    idx=idx,
                    n_hist=n_hist,
                    out_dir=out_dir,
                    proc=proc,
                    log_handle=fh,
                    started_at=time.time(),
                )
            )
            started_dirs.append(out_dir)
            print(f"started chunk {idx:02d}: histories={n_hist} seed={args.seed + idx - 1} out={out_dir}", flush=True)

        failed: list[tuple[int, int]] = []
        now = time.time()
        for chunk in list(active):
            if (
                args.chunk_timeout_s > 0
                and chunk.proc.poll() is None
                and now - chunk.started_at > args.chunk_timeout_s
            ):
                terminate_chunk(chunk, signal.SIGTERM)
                try:
                    chunk.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    terminate_chunk(chunk, signal.SIGKILL)
                    chunk.proc.wait(timeout=10)
            if chunk.proc.poll() is None:
                continue
            rc = int(chunk.proc.returncode)
            chunk.log_handle.close()
            active.remove(chunk)
            completed.append((chunk.idx, chunk.n_hist, chunk.out_dir, rc))
            print(f"finished chunk {chunk.idx:02d}: returncode={rc} out={chunk.out_dir}", flush=True)
            if rc != 0:
                failed.append((chunk.idx, rc))

        if now - last_report >= 30.0:
            totals_lines = 0
            deposits_lines = 0
            for out_dir in started_dirs:
                totals_lines += line_count(
                    next(out_dir.glob("fluka_run/**/*event_totals_tmp.csv"), out_dir / "missing_event_totals")
                )
                deposits_lines += line_count(
                    next(out_dir.glob("fluka_run/**/*raw_deposits_tmp.csv"), out_dir / "missing_raw_deposits")
                )
            print(
                f"progress: done={len(completed)}/{len(jobs)} active={len(active)} pending={len(pending)} "
                f"event_total_lines={totals_lines} raw_deposit_lines={deposits_lines}",
                flush=True,
            )
            last_report = now

        if failed and not args.keep_going:
            for chunk in active:
                if chunk.proc.poll() is None:
                    terminate_chunk(chunk, signal.SIGTERM)
                chunk.log_handle.close()
            print(f"failed chunks: {failed}", flush=True)
            return 2
        if len(completed) == len(jobs):
            break
        if not active and not pending:
            break
        time.sleep(args.poll_interval_s)

    valid = list(skipped_valid)
    valid.extend((idx, n_hist, out_dir) for idx, n_hist, out_dir, _rc in completed if is_valid_run(out_dir))
    valid = sorted(valid, key=lambda row: row[0])
    invalid = [(idx, out_dir) for idx, _n_hist, out_dir, _rc in completed if not is_valid_run(out_dir)]
    print(f"valid chunks: {len(valid)}/{len(sizes)}", flush=True)
    if invalid:
        print("invalid chunks: " + ", ".join(f"{idx}:{out_dir}" for idx, out_dir in invalid), flush=True)
    if not valid:
        return 2

    cmp_cmd = [sys.executable, str(cmp_script), "--primary-tag", str(args.primary_tag)]
    for _idx, _n_hist, out_dir in valid:
        cmp_cmd.extend(["--fluka-run", str(out_dir)])
    cmp_cmd.extend(["--out-dir", str(args.comparison_out)])
    if args.geant4_source_contains:
        cmp_cmd.extend(["--geant4-source-contains", str(args.geant4_source_contains)])
    print("building combined comparison", flush=True)
    cmp_proc = subprocess.run(cmp_cmd, text=True)
    return cmp_proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
