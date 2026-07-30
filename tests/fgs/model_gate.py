#!/usr/bin/env python3
"""Accept or reject a candidate AV1 grain model on texture, using held-out
descriptors the candidate could not have been tuned against.

WHY THIS IS NOT texture_media_report.py
`texture_media_report.py --labelled-negative` answers a different question:
"can the detector see a known texture change?".  It is a sensitivity check on
two encoded arms and makes no claim about which arm is better.  This module
answers "should this model be accepted?", and its subject is a set of AR
coefficients rather than encoded media.

WHY IT EXISTS AT ALL
On 2026-07-30 a direct coordinate-descent optimisation of quantised AR
coefficients against Taxi Driver's source residual beat both analyzers by about
3x on the two descriptors the texture report gates: normalised radial spectrum
total variation, and spatial autocorrelation over lags 1-8.  On descriptors it
was never shown, the same model was substantially WORSE than NVEnc's own:

    H/V gradient anisotropy    0.0166 vs 0.0076    (2.2x further from source)
    diagonal lag-1 ACF         0.0295 vs 0.0021    (14x further from source)

That is a demonstration, not a hypothesis: a model can improve on the gated
descriptors while its real texture degrades in directions the gate does not
measure -- the same class of error as tuning against VMAF and destroying grain.
The specimen is kept at
/media/merged-storage/media/test-encodes/ceiling/taxi_ceiling_q.json and a
correct gate must REJECT it.

THE RULE
Gated descriptors (spectrum TV, H/V ACF lags 1-8) can only ever help a
candidate.  Held-out descriptors (gradient anisotropy, diagonal lag-1 ACF) can
only ever veto one.  A candidate that moves any held-out descriptor materially
further from the source than the incumbent is rejected no matter how much it
improves the gated ones.  Any other arrangement lets an optimiser trade real
texture for score, which is exactly what the specimen did.

The held-out set is not a permanent secret; the point is that it is not what a
candidate was fitted against.  If a future analyzer is ever tuned on anisotropy
and diagonal ACF, this module needs a new held-out direction, and the specimen
that motivated it should be regenerated against the new loss.
"""

import argparse
import json
import os
import subprocess
import sys

import numpy as np

# AV1 luma grain AR template, lag 3: 24 causal neighbours in raster order.
# Identical to the template in scripts/av1_model_ceiling.py so the descriptor
# numbers in that experiment and in this gate are directly comparable.
AR_LAG = 3
AR_TAPS = [(dy, dx) for dy in range(-AR_LAG, 1)
           for dx in range(-AR_LAG, AR_LAG + 1)
           if (dy, dx) != (0, 0) and not (dy == 0 and dx > 0)]
BLOCK = 32
ACF_LAGS = tuple(range(1, 9))

# Held-out veto thresholds.  A candidate may be this much worse than the
# incumbent on a held-out descriptor before it is rejected; the absolute floor
# stops a near-zero incumbent distance from making the ratio meaningless.
DEFAULT_HELD_OUT_RATIO = 1.5
DEFAULT_HELD_OUT_FLOOR = 0.005


class ModelGateError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# descriptors
# --------------------------------------------------------------------------

def synthesize(coeffs, count, rng, size=BLOCK):
    """Generate `count` grain patches the way AV1 does: white noise through the
    causal AR filter.

    The recursion is sequential in raster order so x/y cannot be vectorised,
    but patches are independent and advance together.
    """
    coeffs = np.asarray(coeffs, dtype=np.float64)
    if coeffs.shape != (len(AR_TAPS),):
        raise ModelGateError(
            f"expected {len(AR_TAPS)} AR coefficients, got {coeffs.shape}")
    pad = AR_LAG
    grain = rng.standard_normal((count, size + pad, size + 2 * pad))
    taps = [(dy, dx, c) for (dy, dx), c in zip(AR_TAPS, coeffs) if c]
    for y in range(pad, size + pad):
        for x in range(pad, size + pad):
            accumulator = np.zeros(count)
            for dy, dx, c in taps:
                accumulator += c * grain[:, y + dy, x + dx]
            grain[:, y, x] += accumulator
    return grain[:, pad:, pad:pad + size]


