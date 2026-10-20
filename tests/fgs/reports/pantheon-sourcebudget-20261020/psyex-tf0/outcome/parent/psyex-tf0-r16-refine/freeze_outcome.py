#!/usr/bin/env python3
"""Freeze completed R16 evidence without copying reproducible media into Git."""
import hashlib
import json
import shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
OBS = P / "r16-refine-tbr10042-observations"
REV = ROOT / "reviewer/round16-refine-outcome"
STILLS = ROOT / "worker/psyex-r16-stills"
OUT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/psyex-tf0/outcome")


def ident(p):
    p = Path(p).resolve()
    with p.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(p), size=p.stat().st_size, sha256=digest)


def main():
    pins = {
        P / "quality-inputs.json": "7511075b5c5fe40f7c0e0a9ea110a1bd727f3a758577c3053310f6ddbf3b021f",
        OBS / "stages.json": "02007de9587f0ad958f49abbcc0b425ba40e5eb855e76a5f24400193f8b36106",
        P / "support-result-v2/result.json": "f329a6416f3304130fb07a1cb153b88ad039b13e1392c868499cc70a4ad861bb",
        REV / "freeze-manifest-v2.json": "4627d4d32d4e89984eba68df747233542c3049ff03efb64052c525889a3956cd",
        STILLS / "result/manifest.json": "9cef27d7f5346eab059c5949559f37da63423cc9de19e173a5a64dc4bf623bd7",
    }
    for p, h in pins.items():
        assert ident(p)["sha256"] == h, p
    quality = json.loads((P / "quality-inputs.json").read_text())
    review = json.loads((REV / "freeze-manifest-v2.json").read_text())
    files = set(pins)
    external = {}
    for row in quality.values():
        assert ident(row["path"]) == row
        files.add(Path(row["path"]))
    for section in ("accepted", "preserved_failures_and_superseded"):
        for row in review[section].values():
            assert ident(row["path"]) == row
            files.add(Path(row["path"]))
    files.add(Path(review["supersedes_manifest"]["path"]))
    for name in (
        "observe-attempt1-execution", "score-execution", "compare-controls-execution",
        "support-execution", "support-execution-v2",
    ):
        files.update((P / (name + suffix)) for suffix in (".json", ".log"))
    files.update(P / n for n in (
        "controls-versus-r8.json", "analyze_support.py", "analyze_support_v2.py",
    ))
    files.update(OBS.glob("*-execution.*"))
    for name in ("admitted/admission.json", "admitted/decoder-admission.json",
                 "syntax-binding/command.json", "syntax-binding/result.json",
                 "decoder-off/command.json", "decoder-on/command.json"):
        files.add(OBS / name)
    run = Path(quality["command"]["path"]).parent
    files.add(run / "decoder-validation/decoder-validation.json")
    replay = ROOT / "worker/psyex-r16-calibration-refine/replays"
    for arm in ("off", "on"):
        files.add(replay / ("r16-refine-tbr10042-" + arm) / "command.json")
    files.update(STILLS / n for n in (
        "render.py", "result/execution.json", "result/manifest.json",
        "result/shirt-3panel.png", "result/background-3panel.png", "result/face-3panel.png",
    ))
    files.add(Path(__file__))
    OUT.mkdir(parents=True, exist_ok=False)
    frozen = {}
    for p in sorted(files):
        row = ident(p)
        rel = str(p.relative_to(ROOT))
        if row["size"] > 1024 * 1024:
            external[rel] = row
            continue
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        saved = ident(dest)
        assert saved["sha256"] == row["sha256"] and saved["size"] == row["size"]
        frozen[rel] = dict(source=row, frozen=saved)
    support = json.loads((P / "support-result-v2/result.json").read_text())
    compact = {k: v for k, v in support.items() if k not in ("rows", "maskmaps")}
    compact["full_result"] = ident(P / "support-result-v2/result.json")
    compact_path = OUT / "support-compact.json"
    compact_path.write_text(json.dumps(compact, indent=2) + "\n")
    admission = json.loads((OBS / "admitted/admission.json").read_text())
    result = dict(
        status="independently_reviewed_negative", files=frozen, external=external,
        compact_support=ident(compact_path),
        admitted_media_references={k: admission[k] for k in
            ("trace", "boundary", "token_manifest", "source_boundaries", "unmodified_ivf")},
        scope="Matched-rate R16 failure. Single-frame native stages are diagnostic; no playback or candidate acceptance.",
    )
    (OUT / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(manifest=ident(OUT / "manifest.json"), files=len(frozen),
                          bytes=sum(v["frozen"]["size"] for v in frozen.values()))))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
