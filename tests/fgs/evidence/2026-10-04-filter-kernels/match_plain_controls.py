#!/usr/bin/env python3
"""Match plain NVENC payload rates to a complete, pinned identity receipt.

Uses the exact recorded deployed AV1 argv, removing FGS/table output and replacing
CQP/QVBR with VBR. Every attempt is preserved. No quality or identity verdict is
inferred from a matched bitrate. --validate-only hashes inputs but launches no GPU
process. All new files must live below this script's task workspace.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import statistics
import subprocess
import sys

import repeat_identity as h

ROOT = Path(__file__).resolve().parent
DEPLOYED_SHA = "c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b"
TOLERANCE = 0.03
GIB = 1 << 30
REMOVE = {"--av1-film-grain", "--film-grain-table-out", "--cqp", "--qvbr", "-o"}


def within_task(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f"Path must be inside {ROOT}: {path}")
    return path


def plain_base(command):
    """Transform only the five expected options, preserving every other token."""
    out, removed, i = [], {}, 0
    while i < len(command):
        token = command[i]
        if token in REMOVE:
            if i + 1 >= len(command) or token in removed:
                raise ValueError(f"Missing/duplicate option in recorded argv: {token}")
            removed[token] = command[i + 1]
            i += 2
        else:
            if token.split("=", 1)[0] in REMOVE | {"--vbr", "--cbr", "--film-grain-table"}:
                raise ValueError(f"Unsupported combined/conflicting option: {token}")
            out.append(token)
            i += 1
    if not {"--av1-film-grain", "--film-grain-table-out", "-o"} <= removed.keys():
        raise ValueError("Recorded FGS/table/output arguments missing")
    if len({"--cqp", "--qvbr"} & removed.keys()) != 1:
        raise ValueError("Expected exactly one recorded CQP/QVBR option")
    return out, removed


def option(command, name):
    if command.count(name) != 1 or command.index(name) + 1 == len(command):
        raise ValueError(f"Expected exactly one valued {name} option")
    return command[command.index(name) + 1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--identity-report", required=True, type=Path)
    ap.add_argument("--report-sha256", required=True, help="SHA256 of the designated complete identity report")
    ap.add_argument("--output-dir", required=True, type=Path, help="Fresh directory below task scratch")
    ap.add_argument("--cases", nargs="+", default=["all"], help="Exact input names, or all (default)")
    ap.add_argument("--max-trials", type=int, default=8, help="1..8 attempts per case; no tolerance relaxation")
    ap.add_argument("--timeout", type=int, default=600, help="Seconds per encode, 1..3600")
    ap.add_argument("--max-output-gib", type=int, default=16, help="Total new output budget, 1..32 GiB")
    ap.add_argument("--validate-only", action="store_true", help="Write pinned validation receipt without encoding")
    args = ap.parse_args()
    if not 1 <= args.max_trials <= 8 or not 1 <= args.timeout <= 3600 or not 1 <= args.max_output_gib <= 32:
        ap.error("Require 1..8 trials, 1..3600 seconds and 1..32 GiB")
    report_path = within_task(args.identity_report)
    report_pin = h.pin(report_path, args.report_sha256)
    identity = json.loads(report_path.read_text())
    if identity.get("complete") is not True:
        raise ValueError("Designated identity report is incomplete")
    arms = [a for a in identity["manifest"]["arms"] if a["name"] == "deployed"]
    if len(arms) != 1 or arms[0]["sha256"] != DEPLOYED_SHA or arms[0].get("prefix", []):
        raise ValueError("Require the exact deployed binary and empty recorded prefix")
    binary = within_task(arms[0]["binary"])
    pins = {str(binary): h.pin(binary, DEPLOYED_SHA), str(report_path): report_pin}
    ffmpeg = str(Path(identity["ffmpeg"]["path"]).resolve())
    pins[ffmpeg] = h.pin(ffmpeg, identity["ffmpeg"]["sha256"])
    inputs = {i["name"]: i for i in identity["manifest"]["inputs"]}
    if len(inputs) != len(identity["manifest"]["inputs"]):
        raise ValueError("Duplicate manifest input names")
    selected = list(inputs) if args.cases == ["all"] else args.cases
    if len(set(selected)) != len(selected) or any(n not in inputs or not re.fullmatch(r"[A-Za-z0-9_-]+", n) for n in selected):
        raise ValueError("Unknown, duplicate or invalid input name")
    cases = {}
    for name in selected:
        item = inputs[name]
        source = within_task(item["path"])
        pins[str(source)] = h.pin(source, item["sha256"])
        rows = [r for r in identity["runs"] if r["input"] == name and r["arm"] == "deployed" and r["stage"] == "av1"]
        if not rows or any(not r.get("complete") or r.get("returncode") != 0 for r in rows):
            raise ValueError(f"Incomplete/missing deployed FGS encodes: {name}")
        bases = [plain_base(r["argv"]) for r in rows]
        if any(base != bases[0][0] for base, _ in bases):
            raise ValueError(f"Recorded FGS arguments differ across repeats: {name}")
        base, removed = bases[0]
        invariant_removed = {k: v for k, v in removed.items() if k not in ("-o", "--film-grain-table-out")}
        if any({k: v for k, v in r.items() if k not in ("-o", "--film-grain-table-out")} != invariant_removed for _, r in bases):
            raise ValueError(f"Recorded FGS/rate settings differ across repeats: {name}")
        frames = item["frames"]
        if not isinstance(frames, int) or not 1 <= frames <= 3600 or base[0] != str(binary):
            raise ValueError(f"Invalid frame bound or deployed binary argv: {name}")
        if option(base, "-i") != str(source) or option(base, "--frames") != str(frames) or option(base, "--codec") != "av1":
            raise ValueError(f"Source/frame/codec disagreement: {name}")
        geometry = {(r["width"], r["height"], r["rate"], r["scale"]) for r in rows}
        if len(geometry) != 1 or any(r["binary_sha256"] != DEPLOYED_SHA or r["source_sha256"] != item["sha256"] or r["packets"] != frames for r in rows):
            raise ValueError(f"Recorded pins/frame/geometry disagree: {name}")
        width, height, rate, scale = next(iter(geometry))
        if not 1 <= width <= 7680 or not 1 <= height <= 4320 or rate <= 0 or scale <= 0:
            raise ValueError(f"Unbounded geometry/timebase: {name}")
        payloads = [float(r["payload_kbps"]) for r in rows]
        if any(not math.isfinite(p) or p <= 0 for p in payloads):
            raise ValueError(f"Invalid payload bitrate: {name}")
        target = statistics.median(payloads)
        depth = item["output_depth"]
        if depth not in (8, 10) or option(base, "--output-depth") != str(depth):
            raise ValueError(f"Unsupported/mismatched output depth: {name}")
        cases[name] = {"source": str(source), "source_sha256": item["sha256"], "frames": frames,
                       "output_depth": depth,
                       "geometry": [width, height, rate, scale], "base_argv": base,
                       "removed_from_first_recorded_argv": removed, "fgs_payload_kbps": payloads,
                       "target_median_kbps": target, "reference_ivf_md5_states": sorted({r["file_md5"] for r in rows}),
                       "per_file_limit_bytes": max(64 << 20, width * height * 6 * frames + (16 << 20)),
                       "matched": False, "runs": []}
    destination = within_task(args.output_dir)
    destination.mkdir(parents=True, exist_ok=False)
    receipt = {"complete": False, "validated_only": args.validate_only, "all_matched": False,
               "identity_report": str(report_path), "identity_report_sha256": args.report_sha256,
               "identity_report_pass_value_not_control_verdict": identity.get("identity_pass"),
               "script_sha256": h.digest(__file__), "helper_sha256": h.digest(h.__file__),
               "pins": pins, "deployed_binary_sha256": DEPLOYED_SHA, "ffmpeg": identity["ffmpeg"],
               "relative_tolerance": TOLERANCE,
               "max_trials_per_case": args.max_trials, "max_output_bytes": args.max_output_gib * GIB,
               "minimum_free_reserve_bytes": 2 * GIB, "cases": cases,
               "environment": {k: os.environ[k] for k in ("LD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES", "CUDA_CACHE_PATH") if k in os.environ},
               "note": "Matched payload is a plain-control rate check, not a grain-fidelity, state-identity or throughput verdict. Accepted outputs also pass strict libdav1d grain-off decode/frame/hash checks. Every attempted IVF/log is retained."}

    def save():
        temporary = destination / "report.json.tmp"
        temporary.write_text(json.dumps(receipt, indent=2) + "\n")
        temporary.replace(destination / "report.json")

    def stable():
        for path, pin in pins.items():
            if h.identity(path) != pin["stat"]:
                raise RuntimeError(f"Pinned file metadata changed: {path}")

    save()
    try:
        if args.validate_only:
            stable()
            receipt["complete"] = True
            print(f"Validated {len(cases)} cases; no encoder launched. Receipt: {destination / 'report.json'}")
            return 0
        for name, case in cases.items():
            target = case["target_median_kbps"]
            bitrate, tried = max(1, round(target)), set()
            for trial in range(1, args.max_trials + 1):
                if bitrate in tried:
                    case["unresolved"] = f"Ratio adjustment repeated VBR target {bitrate}; no tolerance relaxation"
                    break
                tried.add(bitrate)
                stable()
                cap = case["per_file_limit_bytes"]
                used = sum(p.stat().st_size for p in destination.rglob("*") if p.is_file())
                if used + 2 * cap + (64 << 20) > args.max_output_gib * GIB or shutil.disk_usage(destination).free < 2 * cap + (64 << 20) + 2 * GIB:
                    raise RuntimeError("Output budget/free-space reserve cannot cover bounded IVF and log")
                directory = destination / name / f"trial-{trial:02d}"
                directory.mkdir(parents=True, exist_ok=False)
                output, log_path = directory / "plain.ivf", directory / "encode.log"
                command = case["base_argv"] + ["--vbr", str(bitrate), "-o", str(output)]
                run = {"trial": trial, "requested_vbr_kbps": bitrate, "argv": command,
                       "directory": str(directory), "complete": False, "matched": False}
                case["runs"].append(run)
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
                            os.killpg(process.pid, signal.SIGKILL)  # Only this newly created process group.
                            process.wait()
                            raise
                    stable()
                    if run["returncode"]:
                        raise RuntimeError(f"Encoder exited {run['returncode']}")
                    counts = re.findall(r"encoded\s+(\d+)\s+frames", log_path.read_text(errors="replace"))
                    if not counts or int(counts[-1]) != case["frames"]:
                        raise ValueError("Missing/wrong encoder completion frame count")
                    run.update(h.inspect_ivf(output, case["frames"]))
                    if [run[k] for k in ("width", "height", "rate", "scale")] != case["geometry"]:
                        raise ValueError("Plain IVF geometry/timebase differs from FGS reference")
                    run["relative_mismatch"] = run["payload_kbps"] / target - 1
                    run["matched"] = abs(run["relative_mismatch"]) <= TOLERANCE
                    if run["matched"]:
                        run.update(h.decoded_md5(ffmpeg, output, run, case["output_depth"], case["frames"], args.timeout))
                        stable()
                    run["complete"] = True
                    case["matched"] = run["matched"]
                    print(f"{name} trial {trial}: VBR {bitrate}, actual {run['payload_kbps']:.6f}, mismatch {run['relative_mismatch']:+.3%}", flush=True)
                except (subprocess.TimeoutExpired, RuntimeError, ValueError) as error:
                    run["matched"] = False
                    run["failure"] = f"{type(error).__name__}: {error}"
                    case["unresolved"] = run["failure"]
                finally:
                    (directory / "receipt.json").write_text(json.dumps(run, indent=2) + "\n")
                    save()
                if not run["complete"] or case["matched"]:
                    break
                bitrate = max(1, round(bitrate * target / run["payload_kbps"]))
            if not case["matched"] and "unresolved" not in case:
                case["unresolved"] = f"No match after {args.max_trials} bounded trials; tolerance unchanged"
            save()
        stable()
        for path, pin in pins.items():
            h.pin(path, pin["sha256"])
        stable()
        receipt.update(complete=True, all_matched=all(c["matched"] for c in cases.values()))
        return 0 if receipt["all_matched"] else 1
    except BaseException as error:
        receipt["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()


if __name__ == "__main__":
    sys.exit(main())