def _normalize(patches):
    """Remove mean and unit-normalise each patch: energy is never the question.

    Amplitude belongs to the retention monitor.  Every descriptor below is
    computed after this step so a louder or quieter model scores identically.
    """
    patches = np.asarray(patches, dtype=np.float64)
    patches = patches - patches.mean(axis=(1, 2), keepdims=True)
    sigma = patches.std(axis=(1, 2), keepdims=True)
    return patches / np.maximum(sigma, 1e-6)


def _radial_spectrum(patches, size):
    transformed = np.fft.fftshift(
        np.abs(np.fft.fft2(patches, axes=(1, 2))) ** 2, axes=(1, 2))
    centre = size // 2
    yy, xx = np.mgrid[0:size, 0:size]
    radius = np.sqrt((yy - centre) ** 2 + (xx - centre) ** 2).astype(int)
    spectrum = np.zeros(centre)
    for k in range(centre):
        mask = radius == k
        if mask.any():
            spectrum[k] = transformed[:, mask].mean()
    return spectrum / max(spectrum.sum(), 1e-12)


def _axis_acf(patches, lags):
    """Horizontal/vertical autocorrelation, averaged -- the GATED descriptor."""
    values = []
    for lag in lags:
        horizontal = (patches[:, :, :-lag] * patches[:, :, lag:]).mean()
        vertical = (patches[:, :-lag, :] * patches[:, lag:, :]).mean()
        values.append(0.5 * float(horizontal + vertical))
    return np.asarray(values)


def _diagonal_acf(patches, lag=1):
    """Both diagonals at one lag -- HELD OUT.

    An optimiser fitted on the H/V axes has no reason to keep this right, and
    the ceiling specimen did not: 14x further from the source than NVEnc.
    """
    down_right = (patches[:, :-lag, :-lag] * patches[:, lag:, lag:]).mean()
    down_left = (patches[:, :-lag, lag:] * patches[:, lag:, :-lag]).mean()
    return 0.5 * float(down_right + down_left)


def _anisotropy(patches):
    """Gradient structure-tensor coherence -- HELD OUT.

    Same definition as texture_metrics._gradient_coherence so the number means
    the same thing in both places: 0 for isotropic texture, 1 for a single
    dominant orientation.
    """
    gx = (patches[:, 1:-1, 2:] - patches[:, 1:-1, :-2]) * 0.5
    gy = (patches[:, 2:, 1:-1] - patches[:, :-2, 1:-1]) * 0.5
    gxx = np.mean(gx * gx, axis=(1, 2))
    gxy = np.mean(gx * gy, axis=(1, 2))
    gyy = np.mean(gy * gy, axis=(1, 2))
    trace = gxx + gyy
    difference = np.sqrt(np.maximum((gxx - gyy) ** 2 + 4.0 * gxy * gxy, 0.0))
    coherence = np.divide(
        difference, trace, out=np.zeros_like(trace), where=trace > 1e-12)
    return float(coherence.mean())


def describe(patches, lags=ACF_LAGS):
    """Amplitude-independent texture descriptors for a stack of 2-D patches."""
    patches = np.asarray(patches)
    if patches.ndim != 3 or patches.shape[1] != patches.shape[2]:
        raise ModelGateError("patches must be a stack of square 2-D arrays")
    size = patches.shape[1]
    normalized = _normalize(patches)
    return {
        "patches": int(patches.shape[0]),
        "radial_spectrum": _radial_spectrum(normalized, size).tolist(),
        "acf": _axis_acf(normalized, lags).tolist(),
        "anisotropy": _anisotropy(normalized),
        "diagonal_acf_lag1": _diagonal_acf(normalized, 1),
    }


