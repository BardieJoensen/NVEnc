#!/usr/bin/env python3
"""Fit the AR grain model from the SOURCE instead of from the separator's residual.

FINDINGS-2026-08-01-SEPARATOR-WHITENING.md localised the whole loss of grain
correlation to one stage: the separator. The fit reproduces its input to three
decimals and the decoder reproduces the fit, but the residual the fit is given
has already been whitened -- on `coarse_luma` the injected grain has lag-1 0.839
and the residual carries 0.655.

That is structural, not a tuning problem. One operator is asked to serve two
objectives at once: produce a base that keeps detail (which wants aggressive,
detail-aware filtering) and produce a residual that is a faithful sample of the
grain (which wants a filter that touches nothing but grain). No single filter
does both, which is why every attempt to improve the separator moved one at the
cost of the other.

Two operators do. The denoiser keeps its job of producing a clean base, and the
MODEL is estimated separately, from the source. The encoder already measures the
source's grain correctly and throws the answer away: `spatialCorrelation` in
`NVEncFilterFilmGrain.cu` is a flat-block lag-1 on the source and reads 0.81 on
Taxi, against 0.60 from the residual the model is actually fitted from -- it is
printed as a diagnostic and never used.

The objection to fitting from the source is real and is what this measures: the
source contains picture, and picture is highly correlated, so a source fit could
simply be reading structure rather than grain. The defence is that model
estimation, unlike separation, only has to work on flat blocks and only has to
remove a per-block plane -- decorrelating at block scale, not at grain scale --
whereas the separator has to produce a clean base everywhere and so must use a
filter that overlaps the grain band. Whether that defence holds is an empirical
question with a ground-truth answer on the KAT fixtures:

  injected lag-1        the grain that went in                    (truth)
  residual fit          what production fits today
  source fit            plane-removed source over flat blocks
  ideal-clean fit       source minus the ideal base, same blocks  (upper bound)

The ideal-clean arm is the control. It is the same estimator run on a residual
with no picture in it at all, so source-fit minus ideal-clean-fit is exactly the
picture contamination, separated from everything else.

Usage:
  python3 tests/fgs/source_fit.py --nvencc build/nvencc [--fixture coarse_luma]
  python3 tests/fgs/source_fit.py --raw src.yuv --clean clean.yuv \
      --size 3840x2160 --bits 10 --frames 10,16,22
"""
import argparse
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ar_acf  # noqa: E402

BS = 32          # FGS_BLOCK_SIZE
LAG = 3          # FGS_AR_LAG


def read_plane(path, index, w, h, bits):
    dtype = np.uint8 if bits == 8 else np.uint16
    itemsize = 1 if bits == 8 else 2
    frame_bytes = w * h * 3 // 2 * itemsize
    with open(path, "rb") as handle:
        handle.seek(index * frame_bytes)
        raw = handle.read(w * h * itemsize)
    if len(raw) < w * h * itemsize:
        raise SystemExit(f"{path}: frame {index} is past the end of the file")
    return np.frombuffer(raw, dtype, count=w * h).reshape(h, w).astype(np.float64)


def blockwise(frame, bs=BS):
    """Trim to whole blocks and reshape to (nby, nbx, bs, bs)."""
    h, w = frame.shape
    nby, nbx = h // bs, w // bs
    trimmed = frame[:nby * bs, :nbx * bs]
    return trimmed.reshape(nby, bs, nbx, bs).transpose(0, 2, 1, 3)


def plane_basis(bs=BS):
    """The encoder's normalised plane basis: constant, x, y over the block."""
    y, x = np.mgrid[0:bs, 0:bs].astype(np.float64)
    xn = (2.0 * x - (bs - 1)) / bs
    yn = (2.0 * y - (bs - 1)) / bs
    return xn, yn


