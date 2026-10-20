#!/usr/bin/env python3
"""Preserve the independently reviewed completed midpoint calibration."""
import hashlib
import json
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
RUN = ROOT / "worker/psyex-r16-calibration-refine/runs/e05-1440/r16-refine-tbr10042"
REVIEW = ROOT / "reviewer/round16-refine-outcome"
OUT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/psyex-tf0/selected-calibration")


def ident(path):
    p = Path(path).resolve()
    with p.open("rb") as f:
        h = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(p), size=p.stat().st_size, sha256=h)


def main():
    assert ident(RUN / "command.json")["sha256"] == "00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497"
    assert ident(P / "encode-attempt1-execution.json")["sha256"] == "e82ff2212660e0453797c5e2383ce910a27099f80252e9c79dc3d5f93517d7d2"
    assert ident(REVIEW / "selected-rate-review.json")["sha256"] == "71cdb861e8a070a7747d99735f9e66fd25c09dff8cd1f54b836e9e71a3522a02"
    assert ident(REVIEW / "selected-rate-review.md")["sha256"] == "e8ecc3319cd9fa9012764eff0defd1b12b1593208384a68188e304cc22e6b5d9"
    d = json.loads((RUN / "command.json").read_text())
    assert d["status"] == "encoded" and d["returncode"] == 0
    assert d["within_source_ceiling"] and d["matched_rate_comparable"]
    assert d["calibration_response_within_bracket"]
    packet = json.loads((RUN / "packet-window.json").read_text())
    assert ident(RUN / "packet-window.json") == d["packet_window"]
    assert sum(int(row["size"]) for row in packet["mkv"]["packets"][96:336]) == 12087309
    assert d["actual_mbps"] == 9.6698472
    assert sum(v["seconds"] for v in d["passes"].values()) == d["wall_seconds"]
    OUT.mkdir(parents=True, exist_ok=False)
    files = {}
    for path in [
        RUN / "command.json", RUN / "packet-window.json", RUN / "pass1.log", RUN / "pass2.log",
        P / "encode-attempt1-execution.json", P / "encode-attempt1-execution.log",
        REVIEW / "selected-rate-review.json", REVIEW / "selected-rate-review.md", Path(__file__),
    ]:
        source = ident(path)
        assert source["size"] < 1024 * 1024
        dest = OUT / path.name
        assert path.name not in files
        shutil.copyfile(path, dest)
        frozen = ident(dest)
        assert frozen["size"] == source["size"] and frozen["sha256"] == source["sha256"]
        files[path.name] = dict(source=source, frozen=frozen)
    external = [ident(RUN / name) for name in ("out.ivf", "out.mkv", "recon.yuv", "pass.stats")]
    result = dict(status="reviewed_rate_selection", actual_mbps=d["actual_mbps"],
                  source_mbps=d["source_mbps"], full336_mbps=d["full_mbps"],
                  two_pass_seconds=d["wall_seconds"], files=files, external=external,
                  scope="Matched-rate selection only; decoder/native/quality/playback acceptance is separate.")
    (OUT / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(ident(OUT / "manifest.json")))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