def distances(candidate, source):
    """Descriptor distances from a candidate to the source residual.

    Split by role, because the roles are not symmetric: `gated` may only help a
    candidate and `held_out` may only veto it.
    """
    candidate_spectrum = np.asarray(candidate["radial_spectrum"])
    source_spectrum = np.asarray(source["radial_spectrum"])
    if candidate_spectrum.shape != source_spectrum.shape:
        raise ModelGateError("spectra have different bin counts")
    candidate_acf = np.asarray(candidate["acf"])
    source_acf = np.asarray(source["acf"])
    if candidate_acf.shape != source_acf.shape:
        raise ModelGateError("ACF vectors have different lag counts")
    return {
        "gated": {
            "spectrum_tv": 0.5 * float(
                np.abs(candidate_spectrum - source_spectrum).sum()),
            "acf_rmse": float(np.sqrt(
                ((candidate_acf - source_acf) ** 2).mean())),
        },
        "held_out": {
            "anisotropy_abs": abs(
                candidate["anisotropy"] - source["anisotropy"]),
            "diagonal_acf_lag1_abs": abs(
                candidate["diagonal_acf_lag1"] - source["diagonal_acf_lag1"]),
        },
    }


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------

def evaluate(candidate, incumbent,
             held_out_ratio=DEFAULT_HELD_OUT_RATIO,
             held_out_floor=DEFAULT_HELD_OUT_FLOOR):
    """Decide whether `candidate` may replace `incumbent`.

    Both arguments are distance dicts from `distances()`, measured against the
    same source residual with the same evaluator.
    """
    for name, value in (("candidate", candidate), ("incumbent", incumbent)):
        if set(value) != {"gated", "held_out"}:
            raise ModelGateError(f"{name} is not a distance dict")

    vetoes = []
    held_out = {}
    for descriptor, candidate_distance in candidate["held_out"].items():
        incumbent_distance = incumbent["held_out"][descriptor]
        budget = max(incumbent_distance * held_out_ratio, held_out_floor)
        regressed = candidate_distance > budget
        held_out[descriptor] = {
            "candidate": candidate_distance,
            "incumbent": incumbent_distance,
            "budget": budget,
            "ratio": (candidate_distance / incumbent_distance
                      if incumbent_distance > 1e-12 else None),
            "regressed": regressed,
        }
        if regressed:
            vetoes.append(descriptor)

    gated = {}
    improvements = []
    for descriptor, candidate_distance in candidate["gated"].items():
        incumbent_distance = incumbent["gated"][descriptor]
        improved = candidate_distance < incumbent_distance
        gated[descriptor] = {
            "candidate": candidate_distance,
            "incumbent": incumbent_distance,
            "improved": improved,
            "ratio": (candidate_distance / incumbent_distance
                      if incumbent_distance > 1e-12 else None),
        }
        if improved:
            improvements.append(descriptor)

    if vetoes:
        verdict = "REJECT"
        reason = (
            "held-out descriptor(s) regressed: " + ", ".join(sorted(vetoes)))
        if improvements:
            # The whole point of the gate. Say it out loud in the report so a
            # future reader does not "fix" the gate by relaxing it.
            reason += (
                "; the candidate improved on the gated descriptor(s) "
                + ", ".join(sorted(improvements))
                + " and is rejected anyway -- improving a descriptor a model "
                  "was fitted against is not evidence of better texture")
    elif improvements:
        verdict = "ACCEPT"
        reason = "no held-out regression; improves " + ", ".join(
            sorted(improvements))
    else:
        verdict = "ACCEPT"
        reason = "no held-out regression; no gated improvement either"

    return {
        "verdict": verdict,
        "reason": reason,
        "vetoes": sorted(vetoes),
        "gated_improvements": sorted(improvements),
        "held_out": held_out,
        "gated": gated,
        "thresholds": {
            "held_out_ratio": held_out_ratio,
            "held_out_floor": held_out_floor,
            "logic": ("held-out descriptors may only veto; gated descriptors "
                      "may only help"),
        },
    }


# --------------------------------------------------------------------------
# model loading and media
# --------------------------------------------------------------------------

