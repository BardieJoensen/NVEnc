#!/usr/bin/env python3
"""Bounded Silo plain-control QVBR calibration after VBR payload quantization.

Keeps the original max50000 and all non-FGS, non-quality arguments. Starts at
QVBR30, then bisects quality [1,63] on exact 1/256 units for at most 12 encodes.
The actual AV1 payload must stay within the unchanged +/-3% FGS target band.
This is only rate matching for a plain control; it makes no quality claim.
"""
import argparse
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import statistics
import subprocess
import sys

import match_plain_controls_v2 as v2
import repeat_identity as h

ROOT = Path(__file__).resolve().parent
V2_SHA = "9a3e6b4ce395b1e2801494325a5c6a982c7dbe8ffab0d94dc29174cc10eb3777"
TOLERANCE = 0.03
GIB = 1 << 30
PREDECESSORS = {
    "reports/kernels-silo-plain-v2/report.json": "de93674b1b3420ba494925852cd5e04114ba444ffee8040c7111fad271749fd6",
    "reports/kernels-silo-plain-refinement/report.json": "52820fa3c90bef06b1a51d6a06a4950f757591b61d4474e96f013bdedf95ced7",
}


def quality_text(units):
    if not 256 <= units <= 63 * 256:
        raise ValueError("Quality is outside [1,63]")
    # Eight decimal places represent every 1/256 step exactly; the CLI truncates
    # fractional quality to eight binary bits (NVEncCmd.cpp:85-89).
    return f"{units / 256:.8f}"


