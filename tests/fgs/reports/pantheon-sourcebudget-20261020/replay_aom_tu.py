#!/usr/bin/env python3
"""Replay a byte-neutral final-TU observation using immutable PSNR pass1 stats."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(os.environ.get(
    "PANTHEON_SOURCEBUDGET_ROOT",
    "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020",
))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path), "size": path.stat().st_size}


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


parser = argparse.ArgumentParser()
parser.add_argument("arm", choices=("off", "trace"))
parser.add_argument("tag")
parser.add_argument("--control-tag")
args = parser.parse_args()
assert re.fullmatch(r"[A-Za-z0-9_.-]+", args.tag)
assert not os.environ.get("LD_PRELOAD")
build_path = ROOT / "worker/aom-tu-r6/implementation-v3/build.json"
build = json.loads(build_path.read_text())
assert build["status"] == "build_complete"
assert build["source_before_after_reviewed_equal"]
build_bindings = {key: build[key] for key in (
    "baseline_source_manifest", "reviewed_source_manifest", "source_manifest_before",
    "source_manifest_after", "patch", "schema", "schema_text", "runner", "builder", "config",
)}
for bound in build_bindings.values():
    assert identity(bound["path"]) == bound
manifests = [json.loads(Path(build[key]["path"]).read_text()) for key in (
    "reviewed_source_manifest", "source_manifest_before", "source_manifest_after")]
assert manifests[0] == manifests[1] == manifests[2] and len(manifests[0]) == 1346
assert json.loads(Path(build["schema"]["path"]).read_text())["version"] == 3
library = Path(build["library"]["path"]).resolve()
assert sha(library) == build["library"]["sha256"]
config_path = library.parent / "config/aom_config.h"
assert sha(config_path) == "b97f78baf39c6d05d105d915f60a3665a204cc1fd4b6d8032f76cf61177f2fec"
control_path = None
if args.arm == "trace":
    assert args.control_tag and re.fullmatch(r"[A-Za-z0-9_.-]+", args.control_tag)
    control_path = ROOT / "parent/tu-observation/runs" / args.control_tag / "command.json"
    control = json.loads(control_path.read_text())
    assert control["status"] == "encoded" and control["arm"] == "off"
    assert control["exact_installed_ivf"] and control["returncode"] == 0
    assert control["build_receipt"] == identity(build_path)
    assert control["library"] == identity(library)
    assert identity(control["output"]["path"]) == control["output"]
else:
    assert args.control_tag is None
source_run = ROOT / "worker/runs/e05-1440/aom-psnr-1x2"
source_receipt = source_run / "command.json"
source = json.loads(source_receipt.read_text())
assert source["status"] == "encoded" and source["settings"]["tune"] == "psnr"
assert source["decisive_rate_gate"]
input_path = Path(source["input"]["path"])
assert sha(input_path) == source["input"]["sha256"]
stats_original = Path(source["passes"]["pass1"]["pass1_stats_snapshot"]["path"])
assert sha(stats_original) == source["passes"]["pass1"]["pass1_stats_snapshot"]["sha256"]
assert sha(source_run / "out.ivf") == source["ivf_sha256"]
assert sha("/usr/bin/ffmpeg") == source["ffmpeg"]["sha256"]
out = ROOT / "parent/tu-observation/runs" / args.tag
out.mkdir(parents=True, exist_ok=False)
default_excepthook = sys.excepthook

def preserve_unhandled(kind, error, traceback):
    dump(out / "unhandled-failure.json", {"status": "failed", "error": repr(error)})
    default_excepthook(kind, error, traceback)

sys.excepthook = preserve_unhandled
snapshot = out / "measured-runner.py"
shutil.copyfile(__file__, snapshot)
stats = out / "aom-pass.log-0.log"
shutil.copyfile(stats_original, stats)
assert sha(stats) == sha(stats_original)
cmd = list(source["commands"]["pass2"])
cmd[cmd.index("-passlogfile") + 1] = str(out / "aom-pass.log")
cmd[-1] = str(out / "out.ivf")
env = dict(os.environ)
env["LD_LIBRARY_PATH"] = str(library.parent)
env.pop("AOM_TRACE_PATH", None)
env.pop("AOM_TRACE_FD", None)
env.pop("AOM_NEUTRALIZE_SOURCE", None)
env.pop("AOM_TU_TRACE_FD", None)
ldd_cmd = ["ldd", "/usr/bin/ffmpeg"]
ldd = subprocess.run(ldd_cmd, env=env, text=True, capture_output=True, check=True)
loaded = re.findall(r"^\s*libaom\.so\.3 => (\S+)", ldd.stdout, re.M)
assert len(loaded) == 1 and Path(loaded[0]).resolve() == library
(out / "ldd.txt").write_text(ldd.stdout + ldd.stderr)
config_cmd = [
    sys.executable, "-c",
    "import ctypes,json,sys;"
    "x=ctypes.CDLL(sys.argv[1]);"
    "x.aom_codec_build_config.restype=ctypes.c_char_p;"
    "x.aom_codec_version_str.restype=ctypes.c_char_p;"
    "print(json.dumps({'build_config':x.aom_codec_build_config().decode(),"
    "'version':x.aom_codec_version_str().decode()}))",
    str(library),
]
config = subprocess.run(config_cmd, env=env, text=True, capture_output=True, check=True)
library_config = json.loads(config.stdout)
trace_fd = None
trace_path = out / "trace.bin"
if args.arm == "trace":
    trace_fd = os.open(trace_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600)
    env["AOM_TU_TRACE_FD"] = str(trace_fd)
receipt = {
    "status": "running", "arm": args.arm, "tag": args.tag,
    "source_command": identity(source_receipt), "input": identity(input_path),
    "build_receipt": identity(build_path), "build_bindings": build_bindings, "library": identity(library),
    "library_config_command": config_cmd, "library_config": library_config,
    "ldd_command": ldd_cmd, "ldd_output": identity(out / "ldd.txt"),
    "environment_overrides": {
        "LD_LIBRARY_PATH": env["LD_LIBRARY_PATH"],
        "AOM_TU_TRACE_FD": env.get("AOM_TU_TRACE_FD"),
    },
    "command": cmd, "stats_original": identity(stats_original), "stats_before": identity(stats),
    "script": identity(snapshot), "ffmpeg": identity("/usr/bin/ffmpeg"),
    "disabled_control": None if control_path is None else identity(control_path),
    "scope": "Diagnostic pass2 replay with preserved installed pass1 statistics; not candidate runtime.",
}
dump(out / "command.json", receipt)
started = time.monotonic()
try:
    with (out / "encode.log").open("wb") as log:
        process = subprocess.run(
            cmd, env=env, stdout=log, stderr=subprocess.STDOUT,
            pass_fds=() if trace_fd is None else (trace_fd,),
        )
    receipt.update(status="validating", returncode=process.returncode,
                   pass2_wall_seconds=time.monotonic() - started)
    dump(out / "command.json", receipt)
    assert process.returncode == 0
    assert sha(input_path) == source["input"]["sha256"]
    assert sha(stats) == sha(stats_original) == receipt["stats_before"]["sha256"]
    assert sha(library) == receipt["library"]["sha256"]
    assert identity(build_path) == receipt["build_receipt"]
    assert all(identity(v["path"]) == v for v in build_bindings.values())
    if control_path is not None:
        assert identity(control_path) == receipt["disabled_control"]
        assert identity(control["output"]["path"]) == control["output"]
    receipt.update(
        input_after=identity(input_path), stats_after=identity(stats),
        output=identity(out / "out.ivf"), log=identity(out / "encode.log"),
        exact_installed_ivf=sha(out / "out.ivf") == source["ivf_sha256"],
    )
    if trace_fd is not None:
        os.close(trace_fd)
        trace_fd = None
        assert 0 < trace_path.stat().st_size <= 250_000_000
        receipt["trace"] = identity(trace_path)
    assert receipt["exact_installed_ivf"], "observation changed output stream"
    receipt["status"] = "encoded"
except BaseException as error:
    receipt["status"] = "validation_failed"
    receipt["error"] = repr(error)
    raise
finally:
    if trace_fd is not None:
        os.close(trace_fd)
    dump(out / "command.json", receipt)
print(json.dumps({k: receipt[k] for k in (
    "arm", "status", "pass2_wall_seconds", "exact_installed_ivf", "output"
)}, indent=2))
