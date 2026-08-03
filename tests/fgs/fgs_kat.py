#!/usr/bin/env python3
"""Known-answer tests for the NVEnc CUDA AV1 film-grain analyzer.

Each test synthesizes a static banded intensity pattern with precisely known
grain, encodes it with `nvencc --av1-film-grain`, decodes the result twice with
dav1d (grain synthesis on and off), and compares the statistics of the
synthesized grain against the injected grain:

  const_luma     constant-strength luma grain, pristine chroma
  warmup_luma    atypical first frame followed by stable luma grain
  ramp_luma      luma grain strength rising with intensity, pristine chroma
  chroma_corr    luma grain plus luma-correlated chroma grain
  chroma_ind     luma grain plus independent chroma grain
  clean          completely clean footage (no grain may be signalled)
  cut            grainy first half, clean second half across a scene cut
  const_10bit    const_luma at 1080p 10-bit
  const_hlg      const_luma at 1080p 10-bit with HLG/BT.2020 signalling
  const_4k10_pq  const_luma at 4K 10-bit with PQ/BT.2020 signalling
  coarse_luma    spatially-correlated grain (35mm proxy), capture-ratio guard
  detail_luma    static fine detail plus grain; separation/detail-loss probe
  coarse_detail  correlated grain OVER detail: does chasing coarse grain take
                 picture detail with it?  (fails with FGS_KAT_DENOISER=bilateral)
  coarse_detail_pan  the same with the picture panning fractionally
  coarse_detail_move the same with fast pan + rotation + zoom, so displacement
                 varies across the frame
  coarse_detail_occl the same with a field of opaque objects sliding over the
                 background, so 21-24% of the region per frame is content that
                 was NOT visible in the previous frame.  Disocclusion is what
                 separates a motion-compensated denoiser from a spatial one, and
                 this is the only fixture that reproduces the real-film ranking
                 of denoiser=motion: see FINDINGS-2026-08-01-SEPARATOR-WHITENING.md
  auto_retain_*  content-aware residual retention on flat and detailed inputs
  dark_luma      grain clipped at legal black; shadow strength + black level
  retain_luma    retain 60% of original luma grain in the encoded base layer
  retain_10bit   retain_luma at 1080p 10-bit

Sigma values in specs and reports are in 8-bit code values; 10-bit variants
scale internally.

Usage:  python3 fgs_kat.py [--tests const_luma,clean] [--keep]
Environment: NVENCC (encoder binary), FGS_KAT_DIR (work dir),
FGS_KAT_DENOISER (fft3d, bilateral, or motion; default fft3d), and
FGS_KAT_QVBR (optional QVBR value; default is the established CQP 20 gate).
"""
import argparse
import contextlib
import json
import os
import re
import subprocess
import sys

import numpy as np

import quality_metrics

FPS = 24
BANDS = 12
FRAMES = 32
FRAMES_CUT = 64
SKIP = 8            # analyzer warm-up frames excluded from measurements
CUT_FRAME = 32      # first clean frame of the "cut" test

# per-test geometry/depth, set by apply_spec()
W, H, BAND_W, BITS, DS = 1920, 1080, 160, 8, 1.0
DTYPE, MAXVAL = np.uint8, 255
LEVELS = np.linspace(32, 224, BANDS)  # keeps +-3 sigma of grain inside range

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NVENCC = os.environ.get("NVENCC", os.path.join(REPO, "build-fgs-cuda", "nvencc"))
WORKDIR = os.environ.get("FGS_KAT_DIR", "/tmp/nvenc-fgs-tests/kat")
FGS_DENOISER = os.environ.get("FGS_KAT_DENOISER", "fft3d").lower()
if FGS_DENOISER not in ("fft3d", "bilateral", "motion"):
    sys.exit(f"invalid FGS_KAT_DENOISER: {FGS_DENOISER}")
# Extra --av1-film-grain sub-options, so an analyzer change can be run against
# the whole suite before it is considered for a default (e.g. FGS_KAT_EXTRA=psd=on).
FGS_EXTRA = os.environ.get("FGS_KAT_EXTRA", "").strip()
FGS_QVBR = os.environ.get("FGS_KAT_QVBR", "").strip()
if FGS_QVBR:
    try:
        if float(FGS_QVBR) <= 0:
            raise ValueError
    except ValueError:
        sys.exit(f"invalid FGS_KAT_QVBR: {FGS_QVBR}")


def apply_spec(spec):
    global W, H, BAND_W, BITS, DS, DTYPE, MAXVAL, LEVELS, CLIP_LO, CLIP_HI
    W = spec.get("width", 1920)
    H = spec.get("height", 1080)
    BITS = spec.get("bits", 8)
    DS = float(1 << (BITS - 8))
    DTYPE = np.uint8 if BITS == 8 else np.uint16
    MAXVAL = (1 << BITS) - 1
    BAND_W = W // BANDS
    # "levels" are native code values at the spec's bit depth; the default
    # ladder is expressed in 8-bit units and scaled.
    LEVELS = np.array(spec["levels"], dtype=np.float64) if "levels" in spec \
        else np.linspace(32, 224, BANDS) * DS
    # legal-range masters clip their grain at the range floor/ceiling
    CLIP_LO, CLIP_HI = spec.get("clip", (0, MAXVAL))


