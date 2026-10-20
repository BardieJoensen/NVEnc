#!/usr/bin/env python3
"""Preserve reviewed R16 preparation and the first completed rate calibration."""
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
W = ROOT / "worker/psyex-r16-tf0-budget"
R = ROOT / "reviewer"
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
OUT = REPORT / "psyex-tf0/preflight"

def ident(p):
    p = Path(p).resolve()
    with p.open("rb") as f:
        h = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(p), sha256=h, size=p.stat().st_size)

def main():
    run = W / "runs/e05-1440/r16-tf0-tbr10313"
    assert ident(run / "command.json")["sha256"] == "90b6df06c93ae6e048ee37f0584f17b658f38c674af81fb03ccc785c34271a33"
    d = json.loads((run / "command.json").read_text())
    assert d["status"] == "encoded" and d["returncode"] == 0
    assert d["actual_mbps"] > d["source_mbps"]
    assert not d["within_source_ceiling"] and not d["matched_rate_comparable"]
    for key in ("executed_script", "runner_readme", "source_audit", "packet_window"):
        assert ident(d[key]["path"]) == d[key]
    pins = json.loads((P / "derived-pins.json").read_text())
    assert pins["inputs"]["binder_sha"] == "cc50a6c5ddda9e5d38742ff52886edc7b8722589d6f6980546641e3c9e66c23e"
    for name, digest in pins["files"].items():
        assert ident(P / name)["sha256"] == digest
    assert ident(W / "replay_r16.py")["sha256"] == "03118968ab27f79146bb2d2d95cdcec709e0d7512c220b2d9a2053d084b3fae0"
    assert ident(R / "round16-adapter-review.md")["sha256"] == "1278778225cb9db1e7804c15157ff9203ce06efd8a6165e41db443d304dfa1f7"
    assert ident(P / "observe_selected.py")["sha256"] == "eb6f8a812e66c226a1e9cd5b4189bc61fc1b306191e1a78d4bdd37d525b259ed"
    OUT.mkdir(parents=True, exist_ok=False)
    files = {}
    def add(path, name=None):
        path = Path(path); name = name or path.name
        assert name not in files
        original = ident(path)
        assert original["size"] < 1024 * 1024
        shutil.copyfile(path, OUT / name)
        frozen = ident(OUT / name)
        assert frozen["sha256"] == original["sha256"] and frozen["size"] == original["size"]
        files[name] = dict(source=original, frozen=frozen)
    for path in [P / n for n in pins["files"]]:
        add(path)
    for path in (P / "prepare.py", P / "derived-pins.json", P / "observe_selected.py",
                 P / "CALIBRATION.md", P / "freeze_preflight.py",
                 P / "encode-attempt1-execution.json", P / "encode-attempt1-execution.log",
                 W / "encode_r16.py", W / "replay_r16.py", W / "source-audit.md",
                 W / "lineage-smoke.json", W / "lineage-smoke-provenance.md",
                 R / "round16-binding/bind_r16_headers.py"):
        add(path)
    add(W / "README.md", "encoder-README.md")
    add(P / "README.md", "parent-README.md")
    add(run / "command.json", "attempt1-command.json")
    add(run / "packet-window.json", "attempt1-packet-window.json")
    for name in ("pass1.log", "pass2.log"):
        add(run / name, "attempt1-" + name)
    for path in sorted(R.glob("round16-*.md")):
        add(path)
    add(R / "round16-binding/review.md", "binder-review.md")
    add(R / "round16-binding/README.md", "binder-README.md")
    manifest = dict(
        status="reviewed_preparation_and_first_rate_calibration",
        scope="No R16 quality or playback result. Attempt1 exceeds the original packet ceiling. Later attempts are separate evidence.",
        files=files,
        retained_external=[ident(run / n) for n in ("out.ivf", "out.mkv", "recon.yuv", "pass.stats")],
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(dict(files=len(files), manifest=ident(OUT / "manifest.json"))))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
