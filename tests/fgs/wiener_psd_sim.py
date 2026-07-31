#!/usr/bin/env python3
"""Does a per-bin noise PSD beat a scalar sigma for coarse (correlated) grain?

Reproduces FFT3D's frequency-domain Wiener rule from
NVEncFilterDenoiseFFT3D.cuh:366 --

    factor = max(limit, (power - sigma) / power)

-- on overlapped Hann-windowed blocks, and compares:

  A. scalar sigma   (what NVEnc does today: assumes a flat/white noise PSD)
  B. per-bin sigma  (what libaom's aom_wiener_denoise_2d does: noise_psd[])

The grain is the KAT's `coarse_luma` generator: Gaussian noise blurred with a
Gaussian kernel, i.e. energy concentrated at low/mid frequencies.  Under A the
filter subtracts the same noise power at every frequency, so it under-removes
where the grain actually lives and over-removes where the detail lives.

Reported:
  capture  = std(source - denoised) / std(injected grain)   -> want ~1
  detail   = high-pass transfer of the clean signal through the base -> want ~1
"""
import numpy as np

rng = np.random.default_rng(7)
H, W = 512, 512
BLOCK = 32
LIMIT = 0.10          # FFT3D `limit`
GRAIN_SIGMA = 6.0     # 8-bit code values, matches coarse_luma spec


def correlated_unit_noise(rng, shape, blur_sigma_px=1.2, radius=3):
    """Verbatim from tests/fgs/fgs_kat.py."""
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


def noise_psd_shape(block, blur_sigma_px=1.2, radius=3):
    """Normalised per-bin noise PSD for the same correlated process.

    This is the quantity libaom passes as noise_psd[]. Normalised to mean 1 so
    that total noise power is unchanged and blur_sigma_px -> 0 (white noise)
    reduces exactly to the scalar case.
    """
    ax = np.arange(-radius, radius + 1)
    k1 = np.exp(-(ax ** 2) / (2.0 * blur_sigma_px ** 2))
    k1 /= k1.sum()
    kernel2d = np.outer(k1, k1)
    kpad = np.zeros((block, block))
    kh, kw = kernel2d.shape
    kpad[:kh, :kw] = kernel2d
    kpad = np.roll(kpad, (-radius, -radius), axis=(0, 1))
    psd = np.abs(np.fft.fft2(kpad)) ** 2
    return psd / psd.mean()


def ar1_psd_shape(block, rho):
    """PSD from a lag-one correlation only -- what NVEnc already measures as
    FilmGrainBlockMetric::spatialCorrelation.  Separable AR(1) in x and y."""
    w = 2.0 * np.pi * np.fft.fftfreq(block)
    s1 = (1.0 - rho ** 2) / (1.0 - 2.0 * rho * np.cos(w) + rho ** 2)
    psd = np.outer(s1, s1)
    return psd / psd.mean()


def build_scene():
    """Banded intensity ramp plus static fine detail, like the KAT fixtures."""
    clean = np.zeros((H, W))
    for i in range(12):
        clean[:, i * (W // 12):(i + 1) * (W // 12)] = 20 + i * 18
    yy, xx = np.mgrid[0:H, 0:W]
    clean += 6.0 * np.sin(2 * np.pi * xx / 9.0) * (yy > H // 2)
    return clean


def wiener_denoise(image, sigma_power, psd_shape=None):
    """Overlapped Hann-windowed block Wiener, FFT3D's rule."""
    step = BLOCK // 2
    win1 = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(BLOCK) / BLOCK)
    win = np.outer(win1, win1)
    acc = np.zeros((H + BLOCK, W + BLOCK))
    wacc = np.zeros((H + BLOCK, W + BLOCK))
    pad = np.pad(image, ((0, BLOCK), (0, BLOCK)), mode="reflect")
    shape = psd_shape if psd_shape is not None else 1.0
    for y in range(0, H, step):
        for x in range(0, W, step):
            blk = pad[y:y + BLOCK, x:x + BLOCK] * win
            spec = np.fft.fft2(blk)
            power = np.abs(spec) ** 2
            factor = np.maximum(LIMIT, (power - sigma_power * shape) / (power + 1e-15))
            out = np.real(np.fft.ifft2(spec * factor))
            acc[y:y + BLOCK, x:x + BLOCK] += out * win
            wacc[y:y + BLOCK, x:x + BLOCK] += win * win
    return (acc / np.maximum(wacc, 1e-9))[:H, :W]


def highpass(a):
    return a - 0.25 * (np.roll(a, 1, 0) + np.roll(a, -1, 0)
                       + np.roll(a, 1, 1) + np.roll(a, -1, 1))


clean = build_scene()
grain = correlated_unit_noise(rng, (H, W)) * GRAIN_SIGMA
source = clean + grain
interior = (slice(BLOCK, H - BLOCK), slice(BLOCK, W - BLOCK))
clean_hp_energy = np.std(highpass(clean)[interior])

# FFT3D scales sigma into a power threshold against windowed block spectra;
# calibrate it once on the scalar arm so both arms remove the same total power.
base = (GRAIN_SIGMA ** 2) * (BLOCK ** 2) * 0.25

print(f"injected grain sigma {GRAIN_SIGMA:.2f}, "
      f"lag-one ACF {np.corrcoef(grain[:, :-1].ravel(), grain[:, 1:].ravel())[0,1]:.3f}\n")

shapes = {
    "A  scalar sigma (today)": None,
    "B  exact noise PSD (libaom-style)": noise_psd_shape(BLOCK),
    "C  AR(1) PSD from lag-one only": None,   # filled below
}
rho = float(np.corrcoef(grain[:, :-1].ravel(), grain[:, 1:].ravel())[0, 1])
shapes["C  AR(1) PSD from lag-one only"] = ar1_psd_shape(BLOCK, rho)

print(f"{'arm':<36} {'capture':>9} {'detail':>9}")
for name, shape in shapes.items():
    den = wiener_denoise(source, base, shape)
    residual = source - den
    capture = np.std(residual[interior]) / np.std(grain[interior])
    detail = np.std(highpass(den)[interior]) / clean_hp_energy
    print(f"{name:<36} {capture:>9.3f} {detail:>9.3f}")

print("\ncapture = residual sigma / injected sigma (denoiser's share of the "
      "coarse-grain\n          capture ratio the KAT guards at 0.30)")
print("detail  = high-pass energy of the base / high-pass energy of the clean "
      "signal\n          (>1 means leftover grain is being counted as detail)")
