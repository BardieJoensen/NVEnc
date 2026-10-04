#!/usr/bin/env python3
"""Run paired nsys traces from an identity manifest; never infer fps from GPU sums.

The first of exactly two arms is the comparison reference. Each round reverses
arm order. Defaults select Lost Tapes 240, Amphibia 240 and Taxi HDR 24 from the
manifest, using its exact seek/decoder/QVBR settings and verified SSD copies.
--validate-only checks all pins and commands without launching a GPU workload.
"""
import argparse
from collections import Counter
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys

import profile_summary
import repeat_identity as identity


def statistics_row(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def metrics(profile):
    result = {}

    def flatten(prefix, value):
        if isinstance(value, dict):
            for key, child in value.items():
                flatten(prefix + "." + key, child)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result[prefix] = value

    for name in ("kernel_total", "fgs_kernel_total", "kernel_groups", "host_synchronization"):
        flatten(name, profile[name])
    for name in ("total", "directions"):
        flatten("memcpy." + name, profile["memcpy"][name])
    return result


def summarize(rows, names):
    per_arm = {name: [r for r in rows if r["arm"] == name] for name in names}
    measurements = {name: [metrics(r["profile"]) for r in values] for name, values in per_arm.items()}
    keys = set(measurements[names[0]][0])
    if any(set(v) != keys for values in measurements.values() for v in values):
        raise RuntimeError("Profile metric schemas differ between runs")
    summary = {}
    for key in sorted(keys):
        values = {name: [r[key] for r in measurements[name]] for name in names}
        a, b = (statistics.median(values[name]) for name in names)
        ratios = [y / x for x, y in zip(values[names[0]], values[names[1]]) if x != 0]
        summary[key] = {"arms": {name: statistics_row(v) for name, v in values.items()},
                        "median_ratio_second_to_first": b / a if a else None,
                        "paired_round_ratio_second_to_first": statistics_row(ratios) if len(ratios) == len(values[names[0]]) else None}
    states = {name: Counter((r["ivf"]["file_md5"], r["table_md5"]) for r in values) for name, values in per_arm.items()}
    return {"metrics": summary, "observed_av1_table_states": {
        "equal": set(states[names[0]]) == set(states[names[1]]),
        "arms": {name: [{"ivf_md5": pair[0], "table_md5": pair[1], "runs": count}
                        for pair, count in sorted(counts.items())] for name, counts in states.items()}}}


def execute(argv, log, timeout):
    # Own a separate process group, so timeout/interrupt can only kill our run.
    with log.open("xb") as stream:
        process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    if code:
        raise RuntimeError(f"Command exited {code}; see {log}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True, help="Fresh directory under /tmp/downloads")
    ap.add_argument("--inputs", nargs="+", default=["losttapes", "amphibia", "taxi_hdr"])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--nsys", default="nsys")
    ap.add_argument("--fgs-dir", type=Path, default=Path(__file__).parent / "baseline-pin/tests/fgs")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    if not 2 <= args.repeats <= 20 or args.timeout <= 0:
        ap.error("Require 2..20 repeats and positive timeout")
    manifest = json.loads(args.manifest.read_text())
    arms = manifest["arms"]
    inputs = [next((i for i in manifest["inputs"] if i["name"] == n), None) for n in args.inputs]
    if len(arms) != 2 or not inputs or any(i is None for i in inputs):
        ap.error("Require exactly two arms and every selected input in the manifest")
    for group in (arms, inputs):
        names = [i["name"] for i in group]
        if len(names) != len(set(names)) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", n) for n in names):
            ap.error("Arm/input names must be unique simple path components")
    root = Path("/tmp/downloads").resolve()
    destination = args.output_dir.resolve()
    if not destination.is_relative_to(root) or destination.exists():
        ap.error("Output must be a fresh directory under /tmp/downloads")
    nsys = shutil.which(args.nsys)
    if not nsys:
        ap.error(f"nsys not found: {args.nsys}")
    nsys = str(Path(nsys).resolve())
    prefix = json.loads(os.environ.get("FGS_ENCODER_PREFIX_JSON", "[]"))
    pins = {}
    for arm in arms:
        arm["binary"] = str(Path(arm["binary"]).resolve(strict=True))
        arm["prefix"] = identity.argv_list(arm.get("prefix", prefix), "prefix")
        pins[arm["binary"]] = identity.pin(arm["binary"], arm["sha256"])
    for item in inputs:
        path = Path(item["path"]).resolve(strict=True)
        if not path.is_relative_to(root) or item.get("original_source") is not True or "kat" in item:
            raise ValueError("Profile inputs must be original-source SSD copies under /tmp/downloads")
        if not isinstance(item["frames"], int) or not 1 <= item["frames"] <= 3600 or not 0 <= float(item["qvbr"]) <= 63:
            raise ValueError("Require bounded frame count and valid explicit QVBR")
        item.update(path=str(path), color_args=identity.COLOR, fgs=identity.DEFAULT_FGS, output_depth=10)
        item["input_args"] = identity.argv_list(item.get("input_args", ["--avhw"]), "input_args")
        item["metadata_args"] = identity.argv_list(item.get("metadata_args", []), "metadata_args")
        identity.raw_metadata(item)
        pins[str(path)] = identity.pin(path, item["sha256"])
    sys.path.insert(0, str(args.fgs_dir.resolve(strict=True)))
    filmgrn = importlib.import_module("filmgrn")
    report = {"complete": False, "manifest": manifest, "selected_inputs": args.inputs,
              "manifest_sha256": identity.digest(args.manifest), "pins": pins, "repeats": args.repeats,
              "helper_sha256": {Path(p).name: identity.digest(p) for p in
                                (__file__, identity.__file__, profile_summary.__file__, filmgrn.__file__)},
              "nsys": {"path": nsys, "sha256": identity.digest(nsys)}, "runs": [], "comparisons": {},
              "environment": {k: os.environ[k] for k in ("LD_LIBRARY_PATH", "CUDA_VISIBLE_DEVICES", "CUDA_CACHE_PATH") if k in os.environ},
              "notes": ["These traces report CUDA work and host API duration separately, never their sum or inferred fps.",
                        "All startup/drain activities are included; denominators are checked encoded frame counts.",
                        "The GPU is shared; alternate arms and report all repeats and min/median/max.",
                        "Observed IVF/table states complement identity testing; no raw base is captured here."]}
    if args.validate_only:
        report["preview_argv"] = [identity.encode_argv(i, a, "av1", destination / "video.ivf", destination / "grain.tbl")
                                  for i in inputs for a in arms]
        print(json.dumps(report, indent=2)); return 0
    destination.mkdir(parents=True, exist_ok=False)

    def save():
        temp = destination / "report.json.tmp"
        temp.write_text(json.dumps(report, indent=2) + "\n")
        temp.replace(destination / "report.json")

    save()
    try:
        for item in inputs:
            for repeat in range(1, args.repeats + 1):
                for arm in (arms if repeat % 2 else list(reversed(arms))):
                    directory = destination / item["name"] / f"round-{repeat:02d}-{arm['name']}"
                    directory.mkdir(parents=True, exist_ok=False)
                    if shutil.disk_usage(directory).free < 3 << 30:
                        raise RuntimeError("Need at least 3 GiB free scratch space")
                    for path in (arm["binary"], item["path"]):
                        if identity.identity(path) != pins[path]["stat"]:
                            raise RuntimeError(f"Pinned file changed: {path}")
                    output, table, trace = directory / "video.ivf", directory / "grain.tbl", directory / "trace"
                    command = identity.encode_argv(item, arm, "av1", output, table)
                    profile_command = [nsys, "profile", "--trace=cuda,nvtx", "--sample=none", "--cpuctxsw=none",
                                       "--export=none", "--force-overwrite=false", "--output", str(trace)] + command
                    sqlite = trace.with_suffix(".sqlite")
                    export_command = [nsys, "export", "--type=sqlite", "--force-overwrite=false", "--output", str(sqlite), str(trace.with_suffix(".nsys-rep"))]
                    row = {"input": item["name"], "arm": arm["name"], "repeat": repeat, "complete": False,
                           "binary_sha256": arm["sha256"], "source_sha256": item["sha256"], "directory": str(directory),
                           "encode_argv": command, "profile_argv": profile_command, "export_argv": export_command}
                    report["runs"].append(row); save()
                    execute(profile_command, directory / "profile.log", args.timeout)
                    counts = re.findall(r"encoded\s+(\d+)\s+frames", (directory / "profile.log").read_text(errors="replace"))
                    if not counts or int(counts[-1]) != item["frames"]:
                        raise RuntimeError(f"Missing/wrong encoded frame count: {directory}")
                    row.update(encoded_frames=int(counts[-1]), ivf=identity.inspect_ivf(output, item["frames"]),
                               table_md5=identity.digest(table, "md5"), table_entries=len(filmgrn.load(table)))
                    execute(export_command, directory / "export.log", args.timeout)
                    with sqlite3.connect(sqlite.as_uri() + "?mode=ro", uri=True) as db:
                        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    missing = {"StringIds", "CUPTI_ACTIVITY_KIND_KERNEL", "CUPTI_ACTIVITY_KIND_RUNTIME",
                               "CUPTI_ACTIVITY_KIND_MEMCPY", "ENUM_CUDA_MEMCPY_OPER"} - tables
                    if missing:
                        raise RuntimeError(f"Missing required nsys tables {sorted(missing)}: {sqlite}")
                    row["profile"] = profile_summary.main([str(sqlite), "--frames", str(item["frames"]), "--output", str(directory / "summary.json")])
                    if not row["profile"]["memcpy"]["available"] or not row["profile"]["memcpy"]["direction_labels_available"]:
                        raise RuntimeError(f"Unsupported memcpy schema: {sqlite}")
                    row["complete"] = True; save()
                    print(f"{item['name']} {arm['name']} round {repeat}: {row['profile']['fgs_kernel_total']['ms_per_declared_frame']:.6f} FGS kernel ms/frame", flush=True)
            report["comparisons"][item["name"]] = summarize([r for r in report["runs"] if r["input"] == item["name"]], [a["name"] for a in arms])
            save()
        for path, pinned in pins.items():
            identity.pin(path, pinned["sha256"])
            if identity.identity(path) != pinned["stat"]:
                raise RuntimeError(f"Pinned file metadata changed: {path}")
        report["complete"] = True
        report["observed_state_sets_equal"] = all(c["observed_av1_table_states"]["equal"] for c in report["comparisons"].values())
        return 0
    except BaseException as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()


if __name__ == "__main__":
    sys.exit(main())
