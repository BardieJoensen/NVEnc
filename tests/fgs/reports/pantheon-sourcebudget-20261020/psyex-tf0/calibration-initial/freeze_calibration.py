#!/usr/bin/env python3
"""Freeze the completed three-request calibration and reviewed method revision."""
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
OUT = REPORT / "psyex-tf0/calibration-initial"

def ident(p):
    p = Path(p).resolve()
    with p.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(p), sha256=digest, size=p.stat().st_size)

def main():
    OUT.mkdir(exist_ok=False)
    files = {}
    def add(path, name=None):
        path = Path(path); name = name or path.name
        assert name not in files
        source = ident(path); assert source["size"] < 1024 * 1024
        shutil.copyfile(path, OUT / name)
        frozen = ident(OUT / name)
        assert source["sha256"] == frozen["sha256"] and source["size"] == frozen["size"]
        files[name] = dict(source=source, frozen=frozen)
    records = []
    for attempt, request, expected in [
        (2, 10070, "690beb605f882ddb9748f4e23f4aabc604cca1027f019b5ad09004b9b31b442a"),
        (3, 10014, "02bc209310beb0c88d72c9ca40deb621ce07b2694dfd52bc9ddc5db5219deadd"),
    ]:
        run = ROOT / f"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr{request}"
        assert ident(run / "command.json")["sha256"] == expected
        d = json.loads((run / "command.json").read_text())
        assert d["status"] == "encoded" and d["returncode"] == 0 and not d["matched_rate_comparable"]
        assert d["calibration"]["attempt"] == attempt
        for key in ("packet_window", "stats", "stats_snapshot"):
            assert ident(d[key]["path"]) == d[key]
        for name in ("command.json", "packet-window.json", "pass1.log", "pass2.log"):
            add(run / name, f"attempt{attempt}-" + name)
        for suffix in ("json", "log"):
            add(P / f"encode-attempt{attempt}-execution.{suffix}")
        records.append({k: d[k] for k in ("request_kbps", "actual_mbps", "full_mbps",
                                        "source_mbps", "wall_seconds", "calibration",
                                        "within_source_ceiling", "matched_rate_comparable")})
    for path in (P / "freeze_calibration.py", P / "CALIBRATION.md",
                 ROOT / "reviewer/round16-calibration-refinement-review.md",
                 ROOT / "reviewer/round16-calibration-refinement-review-strict-rate-superseded.md"):
        add(path)
    manifest = dict(status="completed_initial_calibration_no_matched_arm", files=files,
                    attempts2and3=records, attempt1_manifest="../preflight/manifest.json",
                    scope="Packet-rate calibration only; no R16 texture, decoder, playback or repair claim.")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(dict(files=len(files), manifest=ident(OUT / "manifest.json"))))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
