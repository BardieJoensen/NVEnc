#!/usr/bin/env python3
"""Run the preregistered source-budget SVT preset-policy trial.

The runner is deliberately self-contained.  It derives the encoder command from
the preserved causal receipt and permits only the declared preset and bitrate
changes.  A run directory is created exclusively, so a calibration cannot
overwrite the first trial.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT", "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
CASE = "e05-1440"
ARCHIVE = Path("/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019")
ARCHIVE_CMD = ARCHIVE / CASE / "b-baseline-try2-command.json"
ARCHIVE_BIN = ARCHIVE / "SvtAv1EncApp-unmodified"
WORKER = ROOT / "worker"
FIXTURE = ROOT / "fixtures" / CASE


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_capture(argv: list[str], *, cwd: Path | None = None) -> dict:
    p = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False)
    return {"argv": argv, "returncode": p.returncode,
            "stdout": p.stdout, "stderr": p.stderr}


def ffprobe(path: Path, *extra: str) -> dict:
    r = run_capture(["ffprobe", "-v", "error", *extra, "-of", "json", str(path)])
    if r["returncode"]:
        raise RuntimeError(f"ffprobe failed for {path}: {r['stderr']}")
    return json.loads(r["stdout"] or "{}")


def input_header(path: Path) -> dict:
    with path.open("rb") as f:
        line = f.readline().decode("ascii")
    if not line.startswith("YUV4MPEG2 "):
        raise ValueError(f"not a Y4M input: {path}")
    fields = {}
    for token in line.rstrip("\n").split()[1:]:
        if token.startswith("W"): fields["W"] = token[1:]
        elif token.startswith("H"): fields["H"] = token[1:]
        elif token.startswith("F"): fields["F"] = token[1:]
        elif token.startswith("C"): fields["C"] = token[1:]
    if fields.get("W") != "1920" or fields.get("H") != "1080" or fields.get("F") != "24:1":
        raise ValueError(f"unexpected input geometry/cadence: {fields}")
    if not fields.get("C", "").startswith("420p10"):
        raise ValueError(f"unexpected input pixel format: {fields.get('C')}")
    return {"header": line.rstrip("\n"), "fields": fields}


def derive_command(request_kbps: int, run_dir: Path, input_path: Path, binary: Path) -> list[str]:
    archived = json.loads(ARCHIVE_CMD.read_text())
    av = list(archived["argv"])
    expected = ["nice", "-n", "10", "taskset", "-c", "0-7"]
    if av[:6] != expected:
        raise ValueError(f"archived affinity/nice prefix changed: {av[:6]}")
    def replace_after(flag: str, value: str) -> None:
        try:
            i = av.index(flag)
        except ValueError as e:
            raise ValueError(f"archived command lacks {flag}") from e
        av[i + 1] = value
    av[6] = str(binary)
    replace_after("-i", str(input_path))
    replace_after("-b", str(run_dir / "out.ivf"))
    replace_after("--preset", "0")
    replace_after("--tbr", str(request_kbps))
    replace_after("-o", str(run_dir / "recon.yuv"))
    required = {"--tune": "0", "--rc": "1", "--lp": "1", "--film-grain": "0",
                "--film-grain-denoise": "0", "--color-range": "0",
                "--color-primaries": "1", "--transfer-characteristics": "1",
                "--matrix-coefficients": "1", "--progress": "0"}
    for flag, value in required.items():
        try: i = av.index(flag)
        except ValueError as e: raise ValueError(f"archived command lacks {flag}") from e
        if av[i + 1] != value: raise ValueError(f"unexpected archived {flag}: {av[i+1]}")
    if av[av.index("--preset") + 1] != "0":
        raise AssertionError("preset substitution failed")
    return av


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=[CASE])
    ap.add_argument("tag", help="fresh run tag, e.g. preset0-1x0")
    ap.add_argument("request_kbps", type=int)
    args = ap.parse_args()
    if args.request_kbps <= 0 or not args.tag or "/" in args.tag or args.tag.startswith("."):
        ap.error("invalid request or run tag")
    validity = json.loads((FIXTURE / "validity.json").read_text())
    source_mbps = float(validity["source_mbps"])
    fps = float(validity["fps"])
    target_mbps = source_mbps * 0.995
    run_dir = WORKER / "runs" / args.case / args.tag
    run_dir.mkdir(parents=True, exist_ok=False)
    script_hash = sha(Path(__file__).resolve())
    input_path = FIXTURE / "input10.y4m"
    if not input_path.is_file() or not ARCHIVE_BIN.is_file() or not ARCHIVE_CMD.is_file():
        raise FileNotFoundError("fixture or immutable causal archive input is missing")
    ih = input_header(input_path)
    historical_path = FIXTURE / 'historical-input-validation.json'
    historical = json.loads(historical_path.read_text())
    input_sha = sha(input_path)
    assert historical['all336_exact_Y4M_bytes_match_prior']
    assert input_sha == historical['input']['sha256']
    bin_dir = WORKER / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / "SvtAv1EncApp-unmodified"
    if binary.exists():
        if sha(binary) != sha(ARCHIVE_BIN):
            raise RuntimeError(f"worker binary exists with wrong SHA: {binary}")
    else:
        shutil.copy2(ARCHIVE_BIN, binary)
        binary.chmod(binary.stat().st_mode | 0o111)
    if sha(binary) != sha(ARCHIVE_BIN):
        raise RuntimeError("copied binary SHA does not match immutable archive")
    argv = derive_command(args.request_kbps, run_dir, input_path, binary)
    shutil.copy2(Path(__file__).resolve(), run_dir / "measured-runner.py")
    env = {k: v for k, v in os.environ.items() if not (k.startswith("PANTHEON_") or k in {"DETAIL_DIR", "TRACE_DIR"})}
    version = run_capture([str(binary), "--version"])
    receipt = {
        "status": "prepared", "case": args.case, "tag": args.tag,
        "created_utc": utc(), "cwd": str(run_dir), "argv": argv,
        "env": {k: env[k] for k in sorted(env) if k in {"PATH", "LC_ALL", "LANG"}},
        "script": {"path": str(Path(__file__).resolve()), "sha256": script_hash},
        "archive_command": {"path": str(ARCHIVE_CMD), "sha256": sha(ARCHIVE_CMD)},
        "archive_binary": {"path": str(ARCHIVE_BIN), "sha256": sha(ARCHIVE_BIN)},
        "binary": {"path": str(binary), "sha256": sha(binary), "version": version},
        "input": {"path": str(input_path), "sha256": input_sha, **ih},
        "historical_input_validation": {"path": str(historical_path), "sha256": sha(historical_path)},
        "validity": {"path": str(FIXTURE / "validity.json"), "sha256": sha(FIXTURE / "validity.json"),
                     "source_mbps": source_mbps, "fps": fps, "target_mbps_99_5": target_mbps},
        "request_kbps": args.request_kbps,
    }
    (run_dir / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    start = time.monotonic(); start_utc = utc()
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with (run_dir / "encode.log").open("w") as log:
        log.write("# argv " + json.dumps(argv) + "\n")
        log.flush()
        proc = subprocess.run(argv, cwd=run_dir, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    elapsed = time.monotonic() - start
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt.update({"status": "validating" if proc.returncode == 0 else "encode_failed", "start_utc": start_utc, "end_utc": utc(),
                    "wall_seconds": elapsed, "returncode": proc.returncode,
                    "cumulative_child_ru_maxrss_delta": max(0, usage_after.ru_maxrss - usage_before.ru_maxrss),
                    "memory_note": "cumulative RUSAGE_CHILDREN high-water delta; not per-process peak"})
    (run_dir / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    out = run_dir / "out.ivf"
    recon = run_dir / "recon.yuv"
    if proc.returncode == 0 and out.is_file():
        log_text = (run_dir / "encode.log").read_text(errors="replace")
        if not re.search(r"preset / tune / pred struct\s*:\s*0\s*/\s*VQ\s*/", log_text):
            raise RuntimeError("encoder log lacks effective preset 0 / VQ settings")
        if not re.search(r"BRC mode / target bitrate \(kbps\)\s*:\s*VBR\s*/", log_text):
            raise RuntimeError("encoder log lacks effective VBR settings")
        expected_recon = 1920 * 1080 * 3 // 2 * 2 * 336
        if not recon.is_file() or recon.stat().st_size != expected_recon:
            raise RuntimeError(f"recon size mismatch: expected {expected_recon}, got {recon.stat().st_size if recon.exists() else None}")
        receipt["output"] = {"path": str(out), "sha256": sha(out), "size": out.stat().st_size,
                             "ffprobe": ffprobe(out, "-show_streams", "-show_format")}
        receipt["recon"] = {"path": str(recon), "sha256": sha(recon), "size": recon.stat().st_size}
        stream = receipt["output"]["ffprobe"].get("streams", [{}])[0]
        if (stream.get("codec_name"), stream.get("width"), stream.get("height"), stream.get("pix_fmt")) != ("av1", 1920, 1080, "yuv420p10le"):
            raise RuntimeError(f"unexpected output stream metadata: {stream}")
        assert [stream.get(k) for k in ('color_range','color_space','color_transfer','color_primaries')] == ['tv','bt709','bt709','bt709']
        packets = ffprobe(out, "-select_streams", "v:0", "-show_packets",
                          "-show_entries", "packet=pts_time,dts_time,size,flags") .get("packets", [])
        packets = sorted(packets, key=lambda p: float(p["pts_time"]))
        pts = [float(p["pts_time"]) for p in packets]
        if len(packets) != 336 or len(set(pts)) != 336:
            raise RuntimeError(f"expected 336 packets, got {len(packets)}")
        cadence = 1.0 / fps
        if any(abs((b - a) - cadence) > 1e-6 for a, b in zip(pts, pts[1:])):
            raise RuntimeError("IVF packet PTS cadence is not strict")
        mkv = run_dir / "out.mkv"
        remux = run_capture(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-c", "copy", str(mkv)])
        if remux["returncode"]:
            raise RuntimeError(f"IVF remux failed: {remux['stderr']}")
        mkv_packets = ffprobe(mkv, "-select_streams", "v:0", "-show_packets",
                              "-show_entries", "packet=pts_time,dts_time,size,flags").get("packets", [])
        mkv_packets = sorted(mkv_packets, key=lambda p: float(p["pts_time"]))
        if len(mkv_packets) != 336 or len({float(p["pts_time"]) for p in mkv_packets}) != 336:
            raise RuntimeError(f"expected 336 unique MKV packets, got {len(mkv_packets)}")
        mkv_pts = [float(p['pts_time']) for p in mkv_packets]
        assert all(mkv_pts[i+1]>mkv_pts[i] for i in range(335))
        assert all(abs((pt-mkv_pts[0])*fps-i)<.03 for i,pt in enumerate(mkv_pts))
        receipt['remux'] = remux
        receipt['remux_tool'] = {'path': shutil.which('ffmpeg'), 'sha256': sha(Path(shutil.which('ffmpeg')))}
        receipt['mkv_output'] = {'path': str(mkv), 'sha256': sha(mkv), 'size': mkv.stat().st_size}
        assert sha(input_path) == input_sha
        selected = packets[96:336]
        mkv_selected = mkv_packets[96:336]
        seconds = len(selected) / fps
        actual = sum(int(p["size"]) for p in mkv_selected) * 8 / seconds / 1e6
        window = {"fps": fps, "packet_count": len(packets), "selected_indices": [96, 336],
                  "selected_seconds": seconds, "actual_mbps": actual,
                  "ivf_actual_mbps": sum(int(p["size"]) for p in selected) * 8 / seconds / 1e6,
                  "source_mbps": source_mbps, "target_mbps_99_5": target_mbps,
                  "within_source_ceiling": actual <= source_mbps,
                  "within_99_floor": actual >= source_mbps * .99,
                  "decisive_rate_gate": source_mbps * .99 <= actual <= source_mbps,
                  "ivf_packets": packets, "mkv_packets": mkv_packets}
        (run_dir / "packet-window.json").write_text(json.dumps(window, indent=2) + "\n")
        receipt["packet_window"] = window
        if not window["decisive_rate_gate"]:
            receipt["status"] = "rate_gate_failed"
        else:
            receipt["status"] = "encoded"
    (run_dir / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return 0 if receipt["status"] == "encoded" and receipt.get("packet_window", {}).get("decisive_rate_gate") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"encode_svt.py: {e}", file=sys.stderr)
        raise
