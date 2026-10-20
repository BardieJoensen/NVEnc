#!/usr/bin/env python3
"""Prepare a private build wrapper from the admitted R11 build recipe."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = ROOT / "parent/psyex-coeff-r11/build_runner.sh"
SEED_SHA = "088d599f60a022828105f83555eaf7273a1e3360f8824540ca2340dcc8bc3fd2"
OLD_MANIFEST = "c4a264dfa50cf24e5411c27719cf9e7ac118357ee8f0ee133e5a371854065b55"


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("manifest_sha")
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    assert ident(SEED)["sha256"] == SEED_SHA
    assert ident(args.manifest)["sha256"] == args.manifest_sha
    rows = json.loads(args.manifest.read_text())
    source = args.source.resolve()
    found = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if ".git" in rel.parts:
            continue
        assert not path.is_symlink(), path
        if path.is_file():
            row = ident(path)
            found.append([str(rel), row["size"], row["sha256"]])
    assert found == rows
    text = SEED.read_text()
    assert text.count('SRC="$ROOT/source"') == 1
    assert "'" not in str(source)
    text = text.replace('SRC="$ROOT/source"', "SRC='" + str(source) + "'")
    assert text.count(OLD_MANIFEST) == 2
    text = text.replace(OLD_MANIFEST, args.manifest_sha)
    assert text.count('-ge 130') == 1
    text = text.replace('-ge 130', '-ge 160')
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.manifest, args.out / "source-manifest.json")
    runner = args.out / "build_runner.sh"
    runner.write_text(text)
    (args.out / "preparation.json").write_text(json.dumps(dict(
        status="prepared_not_built", script=ident(__file__), seed=ident(SEED),
        source=str(source), manifest=ident(args.manifest), runner=ident(runner),
        changes=["explicit fresh source path", "reviewed new manifest pin",
                 "160GB free-space gate covers 120GB floor plus 40GB allowance"],
    ), indent=2) + "\n")
    print(json.dumps(ident(args.out / "preparation.json")))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
