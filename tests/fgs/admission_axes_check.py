#!/usr/bin/env python3
"""Would the shadow-admission conjunction reject artifact-bearing input?

`FINDINGS-2026-08-04-SHADOW-ADMISSION.md` froze an exploratory rule:

    cross-frame correlation <= 0.127  AND  anisotropy mismatch <= 0.032

and could not evaluate its specificity, because the corpus contained no input
on which source fitting was known to do harm.  `FINDINGS-2026-08-05-COVARIANCE-
ARTIFACT.md` supplies one: an x264 recompression C, on which the unprotected
source fit synthesizes codec texture rather than the original's grain.

This runs the axes on the matched pair -- the lossless original O and its
recompression C -- so the question is concrete: does the film-like evidence
separate them?  If C scores as film-like as O, the conjunction cannot protect
against artifact-bearing input, whatever it does on origin labels.

A table is required per source, so each is encoded once with the same guarded
candidate configuration and its emitted table is used.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from negative_specimen import CANDIDATE, encode, run  # noqa: E402
from covariance_artifact import ARMS, FGS_OPTS, TITLES, WORK  # noqa: E402

FROZEN_CROSS_FRAME = 0.127
FROZEN_ANISOTROPY = 0.032


def axes(source, table, out_json, work):
    if not os.path.isfile(out_json):
        run([sys.executable, os.path.join(HERE, "sourcefit_admission_report.py"),
             "--source", source, "--table", table, "--bits", "8",
             "--flat-selector", "production", "--json-out", out_json],
            log=os.path.join(work, os.path.basename(out_json) + ".log"))
    with open(out_json, encoding="utf-8") as handle:
        doc = json.load(handle)
    summary = doc["summary"]
    return {
        "cross_frame_correlation":
            summary["film_like_evidence"]["cross_frame_correlation"],
        "anisotropy_mismatch": summary["model_fidelity"]["anisotropy_abs"],
        "temporal_sigma_8bit":
            summary["film_like_evidence"]["temporal_sigma_8bit"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", default=WORK)
    parser.add_argument("--rate", type=int, default=2000)
    args = parser.parse_args()
    env = ARMS["A1_response"]
    rows = []
    for title in TITLES:
        o = os.path.join(args.work, f"{title}-O.mkv")
        d = os.path.join(args.work, f"{title}-{args.rate}k")
        c = os.path.join(d, "C.mp4")
        if not (os.path.isfile(o) and os.path.isfile(c)):
            print(f"MISSING {title}", flush=True)
            continue
        # O needs its own table; C already has one from the A1 arm
        encode(CANDIDATE, o, os.path.join(d, "O_fgs.mkv"), 29, 8,
               fgs=FGS_OPTS, env=env, log=os.path.join(d, "O_fgs.log"))
        for label, src, tbl in (
                ("O_original", o, os.path.join(d, "O_fgs.tbl")),
                ("C_recompressed", c, os.path.join(d, "A1_response.tbl"))):
            row = {"title": title, "rate_kbps": args.rate, "input": label}
            row.update(axes(src, tbl,
                            os.path.join(d, f"admission-{label}.json"),
                            args.work))
            cf, an = row["cross_frame_correlation"], row["anisotropy_mismatch"]
            row["admits"] = (cf is not None and an is not None
                             and cf <= FROZEN_CROSS_FRAME
                             and an <= FROZEN_ANISOTROPY)
            rows.append(row)
            print(json.dumps(row), flush=True)
            with open(os.path.join(args.work, "admission-axes.json"), "w",
                      encoding="utf-8") as handle:
                json.dump(rows, handle, indent=1)


if __name__ == "__main__":
    main()