def load_model(path):
    """Return real-valued luma AR coefficients from a filmgrn1 table or JSON.

    A .json specimen carries `ar_coeffs` already in real units.  A .tbl carries
    integers scaled by 1 << ar_coeff_shift and must be divided back down, or the
    synthesised texture is meaningless.
    """
    if path.endswith(".json"):
        with open(path) as handle:
            payload = json.load(handle)
        coefficients = payload.get("ar_coeffs")
        if coefficients is None:
            raise ModelGateError(f"{path} has no ar_coeffs")
        return np.asarray(coefficients, dtype=np.float64), payload

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import filmgrn  # noqa: E402  (local module, kept off the import path above)

    with open(path) as handle:
        entry = filmgrn.representative(filmgrn.parse(handle.read()))
    if entry is None:
        raise ModelGateError(f"{path} has no grain-applying entry")
    shift = entry["params"]["ar_coeff_shift"]
    lag = entry["params"]["ar_coeff_lag"]
    if lag != AR_LAG:
        raise ModelGateError(
            f"{path} uses ar_coeff_lag {lag}; this gate assumes {AR_LAG}")
    coefficients = np.asarray(entry["ar_coeffs"]["y"], dtype=np.float64)
    return coefficients / float(1 << shift), {"table": path, "entry": entry}


def _probe_geometry(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path],
        capture_output=True, text=True)
    if result.returncode:
        raise ModelGateError(f"cannot probe {path}: {result.stderr.strip()}")
    width, _, height = result.stdout.strip().partition("x")
    return int(width), int(height)


def decode_luma(path, frames):
    width, height = _probe_geometry(path)
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vframes", str(frames),
         "-pix_fmt", "gray16le", "-f", "rawvideo", "-"],
        capture_output=True, timeout=3600)
    if result.returncode or not result.stdout:
        raise ModelGateError(f"decode failed: {path}")
    samples = np.frombuffer(result.stdout, dtype=np.uint16).astype(np.float32)
    plane = width * height
    usable = len(samples) // plane
    return [samples[i * plane:(i + 1) * plane].reshape(height, width)
            for i in range(usable)]


