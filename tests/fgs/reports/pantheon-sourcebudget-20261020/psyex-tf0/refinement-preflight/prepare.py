#!/usr/bin/env python3
"""Derive R16 midpoint-refinement wrappers from hash-bound, executed R15 implementations."""
import argparse
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
OLD = ROOT / "parent/psyex-real-r15"

def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def read(p, expected):
    assert sha(p) == expected
    return p.read_text()

def replace(text, a, b):
    assert a in text, a
    return text.replace(a, b)

def write(name, text):
    dest = P / name
    assert not dest.exists(), dest
    dest.write_text(text)
    return sha(dest)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("encoder_sha")
    ap.add_argument("replay_sha")
    ap.add_argument("binder_sha")
    args = ap.parse_args()
    for value in vars(args).values():
        assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    pins = {}
    t = read(OLD / "validate_decoders.py", "d7c0d08e0cfa2d52fbc02f5bec2073b1b462a5f5922c54265a76a10306089175")
    t = replace(t, "worker/psyex-r15-real", "worker/psyex-r16-calibration-refine")
    pins["validate_decoders.py"] = write("validate_decoders.py", t)
    t = read(OLD / "replay_decoder.py", "99ccb7993dcf720f9f0f8835d3f0e41750db6bd27acd638299717f6b52efaf7b")
    t = replace(t, "34689de8b365801e762fd80a83ec9a349d88bb944c667e96da7bab9edce9323d", args.binder_sha)
    t = replace(t, "8616fe44a383c8aaf1722d55891cdc040b7af6886a288fcf8817903794e42ce2", args.encoder_sha)
    pins["replay_decoder.py"] = write("replay_decoder.py", t)
    t = read(OLD / "admit.py", "7dc554ff79d8b9c8b206e10f5326394dcc4483e5c679cfcb22529340aa7c9da4")
    for old, new in {
        "R15": "R16", "r15_": "r16_", "worker/psyex-r15-real": "worker/psyex-r16-calibration-refine",
        "34689de8b365801e762fd80a83ec9a349d88bb944c667e96da7bab9edce9323d": args.binder_sha,
        "5bbb7181497151db29cb1683564a34407fc026a1c4bb50ab40a161420a462d38": args.replay_sha,
        "8616fe44a383c8aaf1722d55891cdc040b7af6886a288fcf8817903794e42ce2": args.encoder_sha,
        "d7c0d08e0cfa2d52fbc02f5bec2073b1b462a5f5922c54265a76a10306089175": pins["validate_decoders.py"],
        "99ccb7993dcf720f9f0f8835d3f0e41750db6bd27acd638299717f6b52efaf7b": pins["replay_decoder.py"],
        "65abe8440193c14cd4925961f2cf712081e2c9876d18de8ab90440ac8d5099f3": "9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82",
        "'--min-qp':'1','--max-qp':'1',": "",
        "P/'parsers.py'": "ROOT/'parent/psyex-real-r15/parsers.py'",
        "P/'parser-control.json'": "ROOT/'parent/psyex-real-r15/parser-control.json'",
        "P/'prepare_parsers.py'": "ROOT/'parent/psyex-real-r15/prepare_parsers.py'",
    }.items():
        t = replace(t, old, new)
    marker = "    bind('syntax_binding',a.binding,a.binding_sha);binding=json.loads(a.binding.read_text())"
    extra = """    encoder=load(WORK/'encode_refine.py','r16_encoder',ENCODE_SHA)
    validated, dependencies=encoder.validate_chain(originalp,a.run_sha)
    assert validated==original
    assert original['within_source_ceiling'] and original['matched_rate_comparable']
"""
    t = replace(t, marker, extra + marker)
    # The independent syntax binder validates and retains the outer execution receipt.
    marker = "    expected=json.loads(exact(binding['events']).read_text())"
    extra = """    outer_path=exact(binding['outer_execution'])
    outer=json.loads(outer_path.read_text())
    assert outer['status']=='complete' and outer['returncode']==0
    bind('outer_execution',outer_path)
"""
    t = replace(t, marker, extra + marker)
    pins["admit.py"] = write("admit.py", t)
    t = read(OLD / "stage_diagnostic.py", "1f1e42c05a50a4d2e8e243c073157113459bbb92ed84e303e972e386399a7a52")
    t = replace(t, "R15", "R16")
    t = replace(t, "r15_", "r16_")
    t = replace(t, "7dc554ff79d8b9c8b206e10f5326394dcc4483e5c679cfcb22529340aa7c9da4", pins["admit.py"])
    t = replace(t, 'P / "parsers.py"', 'ROOT / "parent/psyex-real-r15/parsers.py"')
    pins["stage_diagnostic.py"] = write("stage_diagnostic.py", t)
    t = read(ROOT / "worker/psyex-r15-real/score_r15.py", "bdb6991391f52fe9c21644144c038bed05784c918a896eb133a67cda227d207c")
    for old, new in {
        "r15-tf0-publicqp1": "r16-tf0-original-budget",
        "worker/psyex-r15-real": "worker/psyex-r16-calibration-refine",
        "7dc554ff79d8b9c8b206e10f5326394dcc4483e5c679cfcb22529340aa7c9da4": pins["admit.py"],
        "d7c0d08e0cfa2d52fbc02f5bec2073b1b462a5f5922c54265a76a10306089175": pins["validate_decoders.py"],
        "unconstrained TF-off/public-QP-bound PSYEX diagnostic; matched-rate flag is descriptive only":
            "TF-off PSYEX policy at the original packet budget; bundled source/reference/search contrast",
        "Decoder and numerical quality measurements performed; playback unobserved; no matched-rate or repair claim.":
            "Decoder and numerical quality measurements at the original packet budget; playback unobserved; no repair acceptance.",
    }.items():
        t = replace(t, old, new)
    marker = "assert run['matched_rate_comparable'] == (.99 <= ratio <= 1.0)"
    t = replace(t, marker, marker + "\nassert run['within_source_ceiling'] and run['matched_rate_comparable']")
    pins["score_r16.py"] = write("score_r16.py", t)
    t = read(OLD / "compare_controls.py", "1e0956de13835bdcd961ef4ec021c0743dcac8e728775b1cbcf990a3ae1357d9")
    t = replace(t, "R15", "R16")
    t = replace(t, "at different actual rates; not a matched-rate causal contrast or acceptance decision.",
                "at actual rates within 1%; bundled TF policy contrast, not isolated source pixels or acceptance.")
    t = replace(t, '    summary = {}',
                '    assert ca["practical_rate_eligible"] and ca["matched_comparison_eligible"]\n'
                '    assert abs(ca["actual_mbps"]/pa["actual_mbps"]-1) <= .01\n'
                '    summary = {}')
    pins["compare_controls.py"] = write("compare_controls.py", t)
    (P / "derived-pins.json").write_text(json.dumps(dict(inputs=vars(args), files=pins), indent=2)+"\n")
    print(json.dumps(pins))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
