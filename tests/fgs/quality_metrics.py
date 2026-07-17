"""Grain/detail separation and synthesized-grain diagnostics for raw YUV420."""

import math

import numpy as np


SPECTRUM_BINS = 12
SPECTRUM_SIZE = 256


class LumaReader:
    def __init__(self, path, width, height, bits):
        self.width = width
        self.height = height
        self.dtype = np.uint8 if bits == 8 else np.uint16
        self.frame_samples = width * height * 3 // 2
        self.data = np.memmap(path, dtype=self.dtype, mode="r")
        if self.data.size % self.frame_samples:
            raise ValueError(f"raw YUV size is not frame-aligned: {path}")
        self.frames = self.data.size // self.frame_samples

    def luma(self, frame):
        start = frame * self.frame_samples
        return self.data[start:start + self.width * self.height].reshape(
            self.height, self.width)


def highpass(image):
    image = image.astype(np.float64, copy=False)
    result = np.zeros_like(image)
    result[1:-1, 1:-1] = image[1:-1, 1:-1] - (
        image[:-2, 1:-1] + image[2:, 1:-1]
        + image[1:-1, :-2] + image[1:-1, 2:]) * 0.25
    return result


def detail_masks(image, scale):
    image = image.astype(np.float64, copy=False)
    gradient = np.zeros_like(image)
    gradient[:, 1:] += np.abs(image[:, 1:] - image[:, :-1])
    gradient[1:, :] += np.abs(image[1:, :] - image[:-1, :])
    return gradient >= 2.0 * scale, gradient <= 0.25 * scale


def _spectrum_layout(size, bins):
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.rfftfreq(size)[None, :]
    radius = np.sqrt(fx * fx + fy * fy)
    # The maximum corner radius is sqrt(0.5^2 + 0.5^2).  Keep the binning
    # linear so low/mid-frequency correlated grain remains visible.
    indices = np.minimum(
        (radius / math.sqrt(0.5) * bins).astype(np.int32), bins - 1)
    window = np.outer(np.hanning(size), np.hanning(size))
    return indices, window


def radial_spectrum(images, bins=SPECTRUM_BINS, size=SPECTRUM_SIZE):
    """Return a normalized radial power distribution for 2-D arrays."""
    images = list(images)
    if not images:
        return [0.0] * bins
    height, width = images[0].shape
    size = min(size, height, width)
    if size < 8:
        raise ValueError("spectrum images are too small")
    indices, window = _spectrum_layout(size, bins)
    centers = ((0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75))
    power = np.zeros(bins, dtype=np.float64)
    observations = 0
    for image in images:
        for y_fraction, x_fraction in centers:
            top = min(max(int(y_fraction * height - size / 2), 0), height - size)
            left = min(max(int(x_fraction * width - size / 2), 0), width - size)
            block = image[top:top + size, left:left + size].astype(np.float64)
            block = (block - block.mean()) * window
            transformed = np.fft.rfft2(block)
            block_power = transformed.real ** 2 + transformed.imag ** 2
            block_power[0, 0] = 0.0
            power += np.bincount(indices.ravel(), weights=block_power.ravel(),
                                 minlength=bins)[:bins]
            observations += 1
    total = float(power.sum())
    return (power / total).tolist() if observations and total else [0.0] * bins


def spectrum_similarity(candidate, reference):
    if len(candidate) != len(reference):
        raise ValueError("spectrum lengths differ")
    return max(0.0, 1.0 - 0.5 * sum(abs(a - b)
                                    for a, b in zip(candidate, reference)))


