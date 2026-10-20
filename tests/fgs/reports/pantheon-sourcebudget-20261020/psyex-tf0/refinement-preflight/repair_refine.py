#!/usr/bin/env python3
"""Apply focused parent corrections and derive replay from its verified base."""
import hashlib
from pathlib import Path
import shutil

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
W = ROOT / "worker/psyex-r16-calibration-refine"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def sub(t, old, new):
    assert old in t, old
    return t.replace(old, new)

def main():
    f = W / "encode_refine.py"
    assert sha(f) == "c5c71050d58a60ced06593a44eaeb4a18a448921ea18a2e3f6cf9b054e44b06c"
    shutil.copyfile(f, W / "encode_refine-worker-c5c710.py")
    t = f.read_text()
    start, end = t.index("def legacy_validate_chain"), t.index("def load_legacy_runner")
    t = t[:start] + t[end:]
    t = sub(t, '    before=d.get("identity_before",{}); after=d.get("identity_after",{}); assert before and before==after',
        '''    assert d.get("source_commit")=="59d1a025698f2ca7b4c4b0e833937dd15e382494"
    validity=d["validity"]; assert ident(validity["path"])==validity
    validity_data=json.loads(Path(validity["path"]).read_text())
    assert validity_data["source_mbps"]==9.6765224 and validity_data["fps"]==24
    before=d.get("identity_before",{}); after=d.get("identity_after",{}); assert before and before==after''')
    t = sub(t, '    assert abs(measured-float(d["actual_mbps"]))<1e-10',
        '''    assert all(abs(measured-float(v))<1e-10 for v in
               (d["actual_mbps"],pj["actual_mbps"],pj["mkv"]["actual_mbps"]))
    assert pj["source_mbps"]==9.6765224''')
    t = sub(t, '    bracket=d.get("bracket"); assert bracket and set(bracket)=={"low","high"}',
        '''    assert cal.get("phase")=="midpoint-refinement" and cal.get("request_kbps")==d["request_kbps"]
    bracket=d.get("bracket"); assert bracket and set(bracket)=={"low","high"}''')
    t = sub(t, '    if attempt==1:\n        assert d["request_kbps"]==10042',
        '''    if attempt==1:
        assert "previous_receipt" not in cal and cal.get("low")==bracket["low"] and cal.get("high")==bracket["high"]
        assert bracket["low"]["phase"]==bracket["high"]["phase"]=="old"
        assert d["request_kbps"]==10042''')
    t = sub(t, '        if float(pd["actual_mbps"]) < 9.579757176:',
        '''        updated={"phase":"refinement","path":prev["path"],"sha256":prev["sha256"],
                 "request_kbps":pd["request_kbps"],"actual_mbps":pd["actual_mbps"]}
        if float(pd["actual_mbps"]) < 9.579757176:''')
    t = sub(t, 'assert cal.get("bracket_transition")=="raise_low" and bracket["low"]["path"]==prev["path"] and bracket["low"]["sha256"]==prev["sha256"] and bracket["high"]==oldb["high"]',
        'assert cal.get("bracket_transition")=="raise_low" and bracket["low"]==updated and bracket["high"]==oldb["high"]')
    t = sub(t, 'assert cal.get("bracket_transition")=="lower_high" and bracket["high"]["path"]==prev["path"] and bracket["high"]["sha256"]==prev["sha256"] and bracket["low"]==oldb["low"]',
        'assert cal.get("bracket_transition")=="lower_high" and bracket["high"]==updated and bracket["low"]==oldb["low"]')
    start = t.index('    old_runner = PSYROOT.parent', t.index('def main():'))
    end = t.index('    source = float(validity["source_mbps"])', start)
    t = t[:start] + '    old_endpoint = validate_legacy_endpoint\n' + t[end:]
    t = sub(t, '        assert a.low_receipt_sha and a.high_receipt_sha',
        '''        assert a.low_receipt_sha=="02bc209310beb0c88d72c9ca40deb621ce07b2694dfd52bc9ddc5db5219deadd"
        assert a.high_receipt_sha=="690beb605f882ddb9748f4e23f4aabc604cca1027f019b5ad09004b9b31b442a"
        assert a.low_receipt.resolve()==ROOT/"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10014/command.json"
        assert a.high_receipt.resolve()==ROOT/"worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10070/command.json"''')
    t = sub(t, 'and not (a.low_receipt or a.high_receipt)',
        'and not (a.low_receipt or a.high_receipt or a.low_receipt_sha or a.high_receipt_sha)')
    # Existing post-encode packet checks remain unchanged; report response status
    # so an out-of-range measurement is retained but never drives another request.
    t = sub(t, '        receipt["wall_seconds"] = sum(p["seconds"] for p in receipt["passes"].values())',
        '''        receipt["calibration_response_within_bracket"] = bracket["low"]["actual_mbps"] <= actual <= bracket["high"]["actual_mbps"]
        receipt["wall_seconds"] = sum(p["seconds"] for p in receipt["passes"].values())''')
    f.write_text(t)
    encoder_sha = sha(f)
    old_replay = ROOT / "worker/psyex-r16-tf0-budget/replay_r16.py"
    assert sha(old_replay) == "03118968ab27f79146bb2d2d95cdcec709e0d7512c220b2d9a2053d084b3fae0"
    r = old_replay.read_text()
    for old, new in {
        "worker/psyex-r16-tf0-budget": "worker/psyex-r16-calibration-refine",
        "encode_r16.py": "encode_refine.py",
        "2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b": encoder_sha,
        "5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71":
            "9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82",
    }.items():
        r = sub(r, old, new)
    shutil.copyfile(W / "replay_refine.py", W / "replay_refine-worker-transfer.py")
    (W / "replay_refine.py").write_text(r)
    print("encoder", encoder_sha)
    print("replay", sha(W / "replay_refine.py"))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
