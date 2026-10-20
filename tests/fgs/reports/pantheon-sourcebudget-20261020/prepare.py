#!/usr/bin/env python3
"""Fresh original extraction plus exact historical 336-frame input binding."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                           "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
case = sys.argv[1]
assert case in ("e04", "e05-1440")
assert str(ROOT.resolve()).startswith("/tmp/downloads/codex-work/")
os.environ["PANTHEON_RD_ROOT"] = str(ROOT)
upstream = runpy.run_path(str(HERE.parent / "pantheon-rd-20261019/prepare.py"))
upstream["prepare"](case)
d = ROOT / "fixtures" / case
prior = Path("/media/merged-storage/cold-storage/docker-apps/pantheon-rd-20261019") / (
    "parent/crosscodec") / case / "x264-search11-4x1/input-validation.json"
p = json.loads(prior.read_text())
assert p["all336_8bit_input_lift_matches_SVT_input"] and len(p["hashes"]) == 336

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

input_path = d / "input10.y4m"
input_sha = sha(input_path)
assert input_sha == p["svt_input"]["sha256"]
receipt = {
    "all336_exact_Y4M_bytes_match_prior": True,
    "input": {"path": str(input_path), "sha256": input_sha},
    "prior_receipt": {"path": str(prior), "sha256": sha(prior)},
    "prior_input_identity": p,
}
(d / "historical-input-validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(case, "full336 Y4M bytes match preserved baseline input")