def base_luma(shift=0, detail=False, pan=(0.0, 0.0), rot=0.0, zoom=1.0,
              occluders=()):
    y = np.empty((H, W), np.float64)
    for i, level in enumerate(np.roll(LEVELS, shift)):
        y[:, i * BAND_W:(i + 1) * BAND_W] = level
    if detail:
        # High-frequency picture content occupies the top half while the bottom
        # remains flat enough for a trustworthy noise estimate.  Multiple
        # incommensurate periods prevent one favorable FFT bin from making this
        # an unrealistically easy preservation test.
        #
        # `pan` displaces this content by a (dx, dy) already multiplied by the
        # frame index.  The texture is analytic, so a fractional displacement is
        # evaluated exactly rather than resampled -- a resampling artifact would
        # be indistinguishable from the denoiser damage this fixture measures.
        # The bands do not move: they are the flat regions every per-band sigma
        # measurement in this suite depends on.
        top = H // 2
        left, right = BAND_W, W - BAND_W
        yy, xx = np.mgrid[32:top - 32, left:right]
        # Rotation and zoom about the region centre make the displacement vary
        # across the frame, so no single motion vector describes it.
        if rot or zoom != 1.0:
            cy, cx = 0.5 * (32 + top - 32), 0.5 * (left + right)
            dx, dy = xx - cx, yy - cy
            c, s = np.cos(rot), np.sin(rot)
            xx = cx + (c * dx - s * dy) / zoom
            yy = cy + (s * dx + c * dy) / zoom
        xx = xx - pan[0]
        yy = yy - pan[1]
        texture = (6.0 * np.sin(2.0 * np.pi * xx / 8.0)
                   + 4.0 * np.sin(2.0 * np.pi * (xx + yy) / 17.0)
                   + 2.0 * np.sin(2.0 * np.pi * yy / 29.0))
        y[32:top - 32, left:right] += texture
        for ox, oy, ow, oh in occluders:
            # Opaque foreground with its own incommensurate periods, WRITTEN
            # OVER the background rather than added to it -- an added layer
            # would leave the background visible underneath and there would be
            # nothing to disocclude.
            x0 = max(left, int(round(ox))); x1 = min(right, int(round(ox)) + ow)
            y0 = max(32, int(round(oy)));   y1 = min(top - 32, int(round(oy)) + oh)
            if x1 <= x0 or y1 <= y0:
                continue
            fy, fx = np.mgrid[y0:y1, x0:x1]
            y[y0:y1, x0:x1] = LEVELS[BANDS // 2] + (
                7.0 * np.sin(2.0 * np.pi * fx / 5.0)
                + 5.0 * np.sin(2.0 * np.pi * (fx - fy) / 11.0)
                + 3.0 * np.sin(2.0 * np.pi * fy / 23.0))
    return y


def occluder_field(spec, n):
    """Positions of the moving foreground objects on frame `n`.

    spec["occluders"] is (w, h, speed, nx, ny): an nx-by-ny grid of w-by-h
    objects sliding horizontally at `speed` px/frame, alternate rows travelling
    in opposite directions so objects cross rather than moving as one rigid
    field (a rigid field is just a pan, which the pan fixtures already cover).
    """
    field = spec.get("occluders")
    if not field:
        return ()
    w, h, speed, nx, ny = field
    top, left, right = H // 2, BAND_W, W - BAND_W
    span_x = max(right - left - w, 1)
    step_x = (right - left) / max(nx, 1)
    step_y = (top - 64 - h) / max(ny - 1, 1) if ny > 1 else 0
    rects = []
    for row in range(ny):
        direction = 1 if row % 2 == 0 else -1
        travel = (speed * n * direction) % (2 * span_x)
        for col in range(nx):
            x = left + (col * step_x + travel) % span_x
            rects.append((x, 32 + row * step_y, w, h))
    return rects


def sigma_map_for(spec, base):
    if spec["sigma_y_mode"] in ("const", "coarse"):
        return np.full_like(base, spec["sigma_y"] * DS)
    # linear in intensity: sigma(32) = 2 .. sigma(224) = 10 (8-bit units)
    return (2.0 + (base - LEVELS[0]) / (LEVELS[-1] - LEVELS[0]) * 8.0) * DS


