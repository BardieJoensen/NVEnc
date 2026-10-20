#!/usr/bin/env python3
"""Read-only reference-stream QP diagnostic; never a repair/copy proposal."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                           "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
sys.path.insert(0, str(HERE.parent / "pantheon-independent-20261019"))
import investigate as x

case = sys.argv[1]
assert case == "e05-1440"
f = ROOT / "fixtures" / case
v = json.loads((f / "validity.json").read_text())
d = ROOT / "parent/original-qp" / case / "preroll"
d.mkdir(parents=True, exist_ok=False)
source = Path(v["source"])
stat = source.stat()
assert v["source_stat"] == {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
start = v["requested_start"] - 96 / v["fps"]
assert start == 1436
# Use the same FFmpeg build as original fixture extraction. System FFmpeg6
# selected the preceding GOP for packet copy; full sample identity rejected it.
ffmpeg = shutil.which("ffmpeg")
cmd = [ffmpeg, "-v", "info", "-ss", str(start), "-i", str(source),
       "-map", "0:v:0", "-an", "-sn", "-frames:v", "384", "-c:v", "copy", str(d / "original.mkv")]
before = time.monotonic()
with (d / "extract.log").open("w") as log:
    p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
receipt = {"argv": cmd, "returncode": p.returncode, "wall_seconds": time.monotonic()-before,
           "source": str(source), "source_stat": v["source_stat"],
           "ffmpeg": x.fingerprint(ffmpeg), "script": x.fingerprint(__file__),
           "purpose": "Original quantizer-state observation only; not a re-encode candidate."}
x.dump(d / "extract.json", receipt)
assert p.returncode == 0
hashes = []
for path in (d / "original.mkv", f / "input10.y4m"):
    hashes.append(x.hashes(["/usr/bin/ffmpeg", "-v", "error", "-threads", "2",
                           "-i", path, "-pix_fmt", "yuv420p10le"]))
offsets = [i for i in range(len(hashes[0]) - len(hashes[1]) + 1)
           if hashes[0][i:i+len(hashes[1])] == hashes[1]]
x.dump(d / "identity-check.json", {"hashes": hashes, "counts": list(map(len, hashes)),
                                 "matching_offsets": offsets})
assert len(hashes[0]) == 384 and len(hashes[1]) == 336 and offsets == [48], (
    "The complete original decode must contain the exact336 input frames after48 preroll")
receipt.update({"all336_original_planes_match_fixture": True, "hashes": hashes[1],
                "decoded_population": 384, "selected_display_positions": [48, 384],
                "copy": x.fingerprint(d / "original.mkv"),
                "fixture": x.fingerprint(f / "input10.y4m")})
x.dump(d / "extract.json", receipt)
# Preserve the proven reader's exact logic. Only its fixed expected population
# changes from336 to384, to cover original keyframe preroll. Generated sources
# are retained and fingerprinted by the existing wrapper.
tool = d / "tool"
tool.mkdir()
upstream = HERE.parent / "pantheon-rd-20261019"
patches = {}
for name in ("h264_qp.c", "export_h264_qp.py"):
    text = (upstream / name).read_text()
    assert "384" not in text
    modified = text.replace("336", "384")
    assert modified != text
    (tool / name).write_text(modified)
    patches[name] = {"upstream": x.fingerprint(upstream / name),
                     "generated": x.fingerprint(tool / name),
                     "only_change": "Literal expected frame population336→384"}
x.dump(d / "tool-provenance.json", patches)
cmd = [sys.executable, str(tool / "export_h264_qp.py"),
       str(d / "original.mkv"), str(d / "export/blocks.csv")]
with (d / "export.log").open("w") as log:
    p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
assert p.returncode == 0, (d / "export.log").read_text()[-2000:]
state = np.fromfile(d / "export/qp-state.i8", dtype=np.int8).reshape(384, 68, 120)
selected = state[48:384].copy()
selected.tofile(d / "fixture-qp-state.i8")
st = source.stat()
assert v["source_stat"] == {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
x.dump(d / "selection.json", {
    "all336_original_planes_match_fixture": True, "display_positions": [48, 384],
    "export": x.fingerprint(d / "export/receipt.json"),
    "input_validation": x.fingerprint(d / "extract.json"),
    "state": x.fingerprint(d / "fixture-qp-state.i8"), "shape": [336, 68, 120],
    "dtype": "int8", "scope": "H2648bit QP_Y decoder state; skipped MBs may not execute residual quantization.",
    "original_source_stat_unchanged": True})
print("Original336-frame identity and complete384-frame QP-state export verified")