def detrend_blocks(blocks):
    """Remove each block's own mean-plus-plane, as kernel_fgs_flat_metrics does.

    This is the whole reason a source fit is not circular. It is a three-term
    least-squares fit over a 32x32 block, so it can only take out a gradient at
    block scale; the grain band is orders of magnitude above that and passes
    through untouched. A denoiser cannot be this gentle because it has to
    produce a clean base at every pixel, not statistics over selected blocks.
    """
    xn, yn = plane_basis(blocks.shape[-1])
    mean = blocks.mean(axis=(-2, -1), keepdims=True)
    centred = blocks - mean
    ax = (centred * xn).sum(axis=(-2, -1)) / (xn * xn).sum()
    ay = (centred * yn).sum(axis=(-2, -1)) / (yn * yn).sum()
    return centred - ax[..., None, None] * xn - ay[..., None, None] * yn


def flat_scores(frame, bits, bs=BS):
    """Per-block flatness score and sigma, replicating kernel_fgs_flat_metrics."""
    blocks = blockwise(frame, bs)
    resid = detrend_blocks(blocks)
    variance = (resid * resid).mean(axis=(-2, -1))

    xn, yn = plane_basis(bs)
    # The kernel removes the fitted plane's own slope from the gradient before
    # forming the structure tensor, so a smooth ramp does not read as an edge.
    mean = blocks.mean(axis=(-2, -1), keepdims=True)
    centred = blocks - mean
    ax = (centred * xn).sum(axis=(-2, -1)) / (xn * xn).sum()
    ay = (centred * yn).sum(axis=(-2, -1)) / (yn * yn).sum()
    gx = (blocks[..., 1:-1, 2:] - blocks[..., 1:-1, :-2]) * 0.5 - ax[..., None, None] * (2.0 / bs)
    gy = (blocks[..., 2:, 1:-1] - blocks[..., :-2, 1:-1]) * 0.5 - ay[..., None, None] * (2.0 / bs)
    gxx = (gx * gx).mean(axis=(-2, -1))
    gyy = (gy * gy).mean(axis=(-2, -1))
    gxy = (gx * gy).mean(axis=(-2, -1))

    scale2 = float((1 << bits) - 1) ** 2
    var_norm = variance / scale2
    gxx, gyy, gxy = gxx / scale2, gyy / scale2, gxy / scale2
    trace = gxx + gyy
    det = gxx * gyy - gxy * gxy
    disc = np.maximum(0.0, trace * trace - 4.0 * det)
    e1 = (trace + np.sqrt(disc)) * 0.5
    e2 = (trace - np.sqrt(disc)) * 0.5
    ratio = e1 / np.maximum(e2, 1e-6)

    arg = np.clip(-6682.0 * var_norm - 0.2056 * ratio
                  + 13087.0 * trace - 12434.0 * e1 + 2.5694, -25.0, 100.0)
    var_threshold = 0.005 / (bs * bs)
    score = np.where(var_norm > var_threshold, 1.0 / (1.0 + np.exp(-arg)), 0.0)
    return score, np.sqrt(variance)


def select_flat(frame, bits, fraction=0.10, bs=BS):
    """Top-`fraction` blocks by flatness score, as (row, col) block indices."""
    score, sigma = flat_scores(frame, bits, bs)
    n = max(1, int(round(score.size * fraction)))
    order = np.argsort(score.ravel())[::-1][:n]
    rows, cols = np.unravel_index(order, score.shape)
    return list(zip(rows.tolist(), cols.tolist())), score, sigma


