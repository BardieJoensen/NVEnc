#!/usr/bin/env python3
"""Synthetic receipt controls only: this does not encode or establish video quality."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
W = ROOT / "worker/psyex-r16-calibration-refine"
SCRIPT_SHA = "5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4"

def ident(p):
    p = Path(p).resolve()
    return dict(path=str(p), size=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def write(p, d):
    p.write_text(json.dumps(d, indent=2) + "\n")
    return ident(p)

def main():
    script = W / "encode_refine.py"
    assert ident(script)["sha256"] == SCRIPT_SHA
    spec = importlib.util.spec_from_file_location("refinement_control", script)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    preview = W / "runs/e05-1440/parent-preview-10042/command.json"
    base = json.loads(preview.read_text())
    assert base["status"] == "prepared" and base["request_kbps"] == 10042
    out = P / "SYNTHETIC-NOT-ENCODED"
    out.mkdir(exist_ok=False)
    results = {}

    def fixture(name, rate, previous=None):
        d = copy.deepcopy(base)
        d.update(status="encoded", returncode=0,
                 synthetic_control_only="NOT an actual encode or admissible experiment")
        if previous:
            pid, pd = previous
            assert not pd["matched_rate_comparable"]
            b = copy.deepcopy(pd["bracket"])
            side = "low" if pd["actual_mbps"] < 9.579757176 else "high"
            b[side] = dict(phase="refinement", path=pid["path"], sha256=pid["sha256"],
                           request_kbps=pd["request_kbps"], actual_mbps=pd["actual_mbps"])
            d["bracket"] = b
            d["request_kbps"] = (b["low"]["request_kbps"] + b["high"]["request_kbps"]) // 2
            d["calibration"] = dict(phase="midpoint-refinement", attempt=pd["calibration"]["attempt"]+1,
                previous_receipt=pid, bracket_transition="raise_low" if side=="low" else "lower_high",
                target_interval=[9.579757176,9.6765224],
                formula="floor((low.request_kbps + high.request_kbps)/2)", request_kbps=d["request_kbps"])
            d["identity_before"][pid["path"]] = pid["sha256"]
        for command in d["commands"].values():
            command[command.index("--tbr")+1] = str(d["request_kbps"])
        total = round(rate * 10 * 1e6 / 8)
        q, rem = divmod(total, 240)
        packets = [{"size": str(q + int(i >= 96 and i-96 < rem))} for i in range(336)]
        measured = sum(int(x["size"]) for x in packets[96:])*8/10/1e6
        packet = write(out / (name+"-packets.json"), dict(source_mbps=9.6765224,
            actual_mbps=measured, mkv=dict(actual_mbps=measured, selected_indices=[96,336], packets=packets)))
        d.update(packet_window=packet, actual_mbps=measured,
                 within_source_ceiling=measured<=9.6765224,
                 matched_rate_comparable=9.579757176<=measured<=9.6765224)
        d["identity_after"] = copy.deepcopy(d["identity_before"])
        p = out / (name+".json"); pid = write(p, d)
        validated, deps = m.validate_chain(p, pid["sha256"])
        assert validated == d and p in deps
        results[name] = dict(status="accepted_synthetic_control", request=d["request_kbps"], receipt=pid)
        return pid, d

    low = fixture("initial-low", 9.5)
    fixture("raise-low-match", 9.65, low)
    high = fixture("initial-high-plateau", 9.70136)
    fixture("lower-high-match", 9.65, high)
    for name, edit in [
        ("wrong-midpoint", lambda d: d.update(request_kbps=10043)),
        ("wrong-phase", lambda d: d["calibration"].update(phase="proportional")),
        ("stale-endpoint-rate", lambda d: d["bracket"]["low"].update(actual_mbps=9.0)),
        ("wrong-initial-anchor", lambda d: d["bracket"]["high"].update(sha256="0"*64)),
        ("identity-drift", lambda d: d["identity_after"].update({"missing-control": "0"*64})),
    ]:
        d = copy.deepcopy(low[1]); edit(d)
        p = out / (name+".json"); pid = write(p, d)
        try:
            m.validate_chain(p, pid["sha256"])
        except (AssertionError, FileNotFoundError) as e:
            results[name] = dict(status="rejected_synthetic_control", error=repr(e), receipt=pid)
        else:
            raise AssertionError("bad synthetic receipt accepted: "+name)
    write(out / "results.json", dict(status="complete", script=ident(__file__),
          tested_encoder=ident(script), preview=ident(preview), argv=sys.argv,
          scope="Synthetic receipt state-machine tests only; no encode or quality evidence.", cases=results))
    print(json.dumps(ident(out / "results.json")))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
