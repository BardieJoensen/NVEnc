#!/usr/bin/env python3
"""Invoke a prepared shell recipe beneath the standard Python outer wrapper."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("preparation", type=Path)
    ap.add_argument("preparation_sha")
    args = ap.parse_args()
    assert ident(args.preparation)["sha256"] == args.preparation_sha
    prep = json.loads(args.preparation.read_text())
    assert prep["status"] == "prepared_not_built"
    assert ident(prep["runner"]["path"]) == prep["runner"]
    directory = args.preparation.parent
    receipt = directory / "launch.json"
    assert not receipt.exists()
    paths = [Path(__file__), args.preparation, Path(prep["runner"]["path"]), Path("/usr/bin/bash")]
    out = dict(status="running", argv=["/usr/bin/bash", prep["runner"]["path"]],
               inputs_before=[ident(p) for p in paths])
    receipt.write_text(json.dumps(out, indent=2) + "\n")
    started = time.monotonic()
    code = 1
    try:
        process = subprocess.run(out["argv"], cwd=directory)
        code = process.returncode
        out.update(returncode=code, seconds=time.monotonic() - started)
        out["inputs_after"] = [ident(p) for p in paths]
        assert out["inputs_after"] == out["inputs_before"]
        assert code == 0
        out["status"] = "complete"
    except BaseException as error:
        out.update(status="failed", error=repr(error), returncode=code)
        raise
    finally:
        receipt.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