def high_frequency_fraction(spectrum):
    return float(sum(spectrum[len(spectrum) // 2:]))


def _frame_correlation(current, previous):
    current = current[::8, ::8].astype(np.float64).ravel()
    previous = previous[::8, ::8].astype(np.float64).ravel()
    current -= current.mean()
    previous -= previous.mean()
    denominator = math.sqrt(float(np.dot(current, current) * np.dot(previous, previous)))
    return abs(float(np.dot(current, previous)) / denominator) if denominator else 0.0


def separation_metrics(source_path, ideal_path, estimated_path,
                       width, height, bits, first_frame=0, max_spectrum_frames=8):
    """Measure known grain extraction and systematic clean-detail damage."""
    source = LumaReader(source_path, width, height, bits)
    ideal = LumaReader(ideal_path, width, height, bits)
    estimated = LumaReader(estimated_path, width, height, bits)
    frame_count = min(source.frames, ideal.frames, estimated.frames)
    if first_frame >= frame_count:
        raise ValueError("no frames available for separation metrics")
    scale = float(1 << (bits - 8))
    count = frame_count - first_frame
    spectrum_step = max(1, math.ceil(count / max_spectrum_frames))

    true_energy = 0.0
    extracted_energy = 0.0
    projection = 0.0
    clean_error_energy = 0.0
    edge_error_energy = 0.0
    edge_samples = 0
    flat_error_energy = 0.0
    flat_samples = 0
    mean_error = np.zeros((height, width), dtype=np.float64)
    mean_detail = np.zeros((height, width), dtype=np.float64)
    edge_weight = np.zeros((height, width), dtype=np.float64)
    flat_weight = np.zeros((height, width), dtype=np.float64)
    true_spectrum_frames = []
    extracted_spectrum_frames = []
    temporal_correlations = []
    previous_extracted = None

    for relative, frame in enumerate(range(first_frame, frame_count)):
        source_frame = source.luma(frame).astype(np.float64)
        ideal_frame = ideal.luma(frame).astype(np.float64)
        estimated_frame = estimated.luma(frame).astype(np.float64)
        true_grain = source_frame - ideal_frame
        extracted = source_frame - estimated_frame
        clean_error = estimated_frame - ideal_frame
        edge, flat = detail_masks(ideal_frame, scale)

        true_energy += float(np.sum(true_grain * true_grain))
        extracted_energy += float(np.sum(extracted * extracted))
        projection += float(np.sum(extracted * true_grain))
        clean_error_energy += float(np.sum(clean_error * clean_error))
        edge_error_energy += float(np.sum(clean_error[edge] ** 2))
        edge_samples += int(edge.sum())
        flat_error_energy += float(np.sum(clean_error[flat] ** 2))
        flat_samples += int(flat.sum())
        mean_error += clean_error
        mean_detail += highpass(ideal_frame)
        edge_weight += edge
        flat_weight += flat
        if relative % spectrum_step == 0:
            true_spectrum_frames.append(true_grain)
            extracted_spectrum_frames.append(extracted)
        if previous_extracted is not None:
            temporal_correlations.append(_frame_correlation(extracted, previous_extracted))
        previous_extracted = extracted

    samples = count * width * height
    mean_error /= count
    mean_detail /= count
    edge_weight /= count
    flat_weight /= count
    detail_denominator = float(np.sum(mean_detail * mean_detail))
    detail_error = highpass(mean_error)
    detail_loss = (-float(np.sum(detail_error * mean_detail)) / detail_denominator
                   if detail_denominator else 0.0)
    true_spectrum = radial_spectrum(true_spectrum_frames)
    extracted_spectrum = radial_spectrum(extracted_spectrum_frames)
    return {
        "frames": count,
        "true_grain_sigma_8bit": math.sqrt(true_energy / samples) / scale,
        "extracted_sigma_8bit": math.sqrt(extracted_energy / samples) / scale,
        "same_position_gain": projection / true_energy if true_energy else None,
        "clean_rmse_8bit": math.sqrt(clean_error_energy / samples) / scale,
        "edge_clean_rmse_8bit": (math.sqrt(edge_error_energy / edge_samples) / scale
                                  if edge_samples else None),
        "flat_clean_rmse_8bit": (math.sqrt(flat_error_energy / flat_samples) / scale
                                  if flat_samples else None),
        "systematic_clean_bias_rms_8bit": float(np.sqrt(np.mean(mean_error ** 2))) / scale,
        "systematic_edge_bias_rms_8bit": (
            math.sqrt(float(np.sum(mean_error ** 2 * edge_weight))
                      / max(float(edge_weight.sum()), 1.0)) / scale),
        "systematic_flat_bias_rms_8bit": (
            math.sqrt(float(np.sum(mean_error ** 2 * flat_weight))
                      / max(float(flat_weight.sum()), 1.0)) / scale),
        "detail_loss_projection": detail_loss,
        "detail_transfer_gain": 1.0 - detail_loss,
        "extracted_temporal_correlation": (
            float(np.mean(temporal_correlations)) if temporal_correlations else 0.0),
        "true_spectrum": true_spectrum,
        "extracted_spectrum": extracted_spectrum,
        "extracted_spectrum_similarity": spectrum_similarity(
            extracted_spectrum, true_spectrum),
        "true_high_frequency_fraction": high_frequency_fraction(true_spectrum),
        "extracted_high_frequency_fraction": high_frequency_fraction(extracted_spectrum),
    }


def grain_metrics(grain_on_path, grain_off_path, width, height, bits,
                  first_frame=0, max_spectrum_frames=8):
    """Measure decoder-synthesized grain independent of the encoded base."""
    grain_on = LumaReader(grain_on_path, width, height, bits)
    grain_off = LumaReader(grain_off_path, width, height, bits)
    frame_count = min(grain_on.frames, grain_off.frames)
    if first_frame >= frame_count:
        raise ValueError("no frames available for grain metrics")
    scale = float(1 << (bits - 8))
    count = frame_count - first_frame
    spectrum_step = max(1, math.ceil(count / max_spectrum_frames))
    energy = 0.0
    spectrum_frames = []
    temporal_correlations = []
    previous = None
    for relative, frame in enumerate(range(first_frame, frame_count)):
        grain = (grain_on.luma(frame).astype(np.float64)
                 - grain_off.luma(frame).astype(np.float64))
        energy += float(np.sum(grain * grain))
        if relative % spectrum_step == 0:
            spectrum_frames.append(grain)
        if previous is not None:
            temporal_correlations.append(_frame_correlation(grain, previous))
        previous = grain
    spectrum = radial_spectrum(spectrum_frames)
    return {
        "sigma_8bit": math.sqrt(energy / (count * width * height)) / scale,
        "temporal_correlation": (
            float(np.mean(temporal_correlations)) if temporal_correlations else 0.0),
        "spectrum": spectrum,
        "high_frequency_fraction": high_frequency_fraction(spectrum),
    }
