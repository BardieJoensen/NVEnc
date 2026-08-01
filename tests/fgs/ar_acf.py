#!/usr/bin/env python3
"""What spatial correlation do the fitted AR coefficients actually encode?

FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md established that the synthesised
grain layer carries roughly half the source's lag-1 autocorrelation while
matching its amplitude -- right strength, wrong size -- and left two candidates
open:

  * the FIT is weak: our solver returns coefficients whose implied grain is
    less correlated than the residual it was fitted from; or
  * the fit is fine and the loss is DOWNSTREAM: template tiling, overlap
    blending, or luma scaling decorrelates a correctly-correlated model.

Those are distinguishable without any encoder change, because AV1's grain
template is a pure function of the coefficients. This runs the spec's AR
recursion (7.18.3.3) over the fitted taps and measures the resulting field's
autocorrelation. Compare that number against the decoded synth layer:

  implied ~= source, decoded ~= half  ->  the loss is downstream of the fit
  implied ~= decoded ~= half          ->  the fit itself is under-correlated

The innovation is drawn from numpy's Gaussian rather than the spec's
gaussian_sequence LFSR. The AR recursion's autocorrelation is a property of the
taps and is invariant to the innovation's distribution, so this changes nothing
that is measured here; it only means absolute grain amplitude is not comparable
to a decoder's. Clipping is the one place the substitution could matter, so the
fraction of samples that would clip is reported -- if it is not ~0, the field is
saturating and the number should not be trusted.

Usage:
  python3 tests/fgs/ar_acf.py nvenc=a.tbl libaom=b.tbl [--seeds 64] [--plane y]
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import filmgrn  # noqa: E402

# The luma template the spec generates, and the region the AR filter writes.
TEMPLATE_W, TEMPLATE_H = 82, 73


def ar_taps(lag):
    """(deltaRow, deltaCol) in the spec's coefficient order, causal half-plane."""
    taps = []
    for d_row in range(-lag, 1):
        for d_col in range(-lag, lag + 1):
            if d_row == 0 and d_col == 0:
                return taps
            taps.append((d_row, d_col))
    return taps


def round2_signed(value, shift):
    """Spec Round2Signed: symmetric about zero, unlike an arithmetic shift."""
    if shift == 0:
        return value
    half = 1 << (shift - 1)
    return np.where(value >= 0, (value + half) >> shift,
                    -((-value + half) >> shift))


def generate_field(coeffs, lag, shift, rng, height, width, sigma, bit_depth=10):
    """One grain template: white innovation, then the spec's AR recursion."""
    grain = np.rint(rng.normal(0.0, sigma, size=(height, width))).astype(np.int64)
    taps = ar_taps(lag)
    centre = 128 << (bit_depth - 8)
    grain_min, grain_max = -centre, (256 << (bit_depth - 8)) - 1 - centre
    clipped = 0
    for y in range(lag, height):
        for x in range(lag, width - lag):
            total = 0
            for (d_row, d_col), c in zip(taps, coeffs):
                total += c * grain[y + d_row, x + d_col]
            value = grain[y, x] + int(round2_signed(np.int64(total), shift))
            if value < grain_min or value > grain_max:
                clipped += 1
                value = min(max(value, grain_min), grain_max)
            grain[y, x] = value
    return grain[lag:, lag:width - lag], clipped


def autocorr(field):
    """Lag-1/lag-2 autocorrelation, horizontal and vertical, on a zero-mean field."""
    a = field.astype(np.float64)
    a = a - a.mean()
    var = (a * a).mean()
    if var <= 0:
        return {}
    def corr(shifted, base):
        return float((shifted * base).mean() / var)
    return {
        "h1": corr(a[:, 1:], a[:, :-1]),
        "v1": corr(a[1:, :], a[:-1, :]),
        "h2": corr(a[:, 2:], a[:, :-2]),
        "v2": corr(a[2:, :], a[:-2, :]),
        "d1": corr(a[1:, 1:], a[:-1, :-1]),
        "sigma": float(np.sqrt(var)),
    }


def implied(entry, plane="y", seeds=64, size=None, sigma=32.0, bit_depth=10):
    params = entry["params"]
    lag = params["ar_coeff_lag"]
    shift = params["ar_coeff_shift"]
    coeffs = entry["ar_coeffs"][plane]
    if plane != "y":
        # Chroma carries one extra tap for the co-located luma sample, which
        # this luma-only recursion cannot supply.
        coeffs = coeffs[:2 * lag * (lag + 1)]
    height, width = size or (TEMPLATE_H, TEMPLATE_W)
    stats, clip_total, samples = [], 0, 0
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        field, clipped = generate_field(coeffs, lag, shift, rng, height, width,
                                        sigma, bit_depth)
        clip_total += clipped
        samples += field.size
        stats.append(autocorr(field))
    out = {k: float(np.mean([s[k] for s in stats])) for k in stats[0]}
    out["lag1"] = 0.5 * (out["h1"] + out["v1"])
    out["clip_fraction"] = clip_total / max(samples, 1)
    out["lag"] = lag
    out["ar_coeff_shift"] = shift
    out["gain"] = float(np.abs(np.asarray(coeffs, dtype=np.float64)).sum()
                        / (1 << shift))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="+", metavar="LABEL=PATH")
    ap.add_argument("--plane", default="y", choices=("y", "cb", "cr"))
    ap.add_argument("--seeds", type=int, default=64)
    ap.add_argument("--sigma", type=float, default=32.0,
                    help="innovation sigma; affects clipping only, not the ACF")
    ap.add_argument("--size", default="",
                    help="HxW of the simulated field (default: the 73x82 spec template)")
    args = ap.parse_args()

    size = None
    if args.size:
        size = tuple(int(v) for v in args.size.lower().split("x"))

    print(f"{'label':<14}{'lag':>4}{'gain':>8}{'lag1':>8}{'h1':>8}{'v1':>8}"
          f"{'d1':>8}{'h2':>8}{'v2':>8}{'clip%':>8}")
    for spec in args.tables:
        label, _, path = spec.partition("=")
        entry = filmgrn.representative(filmgrn.load(path))
        if entry is None:
            print(f"{label:<14}  no updating grain entry in {path}")
            continue
        r = implied(entry, args.plane, args.seeds, size, args.sigma)
        print(f"{label:<14}{r['lag']:>4}{r['gain']:>8.3f}{r['lag1']:>8.3f}"
              f"{r['h1']:>8.3f}{r['v1']:>8.3f}{r['d1']:>8.3f}"
              f"{r['h2']:>8.3f}{r['v2']:>8.3f}"
              f"{100 * r['clip_fraction']:>8.2f}")


if __name__ == "__main__":
    main()
