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
WORK = ROOT / "worker/psyex-r16-tf0-budget"
OUTER = ROOT / "parent/psyex-real-r15/execute.py"
OUTER_SHA = "93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858"
BINDER = ROOT / "reviewer/round16-binding/bind_r16_headers.py"
BINDER_SHA = "cc50a6c5ddda9e5d38742ff52886edc7b8722589d6f6980546641e3c9e66c23e"
ENCODE_SHA = "2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b"
REPLAY_SHA = "03118968ab27f79146bb2d2d95cdcec709e0d7512c220b2d9a2053d084b3fae0"

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
         "6d830a2e119409a9d9f8cc48b580b87ea824dbc30aed3b528f5ae2ee4d8b971b",
         [a.tag, a.receipt_sha])
    binding_dir = directory / "syntax-binding"
    step("bind-syntax", BINDER, BINDER_SHA,
         [receipt, binding_dir, "--receipt-sha", a.receipt_sha,
          "--encoder-script", WORK / "encode_r16.py", "--encoder-sha", ENCODE_SHA,
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
        step("encoder-" + mode, WORK / "replay_r16.py", REPLAY_SHA,
             [mode, a.tag + "-" + mode, "--original-receipt", receipt,
              "--original-receipt-sha", a.receipt_sha])
    for mode in ("off", "on"):
        args = [receipt, a.receipt_sha, binding, sha(binding), directory / ("decoder-" + mode)]
        if mode == "on":
            args.append("--trace")
        step("decoder-" + mode, P / "replay_decoder.py",
             "c0a1a3820d419f7243bd99a9592cd2703f16de145498cdfed2044b73c40bcde0", args)
    step("admit", P / "admit.py",
         "ebefea72583ab9f618c622bbc4c147a9a1fae443259599b56556679f620c91b7",
         [run, a.receipt_sha, binding, sha(binding),
          WORK / "replays" / (a.tag + "-off"), WORK / "replays" / (a.tag + "-on"),
          directory / "decoder-off", directory / "decoder-on",
          "c0a1a3820d419f7243bd99a9592cd2703f16de145498cdfed2044b73c40bcde0",
          directory / "admitted"])
    admission = directory / "admitted/admission.json"
    step("stages", P / "stage_diagnostic.py",
         "014f96815252dcbe3bb2c6348cc3648dc8ea6903278f77f6fb6714094a6eb39f",
         [admission, sha(admission), directory / "stages.json"])
    print(json.dumps(dict(status="complete", admission=str(admission), sha256=sha(admission))))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
