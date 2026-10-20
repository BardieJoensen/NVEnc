#!/usr/bin/env python3
"""Execute admitted observation steps sequentially with immutable outer receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
WORK = ROOT / "worker/psyex-r16-calibration-refine"
OUTER = ROOT / "parent/psyex-real-r15/execute.py"
OUTER_SHA = "93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858"
BINDER = ROOT / "reviewer/round16-refine-binding/bind_refine_headers.py"
BINDER_SHA = "5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc"
ENCODE_SHA = "5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4"
REPLAY_SHA = "8491a376d6376aeb3f0cd2e3903c513b8f7bd0a300eaddd1d882a06917814cc6"

def sha(p):
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("receipt_sha")
    ap.add_argument("encode_outer", type=Path)
    ap.add_argument("encode_outer_sha")
    a = ap.parse_args()
    assert "/" not in a.tag and a.tag not in ("", ".", "..")
    assert sha(OUTER) == OUTER_SHA
    assert sha(a.encode_outer) == a.encode_outer_sha
    outer = json.loads(a.encode_outer.read_text())
    assert outer["status"] == "complete" and outer["returncode"] == 0
    run = WORK / "runs/e05-1440" / a.tag
    receipt = run / "command.json"
    assert sha(receipt) == a.receipt_sha
    d = json.loads(receipt.read_text())
    assert d["status"] == "encoded" and d["returncode"] == 0
    assert d["within_source_ceiling"] and d["matched_rate_comparable"]
    assert d["executed_script"]["sha256"] == ENCODE_SHA
    directory = P / (a.tag + "-observations")
    directory.mkdir(exist_ok=False)

    def step(name, script, digest, args):
        assert sha(script) == digest
        output = directory / (name + "-execution.json")
        cmd = [sys.executable, str(OUTER), str(output), str(script), digest, *map(str, args)]
        print("starting " + name, flush=True)
        process = subprocess.run(cmd)
        assert process.returncode == 0, name
        done = json.loads(output.read_text())
        assert done["status"] == "complete" and done["returncode"] == 0, name
        assert sha(receipt) == a.receipt_sha
        print("completed " + name, flush=True)

    step("validate-decoders", P / "validate_decoders.py",
         "f9bcdfca7e8782dda55e39770148c46a4d2ea7c2070c9c252040f166e4e3938a",
         [a.tag, a.receipt_sha])
    binding_dir = directory / "syntax-binding"
    step("bind-syntax", BINDER, BINDER_SHA,
         [receipt, binding_dir, "--receipt-sha", a.receipt_sha,
          "--encoder-script", WORK / "encode_refine.py", "--encoder-sha", ENCODE_SHA,
          "--outer-receipt", a.encode_outer, "--outer-receipt-sha", a.encode_outer_sha])
    # Parse the result filename from the frozen binder's documented output.
    binding = binding_dir / "result.json"
    assert binding.is_file()
    b = json.loads(binding.read_text())
    target, summary = b["target_coded_event"], b["summary"]
    assert (target["event_index"], target["coded_ordinal"], target["show_frame"],
            target["order_hint"], target["refresh_frame_flags_normalized"]) == (314, 210, 0, 88, 16)
    assert (summary["frame_headers"], summary["coded_non_show_existing"]) == (502, 336)
    for mode in ("off", "on"):
        step("encoder-" + mode, WORK / "replay_refine.py", REPLAY_SHA,
             [mode, a.tag + "-" + mode, "--original-receipt", receipt,
              "--original-receipt-sha", a.receipt_sha])
    for mode in ("off", "on"):
        args = [receipt, a.receipt_sha, binding, sha(binding), directory / ("decoder-" + mode)]
        if mode == "on":
            args.append("--trace")
        step("decoder-" + mode, P / "replay_decoder.py",
             "d3fc7d7eb4ddcd295f87bd9083bfd6da01c082dae742924a4d249b0461b18a85", args)
    step("admit", P / "admit.py",
         "fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb",
         [run, a.receipt_sha, binding, sha(binding),
          WORK / "replays" / (a.tag + "-off"), WORK / "replays" / (a.tag + "-on"),
          directory / "decoder-off", directory / "decoder-on",
          "d3fc7d7eb4ddcd295f87bd9083bfd6da01c082dae742924a4d249b0461b18a85",
          directory / "admitted"])
    admission = directory / "admitted/admission.json"
    step("stages", P / "stage_diagnostic.py",
         "b34651e7ac7b713d974ca2a1c58ef4a4f7998458c463f93d902f96365aae1ae5",
         [admission, sha(admission), directory / "stages.json"])
    print(json.dumps(dict(status="complete", admission=str(admission), sha256=sha(admission))))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
