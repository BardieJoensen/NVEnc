#!/usr/bin/env python3
"""Where in the FGS chain is the grain's spatial correlation lost?

`layer_acf.py` on real film shows the synthesised layer carrying roughly half
the source's lag-1 correlation and essentially none of its lag-2. `ar_acf.py`
shows the fitted coefficients already imply that, and that libaom's fit on the
same residual implies it too -- so neither the solver nor the decoder is losing
it. That leaves the separator, but real film cannot prove it: the source's own
autocorrelation is inflated by picture structure that no mask fully removes, so
"source 0.81 -> residual 0.60" is not evidence of whitening.

A synthetic fixture removes that ambiguity. `fgs_kat.coarse_luma` injects grain
with a KNOWN correlation onto a smooth base and writes the ideal clean base
alongside, so the injected grain is available exactly as source minus ideal:

  injected        the grain that went in                 (ground truth)
  residual        source minus the analyzer's clean base (what the fit sees)
  implied         what the fitted AR coefficients encode (ar_acf)

Whitening in the separator shows up as injected >> residual. Everything
downstream is already known to be faithful, so that would localise the whole
loss to one stage.

Usage:
  python3 tests/fgs/separator_acf.py --nvencc build/nvencc \
      [--denoiser bilateral] [--fixture coarse_luma] [--extra-fg-opts psd=on]
"""
import argparse
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fgs_kat as kat        # noqa: E402
import filmgrn               # noqa: E402
import ar_acf                # noqa: E402


def read_plane(path, index, w, h, bits):
    dtype = np.uint8 if bits == 8 else np.uint16
    itemsize = 1 if bits == 8 else 2
    frame_bytes = w * h * 3 // 2 * itemsize
    with open(path, "rb") as handle:
        handle.seek(index * frame_bytes)
        raw = handle.read(w * h * itemsize)
    return np.frombuffer(raw, dtype, count=w * h).reshape(h, w).astype(np.float64)


def acf(field):
    a = field - field.mean()
    var = (a * a).mean()
    if var <= 0:
        return None
    n = a.shape[1]
    def r(x, y, span):
        return float((x * y).mean() * n / (n - span) / var)
    return {
        "sigma": float(np.sqrt(var)),
        "h1": r(a[:, 1:], a[:, :-1], 1),
        "v1": r(a[1:, :], a[:-1, :], 1),
        "h2": r(a[:, 2:], a[:, :-2], 2),
        "v2": r(a[2:, :], a[:-2, :], 2),
        "h3": r(a[:, 3:], a[:, :-3], 3),
    }


def summarise(name, planes):
    rows = [acf(p) for p in planes]
    rows = [r for r in rows if r]
    out = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
    out["lag1"] = 0.5 * (out["h1"] + out["v1"])
    out["lag2"] = 0.5 * (out["h2"] + out["v2"])
    print(f"{name:<26}{out['sigma']:>9.3f}{out['lag1']:>9.3f}{out['lag2']:>9.3f}"
          f"{out['h3']:>9.3f}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nvencc", required=True)
    ap.add_argument("--fixture", default="coarse_luma")
    ap.add_argument("--denoiser", default="bilateral")
    ap.add_argument("--extra-fg-opts", default="",
                    help="appended to --av1-film-grain, e.g. psd=on")
    ap.add_argument("--work", default="/tmp/downloads/fgs-separator")
    ap.add_argument("--frames", default="10,16,22")
    args = ap.parse_args()

    os.makedirs(args.work, exist_ok=True)
    spec = kat.TESTS[args.fixture]
    kat.apply_spec(spec)
    source = os.path.join(args.work, f"{args.fixture}_src.y4m")
    ideal = os.path.join(args.work, f"{args.fixture}_ideal.yuv")
    kat.generate(args.fixture, spec, source, ideal)

    tag = args.denoiser + ("_" + args.extra_fg_opts.replace("=", "") if args.extra_fg_opts else "")
    clean_y4m = os.path.join(args.work, f"{args.fixture}_{tag}_clean.y4m")
    clean_raw = os.path.join(args.work, f"{args.fixture}_{tag}_clean.yuv")
    table = os.path.join(args.work, f"{args.fixture}_{tag}.tbl")
    source_raw = os.path.join(args.work, f"{args.fixture}_src.yuv")

    analyzer = f"denoise=auto,chroma=auto,denoiser={args.denoiser}"
    if args.extra_fg_opts:
        analyzer += "," + args.extra_fg_opts
    subprocess.run([args.nvencc, "--codec", "raw", "--av1-film-grain", analyzer,
                    "--film-grain-table-out", table, "--log-level", "debug",
                    "-i", source, "-o", clean_y4m], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for src, dst in ((source, source_raw), (clean_y4m, clean_raw)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src,
                        "-pix_fmt", "yuv420p" if kat.BITS == 8 else "yuv420p10le",
                        "-f", "rawvideo", dst], check=True)

    frames = [int(v) for v in args.frames.split(",")]
    src_p = [read_plane(source_raw, f, kat.W, kat.H, kat.BITS) for f in frames]
    cln_p = [read_plane(clean_raw, f, kat.W, kat.H, kat.BITS) for f in frames]
    idl_p = [read_plane(ideal, f, kat.W, kat.H, kat.BITS) for f in frames]

    print(f"fixture {args.fixture}, denoiser {args.denoiser}"
          f"{' ' + args.extra_fg_opts if args.extra_fg_opts else ''}\n")
    print(f"{'stage':<26}{'sigma':>9}{'lag1':>9}{'lag2':>9}{'h3':>9}")
    injected = summarise("injected grain (truth)",
                         [s - i for s, i in zip(src_p, idl_p)])
    residual = summarise("residual (src-clean)",
                         [s - c for s, c in zip(src_p, cln_p)])
    leaked = summarise("grain left in clean base",
                       [c - i for c, i in zip(cln_p, idl_p)])

    entry = filmgrn.representative(filmgrn.load(table))
    if entry is not None:
        r = ar_acf.implied(entry, "y", seeds=48)
        print(f"{'implied by fitted AR':<26}{'':>9}{r['lag1']:>9.3f}"
              f"{0.5*(r['h2']+r['v2']):>9.3f}{'':>9}")

    print(f"\ncaptured sigma {residual['sigma']/max(injected['sigma'],1e-9):.3f}, "
          f"lag1 retained {residual['lag1']/max(injected['lag1'],1e-9):.3f}, "
          f"lag2 retained {residual['lag2']/max(injected['lag2'],1e-9):.3f}")


if __name__ == "__main__":
    main()
