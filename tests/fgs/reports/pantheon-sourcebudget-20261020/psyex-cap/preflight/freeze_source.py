#!/usr/bin/env python3
"""Freeze parent-integrated R18 source with an R11-compatible manifest/patch."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "parent/psyex-coeff-r11/source"
SOURCE = ROOT / "worker/psyex-r18-cap/source"
BASE_MANIFEST = ROOT / "parent/psyex-coeff-r11/source-manifest.json"
BASE_SHA = "c4a264dfa50cf24e5411c27719cf9e7ac118357ee8f0ee133e5a371854065b55"
CHANGED = {"Source/Lib/Codec/" + name for name in (
    "coding_loop.c", "enc_dec_process.c", "pb_trace.c", "pb_trace.h",
    "pc_impl.h", "rc_process.c")}


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def manifest(root):
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        assert not path.is_symlink()
        if path.is_file():
            row = ident(path)
            rows.append([str(relative), row["size"], row["sha256"]])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    assert ident(BASE_MANIFEST)["sha256"] == BASE_SHA
    baseline = manifest(BASE)
    assert baseline == json.loads(BASE_MANIFEST.read_text())
    current = manifest(SOURCE)
    before, after = {x[0]: x[1:] for x in baseline}, {x[0]: x[1:] for x in current}
    assert before.keys() == after.keys()
    changed = {name for name in before if before[name] != after[name]}
    assert changed == CHANGED
    patch = ""
    for name in sorted(changed):
        patch += "".join(difflib.unified_diff(
            (BASE / name).read_text().splitlines(keepends=True),
            (SOURCE / name).read_text().splitlines(keepends=True),
            fromfile="a/" + name, tofile="b/" + name))
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "source-manifest.json").write_text(json.dumps(current, indent=2) + "\n")
    (args.out / "r18-cap.patch").write_text(patch)
    result = dict(status="source_prepared_not_built", script=ident(__file__),
                  base_manifest=ident(BASE_MANIFEST), base=str(BASE), source=str(SOURCE),
                  manifest=ident(args.out / "source-manifest.json"),
                  patch=ident(args.out / "r18-cap.patch"),
                  changed_files=sorted(changed), files=len(current),
                  reproduction="Copy the verified R11 source, then apply r18-cap.patch with patch -p1 in that copy. Verify the entire manifest before building.")
    (args.out / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