def source_residual_patches(source_frames, clean_frames):
    """Flat 32x32 source-residual patches, selected from the source alone.

    Mirrors the evaluator rule in texture_metrics: rank by residual sigma times
    (1 + gradient coherence), require real grain present, keep the flattest
    quartile.  Candidate models never influence the selection, which is what
    keeps the comparison honest.
    """
    selected = []
    for source, clean in zip(source_frames, clean_frames):
        residual = source - clean
        height, width = clean.shape
        rows, columns = height // BLOCK, width // BLOCK
        guide = clean[:rows * BLOCK, :columns * BLOCK].reshape(
            rows, BLOCK, columns, BLOCK).transpose(0, 2, 1, 3).reshape(
                -1, BLOCK, BLOCK)
        blocks = residual[:rows * BLOCK, :columns * BLOCK].reshape(
            rows, BLOCK, columns, BLOCK).transpose(0, 2, 1, 3).reshape(
                -1, BLOCK, BLOCK)
        gy = np.diff(guide, axis=1)[:, :, :-1]
        gx = np.diff(guide, axis=2)[:, :-1, :]
        coherence = np.sqrt((gy ** 2 + gx ** 2).mean(axis=(1, 2)))
        sigma = blocks.std(axis=(1, 2))
        score = sigma * (1.0 + coherence)
        eligible = sigma > 0.5 * 4.0        # 0.5 8-bit units at 10-bit scale
        if eligible.sum() < 8:
            eligible = sigma > 0
        index = np.where(eligible)[0]
        if not len(index):
            continue
        keep = index[np.argsort(score[index])[:max(8, len(index) // 4)]]
        selected.append(blocks[keep])
    if not selected:
        raise ModelGateError("no flat source-residual patches found")
    return np.concatenate(selected)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True,
                        help="lossless source clip")
    parser.add_argument("--clean", required=True,
                        help="the identically denoised clean base")
    parser.add_argument("--incumbent", required=True,
                        help="filmgrn1 .tbl or .json of the shipping model")
    parser.add_argument("--candidate", required=True,
                        help="filmgrn1 .tbl or .json of the proposed model")
    parser.add_argument("--frames", type=int, default=6)
    # 256 rather than 64: at 64 the Monte-Carlo spread on the held-out
    # anisotropy distance was wide enough to change which descriptors fired the
    # veto between seeds. At 256 the ceiling specimen regresses on both
    # held-out descriptors for every seed tried (1234, 7, 99, 20260730).
    parser.add_argument("--synthesis-patches", type=int, default=256)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--held-out-ratio", type=float,
                        default=DEFAULT_HELD_OUT_RATIO)
    parser.add_argument("--held-out-floor", type=float,
                        default=DEFAULT_HELD_OUT_FLOOR)
    parser.add_argument("--json-out")
    parser.add_argument(
        "--expect", choices=("accept", "reject"),
        help="assert the verdict; exit 0 when it matches, 1 when it does not. "
             "Use this for labelled specimens so the gate is proven able to "
             "fail, not only able to pass.")
    args = parser.parse_args()

    source_frames = decode_luma(args.source, args.frames)
    clean_frames = decode_luma(args.clean, args.frames)
    count = min(len(source_frames), len(clean_frames))
    if not count:
        raise ModelGateError("no decodable frames")
    patches = source_residual_patches(
        source_frames[:count], clean_frames[:count])
    source_descriptors = describe(patches)

    report = {
        "source": args.source,
        "clean": args.clean,
        "frames": count,
        "source_patches": int(len(patches)),
        "source_descriptors": source_descriptors,
        "models": {},
    }
    measured = {}
    for role, path in (("incumbent", args.incumbent),
                       ("candidate", args.candidate)):
        coefficients, provenance = load_model(path)
        # Same seed for both models: the comparison is between AR filters, so
        # letting the white-noise draw differ would add avoidable variance.
        rng = np.random.default_rng(args.seed)
        grain = synthesize(coefficients, args.synthesis_patches, rng)
        descriptors = describe(grain)
        measured[role] = distances(descriptors, source_descriptors)
        report["models"][role] = {
            "path": path,
            "ar_coeffs": coefficients.tolist(),
            "descriptors": descriptors,
            "distances": measured[role],
            "provenance": {k: v for k, v in provenance.items()
                           if k != "entry"},
        }

    result = evaluate(measured["candidate"], measured["incumbent"],
                      args.held_out_ratio, args.held_out_floor)
    report["gate"] = result

    print(f"source residual: {len(patches)} flat patches "
          f"over {count} frame(s)\n")
    print(f"{'descriptor':<26}{'role':>10}{'candidate':>12}"
          f"{'incumbent':>12}{'':>4}")
    for descriptor, values in sorted(result["gated"].items()):
        print(f"{descriptor:<26}{'gated':>10}{values['candidate']:>12.4f}"
              f"{values['incumbent']:>12.4f}"
              f"{'  better' if values['improved'] else '':>4}")
    for descriptor, values in sorted(result["held_out"].items()):
        print(f"{descriptor:<26}{'held out':>10}{values['candidate']:>12.4f}"
              f"{values['incumbent']:>12.4f}"
              f"{'  REGRESSED' if values['regressed'] else '':>4}")
    print(f"\nverdict: {result['verdict']}\nreason : {result['reason']}")

    if args.json_out:
        with open(args.json_out, "w") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"json   : {args.json_out}")

    if args.expect:
        expected = args.expect.upper()
        if result["verdict"] != expected:
            print(f"\nEXPECTATION FAILED: expected {expected}, "
                  f"got {result['verdict']}", file=sys.stderr)
            return 1
        print(f"\nexpectation met: {expected}")
        return 0
    return 0 if result["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ModelGateError as error:
        print(f"model_gate: {error}", file=sys.stderr)
        sys.exit(2)
