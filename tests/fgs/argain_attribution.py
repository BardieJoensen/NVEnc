#!/usr/bin/env python3
"""Does the AR gain explain which titles over-deliver?

`FINDINGS-2026-08-06-EMISSION-EXPONENT.md` rejected a fixed compressive
response and left one lead: among well-determined fits the emission exponent
spans `0.40`--`1.46`, with Casino over-tracking. A single estimator defect
would give one exponent, so the culprit is something that varies per title.

For luma the strength fit is (`NVEncFilmGrainModel.cpp:172,179`):

    templateGain    = sqrt(templateVariance) = arGain
    strength[bin]   = sqrt(binVariance) / arGain
    arGain          = max(1, sqrt(predictorVariance / innovationVariance))

`arGain` is a variance *ratio*, so it describes grain correlation structure and
not amplitude, and it is exactly the per-title quantity in that expression.

What the decoder actually plays is the emitted curve multiplied by the standard
deviation of the AR field it synthesizes from the emitted, **quantised**
coefficients:

    played  ~  curve * arGain_realized

The encoder divided by the `arGain` it fitted. If the AR field the decoder
builds has a different gain -- because the coefficients were quantised to
`ar_coeff_shift`, or clamped, or the fit's implied gain was never realisable --
the division does not cancel and each title carries its own multiplicative
error. Coefficient quantisation is a good candidate for producing exactly that,
because filter gain grows sensitive to small coefficient errors as the filter
approaches the stability boundary, which is where strongly correlated grain
sits.

Measured, not modelled: `av1_grain.generate_luma_template` is the normative
integer AR recursion, so the realized gain is read off the field the decoder
would really produce.

Two questions, in order:

1. Does `arGain_realized` correlate with over-delivery across titles?
2. Does multiplying it back in reconcile emission with source -- that is, does
   `curve * arGain_realized` track source sigma with exponent 1 when `curve`
   alone does not?

A negative answer to (1) removes the last named candidate and says the defect
is not in the AR-gain accounting.

Diagnosis only. No coefficient here is a correction to apply.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

import av1_grain
import filmgrn
from emission_exponent import SOURCES, OUT, source_sigma, fit_loglog
from floor_separation import curve_rms

AOM_GRAIN = Path.home() / (
    ".cache/fgs-gate/aom-18c52422b835/src/av1/decoder/grain_synthesis.c")


def realized_ar_gain(table: Path, gaussian, bit_depth: int = 10) -> tuple[float, float]:
    """Std of the synthesized AR field, and of the same field with no AR taps.

    Their ratio is the gain the AR recursion actually contributes, which is the
    quantity the encoder divided by.
    """
    entries = filmgrn.load(table)
    ups = [e for e in entries if e["apply_grain"] and e["update_parameters"]
           and e["scaling_points"]["y"]]
    if not ups:
        raise RuntimeError(f"{table.name}: no luma-bearing entries")
    gains, whites = [], []
    for entry in ups[:6]:
        field = av1_grain.generate_luma_template(entry, gaussian, bit_depth)
        flat = np.asarray(field, dtype=np.float64).ravel()
        if flat.std() <= 0:
            continue
        gains.append(flat.std())
        # Same entry with the AR taps zeroed: the unfiltered innovation field.
        bare = json.loads(json.dumps(entry))
        bare["ar_coeffs"]["y"] = [0] * len(entry["ar_coeffs"]["y"])
        white = np.asarray(
            av1_grain.generate_luma_template(bare, gaussian, bit_depth),
            dtype=np.float64).ravel()
        if white.std() > 0:
            whites.append(white.std())
    if not gains or not whites:
        raise RuntimeError(f"{table.name}: degenerate AR field")
    return statistics.mean(gains), statistics.mean(whites)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--aom-grain-source", default=str(AOM_GRAIN))
    args = parser.parse_args()

    gaussian = av1_grain.load_gaussian_sequence(args.aom_grain_source)

    rows = []
    print(f"{'title':17} {'src sigma':>10} {'curve':>9} {'AR gain':>8} "
          f"{'curve*gain':>11}")
    for title, source in SOURCES.items():
        table = OUT / f"{title}.tbl"
        if not (source.is_file() and table.is_file()):
            continue
        try:
            field_sd, white_sd = realized_ar_gain(table, gaussian)
        except RuntimeError as error:
            print(f"skip {title}: {error}", file=sys.stderr)
            continue
        gain = field_sd / white_sd
        sigma = source_sigma(source, args.frames)
        curve = curve_rms(table)["y"]
        rows.append((title, sigma, curve, gain, curve * gain))
        print(f"{title:17} {sigma:10.3f} {curve:9.5f} {gain:8.3f} "
              f"{curve * gain:11.5f}")

    if len(rows) < 5:
        print("too few titles", file=sys.stderr)
        return 1

    sigmas = [r[1] for r in rows]
    curves = [r[2] for r in rows]
    gains = [r[3] for r in rows]
    products = [r[4] for r in rows]

    print("\n=== 1. does AR gain track over-delivery? ===")
    over = [c / s for c, s in zip(curves, sigmas)]
    b, r, t = fit_loglog(gains, over)
    print(f"log(curve/source) on log(AR gain):  slope {b:+.3f}  r {r:+.3f}  "
          f"t {t:+.2f}  n {len(rows)}")
    print("  a positive slope would mean high-gain titles over-deliver, i.e."
          "\n  the encoder's division by arGain is not being undone by playback.")

    print("\n=== 2. does multiplying the gain back in reconcile emission? ===")
    b_curve, r_curve, _ = fit_loglog(sigmas, curves)
    b_prod, r_prod, _ = fit_loglog(sigmas, products)
    print(f"curve        vs source:  exponent {b_curve:+.3f}  r {r_curve:+.3f}")
    print(f"curve*gain   vs source:  exponent {b_prod:+.3f}  r {r_prod:+.3f}")
    print("  if the AR accounting were the defect, the product would track"
          "\n  source with exponent nearer 1 than the curve alone does.")

    (OUT / "argain-attribution.json").write_text(json.dumps(
        {"rows": [{"title": a, "source_sigma": s, "curve": c,
                   "ar_gain": g, "product": p} for a, s, c, g, p in rows],
         "gain_vs_overdelivery": {"slope": b, "r": r, "t": t},
         "curve_exponent": b_curve, "product_exponent": b_prod},
        indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
