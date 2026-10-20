#!/usr/bin/env python3
"""Freeze reviewed refinement preparation; exclude active actual encodes."""
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
W = ROOT / "worker/psyex-r16-calibration-refine"
R = ROOT / "reviewer"
OUT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/psyex-tf0/refinement-preflight")


def ident(path):
    p = Path(path).resolve()
    with p.open("rb") as f:
        h = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(p), size=p.stat().st_size, sha256=h)


def main():
    pins = json.loads((P / "derived-pins.json").read_text())
    assert pins["inputs"] == dict(
        encoder_sha="5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4",
        replay_sha="8491a376d6376aeb3f0cd2e3903c513b8f7bd0a300eaddd1d882a06917814cc6",
        binder_sha="5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc")
    for name, h in pins["files"].items():
        assert ident(P / name)["sha256"] == h
    for path, h in [
        (W / "encode_refine.py", pins["inputs"]["encoder_sha"]),
        (W / "replay_refine.py", pins["inputs"]["replay_sha"]),
        (R / "round16-refine-binding/bind_refine_headers.py", pins["inputs"]["binder_sha"]),
        (R / "round16-refinement-release-review.md", "2bec02b603b38196232418a0323e4ea68bc28aac1100e9859e963a3fc0977264"),
        (R / "round16-refinement-wrapper-review.md", "e8ca16ff3820f811e77b2892d4143016a5b4abe749dea346f6f2b0ce36089178"),
        (P / "observe_selected.py", "97d3d02749e6ccf5eb1a6d96e42056ab85cd00f130e200795807a83e1921753f"),
    ]:
        assert ident(path)["sha256"] == h
    for name in ("preview", "validator-controls"):
        d = json.loads((P / (name + "-execution.json")).read_text())
        assert d["status"] == "complete" and d["returncode"] == 0
    controls = json.loads((P / "SYNTHETIC-NOT-ENCODED/results.json").read_text())
    assert controls["status"] == "complete" and len(controls["cases"]) == 9
    assert sum(x["status"] == "accepted_synthetic_control" for x in controls["cases"].values()) == 4
    assert sum(x["status"] == "rejected_synthetic_control" for x in controls["cases"].values()) == 5
    OUT.mkdir(parents=True, exist_ok=False)
    files = {}

    def add(path, name=None):
        path = Path(path)
        name = name or path.name
        assert name not in files
        source = ident(path)
        assert source["size"] < 1024 * 1024
        dest = OUT / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        frozen = ident(dest)
        assert (frozen["size"], frozen["sha256"]) == (source["size"], source["sha256"])
        files[name] = dict(source=source, frozen=frozen)

    for name in pins["files"]:
        add(P / name)
    for name in ("prepare.py", "derived-pins.json", "observe_selected.py",
                 "repair_refine.py", "validator_controls.py", "freeze_preflight.py"):
        add(P / name)
    add(P / "README.md", "parent-README.md")
    for stem in ("preview", "validator-controls"):
        for suffix in ("json", "log"):
            add(P / f"{stem}-execution.{suffix}")
    add(W / "runs/e05-1440/parent-preview-10042/command.json", "preview-command.json")
    for name in ("encode_refine.py", "replay_refine.py", "source-audit.md"):
        add(W / name)
    add(W / "README.md", "encoder-README.md")
    for path in sorted((P / "SYNTHETIC-NOT-ENCODED").glob("*.json")):
        add(path, "SYNTHETIC-NOT-ENCODED/" + path.name)
    for name in ("round16-refinement-package-review.md",
                 "round16-refinement-release-review.md",
                 "round16-refinement-wrapper-review.md"):
        add(R / name)
    for name in ("bind_refine_headers.py", "README.md"):
        add(R / "round16-refine-binding" / name, "binder/" + name)
    result = dict(status="reviewed_refinement_preparation",
                  scope="No actual refinement output or quality claim. Synthetic cases test validation only.",
                  files=files)
    (OUT / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(files=len(files), manifest=ident(OUT / "manifest.json"))))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