def static_flat_blocks(frame, nextframe, blocks, bs=BS, lo=0.8, hi=1.3):
    """Flat blocks whose consecutive-frame difference is consistent with grain.

    Real film has no ideal clean base, so the fixture's control is unavailable
    and "source lag-1 is 0.81" cannot by itself be told apart from picture
    structure leaking through the flat mask. Time supplies the missing control:
    grain is independent frame to frame, picture is not, so on a block with no
    motion (f_n - f_n+1)/sqrt(2) is the grain field with the picture removed
    exactly -- and its autocorrelation is a ground truth as hard as the
    fixture's.

    A block qualifies when its temporal difference variance is close to its
    spatial variance, which is what independent grain over identical picture
    gives and what motion, a cut, or a lighting change does not. Selecting on
    the RATIO rather than on the difference variance alone matters: the latter
    would simply pick the blocks with the least grain and bias every number
    that follows.
    """
    grid_a = blockwise(frame, bs)
    grid_b = blockwise(nextframe, bs)
    keep = []
    for (by, bx) in blocks:
        a = detrend_blocks(grid_a[by, bx][None, None])[0, 0]
        d = (grid_a[by, bx] - grid_b[by, bx]) / np.sqrt(2.0)
        d = d - d.mean()
        v_s = float((a * a).mean())
        v_d = float((d * d).mean())
        if v_s > 1e-6 and lo <= v_d / v_s <= hi:
            keep.append((by, bx))
    return keep


def accumulate_ar(field, blocks, detrend, ata, atb, lag=LAG, bs=BS):
    """Add one frame's lag-3 normal equations over the given blocks.

    Only block-interior pixels contribute, so every tap stays inside the block
    that was selected and detrending is well defined. Production accumulates
    across block boundaries on a full-frame residual; holding that identical
    across arms is what makes them comparable.
    """
    taps = ar_acf.ar_taps(lag)
    total = 0
    grid = blockwise(field, bs)
    for (by, bx) in blocks:
        blk = grid[by, bx]
        if detrend:
            blk = detrend_blocks(blk[None, None])[0, 0]
        # Interior target region: every tap offset stays inside the block.
        target = blk[lag:, lag:bs - lag].ravel()
        pred = np.stack([blk[lag + dr: bs + dr, lag + dc: bs - lag + dc].ravel()
                         for (dr, dc) in taps], axis=1)
        ata += pred.T @ pred
        atb += pred.T @ target
        total += target.size
    return total


def solve_ar(ata, atb):
    reg = max(1e-9, np.abs(np.diag(ata)).mean() * 1e-6)
    return np.linalg.solve(ata + reg * np.eye(ata.shape[0]), atb)


def field_acf(field, blocks, detrend, bs=BS):
    """Autocorrelation of the field itself over the selected blocks."""
    grid = blockwise(field, bs)
    sel = np.stack([grid[by, bx] for (by, bx) in blocks])
    if detrend:
        sel = detrend_blocks(sel[None])[0]
    a = sel - sel.mean(axis=(-2, -1), keepdims=True)
    var = (a * a).mean()
    if var <= 0:
        return None
    return {
        "sigma": float(np.sqrt(var)),
        "h1": float((a[:, :, 1:] * a[:, :, :-1]).mean() / var),
        "v1": float((a[:, 1:, :] * a[:, :-1, :]).mean() / var),
        "h2": float((a[:, :, 2:] * a[:, :, :-2]).mean() / var),
        "v2": float((a[:, 2:, :] * a[:, :-2, :]).mean() / var),
    }


def implied_acf(coeffs, shift, seeds, bit_depth, sigma=32.0):
    """What the fitted taps encode, run through the spec's own AR recursion.

    `sigma` is the innovation amplitude and matters only through clipping: the
    recursion's autocorrelation is a property of the taps alone. A strongly
    correlated fit has a large variance gain and saturates the template at the
    spec's default innovation, which is a real encoder bug
    (FINDINGS-2026-08-01-GRAIN-TEMPLATE-CLIPPING.md) but would mask the fit's
    own behaviour here, so drop it until `clip%` reads ~0.
    """
    quantised = np.rint(np.asarray(coeffs) * (1 << shift)).astype(np.int64)
    entry = {"params": {"ar_coeff_lag": LAG, "ar_coeff_shift": shift},
             "ar_coeffs": {"y": quantised.tolist()}}
    return ar_acf.implied(entry, "y", seeds=seeds, bit_depth=bit_depth,
                          sigma=sigma)


