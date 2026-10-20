#!/usr/bin/env python3
"""Bind raw Y4M plane serialization to historical whole-frame identities."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get(
    "PANTHEON_SOURCEBUDGET_ROOT",
    "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020",
))
fixture = ROOT / "fixtures/e05-1440"
out = ROOT / "parent/source-boundary/input-planes.json"
assert not out.exists()
historical_path = fixture / "historical-input-validation.json"
historical = json.loads(historical_path.read_text())
source = fixture / "input10.y4m"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


before = sha(source)
assert before == historical["input"]["sha256"]
expected = historical["prior_input_identity"]["hashes"]
assert len(expected) == len(set(expected)) == 336
rows = []
with source.open("rb") as stream:
    header = stream.readline()
    assert header == (
        b"YUV4MPEG2 W1920 H1080 F24:1 Ip A1:1 C420p10 "
        b"XYSCSS=420P10 XCOLORRANGE=LIMITED\n"
    )
    for index in range(336):
        assert stream.readline() == b"FRAME\n"
        planes = [stream.read(n) for n in (1920 * 1080 * 2, 960 * 540 * 2, 960 * 540 * 2)]
        assert list(map(len, planes)) == [4147200, 1036800, 1036800]
        whole = hashlib.md5(b"".join(planes)).hexdigest()
        assert whole == expected[index]
        rows.append({
            "source_index": index,
            "whole_md5": whole,
            "plane_md5": [hashlib.md5(p).hexdigest() for p in planes],
        })
    assert not stream.read(1)
assert sha(source) == before
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({
    "source": {"path": str(source), "sha256": before},
    "historical": {"path": str(historical_path), "sha256": sha(historical_path)},
    "script": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
    "serialization": "Y then U then V; visible rows; unsigned 16-bit little-endian samples",
    "width": 1920, "height": 1080, "bit_depth": 10, "subsampling": [1, 1],
    "source_unchanged": True,
    "all336_whole_md5_equal_historical": True,
    "frames": rows,
}, indent=2) + "\n")
print(out)
