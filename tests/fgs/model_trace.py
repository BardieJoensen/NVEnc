#!/usr/bin/env python3
"""Does the signalled grain model track the source grain it was fitted from?

Parses `--log-level debug` `fgs-model` lines. Each carries both quantities, so
one encode answers two questions that have been conflated:

  * How many DISTINCT parameter sets were signalled across the file? A title
    whose grain varies but whose model does not is the defect class in
    fgs-open-questions.md 3g.
  * Does signalled amplitude follow measured source noise? If the source swings
    an order of magnitude and the model stays flat, the model is not adapting;
    if it follows, the loss is downstream of the fit.

The analyzer holds the previous model when a fresh fit is within tolerance
(NVEncFilterFilmGrain.cu:1612), requires a different fit to persist
FGS_MODEL_CANDIDATE_FRAMES, and enforces FGS_MODEL_MIN_UPDATE_FRAMES between
updates. `held=1` runs spanning a rising source noise are that cadence caught
acting.

Usage: python3 tests/fgs/model_trace.py encode-debug.log [--bins 20]
"""
import argparse
import re
import statistics as st
import sys

LINE = re.compile(
    r"fgs-model frame=(\d+).*?reliable=(\d).*?reset=(\d)(?:.*?held=(\d))?"
    r".*?noise=([0-9.]+)")
YARR = re.compile(r"y=\[([^\]]*)\]")


def parse(path):
    out = []
    for raw in open(path, "rb"):
        line = raw.decode("utf-8", "replace")
        m = LINE.search(line)
        if not m:
            continue
        y = YARR.search(line)
        # Signalled luma amplitude: mean of the scaling-curve points actually
        # emitted, which is what the decoder synthesises from.
        amp = None
        if y:
            pts = [int(p.split(":")[1]) for p in y.group(1).split() if ":" in p]
            amp = sum(pts) / len(pts) if pts else None
        out.append({
            "frame": int(m.group(1)), "reliable": int(m.group(2)),
            "reset": int(m.group(3)), "held": int(m.group(4) or 0),
            "noise": float(m.group(5)),
            "amp": amp, "model": y.group(1).strip() if y else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--bins", type=int, default=20)
    args = ap.parse_args()
    rows = parse(args.log)
    live = [r for r in rows if r["model"]]
    if not live:
        sys.exit("no signalled models in log")

    models = [r["model"] for r in live]
    distinct, changes = [], []
    for r in live:
        if not distinct or r["model"] != distinct[-1]:
            distinct.append(r["model"])
            changes.append(r["frame"])
    print(f"frames with a signalled model : {len(live)} of {len(rows)}")
    print(f"DISTINCT parameter sets       : {len(set(models))}")
    print(f"model changes                 : {len(distinct)}")
    print(f"scene resets                  : {sum(r['reset'] for r in rows)}")
    print(f"frames holding previous model : {sum(r['held'] for r in live)} "
          f"({100*sum(r['held'] for r in live)/len(live):.1f}%)")

    ns = [r["noise"] for r in live]
    amps = [r["amp"] for r in live if r["amp"] is not None]
    print(f"\nsource noise  min {min(ns):.2f}  max {max(ns):.2f}  "
          f"range {max(ns)/max(min(ns),1e-6):.1f}x")
    print(f"signalled amp min {min(amps):.1f}  max {max(amps):.1f}  "
          f"range {max(amps)/max(min(amps),1e-6):.1f}x")

    # Longest run of held frames while source noise is climbing: the cadence
    # gate caught acting.
    worst = (0, 0, 0.0, 0.0)
    run_start = None
    for i, r in enumerate(live):
        if r["held"]:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start > worst[0]:
                seg = live[run_start:i]
                worst = (i - run_start, seg[0]["frame"],
                         seg[0]["noise"], max(x["noise"] for x in seg))
            run_start = None
    print(f"\nlongest held run: {worst[0]} frames from frame {worst[1]}, "
          f"source noise {worst[2]:.2f} -> {worst[3]:.2f} during the hold")

    n = max(1, len(live) // args.bins)
    print(f"\n{'frame':>8}{'src noise':>11}{'signalled':>11}{'held%':>7}")
    for i in range(0, len(live), n):
        seg = live[i:i + n]
        a = [x["amp"] for x in seg if x["amp"] is not None]
        print(f"{seg[0]['frame']:>8}{st.mean(x['noise'] for x in seg):>11.2f}"
              f"{(st.mean(a) if a else float('nan')):>11.1f}"
              f"{100*sum(x['held'] for x in seg)/len(seg):>7.0f}")


if __name__ == "__main__":
    main()