def report(label, acf, implied):
    lag1 = 0.5 * (acf["h1"] + acf["v1"]) if acf else float("nan")
    lag2 = 0.5 * (acf["h2"] + acf["v2"]) if acf else float("nan")
    sigma = acf["sigma"] if acf else float("nan")
    if implied is None:
        print(f"{label:<28}{sigma:>9.3f}{lag1:>9.3f}{lag2:>9.3f}"
              f"{'-':>9}{'-':>9}{'-':>8}{'-':>8}")
        return
    print(f"{label:<28}{sigma:>9.3f}{lag1:>9.3f}{lag2:>9.3f}"
          f"{implied['lag1']:>9.3f}{0.5 * (implied['h2'] + implied['v2']):>9.3f}"
          f"{implied['gain']:>8.3f}{100 * implied['clip_fraction']:>8.2f}")


def run(src_p, cln_p, idl_p, bits, seeds, shift, fraction, sim_sigma=32.0,
        nxt_p=None):
    blocks, score, sigma = select_flat(src_p[0], bits, fraction)
    nb = blockwise(src_p[0], BS).shape[:2]
    cut = score.ravel()[np.argsort(score.ravel())[::-1][len(blocks) - 1]]
    total_flat = len(blocks)
    if nxt_p is not None:
        # Restrict EVERY arm to the same static subset, so the temporal truth
        # and the estimators under test are measured on identical pixels.
        blocks = static_flat_blocks(src_p[0], nxt_p[0], blocks)
        if len(blocks) < 8:
            raise SystemExit(f"only {len(blocks)} static flat blocks; "
                             "pick frames with less motion")
    print(f"flat blocks {total_flat}/{nb[0] * nb[1]} (score {cut:.3f} at the cut)"
          + (f", {len(blocks)} of them static" if nxt_p is not None else "")
          + f", block sigma median {np.median([sigma[b] for b in blocks]):.2f}\n")

    print(f"{'estimator':<28}{'sigma':>9}{'lag1':>9}{'lag2':>9}"
          f"{'AR lag1':>9}{'AR lag2':>9}{'gain':>8}{'clip%':>8}")

    arms = []
    if idl_p is not None:
        arms.append(("injected grain (truth)",
                     [s - i for s, i in zip(src_p, idl_p)], False))
    if nxt_p is not None:
        arms.append(("temporal grain (truth)",
                     [(a - b) / np.sqrt(2.0) for a, b in zip(src_p, nxt_p)], False))
    arms.append(("residual fit (production)",
                 [s - c for s, c in zip(src_p, cln_p)], False))
    arms.append(("source fit (plane removed)", list(src_p), True))
    if idl_p is not None:
        arms.append(("ideal-clean fit (control)",
                     [s - i for s, i in zip(src_p, idl_p)], True))

    out = {}
    n = len(ar_acf.ar_taps(LAG))
    for label, fields, detrend in arms:
        # Accumulate every frame into one system rather than averaging
        # per-frame solutions: the normal equations are additive, the solutions
        # are not.
        ata = np.zeros((n, n))
        atb = np.zeros(n)
        acfs = []
        for f in fields:
            accumulate_ar(f, blocks, detrend, ata, atb)
            acfs.append(field_acf(f, blocks, detrend))
        coeffs = solve_ar(ata, atb)
        acf = {k: float(np.mean([a[k] for a in acfs if a])) for k in acfs[0]}
        implied = implied_acf(coeffs, shift, seeds, bits, sim_sigma)
        report(label, acf, implied)
        out[label] = (acf, implied, coeffs)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nvencc")
    ap.add_argument("--fixture", default="coarse_luma")
    ap.add_argument("--denoiser", default="bilateral")
    ap.add_argument("--work", default="/tmp/downloads/fgs-sourcefit")
    ap.add_argument("--raw", help="source as raw yuv420p (skips fixture generation)")
    ap.add_argument("--clean", help="clean base as raw yuv420p")
    ap.add_argument("--ideal", help="ideal clean base, when ground truth exists")
    ap.add_argument("--size", default="", help="WxH, required with --raw")
    ap.add_argument("--bits", type=int, default=0)
    ap.add_argument("--frames", default="10,16,22")
    ap.add_argument("--seeds", type=int, default=32)
    ap.add_argument("--ar-shift", type=int, default=9,
                    help="quantisation shift for the implied ACF; 9 isolates the "
                         "fit from quantisation, production picks 6-9 itself")
    ap.add_argument("--flat-fraction", type=float, default=0.10)
    ap.add_argument("--temporal", action="store_true",
                    help="add the consecutive-frame grain truth and restrict "
                         "every arm to static flat blocks; the only ground "
                         "truth available on real film")
    ap.add_argument("--sim-sigma", type=float, default=32.0,
                    help="innovation sigma for the implied-ACF simulation; "
                         "lower it until clip%% reads ~0 to see the fit alone")
    args = ap.parse_args()

    frames = [int(v) for v in args.frames.split(",")]

    if args.raw:
        if not args.size:
            raise SystemExit("--size WxH is required with --raw")
        w, h = (int(v) for v in args.size.lower().split("x"))
        bits = args.bits or 10
        src_p = [read_plane(args.raw, f, w, h, bits) for f in frames]
        cln_p = [read_plane(args.clean, f, w, h, bits) for f in frames]
        idl_p = ([read_plane(args.ideal, f, w, h, bits) for f in frames]
                 if args.ideal else None)
        nxt_p = ([read_plane(args.raw, f + 1, w, h, bits) for f in frames]
                 if args.temporal else None)
        print(f"source {os.path.basename(args.raw)}, "
              f"clean {os.path.basename(args.clean)}, {w}x{h} {bits}-bit\n")
    else:
        if not args.nvencc:
            raise SystemExit("--nvencc is required unless --raw is given")
        import fgs_kat as kat
        os.makedirs(args.work, exist_ok=True)
        spec = kat.TESTS[args.fixture]
        kat.apply_spec(spec)
        source = os.path.join(args.work, f"{args.fixture}_src.y4m")
        ideal = os.path.join(args.work, f"{args.fixture}_ideal.yuv")
        kat.generate(args.fixture, spec, source, ideal)
        clean_y4m = os.path.join(args.work, f"{args.fixture}_{args.denoiser}_clean.y4m")
        clean_raw = os.path.join(args.work, f"{args.fixture}_{args.denoiser}_clean.yuv")
        source_raw = os.path.join(args.work, f"{args.fixture}_src.yuv")
        subprocess.run([args.nvencc, "--codec", "raw", "--av1-film-grain",
                        f"denoise=auto,chroma=auto,denoiser={args.denoiser}",
                        "-i", source, "-o", clean_y4m], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pix = "yuv420p" if kat.BITS == 8 else "yuv420p10le"
        for s, d in ((source, source_raw), (clean_y4m, clean_raw)):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", s,
                            "-pix_fmt", pix, "-f", "rawvideo", d], check=True)
        w, h, bits = kat.W, kat.H, kat.BITS
        src_p = [read_plane(source_raw, f, w, h, bits) for f in frames]
        cln_p = [read_plane(clean_raw, f, w, h, bits) for f in frames]
        idl_p = [read_plane(ideal, f, w, h, bits) for f in frames]
        nxt_p = ([read_plane(source_raw, f + 1, w, h, bits) for f in frames]
                 if args.temporal else None)
        print(f"fixture {args.fixture}, denoiser {args.denoiser}, "
              f"{w}x{h} {bits}-bit\n")

    run(src_p, cln_p, idl_p, bits, args.seeds, args.ar_shift,
        args.flat_fraction, args.sim_sigma, nxt_p)


if __name__ == "__main__":
    main()