def next_quality(low, high, current, actual, target):
    if abs(actual / target - 1) <= TOLERANCE:
        return None
    if actual > target:
        low = current + 1  # Larger quality number reduces bitrate.
    else:
        high = current - 1
    if low > high:
        raise ValueError("No remaining 1/256 quality setting in the bounded interval")
    return {"low_units": low, "high_units": high, "next_units": (low + high) // 2}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--identity-report", type=Path, required=True)
    ap.add_argument("--report-sha256", required=True)
    ap.add_argument("--output-dir", type=Path, required=True, help="Must be new and inside task scratch")
    ap.add_argument("--max-trials", type=int, default=12, help="1..12, including initial QVBR30")
    ap.add_argument("--timeout", type=int, default=600, help="1..3600 seconds per encode/decode")
    ap.add_argument("--validate-only", action="store_true", help="Pin/check/write receipt without GPU execution")
    args = ap.parse_args()
    if not 1 <= args.max_trials <= 12 or not 1 <= args.timeout <= 3600:
        ap.error("Require 1..12 trials and 1..3600 seconds")
    report_path = v2.within_task(args.identity_report)
    pins = {str(report_path): h.pin(report_path, args.report_sha256),
            str(ROOT / "match_plain_controls_v2.py"): h.pin(ROOT / "match_plain_controls_v2.py", V2_SHA)}
    for relative, sha in PREDECESSORS.items():
        pins[str(ROOT / relative)] = h.pin(ROOT / relative, sha)
    identity = json.loads(report_path.read_text())
    if identity.get("complete") is not True:
        raise ValueError("Designated identity report is incomplete")
    items = [i for i in identity["manifest"]["inputs"] if i["name"] == "silo_partial"]
    arms = [a for a in identity["manifest"]["arms"] if a["name"] == "deployed"]
    if len(items) != 1 or len(arms) != 1 or arms[0]["sha256"] != v2.DEPLOYED_SHA or arms[0].get("prefix", []):
        raise ValueError("Require one pinned Silo case and exact deployed arm with no wrapper")
    item, arm = items[0], arms[0]
    binary, source = v2.within_task(arm["binary"]), v2.within_task(item["path"])
    ffmpeg = str(Path(identity["ffmpeg"]["path"]).resolve())
    for path, sha in ((binary, v2.DEPLOYED_SHA), (source, item["sha256"]), (ffmpeg, identity["ffmpeg"]["sha256"])):
        pins[str(path)] = h.pin(path, sha)
    rows = [r for r in identity["runs"] if r["input"] == "silo_partial" and r["arm"] == "deployed" and r["stage"] == "av1"]
    if not rows or any(not r.get("complete") or r.get("returncode") != 0 for r in rows):
        raise ValueError("Missing/incomplete deployed Silo FGS encodes")
    bases = [v2.plain_base(r["argv"]) for r in rows]
    base = bases[0][0]
    if any(b != base or removed.get("--qvbr") != "30" for b, removed in bases):
        raise ValueError("Expected identical original non-FGS args and QVBR30")
    if base[0] != str(binary) or v2.option(base, "-i") != str(source) or v2.option(base, "--max-bitrate") != "50000":
        raise ValueError("Deployed binary/source/max50000 argv differs")
    frames, depth = item["frames"], item["output_depth"]
    if frames != 24 or depth != 10 or v2.option(base, "--frames") != "24" or v2.option(base, "--output-depth") != "10" or v2.option(base, "--codec") != "av1":
        raise ValueError("Unexpected Silo frame/depth/codec definition")
    if any(r["binary_sha256"] != v2.DEPLOYED_SHA or r["source_sha256"] != item["sha256"] or r["packets"] != frames for r in rows):
        raise ValueError("Reference row source/binary/frame pin differs")
    geometry = {(r["width"], r["height"], r["rate"], r["scale"]) for r in rows}
    if geometry != {(1918, 802, 24000, 1001)}:
        raise ValueError("Unexpected Silo IVF geometry/timebase")
    target = statistics.median(r["payload_kbps"] for r in rows)
    destination = v2.within_task(args.output_dir)
    destination.mkdir(parents=True, exist_ok=False)
    cap = max(64 << 20, 1918 * 802 * 6 * frames + (16 << 20))
    receipt = {"complete": False, "validated_only": args.validate_only, "matched": False,
               "identity_report": str(report_path), "identity_report_sha256": args.report_sha256,
               "script_sha256": h.digest(__file__), "helper_sha256": h.digest(h.__file__), "v2_sha256": V2_SHA,
               "pins": pins, "source_sha256": item["sha256"], "deployed_binary_sha256": v2.DEPLOYED_SHA,
               "base_argv": base, "frames": frames, "output_depth": depth, "geometry": list(next(iter(geometry))),
               "fgs_payload_kbps": [r["payload_kbps"] for r in rows], "target_kbps": target,
               "relative_tolerance": TOLERANCE, "quality_range": [1, 63], "quality_step": "1/256",
               "initial_qvbr": 30, "max_trials": args.max_trials, "max_bitrate_kbps_unchanged": 50000,
               "per_file_limit_bytes": cap, "max_output_bytes": 8 * GIB, "minimum_free_reserve_bytes": 2 * GIB,
               "environment": {k: os.environ[k] for k in ("LD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES", "CUDA_CACHE_PATH") if k in os.environ},
               "reason": "Plain VBR has a discrete payload jump: requested 2093/2094 gives 1302.521 kbps and 2095..2106 gives 1438.977, outside the fixed 3% band around 1392.863. Try fractional QVBR solely to obtain the required matched-rate plain control. Canonical FGS and candidate settings stay unchanged.",
               "note": "Bisection assumes decreasing payload as quality number rises. Finite failure remains unresolved; no tolerance change or grain-quality/throughput claim.", "runs": []}

    def stable():
        for path, pin in pins.items():
            if h.identity(path) != pin["stat"]:
                raise RuntimeError(f"Pinned file metadata changed: {path}")

    def save():
        temporary = destination / "report.json.tmp"
        temporary.write_text(json.dumps(receipt, indent=2) + "\n")
        temporary.replace(destination / "report.json")

    save()
    try:
        stable()
        if args.validate_only:
            receipt["complete"] = True
            print(f"Validated Silo QVBR control; no encoder launched. Receipt: {destination / 'report.json'}")
            return 0
        low, high, current, tried = 256, 63 * 256, 30 * 256, set()
        for trial in range(1, args.max_trials + 1):
            if current in tried:
                receipt["unresolved"] = "Repeated quantized quality target; no tolerance relaxation"
                break
            tried.add(current)
            stable()
            used = sum(p.stat().st_size for p in destination.rglob("*") if p.is_file())
            if used + 2 * cap + (64 << 20) > 8 * GIB or shutil.disk_usage(destination).free < 2 * cap + (64 << 20) + 2 * GIB:
                raise RuntimeError("Insufficient bounded scratch output/free-space reserve")
            directory = destination / f"trial-{trial:02d}"
            directory.mkdir(exist_ok=False)
            output, log_path = directory / "plain.ivf", directory / "encode.log"
            text = quality_text(current)
            command = base + ["--qvbr", text, "-o", str(output)]
            run = {"trial": trial, "quality_units": current, "requested_qvbr": text,
                   "search_interval_units": [low, high], "argv": command,
                   "directory": str(directory), "complete": False, "matched": False}
            receipt["runs"].append(run)
            save()
            try:
                def limits():
                    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
                with log_path.open("xb") as log:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True, preexec_fn=limits)
                    try:
                        run["returncode"] = process.wait(timeout=args.timeout)
                    except BaseException:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
                stable()
                if run["returncode"]:
                    raise RuntimeError(f"Encoder exited {run['returncode']}")
                log_text = log_path.read_text(errors="replace")
                counts = re.findall(r"encoded\s+(\d+)\s+frames", log_text)
                rates = re.findall(r"Bitrate\s+(\d+)\s+kbps\s+\(Max:\s*(\d+)\s+kbps\)", log_text)
                qualities = re.findall(r"Target Quality\s+(\d+(?:\.\d+)?)", log_text)
                if not counts or int(counts[-1]) != frames or not rates or tuple(map(int, rates[-1])) != (0, 50000):
                    raise ValueError("Wrong/missing encoded count or effective QVBR average0/max50000")
                if not qualities or abs(float(qualities[-1]) - current / 256) > 0.005001:
                    raise ValueError("Effective logged quality differs beyond its two-decimal display precision")
                run.update(logged_qvbr=qualities[-1], logged_average_kbps=0, logged_max_bitrate_kbps=50000)
                run.update(h.inspect_ivf(output, frames))
                if [run[k] for k in ("width", "height", "rate", "scale")] != receipt["geometry"]:
                    raise ValueError("Plain IVF geometry/timebase differs from the pinned source")
                run["relative_mismatch"] = run["payload_kbps"] / target - 1
                if abs(run["relative_mismatch"]) <= TOLERANCE:
                    run.update(h.decoded_md5(ffmpeg, output, run, depth, frames, args.timeout))
                    stable()
                    run["matched"] = receipt["matched"] = True
                run["complete"] = True
                print(f"Silo trial {trial}: QVBR{text}, actual {run['payload_kbps']:.6f}, mismatch {run['relative_mismatch']:+.3%}", flush=True)
                if not run["matched"]:
                    decision = next_quality(low, high, current, run["payload_kbps"], target)
                    run["next_quality"] = decision
                    low, high, current = decision["low_units"], decision["high_units"], decision["next_units"]
            except (subprocess.TimeoutExpired, RuntimeError, ValueError) as error:
                run["failure"] = f"{type(error).__name__}: {error}"
                receipt["unresolved"] = run["failure"]
            finally:
                (directory / "receipt.json").write_text(json.dumps(run, indent=2) + "\n")
                save()
            if run["matched"] or "failure" in run:
                break
        stable()
        for path, pin in pins.items():
            h.pin(path, pin["sha256"])
        stable()
        if not receipt["matched"] and "unresolved" not in receipt:
            receipt["unresolved"] = f"No match within {args.max_trials} fractional-QVBR trials; tolerance unchanged"
        receipt["complete"] = True
        return 0 if receipt["matched"] else 1
    except BaseException as error:
        receipt["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()


if __name__ == "__main__":
    sys.exit(main())
