#!/usr/bin/env python3
"""Generate canonical KAT inputs from the aeb14263 pinned clone, CPU only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
sys.dont_write_bytecode = True
ROOT = Path("/tmp/downloads/codex-work/fgs-improvement-20261004")
MODULES = ROOT / "baseline-pin/tests/fgs"
sys.path.insert(0, str(MODULES))
import fgs_kat as kat
import numpy as np


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            result.update(block)
    return result.hexdigest()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "identity-sources"
    expected = sum(s.get("width", 1920) * s.get("height", 1080) * 3 // 2
                   * (2 if s.get("bits", 8) == 10 else 1)
                   * s.get("frames", kat.FRAMES) + s.get("frames", kat.FRAMES) * 6 + 100
                   for s in kat.TESTS.values())
    if expected > 10 * 2**30 or shutil.disk_usage(output.parent).free < expected + 2 * 2**30:
        raise RuntimeError("Generation exceeds 10 GiB budget or free space minus reserve")
    output.mkdir(exist_ok=False)
    (output / "README.md").write_text(
        "# Canonical FGS identity sources\n\n"
        "Owner/task: Codex, NVEnc production improvement study 2026-10-04.\n"
        "Contains synthetic Y4M fixtures generated unchanged from the aeb14263 pinned "
        "clone's tests/fgs/fgs_kat.py, plus their pinned input manifest.\n"
        "Regenerate with OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 "
        f"{ROOT / 'generate_identity_sources.py'} /new/empty/output-directory.\n"
        "The generator refuses an existing output directory. No encoder or GPU is used.\n"
        "Retain until the identity comparison and qualification evidence are complete; "
        "then these reproducible synthetic sources are cleanup candidates. "
        "Temporary storage is not a backup.\n")
    module = Path(kat.__file__)
    manifest = {"complete": False, "source_commit": "aeb14263", "kat_module": str(module),
                "kat_module_sha256": sha(module), "generator_sha256": sha(Path(__file__)),
                "numpy_version": np.__version__, "seed": 20260715,
                "estimated_bytes": expected, "budget_bytes": 10 * 2**30, "inputs": []}

    def save():
        tmp = output / "kat-inputs.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=2) + "\n")
        tmp.replace(output / "kat-inputs.json")

    save()
    try:
        for name, spec in kat.TESTS.items():
            path = output / f"{name}.y4m"
            kat.apply_spec(spec)
            expected_sigma, expected_mean = kat.generate(name, spec, str(path))
            manifest["inputs"].append({"name": name, "kat": name, "path": str(path),
                "frames": spec.get("frames", kat.FRAMES), "width": kat.W, "height": kat.H,
                "bits": kat.BITS, "spec": spec, "sha256": sha(path), "bytes": path.stat().st_size,
                "expected_sigma": expected_sigma.tolist(), "expected_mean": expected_mean.tolist()})
            save()
            print(f"{name}: {path.stat().st_size} bytes; {manifest['inputs'][-1]['sha256']}", flush=True)
        if sha(module) != manifest["kat_module_sha256"]:
            raise RuntimeError("Canonical source module changed during generation")
        manifest.update(complete=True, total_bytes=sum(x["bytes"] for x in manifest["inputs"]))
    except BaseException as error:
        manifest["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        save()
    print(json.dumps({"complete": True, "fixtures": len(manifest["inputs"]),
                      "bytes": manifest["total_bytes"], "manifest": str(output / "kat-inputs.json")}), flush=True)


if __name__ == "__main__":
    main()
