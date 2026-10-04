#!/usr/bin/env python3
"""Bounded, sequential FGS identity comparison; never generates source fixtures.

Manifest: {"arms": [{"name": "prod", "binary": "/absolute/nvencc",
"sha256": "..."}, ...], "inputs": [{"name": "kat", "path": "/.../src.y4m",
"sha256": "...", "kat": "const_luma", "frames": 32},
{"name": "real", "path": "/.../original-clip.mkv", "sha256": "...",
"original_source": true, "frames": 240, "qvbr": 29,
"input_args": ["--avhw", "--timestamp-passthrough", "--video-track", "1"]}]}

KAT definitions/colors/retention come from the pinned prod tests/fgs/fgs_kat.py.
KAT encodes retain their fixture depth and canonical CQP 20 settings.
Real clips use production video core defaults, output depth 10, bilateral FGS.
input_args defaults to [--avhw] for real clips; supply source-specific timestamp,
track, SAR and metadata options explicitly (metadata_args). No library lookup.
Optional seek is an NVEncC --seek value. Optional plain controls encode the
original input without FGS at the supplied VBR target; payload bitrate matching
is measured, never assumed. Reports do not claim grain-quality qualification.

FGS_ENCODER_PREFIX_JSON can be a JSON argv list prepended to each binary, e.g.
["env", "LD_LIBRARY_PATH=/path"]. Each arm may override with a prefix list;
wrapper paths must expose the same absolute binary/input/output paths.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

DEFAULT_FGS = "denoise=auto,chroma=auto,denoiser=bilateral"
CORE = ["--max-bitrate", "50000", "--preset", "quality", "--tune", "hq",
        "--lookahead", "32", "--lookahead-level", "3", "--aq", "--aq-temporal"]
COLOR = ["--colormatrix", "auto", "--colorprim", "auto", "--transfer", "auto",
         "--colorrange", "auto", "--chromaloc", "auto"]
COPY_METADATA = ["--master-display", "copy", "--max-cll", "copy", "--video-metadata", "copy"]
ENCODED_METADATA = {"--master-display", "--max-cll", "--video-metadata", "--atc-sei",
                    "--dhdr10-info", "--dolby-vision-profile", "--dolby-vision-rpu",
                    "--dolby-vision-rpu-prm"}
RAW_METADATA = {"--colormatrix", "--colorprim", "--transfer", "--colorrange",
                "--chromaloc", "--sar", "--dar", "--videoformat"}
FORBIDDEN = {"-i", "--input", "-o", "--output", "--codec", "-c", "--frames",
             "--trim", "--seek", "--av1-film-grain", "--film-grain-table",
             "--film-grain-table-out", "--qvbr", "--cqp", "--vbr", "--cbr",
             "--audio-copy", "--sub-copy", "--chapter-copy", "--output-depth"}


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def identity(path):
    st = Path(path).stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def pin(path, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected or ""):
        raise ValueError(f"Required lowercase SHA256 is missing/invalid: {path}")
    before = identity(path)
    actual = digest(path)
    if actual != expected or before != identity(path):
        raise ValueError(f"Pinned identity mismatch: {path}")
    return {"path": str(Path(path).resolve()), "sha256": actual, "stat": before}


def argv_list(value, label):
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(f"{label} must be a JSON string array")
    if any(x.split("=", 1)[0] in FORBIDDEN for x in value):
        raise ValueError(f"{label} overrides a harness-owned option")
    return value


def hash_y4m(path, expected_frames=None):
    pixels, whole = hashlib.md5(), hashlib.md5()
    frame_md5 = []
    with Path(path).open("rb") as stream:
        header = stream.readline(4096)
        if not header.startswith(b"YUV4MPEG2 ") or not header.endswith(b"\n"):
            raise ValueError("Invalid Y4M header")
        fields = {x[:1]: x[1:] for x in header.split()[1:]}
        width, height = int(fields[b"W"]), int(fields[b"H"])
        csp = fields.get(b"C", b"420jpeg")
        if csp not in (b"420", b"420jpeg", b"420mpeg2", b"420paldv", b"420p10"):
            raise ValueError(f"Unsupported raw color format: {csp!r}")
        if width % 2 or height % 2 or width <= 0 or height <= 0:
            raise ValueError("Invalid 4:2:0 geometry")
        depth = 10 if csp == b"420p10" else 8
        frame_bytes = width * height * 3 // 2 * (2 if depth == 10 else 1)
        whole.update(header)
        while True:
            marker = stream.readline(4096)
            if not marker:
                break
            if not (marker == b"FRAME\n" or marker.startswith(b"FRAME ")) or not marker.endswith(b"\n"):
                raise ValueError("Invalid Y4M frame marker")
            data = stream.read(frame_bytes)
            if len(data) != frame_bytes:
                raise ValueError("Truncated raw frame")
            whole.update(marker); whole.update(data); pixels.update(data)
            frame_md5.append(hashlib.md5(data).hexdigest())
    if not frame_md5 or (expected_frames is not None and len(frame_md5) != expected_frames):
        raise ValueError(f"Raw frame count {len(frame_md5)} != {expected_frames}")
    return {"file_md5": whole.hexdigest(), "pixel_md5": pixels.hexdigest(),
            "frames": len(frame_md5), "frame_md5": frame_md5, "width": width,
            "height": height, "depth": depth, "frame_bytes": frame_bytes}


def inspect_ivf(path, expected_frames):
    with Path(path).open("rb") as stream:
        header = stream.read(32)
        if len(header) != 32 or header[:4] != b"DKIF" or header[8:12] != b"AV01":
            raise ValueError("Not AV1 IVF")
        version, header_size = struct.unpack_from("<HH", header, 4)
        width, height, rate, scale, declared = struct.unpack_from("<HHIII", header, 12)
        if version != 0 or header_size != 32 or not rate or not scale:
            raise ValueError("Invalid IVF header")
        packets, payload_bytes, timestamps, packet_md5 = 0, 0, [], []
        while True:
            block = stream.read(12)
            if not block:
                break
            if len(block) != 12:
                raise ValueError("Truncated IVF packet header")
            size, timestamp = struct.unpack("<IQ", block)
            data = stream.read(size)
            if len(data) != size or size == 0:
                raise ValueError("Truncated/empty IVF packet")
            packets += 1; payload_bytes += size; timestamps.append(timestamp)
            packet_md5.append(hashlib.md5(data).hexdigest())
    if packets != expected_frames or declared not in (0, expected_frames):
        raise ValueError(f"IVF packets/header {packets}/{declared} != {expected_frames}")
    duration = Fraction(expected_frames * scale, rate)
    return {"file_md5": digest(path, "md5"), "packets": packets,
            "width": width, "height": height, "rate": rate, "scale": scale,
            "timestamps": timestamps, "packet_md5": packet_md5,
            "payload_bytes": payload_bytes, "payload_kbps": payload_bytes * 8 / float(duration) / 1000}


def raw_metadata(item):
    """Retain explicit raw-compatible options; document encoded-only omissions."""
    values, kept = iter(item["metadata_args"]), []
    omitted = list(COPY_METADATA) if "kat" not in item else []
    for token in values:
        option = token.split("=", 1)[0]
        if option not in RAW_METADATA | ENCODED_METADATA:
            raise ValueError(f"Unsupported raw metadata option {option!r}; classify it explicitly before this trial")
        group = [token]
        if "=" not in token:
            value = next(values, None)
            if value is None or value.startswith("--"):
                raise ValueError(f"Missing metadata value for {option}")
            group.append(value)
        (omitted if option in ENCODED_METADATA else kept).extend(group)
    return kept, omitted


def encode_argv(item, arm, stage, output, table, plain_rate=None):
    command = arm["prefix"] + [arm["binary"]] + item["input_args"]
    if "kat" not in item:
        command += ["--allow-other-negative-pts"]
    if item.get("seek") is not None:
        command += ["--seek", str(item["seek"])]
    command += ["-i", item["path"], "--frames", str(item["frames"]),
                "--codec", "raw" if stage == "raw" else "av1",
                "--output-depth", str(item["output_depth"])]
    if stage != "raw":
        command += (["--vbr", str(round(plain_rate))] if stage == "plain" else
                    ["--cqp", "20"] if "kat" in item else ["--qvbr", str(item["qvbr"])])
        if "kat" not in item:
            command += CORE
    # Color/range choices also describe the diagnostic raw base.
    command += item["color_args"] + (raw_metadata(item)[0] if stage == "raw" else item["metadata_args"])
    if "kat" not in item and stage != "raw":
        command += COPY_METADATA
    if stage != "plain":
        command += ["--av1-film-grain", item["fgs"], "--film-grain-table-out", str(table)]
    if "kat" in item:
        command += ["--log-level", "debug"]
    return command + ["-o", str(output)]


def decoded_md5(ffmpeg, output, row, depth, frames, timeout):
    directory = output.parent
    per_frame, all_pixels = directory / "grain-off.framemd5", directory / "grain-off.md5"
    pix_fmt = "yuv420p10le" if depth == 10 else "yuv420p"
    command = [ffmpeg, "-nostdin", "-v", "error", "-xerror", "-c:v", "libdav1d",
               "-threads", "2", "-filmgrain", "0", "-i", str(output)]
    # Both tiny hash outputs share one software decode; no decoded media is retained.
    for format_name, destination in (("framemd5", per_frame), ("md5", all_pixels)):
        command += ["-map", "0:v:0", "-an", "-sn", "-pix_fmt", pix_fmt,
                    "-c:v", "rawvideo", "-threads", "1", "-fps_mode", "passthrough",
                    "-f", format_name, str(destination)]
    row["decode_argv"] = command
    with (directory / "decode.log").open("wb") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if completed.returncode:
        raise RuntimeError(f"Strict grain-off decode failed: {directory}")
    records = [line.split(",") for line in per_frame.read_text().splitlines() if line and not line.startswith("#")]
    frame_bytes = row["width"] * row["height"] * 3 // 2 * (2 if depth == 10 else 1)
    if len(records) != frames or any(len(r) != 6 or int(r[4]) != frame_bytes for r in records):
        raise ValueError("Decoded grain-off frame count/size mismatch")
    match = re.fullmatch(r"MD5=([0-9a-f]{32})\s*", all_pixels.read_text())
    if not match or any(not re.fullmatch(r"[0-9a-f]{32}", r[5].strip()) for r in records):
        raise ValueError("Malformed decoded pixel MD5 output")
    return {"decoded_pixel_md5": match[1], "decoded_frame_md5": [r[5].strip() for r in records],
            "decoded_frames": len(records), "decoded_pix_fmt": pix_fmt}


def compare_sets(rows, names):
    result = {}
    for label, stage, keys in (("raw", "raw", ("pixel_md5", "table_md5")),
                              ("av1", "av1", ("file_md5", "table_md5")),
                              ("decoded_grain_off", "av1", ("decoded_pixel_md5",))):
        states = {}
        for name in names:
            selected = [r for r in rows if r["stage"] == stage and r["arm"] == name]
            states[name] = Counter(tuple(r[k] for k in keys) for r in selected)
        sets = [set(states[n]) for n in names]
        result[label] = {"keys": keys, "equal": bool(sets[0]) and all(s == sets[0] for s in sets),
                         "states": {n: [{"md5": list(s), "runs": count} for s, count in sorted(c.items())]
                                    for n, c in states.items()}}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True, help="Must not already exist")
    ap.add_argument("--fgs-dir", type=Path, default=Path("/home/bardie/git-repos/NVEnc-merge937/tests/fgs"))
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=1800, help="Seconds per bounded encoder run")
    ap.add_argument("--ffmpeg", default=os.environ.get("FGS_FFMPEG", "ffmpeg"),
                    help="Software libdav1d decoder for grain-off pixel hashes")
    ap.add_argument("--plain-bitrate", action="append", default=[], metavar="INPUT=KBPS",
                    help="Plain NVENC control on first arm; repeat after tuning target if actual rate differs")
    ap.add_argument("--plain-tolerance", type=float, default=0.03)
    ap.add_argument("--validate-only", action="store_true", help="Pin sources/binaries and validate manifest; no encoding")
    args = ap.parse_args()
    args.output_dir = args.output_dir.resolve()
    if not 2 <= args.repeats <= 20 or args.timeout <= 0 or not 0 < args.plain_tolerance < 1:
        ap.error("Require 2..20 repeats, positive timeout, and plain tolerance in (0,1)")
    manifest = json.loads(args.manifest.read_text())
    arms, inputs = manifest["arms"], manifest["inputs"]
    if len(arms) < 2 or not inputs:
        ap.error("Manifest requires at least two named arms and one explicit input")
    for group in (arms, inputs):
        names = [x["name"] for x in group]
        if len(set(names)) != len(names) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", n) for n in names):
            ap.error("Names must be unique, simple path components")
    sys.path.insert(0, str(args.fgs_dir.resolve()))
    kat, filmgrn = importlib.import_module("fgs_kat"), importlib.import_module("filmgrn")
    prefix = json.loads(os.environ.get("FGS_ENCODER_PREFIX_JSON", "[]"))
    pins = {}
    for arm in arms:
        arm["binary"] = str(Path(arm["binary"]).resolve())
        arm["prefix"] = argv_list(arm.get("prefix", prefix), "prefix")
        pins[arm["binary"]] = pin(arm["binary"], arm["sha256"])
    for item in inputs:
        item["path"] = str(Path(item["path"]).resolve())
        pins[item["path"]] = pin(item["path"], item["sha256"])
        if not isinstance(item["frames"], int) or not 1 <= item["frames"] <= 3600:
            raise ValueError("Every input requires bounded frames (1..3600)")
        if "kat" in item:
            spec = kat.TESTS[item["kat"]]
            source = hash_y4m(item["path"])
            expected = (spec.get("width", 1920), spec.get("height", 1080), spec.get("bits", 8))
            if (source["width"], source["height"], source["depth"]) != expected or source["frames"] < item["frames"]:
                raise ValueError("KAT source geometry/depth/length mismatch")
            item["kat_spec"] = spec
            item["output_depth"] = spec.get("bits", 8)
            item["color_args"] = kat.COLOR_ARGS.get(spec.get("color"), [])
            if spec.get("limited") and not spec.get("color"):
                item["color_args"] = ["--colorrange", "limited"]
            item["fgs"] = DEFAULT_FGS + (f",retain={spec['retain']}" if "retain" in spec else "")
        else:
            if item.get("original_source") is not True or not 0 <= float(item["qvbr"]) <= 63:
                raise ValueError("Real clips require original_source=true and explicit qvbr")
            item["color_args"] = COLOR
            item["fgs"] = DEFAULT_FGS
            item["output_depth"] = 10
        item["input_args"] = argv_list(item.get("input_args", [] if "kat" in item else ["--avhw"]), "input_args")
        item["metadata_args"] = argv_list(item.get("metadata_args", []), "metadata_args")
        raw_metadata(item)  # Reject unclassified explicit metadata before any run.
    plain = {}
    for option in args.plain_bitrate:
        name, value = option.split("=", 1)
        if name not in {i["name"] for i in inputs} or float(value) <= 0:
            raise ValueError("Unknown plain-control input or invalid bitrate")
        plain[name] = float(value)
    if args.validate_only:
        print(json.dumps({"valid": True, "pins": pins, "arms": arms, "inputs": inputs}, indent=2)); return 0
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        raise ValueError(f"FFmpeg not found: {args.ffmpeg}")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"complete": False, "identity_pass": False, "manifest": manifest,
              "manifest_sha256": digest(args.manifest), "harness_sha256": digest(__file__),
              "kat_module_sha256": digest(kat.__file__), "filmgrn_module_sha256": digest(filmgrn.__file__),
              "ffmpeg": {"path": ffmpeg, "sha256": digest(ffmpeg)},
              "pins": pins, "runs": [], "comparisons": {}, "plain_controls": {},
              "note": "Raw/table and AV1/table are independent runs. Raw pixels are not a capture of the corresponding encoder submission. State equality is finite-sample evidence, not universal determinism.",
              "raw_metadata_note": "Raw diagnostics preserve color/range arguments but omit encoded HDR/container metadata: master-display, max-cll, video-metadata and explicitly supplied encoded-only metadata. Raw cannot carry these; NVEncC rejects master-display/max-cll with codec raw. Each raw run lists its exact omitted arguments. AV1 keeps production metadata flags. Real runs use default production logging; KAT runs keep canonical debug logging."}

    def save():
        temp = args.output_dir / "report.json.tmp"
        temp.write_text(json.dumps(report, indent=2) + "\n")
        temp.replace(args.output_dir / "report.json")

    def run(item, arm, repeat, stage):
        directory = args.output_dir / item["name"] / arm["name"] / f"{stage}-{repeat:02d}"
        directory.mkdir(parents=True, exist_ok=False)
        output = directory / ("base.y4m" if stage == "raw" else "video.ivf")
        table = directory / "grain.tbl"
        # Conservative bounded raw allowance: 4K 10-bit; clips larger than 4K
        # should supply width/height so the preflight allowance is increased.
        raw_bytes = max(3840, item.get("width", 0)) * max(2160, item.get("height", 0)) * 3 * item["frames"]
        if shutil.disk_usage(directory).free < (raw_bytes if stage == "raw" else 1 << 30) + (2 << 30):
            raise RuntimeError("Insufficient scratch space for bounded output plus 2 GiB reserve")
        for path in (arm["binary"], item["path"]):
            if identity(path) != pins[path]["stat"]:
                raise RuntimeError(f"Pinned input changed: {path}")
        command = encode_argv(item, arm, stage, output, table, plain.get(item["name"]))
        row = {"input": item["name"], "arm": arm["name"], "repeat": repeat,
               "stage": stage, "argv": command, "binary_sha256": arm["sha256"],
               "source_sha256": item["sha256"], "directory": str(directory), "complete": False}
        if stage == "raw":
            row["raw_omitted_metadata_args"] = raw_metadata(item)[1]
        report["runs"].append(row); save()
        start = time.monotonic()
        with (directory / "encode.log").open("wb") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
        row.update(returncode=completed.returncode, elapsed_seconds=time.monotonic() - start)
        if completed.returncode:
            raise RuntimeError(f"Encoder failed: {directory}")
        text = (directory / "encode.log").read_text(errors="replace")
        counts = re.findall(r"encoded\s+(\d+)\s+frames", text)
        if not counts or int(counts[-1]) != item["frames"]:
            raise RuntimeError(f"Missing/wrong encoder completion count: {directory}")
        row.update(hash_y4m(output, item["frames"]) if stage == "raw" else inspect_ivf(output, item["frames"]))
        if stage != "raw":
            row.update(decoded_md5(ffmpeg, output, row, item["output_depth"], item["frames"], args.timeout))
        if stage != "plain":
            entries = filmgrn.load(table)
            row.update(table_md5=digest(table, "md5"), table_entries=len(entries),
                       active_table_entries=sum(bool(e["apply_grain"]) for e in entries))
        row.update(complete=True, output_bytes=output.stat().st_size)
        save()
        if stage == "raw":
            output.unlink()  # Unique new directory; this process created it.
            row["raw_deleted_after_hash"] = True; save()
        print(f"{item['name']} {arm['name']} {stage} {repeat}: {row.get('pixel_md5', row['file_md5'])}", flush=True)

    save()
    try:
        for item in inputs:
            for repeat in range(1, args.repeats + 1):
                # Alternate arm order to avoid assigning one arm every first run.
                for arm in (arms if repeat % 2 else list(reversed(arms))):
                    for stage in ("raw", "av1"):
                        run(item, arm, repeat, stage)
                if item["name"] in plain:
                    run(item, arms[0], repeat, "plain")
            rows = [r for r in report["runs"] if r["input"] == item["name"]]
            report["comparisons"][item["name"]] = compare_sets(rows, [a["name"] for a in arms])
            fgs_rates = sorted(r["payload_kbps"] for r in rows if r["stage"] == "av1" and r["arm"] == arms[0]["name"])
            controls = [r["payload_kbps"] for r in rows if r["stage"] == "plain"]
            reference_rate = fgs_rates[len(fgs_rates) // 2]
            report["plain_controls"][item["name"]] = {"supplied": bool(controls), "target_kbps": plain.get(item["name"]),
                "fgs_median_payload_kbps": reference_rate, "plain_payload_kbps": controls,
                "matched": bool(controls) and all(abs(r / reference_rate - 1) <= args.plain_tolerance for r in controls),
                "relative_tolerance": args.plain_tolerance}
            save()
        for path, pinned in pins.items():
            pin(path, pinned["sha256"])
            if identity(path) != pinned["stat"]:
                raise RuntimeError(f"Pinned file metadata changed: {path}")
        passed = all(stage["equal"] for item in report["comparisons"].values() for stage in item.values())
        controls_ok = all(not c["supplied"] or c["matched"] for c in report["plain_controls"].values())
        report.update(complete=True, identity_pass=passed,
                      all_inputs_have_matched_plain_control=all(c["matched"] for c in report["plain_controls"].values()))
        if not passed:
            report["failure"] = "Observed state sets differ; new/missing states are rejected, not waived as repeat variability"
        if not controls_ok:
            report["control_failure"] = "Plain control is not within supplied matched-rate tolerance; tune and repeat"
        return 0 if passed and controls_ok else 1
    except BaseException as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()


if __name__ == "__main__":
    sys.exit(main())
