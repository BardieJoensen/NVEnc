#!/usr/bin/env python3
"""Admit all-picture delivered q and committed coverage before quality claims."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_cap_trace import fingerprint, read_records
from trace_provenance2 import validate as validate_provenance
from cap_semantics2 import evaluate, SELECTED

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provenance_index", type=Path)
    ap.add_argument("provenance_index_sha")
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    started = time.monotonic()
    scripts_before = [fingerprint(Path(__file__).with_name(x)) for x in
                      ("admit_cap_trace2.py", "cap_semantics2.py", "admit_cap_trace.py", "read_cap_trace.py",
                       "trace_provenance2.py", "policy_provenance.py", "provenance.py", "replay_observer2.py")]
    expected = {'cap_semantics2.py': 'c94327149138fb95d347ae409c8deed29d75566d2381795e5f806f7a93341acb', 'admit_cap_trace.py': 'b5a9c506e58fc897b695ea2a87e06c8b07d0dd4e798190fc752a0a0f1c004645', 'read_cap_trace.py': '08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8', 'trace_provenance2.py': '1111b50a7b8272e280ca326207ac4ba314cc639910d861d5e83bab856e08b037', 'policy_provenance.py': 'a7fa1a5f102444d2a1aa87cd21afbae8b09b13ed748036368e37c06d533b4792', 'provenance.py': 'b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f', 'replay_observer2.py': '8276cad4df501913b9e05604f91ceb91020fc56d7157cde0dd7146b63ef3626d'}
    for name, digest in expected.items():
        assert fingerprint(Path(__file__).with_name(name))["sha256"] == digest, name
    runs, index_identity = validate_provenance(args.provenance_index, args.provenance_index_sha)
    receipt = runs["trace"]
    receipt_path = Path(__file__).resolve().parent / "runs" / receipt["tag"] / "command.json"
    before = fingerprint(receipt_path)
    trace = receipt["outputs"]["r18-trace.bin"]
    assert fingerprint(trace["path"]) == trace
    assert not args.out.exists()
    values = evaluate(read_records(trace["path"]))
    assert fingerprint(receipt_path) == before and fingerprint(trace["path"]) == trace
    assert fingerprint(args.provenance_index) == index_identity
    assert [fingerprint(x["path"]) for x in scripts_before] == scripts_before
    result = dict(status="all_picture_quantizer_and_committed_coverage_admitted",
                  script=fingerprint(__file__), reader=fingerprint(Path(__file__).with_name("read_cap_trace.py")),
                  receipt=before, trace=trace, selected_sbs=sorted(SELECTED),
                  provenance_index=index_identity, scripts=scripts_before,
                  **values, seconds=time.monotonic() - started,
                  limitations=["Separate native coefficient/decoder admission and all-frame decoder identity still required.",
                               "Stored q on uninvoked skip units is not an executed quantizer or independent syntax q.",
                               "Lambda population/scaling consistency verified; absolute RD-mult formula is bound to the reviewed executed native function, not independently recomputed.",
                               "Non-skip-mode uninvoked classification uses observed skip flags and the source's MD-skip route; it is not independent bitstream syntax.",
                               "Exact original lambda values remain in the hash-bound trace."])
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(fingerprint(args.out)))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
