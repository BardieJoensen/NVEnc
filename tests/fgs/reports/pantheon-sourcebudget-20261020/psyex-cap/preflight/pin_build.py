#!/usr/bin/env python3
"""Validate and freeze identities of one completed, privately reviewed build."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREPARE = HERE / "prepare_build.py"
PREPARE_SHA = "f0c29f5be5bd910f7bf7ea04b021005fbdeb7dbfeb4730937386f4d6510b58e8"
SEED = ROOT / "parent/psyex-coeff-r11/build_runner.sh"
SEED_SHA = "088d599f60a022828105f83555eaf7273a1e3360f8824540ca2340dcc8bc3fd2"


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_root", type=Path)
    ap.add_argument("preparation_sha")
    ap.add_argument("patch", type=Path)
    ap.add_argument("patch_sha")
    ap.add_argument("review", type=Path)
    ap.add_argument("review_sha")
    args = ap.parse_args()
    folder = args.build_root.resolve()
    out = folder / "completed-build-pins.json"
    assert not out.exists()
    preparation = folder / "preparation.json"
    assert ident(preparation)["sha256"] == args.preparation_sha
    prep = json.loads(preparation.read_text())
    assert prep["status"] == "prepared_not_built"
    assert ident(PREPARE)["sha256"] == PREPARE_SHA and prep["script"] == ident(PREPARE)
    assert ident(SEED)["sha256"] == SEED_SHA and prep["seed"] == ident(SEED)
    for name in ("script", "seed", "manifest", "runner"):
        assert ident(prep[name]["path"]) == prep[name], name
    assert prep["runner"]["path"] == str(folder / "build_runner.sh")
    assert ident(folder / "source-manifest.json")["sha256"] == prep["manifest"]["sha256"]
    expected = SEED.read_text().replace('SRC="$ROOT/source"', "SRC='" + prep["source"] + "'")
    expected = expected.replace("c4a264dfa50cf24e5411c27719cf9e7ac118357ee8f0ee133e5a371854065b55",
                                prep["manifest"]["sha256"]).replace("-ge 130", "-ge 160")
    assert (folder / "build_runner.sh").read_text() == expected
    assert ident(args.patch)["sha256"] == args.patch_sha
    assert ident(args.review)["sha256"] == args.review_sha
    receipt = folder / "build-receipt.log"
    log = receipt.read_text()
    assert log.count("final_status=build_complete\n") == 1
    assert log.rstrip().endswith("exit_code=0")
    assert "configure_returncode=0\n" in log and "build_returncode=0\n" in log
    before, after = folder / "source-manifest-before.json", folder / "source-manifest-after.json"
    assert ident(before)["sha256"] == ident(after)["sha256"] == prep["manifest"]["sha256"]
    rows = []
    source = Path(prep["source"])
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if ".git" in relative.parts:
            continue
        assert not path.is_symlink()
        if path.is_file():
            row = ident(path)
            rows.append([str(relative), row["size"], row["sha256"]])
    assert rows == json.loads(before.read_text())
    assert (folder / "tool-identities-before.txt").read_bytes() == (folder / "tool-identities-after.txt").read_bytes()
    assert ident(folder / "measured-runner.sh")["sha256"] == prep["runner"]["sha256"]
    for line in (folder / "build-artifact-hashes.txt").read_text().splitlines():
        digest, path = line.split(maxsplit=1)
        assert ident(path)["sha256"] == digest, path
    result = dict(status="build_complete", returncode=0, source_root=str(source),
                  pin_script=ident(__file__), preparation=ident(preparation),
                  source_manifest=ident(folder / "source-manifest.json"),
                  manifest_before=ident(before), manifest_after=ident(after),
                  patch=ident(args.patch), implementation_review=ident(args.review))
    for key, relative in {
        "app": "build/bin/SvtAv1EncApp",
        "library": "build/bin/libSvtAv1Enc.so.3.0.2",
        "build_receipt": "build-receipt.log",
        "runner": "measured-runner.sh",
        "cmakecache": "build/CMakeCache.txt",
        "build_ninja": "build/build.ninja",
        "artifact_hashes": "build-artifact-hashes.txt",
        "tools": "tool-identities.txt",
        "configure_log": "configure.log",
        "build_log": "build.log",
        "ldd": "app-ldd.txt",
        "version": "app-version.txt",
    }.items():
        result[key] = ident(folder / relative)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(ident(out)))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
