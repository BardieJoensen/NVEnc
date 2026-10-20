#!/usr/bin/env python3
"""Freeze verified R18 source/build preparation, with external binary identities."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
OUT = REPORT / "psyex-cap/preflight"
FILES = [
    "README.md", "freeze_preflight.py", "freeze_source.py", "prepare_build.py",
    "execute_build.py", "pin_build.py", "run.py", "harness-revision3.json",
    "source-freeze-1/r18-cap.patch", "source-freeze-1/source-manifest.json",
    "source-freeze-1/receipt.json",
    "source-freeze-1-execution.json", "source-freeze-1-execution.log",
    "build-1-preparation-execution.json", "build-1-preparation-execution.log",
    "build-1-execution.json", "build-1-execution.log",
    "build-1-pin-execution.json", "build-1-pin-execution.log",
    "baseline-preview-execution.json", "baseline-preview-execution.log",
    "build-1/build_runner.sh", "build-1/preparation.json", "build-1/launch.json",
    "build-1/completed-build-pins.json", "build-1/build-receipt.log",
    "build-1/configure.log", "build-1/build.log",
    "build-1/source-manifest-before.json", "build-1/source-manifest-after.json",
    "build-1/build-artifact-hashes.txt", "build-1/tool-identities-before.txt",
    "build-1/tool-identities-after.txt", "build-1/tool-identities.txt",
    "build-1/app-ldd.txt", "build-1/app-version.txt",
    "native-parent-prebuild-notes.md", "parent-cap-correction.json",
]
REVIEWS = [
    "round18-contract-review.md", "round18-v1-review.md",
    "round18-implementation-review.md", "round18-implementation-review-v5.md",
    "round18-harness-review.md", "round18-harness-review-revision3.md",
    "round18-source-release.md",
]


def identity(path):
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(path=str(path.resolve()), size=path.stat().st_size, sha256=digest)


def main():
    assert not OUT.exists()
    pins_path = HERE / "build-1/completed-build-pins.json"
    assert identity(pins_path)["sha256"] == "c0e389a6ca98513c5b4117b48dab02552b7f21ea978585974243f747803e1fe7"
    pins = json.loads(pins_path.read_text())
    assert pins["status"] == "build_complete"
    pairs = [(HERE / name, Path(name)) for name in FILES]
    pairs += [(ROOT / "reviewer" / name, Path("reviews") / name) for name in REVIEWS]
    rows = []
    for source, rel in pairs:
        before = identity(source)
        target = OUT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        shutil.copyfile(source, target)
        after = identity(target)
        assert (before["sha256"], before["size"]) == (after["sha256"], after["size"])
        assert identity(source) == before
        rows.append(dict(source=before, frozen=dict(path=str(rel), size=after["size"], sha256=after["sha256"])))
    manifest = dict(scope="Source/build preflight only; no encode or quality outcome.",
                    files=rows, bytes=sum(row["source"]["size"] for row in rows),
                    external=[pins["app"], pins["library"], pins["cmakecache"], pins["build_ninja"]])
    for item in manifest["external"]:
        assert identity(Path(item["path"])) == item
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(identity(OUT / "manifest.json")))


if __name__ == "__main__":
    assert __debug__
    main()
