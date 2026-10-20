#!/usr/bin/env python3
"""Pair unchanged frozen control tiles against admitted R8; descriptive only."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parent
ROOT = P.parents[1]

def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path), sha256=sha, size=path.stat().st_size)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("assessment_sha")
    ap.add_argument("controls_sha")
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    assert not args.output.exists()
    old = ROOT / "worker/psyex-r8/runs/e05-1440/psyex-1x1"
    pins = {
        old / "assessment.json": "cc3d2a383732d8d5c40b80ff49a54b76b6e199d4de830f3dd4adf4ed3b95620f",
        old / "controls.json": "e38545478d03ebfd74d447e54178adfc03673bf7df3efbd42587a2c3ed598c1d",
        args.run / "assessment.json": args.assessment_sha,
        args.run / "controls.json": args.controls_sha,
    }
    before = [ident(path) for path in pins]
    assert all(row["sha256"] == sha for row, sha in zip(before, pins.values()))
    previous, current = [
        json.loads((directory / "controls.json").read_text())
        for directory in (old, args.run)
    ]
    pa, ca = [
        json.loads((directory / "assessment.json").read_text())
        for directory in (old, args.run)
    ]
    assert ca["all336_decoder_identity"] and ca["all240_scored_planes_match"]
    assert pa["controls"] == previous["summary"] and pa["face"] == previous["face"]
    assert ca["controls"] == current["summary"] and ca["face"] == current["face"]
    for key in ("source_control_provenance", "source", "baseline_encode_identity", "baseline_ivf"):
        assert current[key] == previous[key]
    def key(row):
        return row["frame"], row["x"], row["y"]
    prior = {key(row): row for row in previous["tiles"]}
    fresh = {key(row): row for row in current["tiles"]}
    assert set(prior) == set(fresh) and len(prior) == len(previous["tiles"]) == len(current["tiles"]) == 12870
    for k in prior:
        for field in ("source", "kind", "outside_target", "baseline"):
            assert prior[k][field] == fresh[k][field]
    summary = {}
    for kind in ("all", "quiet", "edge", "flat_texture", "other"):
        pairs = [(prior[k], fresh[k]) for k in sorted(prior) if kind == "all" or prior[k]["kind"] == kind]
        group = {"tiles": len(pairs)}
        for metric in ("mse", "hf_abs_error", "acf1_abs_error", "hf_signed_excess"):
            values = []
            for pair in pairs:
                row_values = []
                for row in pair:
                    source, candidate = row["source"], row["candidate"]
                    if metric == "mse":
                        value = candidate["mse"]
                    elif metric.startswith("hf_"):
                        value = candidate["hf_sigma"] - source["hf_sigma"]
                        if metric == "hf_abs_error":
                            value = abs(value)
                    else:
                        value = None if candidate["acf1"] is None or source["acf1"] is None else abs(candidate["acf1"] - source["acf1"])
                    row_values.append(value)
                if all(v is not None for v in row_values):
                    values.append(row_values)
            v = np.asarray(values, dtype=float)
            assert np.isfinite(v).all()
            group[metric] = {"paired_tiles": len(v)}
            if len(v):
                group[metric].update({
                    name: dict(mean=float(v[:, i].mean()), p95=float(np.percentile(v[:, i], 95)), max=float(v[:, i].max()))
                    for i, name in enumerate(("R8", "R15"))
                })
                group[metric]["increased"] = int(np.count_nonzero(v[:, 1] > v[:, 0]))
                group[metric]["decreased"] = int(np.count_nonzero(v[:, 1] < v[:, 0]))
        summary[kind] = group
    assert before == [ident(path) for path in pins]
    result = dict(
        status="complete", script=ident(__file__), inputs=before,
        scope="R15 versus R8 paired descriptive control comparison at different actual rates; not a matched-rate causal contrast or acceptance decision. Increased signed HF excess is not automatically a regression when both values are negative.",
        rate_mbps={"R8": pa["actual_mbps"], "R15": ca["actual_mbps"]},
        two_pass_seconds={"R8": pa["two_pass_wall_seconds"], "R15": ca["two_pass_wall_seconds"]},
        summary=summary,
        face={"R8": previous["face"]["candidate"], "R15": current["face"]["candidate"]},
        texture_screen={"R8": pa["texture_screen"], "R15": ca["texture_screen"]},
    )
    with args.output.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(ident(args.output)))

if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
