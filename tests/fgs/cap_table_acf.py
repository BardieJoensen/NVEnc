#!/usr/bin/env python3
"""Prototype a conservative lag-1 cap for source-fitted film-grain tables.

`modelsrc=on` can fit picture structure that survives the per-block plane.  The
flat-metrics pass independently measures source lag-1 (`grainCorr`) and tracks
the temporal ground truth much more closely.  This prototype scales only the
luma AR coefficients whose implied lag-1 exceeds that diagnostic plus a small
margin, and rescales luma strength so amplitude is held constant.

This is an offline experiment, not an encoder option.  It exists to test the
regularisation rule against decoded media before putting it in C++.
"""
import argparse
import copy
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ar_acf  # noqa: E402
import filmgrn  # noqa: E402


def write_table(path, entries):
    markers = (("sY", "y"), ("sCb", "cb"), ("sCr", "cr"))
    coeff_markers = (("cY", "y"), ("cCb", "cb"), ("cCr", "cr"))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("filmgrn1\n")
        for entry in entries:
            handle.write("E {} {} {} {} {}\n".format(
                entry["start"], entry["end"], int(entry["apply_grain"]),
                entry["random_seed"], int(entry["update_parameters"])))
            if not (entry["apply_grain"] and entry["update_parameters"]):
                continue
            params = entry["params"]
            handle.write("p " + " ".join(
                str(params[name]) for name in filmgrn.PARAM_NAMES) + "\n")
            for marker, plane in markers:
                points = entry["scaling_points"][plane]
                values = [str(len(points))]
                for x, y in points:
                    values.extend((str(x), str(y)))
                handle.write(marker + " " + " ".join(values) + "\n")
            for marker, plane in coeff_markers:
                handle.write(marker + " " + " ".join(
                    str(value) for value in entry["ar_coeffs"][plane]) + "\n")


def scaled_entry(entry, factor):
    candidate = copy.deepcopy(entry)
    candidate["ar_coeffs"]["y"] = [
        int(round(value * factor)) for value in entry["ar_coeffs"]["y"]
    ]
    return candidate


def regularise_entry(entry, target, margin, seeds, iterations, max_strength_gain):
    old = ar_acf.implied(entry, "y", seeds=seeds, sigma=1.0)
    ceiling = min(0.98, target + margin)
    if old["lag1"] <= ceiling:
        return copy.deepcopy(entry), 1.0, old, old, 1.0, "within"

    low, high = 0.0, 1.0
    best = scaled_entry(entry, low)
    best_stats = ar_acf.implied(best, "y", seeds=seeds, sigma=1.0)
    for _ in range(iterations):
        middle = 0.5 * (low + high)
        candidate = scaled_entry(entry, middle)
        stats = ar_acf.implied(candidate, "y", seeds=seeds, sigma=1.0)
        if stats["lag1"] <= ceiling:
            low, best, best_stats = middle, candidate, stats
        else:
            high = middle

    # The AR change moves template variance, not the desired signal amplitude.
    # Compensate in the strength curve before encoding the experimental arm.
    amplitude = old["sigma"] / max(best_stats["sigma"], 1e-9)
    if amplitude > max_strength_gain:
        # A near-unstable fit can ask for several times more strength.  The
        # simulated template gain does not predict the clipped decoder output
        # accurately enough in that regime (Deer Hunter frame 275 reached
        # 2.339x source amplitude).  Preserve the original entry rather than
        # manufacture a new texture-and-energy failure.
        return copy.deepcopy(entry), 1.0, old, old, amplitude, "rejected"
    desired_y = [[x, y * amplitude] for x, y in entry["scaling_points"]["y"]]
    shift_down = 0
    while desired_y and max(value for _, value in desired_y) > 255.0:
        if best["params"]["scaling_shift"] <= 0:
            raise RuntimeError("cannot requantise overflowing luma strength")
        best["params"]["scaling_shift"] -= 1
        desired_y = [[x, value * 0.5] for x, value in desired_y]
        shift_down += 1
    best["scaling_points"]["y"] = [
        [x, min(255, int(round(value)))] for x, value in desired_y
    ]
    if shift_down:
        # scaling_shift is shared by all planes.  Halve chroma's integer points
        # when the denominator is halved so their decoded amplitude is unchanged.
        for plane in ("cb", "cr"):
            best["scaling_points"][plane] = [
                [x, int(round(value / (1 << shift_down)))]
                for x, value in entry["scaling_points"][plane]
            ]
    return best, low, old, best_stats, amplitude, "adjusted"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target", type=float, default=None,
                        help="fixed source grainCorr target")
    parser.add_argument("--trace-log", default="",
                        help="debug log carrying per-frame grainCorr targets")
    parser.add_argument("--fps", default="24000/1001",
                        help="source fps used to map table timestamps to trace frames")
    parser.add_argument("--margin", type=float, default=0.05)
    parser.add_argument("--seeds", type=int, default=2,
                        help="simulation seeds per trial (prototype default 2)")
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--max-strength-gain", type=float, default=1.25,
                        help="reject an adjustment needing more gain (default 1.25)")
    args = parser.parse_args()
    if args.target is None and not args.trace_log:
        parser.error("one of --target or --trace-log is required")

    trace = {}
    if args.trace_log:
        with open(args.trace_log, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                match = re.search(
                    r"fgs-model frame=(\d+).*?grainCorr=([0-9.+-]+)", line)
                if match:
                    trace[int(match.group(1))] = float(match.group(2))
        if not trace:
            raise SystemExit(f"no fgs-model grainCorr rows in {args.trace_log}")
    fps_num, fps_den = (int(value) for value in args.fps.split("/"))

    def entry_target(entry):
        if not trace:
            return args.target
        frame = int(round(entry["start"] * fps_num / (10_000_000 * fps_den)))
        if frame in trace:
            return trace[frame]
        nearest = min(trace, key=lambda value: abs(value - frame))
        return trace[nearest]

    entries = filmgrn.load(args.input)
    out = []
    changed = 0
    rejected = 0
    target_label = "per-entry trace" if trace else f"{args.target:.3f}"
    print(f"target {target_label} + margin {args.margin:.3f}")
    print(f"{'entry':>5}{'target':>9}{'factor':>9}{'old L1':>9}{'new L1':>9}"
          f"{'old L2':>9}{'new L2':>9}{'need x':>9}{'action':>11}")
    for index, entry in enumerate(entries):
        if not (entry["apply_grain"] and entry["update_parameters"]):
            out.append(copy.deepcopy(entry))
            continue
        target = entry_target(entry)
        adjusted, factor, old, new, amplitude, action = regularise_entry(
            entry, target, args.margin, args.seeds, args.iterations,
            args.max_strength_gain)
        if action == "adjusted":
            changed += 1
        elif action == "rejected":
            rejected += 1
        old_lag2 = 0.5 * (old["h2"] + old["v2"])
        new_lag2 = 0.5 * (new["h2"] + new["v2"])
        print(f"{index:>5}{target:>9.3f}{factor:>9.3f}"
              f"{old['lag1']:>9.3f}{new['lag1']:>9.3f}"
              f"{old_lag2:>9.3f}{new_lag2:>9.3f}{amplitude:>9.3f}"
              f"{action:>11}")
        out.append(adjusted)

    write_table(args.output, out)
    # Reparse what was written: the experimental encode must see exactly what
    # was reported, including integer quantisation and line ordering.
    filmgrn.load(args.output)
    print(f"wrote {args.output}: adjusted {changed}, rejected {rejected}, "
          f"total {len(entries)} entries")


if __name__ == "__main__":
    main()
