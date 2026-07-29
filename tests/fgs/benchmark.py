#!/usr/bin/env python3
"""Record and compare reproducible AV1 film-grain analyzer benchmarks.

This runner deliberately uses only generated fixtures.  It records the exact
NVEncC binary, repository revision, GPU, commands, logs, timings, KAT results,
and retain-sweep CSV in one JSON document suitable for before/after review.

Examples:
  python3 tests/fgs/benchmark.py --output /tmp/fgs-before.json
  python3 tests/fgs/benchmark.py --output /tmp/fgs-after.json \
      --compare-to /tmp/fgs-before.json

Environment:
  NVENCC                 encoder binary (default: build-fgs-cuda/nvencc)
  FGS_KAT_DENOISER       fft3d, bilateral, or motion (default: fft3d)
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NVENCC = os.path.abspath(os.environ.get("NVENCC", os.path.join(REPO, "build-fgs-cuda", "nvencc")))
ALL_SUITES = ("cpu", "kat", "retain")


def run_text(argv, env=None):
    """Run a diagnostic command without making an unavailable tool fatal."""
    try:
        result = subprocess.run(argv, cwd=REPO, env=env, capture_output=True,
                                text=True, check=False)
    except OSError:
        return ""
    return (result.stdout or result.stderr).strip()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def run_suite(name, argv, env):
    print(f"== {name}: {' '.join(argv)}", flush=True)
    started = time.monotonic()
    result = subprocess.run(argv, cwd=REPO, env=env, capture_output=True,
                            text=True, check=False)
    duration = time.monotonic() - started
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr,
              end="" if result.stderr.endswith("\n") else "\n")
    return {
        "name": name,
        "argv": argv,
        "returncode": result.returncode,
        "passed": result.returncode == 0,
        "duration_seconds": round(duration, 3),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def parse_kat(output):
    summary = {}
    match = re.search(r"^== summary ==\s*$([\s\S]*)", output, re.MULTILINE)
    if match:
        for name, status in re.findall(r"^\s+([a-zA-Z0-9_]+): (PASS|FAIL)\s*$",
                                       match.group(1), re.MULTILINE):
            summary[name] = status == "PASS"
    metrics = {}
    patterns = {
        "coarse_capture_percent": r"captured ([0-9.]+)% of injected coarse-grain sigma",
        "coarse_source_correlation": r"coarse-grain source correlation: lag-one ([0-9.]+)",
        "ramp_strength_correlation": r"strength curve follows intensity ramp: corr ([0-9.]+)",
        "dark_max_mean_delta": r"black level preserved under synthesis: max \|mean delta\| ([0-9.]+)",
        "detail_transfer_gain": r"fine detail survives the cleaned base: high-pass transfer ([0-9.]+)",
        "detail_edge_rmse_8bit": r"edge/detail distortion remains bounded: edge RMSE ([0-9.]+)",
    }
    for key, pattern in patterns.items():
        found = re.search(pattern, output)
        if found:
            metrics[key] = float(found.group(1))
    return {"tests": summary, "metrics": metrics}


def load_retain_rows(path):
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, newline="") as source:
        for row in csv.DictReader(source):
            rows.append({
                "bits": int(row["bits"]),
                "retain": float(row["retain"]),
                "bytes": int(row["bytes"]),
                "retained_ratio": float(row["retained_ratio"]),
                "position_corr": float(row["position_corr"]),
                "synth_ratio": float(row["synth_ratio"]),
                "synth_target": float(row["synth_target"]),
                "total_ratio": float(row["total_ratio"]),
                "pass": row["pass"].lower() == "true",
            })
    return rows


def environment_record(label):
    git_status = run_text(["git", "status", "--porcelain"])
    gpu = run_text([
        "nvidia-smi", "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader",
    ])
    encoder_version = run_text([NVENCC, "--version"]).splitlines()
    ffmpeg_version = run_text(["ffmpeg", "-version"]).splitlines()
    return {
        "schema": 1,
        "label": label,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repository": {
            "branch": run_text(["git", "branch", "--show-current"]),
            "commit": run_text(["git", "rev-parse", "HEAD"]),
            "dirty": bool(git_status),
            "status": git_status.splitlines(),
        },
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "gpu": gpu.splitlines(),
        },
        "encoder": {
            "path": NVENCC,
            "sha256": sha256(NVENCC),
            "version": encoder_version[0] if encoder_version else "",
        },
        "ffmpeg": ffmpeg_version[0] if ffmpeg_version else "",
        "denoiser": os.environ.get("FGS_KAT_DENOISER", "fft3d"),
    }


def retain_index(report):
    return {(row["bits"], row["retain"]): row
            for row in report.get("retain_sweep", [])}


def print_comparison(before, after):
    print("\n== before/after ==")
    print(f"  before: {before.get('label', '')} {before.get('repository', {}).get('commit', '')[:12]}")
    print(f"  after:  {after.get('label', '')} {after.get('repository', {}).get('commit', '')[:12]}")
    before_suites = {suite["name"]: suite for suite in before.get("suites", [])}
    for suite in after.get("suites", []):
        old = before_suites.get(suite["name"])
        old_status = "PASS" if old and old.get("passed") else "FAIL/missing"
        new_status = "PASS" if suite.get("passed") else "FAIL"
        timing = ""
        if old:
            timing = f" ({old['duration_seconds']:.2f}s -> {suite['duration_seconds']:.2f}s)"
        print(f"  {suite['name']}: {old_status} -> {new_status}{timing}")

    old_metrics = before.get("kat", {}).get("metrics", {})
    new_metrics = after.get("kat", {}).get("metrics", {})
    for key in sorted(set(old_metrics) | set(new_metrics)):
        print(f"  {key}: {old_metrics.get(key, 'missing')} -> {new_metrics.get(key, 'missing')}")

    old_retain = retain_index(before)
    for key, row in sorted(retain_index(after).items()):
        old = old_retain.get(key)
        if not old:
            continue
        byte_delta = row["bytes"] - old["bytes"]
        byte_percent = 100.0 * byte_delta / max(old["bytes"], 1)
        print(f"  {key[0]}-bit retain={key[1]:.2f}: bytes {byte_delta:+d} ({byte_percent:+.2f}%), "
              f"total {old['total_ratio']:.3f}->{row['total_ratio']:.3f}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="JSON result path")
    parser.add_argument("--label", default="", help="short result label")
    parser.add_argument("--suites", default=",".join(ALL_SUITES),
                        help="comma-separated: cpu,kat,retain")
    parser.add_argument("--compare-to", help="prior JSON result to compare")
    return parser.parse_args()


def main():
    args = parse_args()
    suites = tuple(item.strip() for item in args.suites.split(",") if item.strip())
    invalid = sorted(set(suites) - set(ALL_SUITES))
    if not suites or invalid:
        sys.exit(f"invalid --suites: {','.join(invalid) if invalid else 'empty'}")
    if not os.path.isfile(NVENCC):
        sys.exit(f"NVEncC binary not found: {NVENCC}")

    report = environment_record(args.label)
    report["suites"] = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="nvenc-fgs-benchmark-") as work:
        env = os.environ.copy()
        env["NVENCC"] = NVENCC
        env["FGS_KAT_DIR"] = os.path.join(work, "kat")
        env["FGS_RETAIN_SWEEP_DIR"] = os.path.join(work, "retain")
        commands = {
            "cpu": ["bash", "tests/fgs/run_cpu_tests.sh"],
            "kat": [sys.executable, "tests/fgs/fgs_kat.py"],
            "retain": [sys.executable, "tests/fgs/retain_sweep.py", "--bits", "both"],
        }
        for suite in suites:
            result = run_suite(suite, commands[suite], env)
            report["suites"].append(result)
            if suite == "kat":
                report["kat"] = parse_kat(result["stdout"])
            elif suite == "retain":
                report["retain_sweep"] = load_retain_rows(
                    os.path.join(env["FGS_RETAIN_SWEEP_DIR"], "results.csv"))
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    report["passed"] = all(suite["passed"] for suite in report["suites"])

    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as destination:
        json.dump(report, destination, indent=2, sort_keys=True)
        destination.write("\n")
    print(f"benchmark: {output}")

    if args.compare_to:
        with open(args.compare_to) as source:
            print_comparison(json.load(source), report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