def avg2x2(arr):
    return arr.reshape(arr.shape[0] // 2, 2, arr.shape[1] // 2, 2).mean(axis=(1, 3))


def correlated_unit_noise(rng, shape, blur_sigma_px=1.2, radius=3):
    """Unit-variance Gaussian noise with short-range spatial correlation, as a
    synthetic proxy for real (non-white) film grain: energy concentrated at
    low/mid spatial frequencies instead of spread flat across the spectrum,
    which is what makes it hard for a frequency-domain denoiser to separate
    from genuine picture detail."""
    raw = rng.normal(0.0, 1.0, shape)
    ax = np.arange(-radius, radius + 1)
    k1 = np.exp(-(ax ** 2) / (2.0 * blur_sigma_px ** 2))
    k1 /= k1.sum()
    kernel2d = np.outer(k1, k1)
    kpad = np.zeros(shape)
    kh, kw = kernel2d.shape
    kpad[:kh, :kw] = kernel2d
    kpad = np.roll(kpad, (-radius, -radius), axis=(0, 1))
    blurred = np.fft.irfft2(np.fft.rfft2(raw) * np.fft.rfft2(kpad), s=shape)
    return blurred / blurred.std()


def band_slices(margin, band_w, height):
    for i in range(BANDS):
        yield np.s_[margin:height - margin, i * band_w + margin:(i + 1) * band_w - margin]


def generate(test, spec, path, clean_path=None):
    """Write the y4m fixture; return (per-band noise sigma per plane,
    per-band luma mean).  Both are post-clip observations — the ground truth a
    legal-range master actually exposes.

    If clean_path is provided, also write the corresponding ideal clean source
    as headerless planar YUV.  The optional output is used by the libaom
    reference harness and does not change the generated grainy fixture.
    """
    rng = np.random.default_rng(20260715)
    var_sum = np.zeros((3, BANDS))
    mean_sum = np.zeros(BANDS)
    var_frames = 0
    grain_free = test == "clean"
    colorspace = "C420mpeg2" if BITS == 8 else "C420p10"
    clean_context = open(clean_path, "wb") if clean_path else contextlib.nullcontext()
    with open(path, "wb") as f, clean_context as clean_file:
        f.write(f"YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 {colorspace}\n".encode())
        nframes = spec.get("frames", FRAMES)
        for n in range(nframes):
            grainy = not (grain_free or (test == "cut" and n >= CUT_FRAME))
            pan = spec.get("pan", (0.0, 0.0))
            offset = (pan[0] * n, pan[1] * n)
            rot = np.deg2rad(spec.get("rot", 0.0) * n)
            zoom = spec.get("zoom", 1.0) ** n
            occ = occluder_field(spec, n)
            base = base_luma(spec.get("cut_roll", 6), spec.get("detail", False),
                             offset, rot, zoom, occ) \
                + spec.get("cut_offset", 0) \
                if test in ("cut", "cut_grainy") and n >= CUT_FRAME \
                else base_luma(0, spec.get("detail", False), offset, rot, zoom, occ)
            if grainy:
                unit = correlated_unit_noise(rng, (H, W)) if spec["sigma_y_mode"] == "coarse" \
                    else rng.normal(0.0, 1.0, (H, W))
                noise_y = unit * sigma_map_for(spec, base)
                if n == 0 and "first_sigma_y" in spec:
                    noise_y *= spec["first_sigma_y"] / spec["sigma_y"]
            else:
                noise_y = np.zeros((H, W))
            y = np.clip(np.rint(base + noise_y), CLIP_LO, CLIP_HI).astype(DTYPE)
            planes = [y]
            actual_y = y.astype(np.float64) - base
            actual_c = []
            for _ in range(2):  # U then V
                c = np.full((H // 2, W // 2), 128.0 * DS)
                if grainy and spec.get("corr_c", 0.0) != 0.0:
                    c += spec["corr_c"] * avg2x2(noise_y)
                if grainy and spec.get("sigma_c", 0.0) > 0.0:
                    c += rng.normal(0.0, spec["sigma_c"] * DS, (H // 2, W // 2))
                cq = np.clip(np.rint(c), 0, MAXVAL).astype(DTYPE)
                planes.append(cq)
                actual_c.append(cq.astype(np.float64) - 128.0 * DS)
            f.write(b"FRAME\n")
            for plane in planes:
                f.write(plane.tobytes())
            if clean_file:
                clean_y = np.clip(np.rint(base), CLIP_LO, CLIP_HI).astype(DTYPE)
                clean_c = np.full((H // 2, W // 2), 128 * DS, dtype=DTYPE)
                clean_file.write(clean_y.tobytes())
                clean_file.write(clean_c.tobytes())
                clean_file.write(clean_c.tobytes())
            if grainy and n >= SKIP // 2:
                for b, sl in enumerate(band_slices(24, BAND_W, H)):
                    var_sum[0, b] += actual_y[sl].var()
                    mean_sum[b] += y[sl].mean()
                for b, sl in enumerate(band_slices(12, BAND_W // 2, H // 2)):
                    var_sum[1, b] += actual_c[0][sl].var()
                    var_sum[2, b] += actual_c[1][sl].var()
                var_frames += 1
    expected = np.sqrt(var_sum / max(var_frames, 1))
    expected_mean = mean_sum / max(var_frames, 1)
    return expected, expected_mean


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"FAILED ({r.returncode}): {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


COLOR_ARGS = {
    "pq":  ["--colormatrix", "bt2020nc", "--colorprim", "bt2020", "--transfer", "smpte2084", "--colorrange", "limited"],
    "hlg": ["--colormatrix", "bt2020nc", "--colorprim", "bt2020", "--transfer", "arib-std-b67", "--colorrange", "limited"],
}
COLOR_EXPECT = {
    "pq":  {"color_transfer": "smpte2084", "color_primaries": "bt2020", "color_space": "bt2020nc"},
    "hlg": {"color_transfer": "arib-std-b67", "color_primaries": "bt2020", "color_space": "bt2020nc"},
}


def encode(src, out, spec):
    fgs_opts = f"denoise=auto,chroma=auto,denoiser={FGS_DENOISER}"
    if FGS_EXTRA:
        fgs_opts += "," + FGS_EXTRA
    if "retain" in spec:
        fgs_opts += f",retain={spec['retain']}"
    cmd = [NVENCC, "--codec", "av1"]
    if FGS_QVBR:
        cmd += ["--qvbr", FGS_QVBR, "--max-bitrate", "20000",
                "--preset", "p4", "--tune", "hq"]
    else:
        cmd += ["--cqp", "20"]
    cmd += ["--av1-film-grain", fgs_opts, "--log-level", "debug"]
    if BITS == 10:
        cmd += ["--output-depth", "10"]
    cmd += COLOR_ARGS.get(spec.get("color"), [])
    if spec.get("limited") and not spec.get("color"):
        cmd += ["--colorrange", "limited"]
    cmd += ["-i", src, "-o", out]
    r = run(cmd)
    return r.stdout + r.stderr


def decode(mkv, filmgrain, yuv):
    pix = "yuv420p" if BITS == 8 else "yuv420p10le"
    run(["ffmpeg", "-v", "error", "-y", "-c:v", "libdav1d",
         "-filmgrain", str(filmgrain), "-i", mkv,
         "-pix_fmt", pix, "-f", "rawvideo", yuv])


def probe_color(mkv):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=color_transfer,color_primaries,color_space,pix_fmt",
             "-of", "json", mkv])
    return json.loads(r.stdout)["streams"][0]


def parse_log(log):
    """-> list of dicts with frame, reliable, reset, held per fgs-model line."""
    out = []
    for line in log.splitlines():
        m = re.search(r"fgs-model frame=(\d+) pts=\S+ reliable=(\d) reset=(\d)(?: held=(\d))?", line)
        if not m:
            continue
        adaptive = re.search(r"risk=([0-9.]+) retain=([0-9.]+)", line)
        grain_corr = re.search(r"grainCorr=(-?[0-9.]+)", line)
        out.append({"frame": int(m.group(1)), "reliable": int(m.group(2)),
                    "reset": int(m.group(3)), "held": int(m.group(4) or 0),
                    "risk": float(adaptive.group(1)) if adaptive else 0.0,
                    "retain": float(adaptive.group(2)) if adaptive else 0.0,
                    "grain_corr": float(grain_corr.group(1)) if grain_corr else 0.0})
    return out


class YUV:
    def __init__(self, path):
        self.frame_elems = W * H * 3 // 2
        self.mm = np.memmap(path, dtype=DTYPE, mode="r")
        self.n = self.mm.size // self.frame_elems

    def planes(self, n):
        base = n * self.frame_elems
        y = self.mm[base:base + W * H].reshape(H, W)
        u = self.mm[base + W * H:base + W * H * 5 // 4].reshape(H // 2, W // 2)
        v = self.mm[base + W * H * 5 // 4:base + self.frame_elems].reshape(H // 2, W // 2)
        return y, u, v


def measure(on_path, off_path, frames):
    """Per-band sigma of synthesized grain per plane, plus chroma/luma
    correlation of the synthesized grain, averaged over `frames`."""
    on, off = YUV(on_path), YUV(off_path)
    var_sum = np.zeros((3, BANDS))
    corr_uv = []
    for n in frames:
        pon, poff = on.planes(n), off.planes(n)
        d = [pon[i].astype(np.int32) - poff[i].astype(np.int32) for i in range(3)]
        for b, sl in enumerate(band_slices(24, BAND_W, H)):
            var_sum[0, b] += d[0][sl].astype(np.float64).var()
        for b, sl in enumerate(band_slices(12, BAND_W // 2, H // 2)):
            var_sum[1, b] += d[1][sl].astype(np.float64).var()
            var_sum[2, b] += d[2][sl].astype(np.float64).var()
        dy_avg = avg2x2(d[0].astype(np.float64))
        for c in (1, 2):
            dc = d[c].astype(np.float64)
            if dc.std() > 0.05 * DS and dy_avg.std() > 0.05 * DS:
                corr_uv.append(np.corrcoef(dc.ravel(), dy_avg.ravel())[0, 1])
    sigma = np.sqrt(var_sum / max(len(frames), 1))
    return sigma, (float(np.mean(corr_uv)) if corr_uv else 0.0)


def band_means(path, frames):
    """Per-band luma mean of a decoded stream, same band interior as measure()."""
    v = YUV(path)
    acc = np.zeros(BANDS)
    for n in frames:
        y = v.planes(n)[0]
        for b, sl in enumerate(band_slices(24, BAND_W, H)):
            acc[b] += float(y[sl].mean())
    return acc / max(len(frames), 1)


def grain_frame_corr(on_path, off_path, frames):
    """Mean |correlation| between consecutive frames' synthesized luma grain.
    Near zero when the decoder reseeds per frame; near one for frozen grain."""
    on, off = YUV(on_path), YUV(off_path)
    prev = None
    corrs = []
    for n in frames:
        d = (on.planes(n)[0].astype(np.int32) - off.planes(n)[0].astype(np.int32))
        d = d[24:-24, 24:-24].astype(np.float64).ravel()
        if prev is not None and d.std() > 0.1 * DS and prev.std() > 0.1 * DS:
            corrs.append(abs(float(np.corrcoef(d, prev)[0, 1])))
        prev = d
    return float(np.mean(corrs)) if corrs else 1.0


def luma_band_sigmas(path, frames):
    """Per-band luma standard deviation of a decoded stream."""
    video = YUV(path)
    var_sum = np.zeros(BANDS)
    for n in frames:
        y = video.planes(n)[0]
        for b, sl in enumerate(band_slices(24, BAND_W, H)):
            var_sum[b] += y[sl].astype(np.float64).var()
    return np.sqrt(var_sum / max(len(frames), 1))


def retained_grain_corr(src_path, off_path, frames):
    """Correlation between source grain and the grain retained in the base."""
    src, off = YUV(src_path), YUV(off_path)
    corrs = []
    for n in frames:
        src_y, off_y = src.planes(n)[0], off.planes(n)[0]
        for sl in band_slices(24, BAND_W, H):
            a = src_y[sl].astype(np.float64).ravel()
            b = off_y[sl].astype(np.float64).ravel()
            a -= a.mean()
            b -= b.mean()
            if a.std() > 0.1 * DS and b.std() > 0.1 * DS:
                corrs.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(corrs)) if corrs else 0.0


def check(name, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def fmt(a):
    return "[" + " ".join(f"{v:.2f}" for v in a) + "]"


TESTS = {
    "const_luma":    {"sigma_y_mode": "const", "sigma_y": 6.0},
    # The first accepted model necessarily has one frame of statistics.  This
    # fixture makes that frame atypical without crossing the scene-reset noise
    # ratio, then verifies the full rolling-window fit replaces it promptly.
    "warmup_luma":   {"sigma_y_mode": "const", "sigma_y": 6.0, "first_sigma_y": 4.0},
    "ramp_luma":     {"sigma_y_mode": "ramp"},
    "chroma_corr":   {"sigma_y_mode": "const", "sigma_y": 6.0, "corr_c": 0.8, "sigma_c": 1.0},
    "chroma_ind":    {"sigma_y_mode": "const", "sigma_y": 6.0, "sigma_c": 3.0},
    "clean":         {"sigma_y_mode": "const", "sigma_y": 0.0},
    "cut":           {"sigma_y_mode": "const", "sigma_y": 6.0, "frames": FRAMES_CUT},
    "const_10bit":   {"sigma_y_mode": "const", "sigma_y": 6.0, "bits": 10},
    "const_hlg":     {"sigma_y_mode": "const", "sigma_y": 6.0, "bits": 10, "color": "hlg"},
    "const_4k10_pq": {"sigma_y_mode": "const", "sigma_y": 6.0, "bits": 10, "color": "pq",
                      "width": 3840, "height": 2160, "frames": 24},
    "coarse_luma":   {"sigma_y_mode": "coarse", "sigma_y": 6.0},
    "detail_luma":   {"sigma_y_mode": "const", "sigma_y": 6.0, "detail": True},
    # Correlated grain over detail, with a moving OCCLUDING layer.  Every other
    # fixture here is a single texture layer, static or geometrically
    # transformed, so every pixel existed somewhere in the previous frame and a
    # temporal denoiser can in principle find all of it.  Real motion uncovers
    # content that was never visible, which no temporal predictor can supply --
    # the case where a motion-compensated denoiser has no fallback and a purely
    # spatial one is unaffected.  See FINDINGS-2026-08-01-SEPARATOR-WHITENING.md.
    "coarse_detail_occl": {"sigma_y_mode": "coarse", "sigma_y": 6.0, "detail": True,
                           "occluders": (110, 90, 26.0, 9, 4)},
    # The combination neither of the two above can test. coarse_luma is
    # correlated grain over flat bands, so nothing is at risk of being pulled
    # into the grain layer; detail_luma has white grain, so a correlation-driven
    # filter shape never engages. Only correlated grain OVER detail can show
    # whether a separator that chases coarse grain takes picture detail with it,
    # which is the stated blind spot of the PSD-shaped Wiener gain
    # (FINDINGS-2026-07-31-WIENER-PSD.md) and the reason it is not in production.
    "coarse_detail": {"sigma_y_mode": "coarse", "sigma_y": 6.0, "detail": True},
    # coarse_detail with the picture moving.  Every other fixture in this suite
    # is a static image with fresh grain each frame, which is the ideal case for
    # a motion-compensated denoiser and never occurs in film -- on 2026-08-01
    # that gap ranked `motion` first on the fixtures while real 4K film put it
    # far last (Butteraugli max-p95 8.63 -> 53.86 on The Shining).  The pan is
    # deliberately fractional so motion compensation cannot land exactly.
    "coarse_detail_pan": {"sigma_y_mode": "coarse", "sigma_y": 6.0, "detail": True,
                          "pan": (0.77, 0.31)},
    # Hard motion: fast pan plus rotation and zoom, so the displacement varies
    # across the frame and no single vector fits it.  coarse_detail_pan turned
    # out to be too easy -- it left `motion` ranked first, where real 4K film
    # ranks it last, and the real-film damage tracks motion magnitude.
    "coarse_detail_move": {"sigma_y_mode": "coarse", "sigma_y": 6.0, "detail": True,
                           "pan": (5.3, 2.1), "rot": 0.35, "zoom": 1.004},
    "auto_retain_flat": {"sigma_y_mode": "const", "sigma_y": 6.0, "retain": "auto"},
    "auto_retain_detail": {"sigma_y_mode": "const", "sigma_y": 6.0,
                           "detail": True, "retain": "auto"},
    # Grain near legal black, clipped at the range floor like a legal-range
    # master: reproduces the waxy-shadow / black-level artifacts seen on real
    # heavy-grain film (Taxi Driver f388 class).  Band 0 sits 0.25 sigma above
    # the floor, band 4 about 3 sigma (correction fades out beyond that).
    "dark_luma":     {"sigma_y_mode": "const", "sigma_y": 6.0, "bits": 10, "limited": True,
                      "levels": [70, 82, 96, 115, 140, 175, 220, 280, 360, 460, 580, 720],
                      "clip": (64, 940)},
    "retain_luma":   {"sigma_y_mode": "const", "sigma_y": 6.0, "retain": 0.6},
    "retain_10bit":  {"sigma_y_mode": "const", "sigma_y": 6.0, "bits": 10, "retain": 0.6},
    # SUBTLE hard cut between two grainy scenes: the post-cut shot differs only
    # moderately (bands rolled 3 + offset), so the cross-cut SAD sits between
    # grain SAD and an obvious scene change -- the regime where a temporal
    # denoiser with a mistuned scene threshold blends across the cut (the real
    # Taxi Driver f388 ghost).  A loud cut trips even broken thresholds.
    "cut_grainy":    {"sigma_y_mode": "const", "sigma_y": 3.0, "bits": 10, "frames": FRAMES_CUT,
                      "cut_roll": 3, "cut_offset": 60},
}

# Regression guard for coarse_luma, not a quality target: real 35mm grain is
# spatially correlated like this fixture, and as of 2026-07-16 the FFT3D+
# bilateral denoiser only captures a fraction of it (confirmed on real 4K
# remuxes: NVEncFilterFilmGrain output landed at ~95-107% of source remux
# size on heavy-grain content instead of the 30-40% target). This threshold
# only catches a regression below that already-limited baseline.
COARSE_LUMA_MIN_CAPTURE_RATIO = 0.30
COARSE_LUMA_MIN_SOURCE_CORRELATION = 0.50
FINE_LUMA_MAX_SOURCE_CORRELATION = 0.10


def run_test(test, keep):
    spec = TESTS[test]
    apply_spec(spec)
    d = os.path.join(WORKDIR, test)
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "src.y4m")
    mkv = os.path.join(d, "out.mkv")
    ideal_clean = os.path.join(d, "ideal-clean.yuv") if spec.get("detail") else None
    print(f"== {test} ==")
    expected, expected_mean = generate(test, spec, src, ideal_clean)
    log = encode(src, mkv, spec)
    with open(os.path.join(d, "encode.log"), "w") as f:
        f.write(log)
    models = parse_log(log)
    on, off = os.path.join(d, "on.yuv"), os.path.join(d, "off.yuv")
    decode(mkv, 1, on)
    decode(mkv, 0, off)
    nframes = spec.get("frames", FRAMES)

    ok = True
    reliable = [m["frame"] for m in models if m["reliable"]]
    if test == "clean":
        sigma, _ = measure(on, off, range(nframes))
        ok &= check("no grain signalled", len(reliable) == 0, f"reliable frames: {reliable[:8]}")
        ok &= check("no grain synthesized", sigma.max() < 0.05 * DS, f"max sigma {sigma.max():.3f}")
    elif test == "cut":
        first, _ = measure(on, off, range(SKIP, CUT_FRAME))
        second, _ = measure(on, off, range(CUT_FRAME + 2, nframes))
        late = [f for f in reliable if f >= CUT_FRAME]
        resets = [m["frame"] for m in models if m["reset"]]
        exp = expected[0].mean()
        got = first[0].mean()
        ok &= check("grain present before cut", 0.6 * exp < got < 1.25 * exp,
                    f"sigmaY {got:.2f} vs injected {exp:.2f}")
        ok &= check("no grain after cut", len(late) == 0 and second.max() < 0.05 * DS,
                    f"late reliable {late[:8]}, max sigma after cut {second.max():.3f}")
        ok &= check("scene reset at cut", any(CUT_FRAME <= f <= CUT_FRAME + 1 for f in resets),
                    f"resets at {resets[:8]}")
    elif test == "dark_luma":
        sigma, _ = measure(on, off, range(SKIP, nframes))
        means = band_means(on, range(SKIP, nframes))
        delta = means - expected_mean
        ratio = sigma[0] / np.maximum(expected[0], 1e-9)
        print(f"  [info] per-band mean delta (10-bit code values): {fmt(delta)}")
        print(f"  [info] per-band synth/observed sigma ratio: {fmt(ratio)}")
        ok &= check("shadow grain strength tracks observed source grain",
                    bool((ratio > 0.6).all() and (ratio < 1.3).all()),
                    f"synth {fmt(sigma[0] / DS)} vs observed {fmt(expected[0] / DS)} (8-bit units)")
        ok &= check("black level preserved under synthesis",
                    bool(np.abs(delta).max() <= 1.5),
                    f"max |mean delta| {np.abs(delta).max():.2f} (10-bit code values, limit 1.5)")
        n_reliable = len([f for f in reliable if f >= SKIP])
        ok &= check("model reliable after warm-up", n_reliable >= nframes - SKIP - 1,
                    f"{n_reliable}/{nframes - SKIP} frames")
    elif test == "cut_grainy":
        expected_post = np.roll(LEVELS, spec.get("cut_roll", 6)) + spec.get("cut_offset", 0)
        off_cut = band_means(off, [CUT_FRAME])
        ghost = np.abs(off_cut - expected_post)
        print(f"  [info] base band deviation on first post-cut frame: {fmt(ghost)}")
        ok &= check("no cross-cut ghost in base layer",
                    bool(ghost.max() <= 12.0 * DS / 4),
                    f"max band deviation {ghost.max():.1f} (10-bit codes; ghosting blends the previous shot's bands)")
        resets = [m["frame"] for m in models if m["reset"]]
        ok &= check("scene reset at grainy cut", any(CUT_FRAME <= f <= CUT_FRAME + 1 for f in resets),
                    f"resets at {resets[:8]}")
        pre, _ = measure(on, off, range(SKIP, CUT_FRAME))
        post, _ = measure(on, off, range(CUT_FRAME + 4, nframes))
        exp = expected[0].mean()
        ok &= check("grain present in both scenes",
                    pre[0].mean() > 0.6 * exp and post[0].mean() > 0.6 * exp,
                    f"pre {pre[0].mean() / DS:.2f}, post {post[0].mean() / DS:.2f} vs injected {exp / DS:.2f} (8-bit units)")
    elif spec.get("retain") == "auto":
        frames = range(SKIP, nframes)
        adaptive = [m for m in models if m["frame"] >= SKIP and m["reliable"]]
        retains = np.array([m["retain"] for m in adaptive])
        risks = np.array([m["risk"] for m in adaptive])
        retain = float(np.median(retains)) if len(retains) else 0.0
        risk = float(np.median(risks)) if len(risks) else 0.0
        synth_target = (1.0 - retain * retain) ** 0.5
        synth_sigma, _ = measure(on, off, frames)
        synth_ratio = synth_sigma[0] / np.maximum(expected[0], 1e-9)
        if spec.get("detail"):
            ok &= check("auto retention detects structured-detail risk",
                        risk >= 0.20 and 0.40 <= retain <= 0.50,
                        f"risk {risk:.3f}, retain {retain:.2f}")
        else:
            retained_sigma = luma_band_sigmas(off, frames)
            retained_ratio = retained_sigma / np.maximum(expected[0], 1e-9)
            ok &= check("auto retention leaves isotropic grain synthetic",
                        risk < 0.03 and retain == 0.0 and retained_ratio.mean() < 0.25,
                        f"risk {risk:.3f}, retain {retain:.2f}, base ratio {retained_ratio.mean():.3f}")
        ok &= check("auto synthesis is variance-compensated",
                    bool((synth_ratio > synth_target * 0.60).all()
                         and (synth_ratio < synth_target * 1.35).all()),
                    f"ratio {fmt(synth_ratio)}, target {synth_target:.2f}")
        ok &= check("auto retention is temporally stable", len(set(retains)) <= 2,
                    f"values {sorted(set(retains))}")
    elif "retain" in spec:
        frames = range(SKIP, nframes)
        retain = float(spec["retain"])
        synth_target = (1.0 - retain * retain) ** 0.5
        synth_sigma, _ = measure(on, off, frames)
        retained_sigma = luma_band_sigmas(off, frames)
        total_sigma = luma_band_sigmas(on, frames)
        expected_y = np.maximum(expected[0], 1e-9)
        retained_ratio = retained_sigma / expected_y
        synth_ratio = synth_sigma[0] / expected_y
        total_ratio = total_sigma / expected_y
        src_raw = os.path.join(d, "src.yuv")
        pix = "yuv420p" if BITS == 8 else "yuv420p10le"
        run(["ffmpeg", "-v", "error", "-y", "-i", src,
             "-pix_fmt", pix, "-f", "rawvideo", src_raw])
        position_corr = retained_grain_corr(src_raw, off, frames)
        ok &= check("retained grain amplitude",
                    bool((retained_ratio > retain * 0.65).all() and (retained_ratio < retain * 1.35).all()),
                    f"ratio {fmt(retained_ratio)}, target {retain:.2f}")
        ok &= check("retained grain keeps source position", position_corr > 0.70,
                    f"mean per-band correlation {position_corr:.3f}")
        ok &= check("synthesized grain is variance-compensated",
                    bool((synth_ratio > synth_target * 0.60).all() and (synth_ratio < synth_target * 1.35).all()),
                    f"ratio {fmt(synth_ratio)}, target {synth_target:.2f}")
        ok &= check("played-out total grain stays matched",
                    bool((total_ratio > 0.70).all() and (total_ratio < 1.35).all()),
                    f"ratio {fmt(total_ratio)}, target 1.00")
        if not keep and os.path.exists(src_raw):
            os.remove(src_raw)
    elif test in ("coarse_luma", "coarse_detail", "coarse_detail_pan",
                  "coarse_detail_move", "coarse_detail_occl"):
        sigma, _ = measure(on, off, range(SKIP, nframes))
        ratio = float(sigma[0].mean() / max(expected[0].mean(), 1e-9))
        adaptive = [m for m in models if m["frame"] >= SKIP and m["reliable"]]
        grain_corr = float(np.median([m["grain_corr"] for m in adaptive])) if adaptive else 0.0
        ok &= check("coarse-grain source correlation",
                    grain_corr >= COARSE_LUMA_MIN_SOURCE_CORRELATION,
                    f"lag-one {grain_corr:.3f} (minimum {COARSE_LUMA_MIN_SOURCE_CORRELATION:.2f})")
        ok &= check("spatially-correlated grain capture ratio (informational, see comment above TESTS)",
                    ratio >= COARSE_LUMA_MIN_CAPTURE_RATIO,
                    f"captured {ratio * 100:.0f}% of injected coarse-grain sigma "
                    f"(synth {sigma[0].mean() / DS:.2f} vs injected {expected[0].mean() / DS:.2f}, 8-bit units)")
        n_reliable = len([f for f in reliable if f >= SKIP])
        ok &= check("model reliable after warm-up", n_reliable >= nframes - SKIP - 1,
                    f"{n_reliable}/{nframes - SKIP} frames")
    else:
        sigma, corr = measure(on, off, range(SKIP, nframes))
        ratio = sigma[0] / np.maximum(expected[0], 1e-9)
        if test == "const_luma":
            adaptive = [m for m in models if m["frame"] >= SKIP and m["reliable"]]
            grain_corr = float(np.median([m["grain_corr"] for m in adaptive])) if adaptive else 0.0
            ok &= check("fine-grain source correlation",
                        abs(grain_corr) <= FINE_LUMA_MAX_SOURCE_CORRELATION,
                        f"lag-one {grain_corr:.3f} "
                        f"(maximum magnitude {FINE_LUMA_MAX_SOURCE_CORRELATION:.2f})")
        ok &= check("luma strength tracks injected grain",
                    bool((ratio > 0.6).all() and (ratio < 1.25).all()),
                    f"synth {fmt(sigma[0] / DS)} vs injected {fmt(expected[0] / DS)} (8-bit units)")
        if spec["sigma_y_mode"] == "ramp":
            r = float(np.corrcoef(sigma[0], expected[0])[0, 1])
            ok &= check("strength curve follows intensity ramp", r > 0.97, f"corr {r:.3f}")
        else:
            spread = sigma[0].max() / max(sigma[0].min(), 1e-9)
            ok &= check("strength curve is flat", spread < 1.35, f"max/min {spread:.2f}")
        for c, plane in ((1, "U"), (2, "V")):
            exp_c = expected[c].mean()
            got_c = sigma[c].mean()
            if exp_c < 0.1 * DS:
                ok &= check(f"{plane} stays clean", got_c < 0.5 * DS, f"sigma {got_c / DS:.2f}")
            else:
                ok &= check(f"{plane} strength matches injected grain",
                            0.6 * exp_c < got_c < 1.4 * exp_c,
                            f"synth {got_c / DS:.2f} vs injected {exp_c / DS:.2f} (8-bit units)")
        if spec.get("corr_c"):
            ok &= check("chroma grain is luma-correlated", corr > 0.5, f"corr {corr:.2f}")
        elif spec.get("sigma_c"):
            ok &= check("chroma grain is independent of luma", abs(corr) < 0.3, f"corr {corr:.2f}")
        n_reliable = len([f for f in reliable if f >= SKIP])
        ok &= check("model reliable after warm-up", n_reliable >= nframes - SKIP - 1,
                    f"{n_reliable}/{nframes - SKIP} frames")
        first_sigma, _ = measure(on, off, [0, 1])
        frame0 = models[0] if models else {"frame": -1, "reliable": 0}
        ok &= check("grain present from first frame",
                    frame0["frame"] == 0 and frame0["reliable"] == 1
                    and first_sigma[0].mean() > 0.5 * expected[0].mean(),
                    f"frame0 reliable={frame0['reliable']}, sigma {first_sigma[0].mean() / DS:.2f}")
        refreshes = [m["frame"] for m in models if m["reliable"] and not m["held"] and m["frame"] > 0]
        ok &= check("model stable (no twinkle)", len(refreshes) <= 3,
                    f"model refreshed at frames {refreshes[:10]}")
        if test == "warmup_luma":
            ok &= check("full-window model replaces first-frame fit",
                        bool(refreshes) and refreshes[0] <= SKIP,
                        f"first refresh frame {refreshes[0] if refreshes else 'none'} "
                        f"(rolling window completes at frame {SKIP - 1})")
        seed_corr = grain_frame_corr(on, off, range(SKIP, SKIP + 10))
        ok &= check("grain decorrelates frame-to-frame", seed_corr < 0.25,
                    f"mean |corr| between consecutive grain fields {seed_corr:.3f}")
        if spec.get("color"):
            info = probe_color(mkv)
            want = COLOR_EXPECT[spec["color"]]
            match = all(info.get(k) == v for k, v in want.items())
            ok &= check("HDR colorimetry signalled", match and info.get("pix_fmt") == "yuv420p10le",
                        f"got {info}")
    if ideal_clean:
        src_raw = os.path.join(d, "src.yuv")
        pix = "yuv420p" if BITS == 8 else "yuv420p10le"
        run(["ffmpeg", "-v", "error", "-y", "-i", src,
             "-pix_fmt", pix, "-f", "rawvideo", src_raw])
        separation = quality_metrics.separation_metrics(
            src_raw, ideal_clean, off, W, H, BITS, first_frame=SKIP)
        ok &= check("fine detail survives the cleaned base",
                    separation["detail_transfer_gain"] >= 0.25,
                    f"high-pass transfer {separation['detail_transfer_gain']:.3f} (baseline floor 0.25)")
        if test in ("coarse_detail_pan", "coarse_detail_move", "coarse_detail_occl"):
            # Both edge measures are unusable once the picture moves: the
            # systematic one is a temporal mean, so damage that travels with the
            # picture averages out of it, and the plain one is dominated by
            # leftover coarse grain.  Reported, not guarded.
            print(f"  [info] systematic edge RMSE "
                  f"{separation['systematic_edge_bias_rms_8bit']:.2f} "
                  f"(temporal mean; not a guard on moving content)")
            print(f"  [info] plain edge RMSE including leftover grain: "
                  f"{separation['edge_clean_rmse_8bit']:.2f}")
        if test in ("auto_retain_detail", "coarse_detail"):
            # Ordinary edge RMSE includes random grain left in the base, which
            # is not detail damage.  auto_retain_detail retains it deliberately;
            # coarse_detail has it because coarse grain is what the separator
            # struggles to remove.  Either way the plain RMSE measures leftover
            # grain, so temporal mean bias is used instead to isolate repeatable
            # detail damage.  Both numbers are reported so the difference stays
            # visible.
            ok &= check("systematic edge/detail distortion remains bounded",
                        separation["systematic_edge_bias_rms_8bit"] <= 1.5,
                        f"systematic edge RMSE {separation['systematic_edge_bias_rms_8bit']:.2f} "
                        "(8-bit units, limit 1.5)")
            print(f"  [info] plain edge RMSE including leftover grain: "
                  f"{separation['edge_clean_rmse_8bit']:.2f}")
            if test == "auto_retain_detail":
                ok &= check("auto retention restores at-risk fine detail",
                            separation["detail_transfer_gain"] >= 0.65,
                            f"high-pass transfer {separation['detail_transfer_gain']:.3f} (target 0.65)")
        elif test not in ("coarse_detail_pan", "coarse_detail_move",
                          "coarse_detail_occl"):
            # coarse_detail_pan is excluded deliberately: this guard is plain
            # edge RMSE, which coarse grain left in the base dominates, and the
            # fixture reports it as information above instead.
            ok &= check("edge/detail distortion remains bounded",
                        separation["edge_clean_rmse_8bit"] <= 3.0,
                        f"edge RMSE {separation['edge_clean_rmse_8bit']:.2f} (8-bit units, limit 3.0)")
        if not keep:
            for path in (src_raw, ideal_clean):
                if os.path.exists(path):
                    os.remove(path)
    if not keep:
        for p in (src, on, off):
            if os.path.exists(p):
                os.remove(p)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default=",".join(TESTS))
    ap.add_argument("--keep", action="store_true", help="keep y4m/yuv intermediates")
    args = ap.parse_args()
    os.makedirs(WORKDIR, exist_ok=True)
    results = {}
    for test in args.tests.split(","):
        results[test] = run_test(test.strip(), args.keep)
    print("\n== summary ==")
    for test, ok in results.items():
        print(f"  {test}: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
