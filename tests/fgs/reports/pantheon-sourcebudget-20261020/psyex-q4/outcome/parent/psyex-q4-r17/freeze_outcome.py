#!/usr/bin/env python3
"""Preserve the completed R17 evidence, including rejected preparation."""
import hashlib
import json
import shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
REPORT = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020")
OUT = REPORT / "psyex-q4/outcome"


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=sha)


def main():
    pins = {
        P / "experiment.py": "cb0e9a59adfde606ec489095ba71874bf476f5775e5d4223a6cb477fb44f19a6",
        P / "result-1/result.json": "a04eb728936d62662afb4ab6dbc554db394c25f1ac433c563beff59278b3abdb",
        P / "result-1/receipt.json": "4eb2aefae90ff65c2e985cafdfc14f878107c5f8df36d971aad9ad7d6c8728a6",
        P / "result-1/native-arrays.npz": "ee8c41ed2188efacd940ebf3a9fbb6dd5821e9bf2e6c56c75ff4e5d3e8a26b23",
        P / "result-1/mosaics.npz": "aba4ec13038906060b0ec59c1bee1ed342835e2a60caf472200a030b950af50c",
        ROOT / "reviewer/round17-outcome/ADDENDUM.md": "57d650006879017c523897ea3b9bd60ab2a2c010be822c97dd6f1cb52edc49ec",
        ROOT / "reviewer/round17-outcome/derive-v1-failed.py": "48de104a91a2a707277bbd1333269690f02cf2db5cb93c1a812946e348f204c7",
        ROOT / "reviewer/round17-outcome/derived-v2.json": "801d9f44c3656ac021702b5b0be86b89442226d3ac8fee4cde3241dd32ca9587",
    }
    for path, sha in pins.items():
        assert ident(path)["sha256"] == sha, path
    receipt = json.loads((P / "result-1/receipt.json").read_text())
    assert receipt["status"] == "complete"
    assert receipt["inputs_before"] == receipt["inputs_after"]
    failed = json.loads((ROOT / "reviewer/round17-outcome/derive-execution.json").read_text())
    failed_source = ident(ROOT / "reviewer/round17-outcome/derive-v1-failed.py")
    row = next(x for x in failed["inputs_before"] if x["path"].endswith("/derive.py"))
    assert (row["sha256"], row["size"]) == (failed_source["sha256"], failed_source["size"])
    files = set(pins)
    for folder in (
        P, ROOT / "worker/psyex-r17-q4",
        ROOT / "reviewer/round17-outcome", ROOT / "reviewer/round17-parent-preflight",
        ROOT / "reviewer/round17-preflight",
    ):
        files.update(x for x in folder.rglob("*") if x.is_file() and "__pycache__" not in x.parts)
    files.add(ROOT / "reviewer/round17-dc-evidence-review.md")
    OUT.mkdir(parents=True, exist_ok=False)
    frozen, external = {}, {}
    for path in sorted(files):
        source = ident(path)
        relative = str(path.relative_to(ROOT))
        if source["size"] > 1024 * 1024:
            external[relative] = source
            continue
        dest = OUT / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        saved = ident(dest)
        assert (saved["sha256"], saved["size"]) == (source["sha256"], source["size"])
        frozen[relative] = dict(source=source, frozen=saved)
    manifest = dict(
        status="independently_reviewed_single_frame_negative",
        scope="Fixed-choice native q4; no legal encode, packet rate or playback claim.",
        files=frozen, external=external,
        dependency_closure=ident(P / "result-1/receipt.json"),
        missing_rejected_source={
            "sha256": "1a0903beb82688631fbf2459b7b4b3dedf2cf139b0e8a6eff847efa11613bda3",
            "status": "exact worker draft unavailable; audits and README retained, not a source substitute",
        },
        review_interpretation="Read original review together with ADDENDUM.md; raw HF is not a mathematical ceiling.",
        reproduction="Use preserved absolute scratch paths and pinned R15 execute.py with fresh output directories; do not overwrite receipts. Active dependencies remain in place pending final archival.",
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(dict(manifest=ident(OUT / "manifest.json"), files=len(frozen),
                          bytes=sum(x["frozen"]["size"] for x in frozen.values()),
                          external=len(external))))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
