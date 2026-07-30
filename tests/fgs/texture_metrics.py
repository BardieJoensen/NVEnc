"""Amplitude-independent film-grain texture measurements for raw YUV420.

The evaluator deliberately does not reuse NVEnc's production flat-block
classifier.  A monitor sharing the encoder's classifier would share its blind
spots too.  Instead, block selection is frozen from the reference pair:

  * fit and remove a plane from each 32x32 block of the clean guide;
  * rank blocks by clean-guide residual sigma times (1 + coherence);
  * require measurable source-minus-clean residual energy;
  * evaluate both a strict core percentile and a relaxed percentile.

Candidate pixels never affect the mask.  All texture descriptors are calculated
inside source-luma bands before an occupancy-weighted title summary is formed.
Spectra and autocorrelations are normalized per block so grain energy remains a
separate measurement.
"""

import itertools
import math

import numpy as np

import quality_metrics


SCHEMA = "nvenc-fgs-texture/v1"
DEFAULT_BLOCK_SIZE = 32
DEFAULT_SPECTRUM_BINS = 12
DEFAULT_MAX_LAG = 8
DEFAULT_LUMA_BANDS = (0, 32, 64, 96, 128, 160, 192, 224, 256)
DEFAULT_MASK_PERCENTILES = (("core", 25.0), ("expanded", 60.0))
DEFAULT_MIN_REFERENCE_SIGMA_8BIT = 0.5
DEFAULT_MIN_BLOCKS = 32


def _validate_band_edges(edges):
    edges = tuple(int(value) for value in edges)
    if len(edges) < 2 or edges[0] != 0 or edges[-1] != 256:
        raise ValueError("luma band edges must begin at 0 and end at 256")
    if any(right <= left for left, right in zip(edges, edges[1:])):
        raise ValueError("luma band edges must be strictly increasing")
    return edges


def _block_view(image, block_size):
    rows = image.shape[0] // block_size
    columns = image.shape[1] // block_size
    if rows == 0 or columns == 0:
        raise ValueError("image is smaller than one texture block")
    cropped = image[:rows * block_size, :columns * block_size]
    return cropped.reshape(
        rows, block_size, columns, block_size).transpose(0, 2, 1, 3)


def _plane_residuals(image, block_size):
    """Return block means and plane-detrended block pixels."""
    blocks = _block_view(image, block_size).astype(np.float32)
    coordinate = (
        2.0 * np.arange(block_size, dtype=np.float32) - (block_size - 1)
    ) / block_size
    x = coordinate[None, None, None, :]
    y = coordinate[None, None, :, None]
    mean = blocks.mean(axis=(-2, -1))
    norm = float(block_size * np.sum(coordinate * coordinate))
    plane_x = np.sum(blocks * x, axis=(-2, -1)) / max(norm, 1e-12)
    plane_y = np.sum(blocks * y, axis=(-2, -1)) / max(norm, 1e-12)
    residual = (
        blocks - mean[..., None, None]
        - plane_x[..., None, None] * x
        - plane_y[..., None, None] * y
    )
    return mean, residual


def _gradient_coherence(residual):
    gx = (residual[..., 1:-1, 2:] - residual[..., 1:-1, :-2]) * 0.5
    gy = (residual[..., 2:, 1:-1] - residual[..., :-2, 1:-1]) * 0.5
    gxx = np.mean(gx * gx, axis=(-2, -1))
    gxy = np.mean(gx * gy, axis=(-2, -1))
    gyy = np.mean(gy * gy, axis=(-2, -1))
    trace = gxx + gyy
    difference = np.sqrt(np.maximum(
        (gxx - gyy) ** 2 + 4.0 * gxy * gxy, 0.0))
    return np.divide(
        difference, trace, out=np.zeros_like(trace), where=trace > 1e-12)


def flat_block_metrics(source, clean, bits, block_size=DEFAULT_BLOCK_SIZE,
                       min_reference_sigma_8bit=DEFAULT_MIN_REFERENCE_SIGMA_8BIT):
    """Calculate the independent evaluator's reference-only block metrics."""
    scale = float(1 << (bits - 8))
    clean_mean, clean_residual = _plane_residuals(clean, block_size)
    source_blocks = _block_view(source, block_size).astype(np.float32)
    clean_blocks = _block_view(clean, block_size).astype(np.float32)
    reference_texture = source_blocks - clean_blocks
    reference_texture -= reference_texture.mean(axis=(-2, -1), keepdims=True)
    reference_sigma = np.sqrt(np.mean(
        reference_texture * reference_texture, axis=(-2, -1))) / scale
    guide_sigma = np.sqrt(np.mean(
        clean_residual * clean_residual, axis=(-2, -1))) / scale
    coherence = _gradient_coherence(clean_residual)
    structure_score = guide_sigma * (1.0 + coherence)
    mean_8bit = clean_mean / scale
    eligible = (
        np.isfinite(structure_score)
        & np.isfinite(reference_sigma)
        & (reference_sigma >= min_reference_sigma_8bit)
        & (mean_8bit > 0.5)
        & (mean_8bit < 254.5)
    )
    return {
        "structure_score": structure_score,
        "guide_sigma_8bit": guide_sigma,
        "guide_coherence": coherence,
        "reference_sigma_8bit": reference_sigma,
        "mean_8bit": mean_8bit,
        "eligible": eligible,
    }


def _band_indices(means, edges):
    # searchsorted returns len(edges) at exactly 256; keep the last band valid.
    return np.clip(
        np.searchsorted(edges, means, side="right") - 1,
        0, len(edges) - 2).astype(np.int16)


def _percentile_summary(values):
    if not len(values):
        return None
    percentiles = np.percentile(values, (5, 25, 50, 60, 75, 95))
    return {
        "p05": float(percentiles[0]),
        "p25": float(percentiles[1]),
        "p50": float(percentiles[2]),
        "p60": float(percentiles[3]),
        "p75": float(percentiles[4]),
        "p95": float(percentiles[5]),
    }


def build_flat_selection(source, clean, frames, bits,
                         block_size=DEFAULT_BLOCK_SIZE,
                         mask_percentiles=DEFAULT_MASK_PERCENTILES,
                         luma_bands=DEFAULT_LUMA_BANDS,
                         min_reference_sigma_8bit=DEFAULT_MIN_REFERENCE_SIGMA_8BIT):
    """Freeze strict and relaxed masks from the reference source/clean pair."""
    edges = _validate_band_edges(luma_bands)
    records = []
    eligible_scores = []
    occupancy = np.zeros(256, dtype=np.int64)
    scale = float(1 << (bits - 8))
    for frame in frames:
        source_frame = source.luma(frame)
        clean_frame = clean.luma(frame)
        source_codes = np.clip(
            np.rint(source_frame.astype(np.float64) / scale), 0, 255
        ).astype(np.uint8)
        occupancy += np.bincount(source_codes.ravel(), minlength=256)
        metrics = flat_block_metrics(
            source_frame, clean_frame, bits, block_size,
            min_reference_sigma_8bit)
        metrics["band"] = _band_indices(metrics["mean_8bit"], edges)
        records.append(metrics)
        eligible_scores.append(metrics["structure_score"][metrics["eligible"]])
    scores = (
        np.concatenate(eligible_scores)
        if eligible_scores and any(values.size for values in eligible_scores)
        else np.empty(0, dtype=np.float64)
    )
    if not scores.size:
        raise ValueError("reference pair has no eligible texture blocks")

    masks = {}
    for name, percentile in mask_percentiles:
        threshold = float(np.percentile(scores, percentile))
        selected = 0
        per_band = np.zeros(len(edges) - 1, dtype=np.int64)
        for record in records:
            mask = record["eligible"] & (
                record["structure_score"] <= threshold)
            record.setdefault("masks", {})[name] = mask
            selected += int(mask.sum())
            per_band += np.bincount(
                record["band"][mask], minlength=len(edges) - 1)
        masks[name] = {
            "percentile": float(percentile),
            "structure_score_threshold": threshold,
            "selected_blocks": selected,
            "selected_blocks_by_luma_band": per_band.tolist(),
        }

    occupancy_total = int(occupancy.sum())
    occupancy_bands = [
        int(occupancy[left:right].sum())
        for left, right in zip(edges, edges[1:])
    ]
    occupancy_weights = [
        count / occupancy_total if occupancy_total else 0.0
        for count in occupancy_bands
    ]
    return records, {
        "rule": (
            "reference-only 32x32 clean-guide plane residual sigma * "
            "(1 + gradient coherence); measurable source-clean residual; "
            "lowest-score percentile"
        ),
        "candidate_independent": True,
        "block_size": block_size,
        "eligible_blocks": int(scores.size),
        "structure_score_distribution": _percentile_summary(scores),
        "minimum_reference_sigma_8bit": min_reference_sigma_8bit,
        "masks": masks,
        "luma_band_edges": list(edges),
        "source_luma_occupancy": {
            "pixels_by_band": occupancy_bands,
            "weights_by_band": occupancy_weights,
        },
    }


def _spectrum_layout(block_size, bins):
    fy = np.fft.fftfreq(block_size)[:, None]
    fx = np.fft.rfftfreq(block_size)[None, :]
    radius = np.sqrt(fx * fx + fy * fy)
    indices = np.minimum(
        (radius / math.sqrt(0.5) * bins).astype(np.int16), bins - 1)
    window = np.outer(
        np.hanning(block_size), np.hanning(block_size)).astype(np.float32)
    return indices, window


class _BandAccumulator:
    def __init__(self, spectrum_bins, max_lag):
        self.power = np.zeros(spectrum_bins, dtype=np.float64)
        self.acf = np.zeros(max_lag, dtype=np.float64)
        self.anisotropy = 0.0
        self.blocks = 0
        self.sigmas = []
        self.frame_medians = []

    def add(self, patches, scale, layout, window, max_lag, batch_size=512):
        frame_sigmas = []
        for first in range(0, len(patches), batch_size):
            batch = patches[first:first + batch_size].astype(np.float32)
            batch -= batch.mean(axis=(-2, -1), keepdims=True)
            variance = np.mean(batch * batch, axis=(-2, -1))
            valid = variance > 1e-8
            if not np.any(valid):
                continue
            batch = batch[valid]
            variance = variance[valid]
            sigmas = np.sqrt(variance) / scale
            self.sigmas.extend(sigmas.astype(np.float64).tolist())
            frame_sigmas.extend(sigmas.astype(np.float64).tolist())

            transformed = np.fft.rfft2(batch * window, axes=(-2, -1))
            power = transformed.real ** 2 + transformed.imag ** 2
            power[:, 0, 0] = 0.0
            binned = np.stack([
                power[:, layout == index].sum(axis=1)
                for index in range(len(self.power))
            ], axis=1)
            totals = binned.sum(axis=1)
            useful = totals > 1e-12
            if np.any(useful):
                self.power += np.sum(
                    binned[useful] / totals[useful, None], axis=0)

            for lag in range(1, max_lag + 1):
                horizontal = np.mean(
                    batch[:, :, :-lag] * batch[:, :, lag:], axis=(-2, -1))
                vertical = np.mean(
                    batch[:, :-lag, :] * batch[:, lag:, :], axis=(-2, -1))
                self.acf[lag - 1] += float(np.sum(
                    (horizontal + vertical) / (2.0 * variance)))

            coherence = _gradient_coherence(batch)
            self.anisotropy += float(np.sum(coherence))
            self.blocks += len(batch)
        if frame_sigmas:
            self.frame_medians.append(float(np.median(frame_sigmas)))

    def finish(self, minimum_blocks):
        if self.blocks < minimum_blocks:
            return {
                "status": "N/A",
                "reason": (
                    f"{self.blocks} blocks; minimum is {minimum_blocks}"),
                "blocks": self.blocks,
            }
        spectrum_total = float(self.power.sum())
        spectrum = (
            self.power / spectrum_total
            if spectrum_total > 0.0 else np.zeros_like(self.power))
        sigma_percentiles = np.percentile(self.sigmas, (5, 50, 95))
        frame_values = np.asarray(self.frame_medians, dtype=np.float64)
        frame_middle = float(np.median(frame_values)) if len(frame_values) else 0.0
        if frame_middle > 1e-12:
            normalized_frames = frame_values / frame_middle
            temporal = np.percentile(normalized_frames, (5, 50, 95))
        else:
            temporal = np.zeros(3, dtype=np.float64)
        return {
            "status": "OK",
            "blocks": self.blocks,
            "frames_with_blocks": len(self.frame_medians),
            # Diagnostic only. Texture comparisons below do not use amplitude.
            "energy_diagnostic": {
                "sigma_8bit_p05": float(sigma_percentiles[0]),
                "sigma_8bit_p50": float(sigma_percentiles[1]),
                "sigma_8bit_p95": float(sigma_percentiles[2]),
            },
            "normalized_radial_spectrum": spectrum.tolist(),
            "spatial_autocorrelation": (
                self.acf / max(self.blocks, 1)).tolist(),
            "gradient_anisotropy": self.anisotropy / max(self.blocks, 1),
            "temporal_local_energy": {
                "normalized_frame_median_p05": float(temporal[0]),
                "normalized_frame_median_p50": float(temporal[1]),
                "normalized_frame_median_p95": float(temporal[2]),
                "normalized_p95_p05_spread": float(temporal[2] - temporal[0]),
            },
        }


def _describe_texture(read_frame, frame_numbers, selection, scale, band_count,
                      mask_names, block_size, spectrum_bins, max_lag,
                      minimum_blocks):
    accumulators = {
        mask: [_BandAccumulator(spectrum_bins, max_lag)
               for _ in range(band_count)]
        for mask in mask_names
    }
    layout, window = _spectrum_layout(block_size, spectrum_bins)
    for index, frame in enumerate(frame_numbers):
        texture = read_frame(frame)
        blocks = _block_view(texture, block_size)
        record = selection[index]
        for mask_name in mask_names:
            mask = record["masks"][mask_name]
            for band in range(band_count):
                chosen = mask & (record["band"] == band)
                if np.any(chosen):
                    accumulators[mask_name][band].add(
                        blocks[chosen], scale, layout, window, max_lag)
    return {
        mask_name: {
            str(band): accumulator.finish(minimum_blocks)
            for band, accumulator in enumerate(per_band)
        }
        for mask_name, per_band in accumulators.items()
    }


def _weighted_mean(values):
    total_weight = sum(weight for _, weight in values)
    if total_weight <= 0.0:
        return None
    return sum(value * weight for value, weight in values) / total_weight


def compare_descriptor_sets(candidate, reference, occupancy_weights):
    """Compare texture shape only; energy is reported but never scored."""
    masks = {}
    for mask_name in reference:
        band_results = {}
        aggregates = {
            "spectrum_total_variation": [],
            "acf_rmse": [],
            "anisotropy_abs_delta": [],
            "temporal_spread_abs_delta": [],
        }
        valid_weight = 0.0
        for band, weight in enumerate(occupancy_weights):
            key = str(band)
            candidate_band = candidate[mask_name][key]
            reference_band = reference[mask_name][key]
            if (candidate_band.get("status") != "OK"
                    or reference_band.get("status") != "OK"):
                band_results[key] = {
                    "status": "N/A",
                    "candidate_blocks": candidate_band.get("blocks", 0),
                    "reference_blocks": reference_band.get("blocks", 0),
                }
                continue
            candidate_spectrum = np.asarray(
                candidate_band["normalized_radial_spectrum"])
            reference_spectrum = np.asarray(
                reference_band["normalized_radial_spectrum"])
            spectrum_tv = 0.5 * float(np.sum(np.abs(
                candidate_spectrum - reference_spectrum)))
            candidate_acf = np.asarray(
                candidate_band["spatial_autocorrelation"])
            reference_acf = np.asarray(
                reference_band["spatial_autocorrelation"])
            acf_rmse = float(np.sqrt(np.mean(
                (candidate_acf - reference_acf) ** 2)))
            anisotropy_delta = abs(
                candidate_band["gradient_anisotropy"]
                - reference_band["gradient_anisotropy"])
            candidate_temporal = candidate_band[
                "temporal_local_energy"]["normalized_p95_p05_spread"]
            reference_temporal = reference_band[
                "temporal_local_energy"]["normalized_p95_p05_spread"]
            temporal_delta = abs(candidate_temporal - reference_temporal)
            reference_sigma = reference_band[
                "energy_diagnostic"]["sigma_8bit_p50"]
            candidate_sigma = candidate_band[
                "energy_diagnostic"]["sigma_8bit_p50"]
            band_results[key] = {
                "status": "OK",
                "source_luma_occupancy_weight": weight,
                "spectrum_total_variation": spectrum_tv,
                "spectrum_similarity": 1.0 - spectrum_tv,
                "acf_rmse": acf_rmse,
                "acf_lag1_delta": (
                    float(candidate_acf[0] - reference_acf[0])
                    if len(candidate_acf) else None),
                "anisotropy_abs_delta": anisotropy_delta,
                "temporal_spread_abs_delta": temporal_delta,
                "energy_diagnostic_sigma_ratio": (
                    candidate_sigma / reference_sigma
                    if reference_sigma > 1e-12 else None),
            }
            valid_weight += weight
            aggregates["spectrum_total_variation"].append(
                (spectrum_tv, weight))
            aggregates["acf_rmse"].append((acf_rmse, weight))
            aggregates["anisotropy_abs_delta"].append(
                (anisotropy_delta, weight))
            aggregates["temporal_spread_abs_delta"].append(
                (temporal_delta, weight))
        masks[mask_name] = {
            "bands": band_results,
            "occupancy_coverage": valid_weight,
            "occupancy_weighted": {
                name: _weighted_mean(values)
                for name, values in aggregates.items()
            },
        }
    return masks


def comparison_mask_sensitivity(comparison):
    """Expose descriptor movement between the strict and relaxed masks."""
    if "core" not in comparison or "expanded" not in comparison:
        return None
    core = comparison["core"]["occupancy_weighted"]
    expanded = comparison["expanded"]["occupancy_weighted"]
    deltas = {}
    for name in core:
        left, right = core[name], expanded.get(name)
        deltas[name] = (
            abs(right - left)
            if left is not None and right is not None else None)
    return {
        "purpose": "threshold sensitivity diagnostic; no pass/fail bound",
        "core_occupancy_coverage": comparison[
            "core"]["occupancy_coverage"],
        "expanded_occupancy_coverage": comparison[
            "expanded"]["occupancy_coverage"],
        "absolute_delta": deltas,
    }


def analyze_raw_texture(source_path, clean_path, arms, width, height, bits,
                        first_frame=0, frame_count=None,
                        block_size=DEFAULT_BLOCK_SIZE,
                        spectrum_bins=DEFAULT_SPECTRUM_BINS,
                        max_lag=DEFAULT_MAX_LAG,
                        luma_bands=DEFAULT_LUMA_BANDS,
                        mask_percentiles=DEFAULT_MASK_PERCENTILES,
                        min_reference_sigma_8bit=DEFAULT_MIN_REFERENCE_SIGMA_8BIT,
                        minimum_blocks=DEFAULT_MIN_BLOCKS):
    """Build a versioned, per-luma texture report from aligned raw YUV420."""
    source = quality_metrics.LumaReader(source_path, width, height, bits)
    clean = quality_metrics.LumaReader(clean_path, width, height, bits)
    arm_readers = {
        label: (
            quality_metrics.LumaReader(on_path, width, height, bits),
            quality_metrics.LumaReader(off_path, width, height, bits),
        )
        for label, (on_path, off_path) in arms.items()
    }
    available = min(
        [source.frames, clean.frames]
        + [reader.frames for pair in arm_readers.values() for reader in pair])
    stop = (
        min(first_frame + frame_count, available)
        if frame_count is not None else available)
    if first_frame < 0 or first_frame >= stop:
        raise ValueError("no aligned frames available for texture analysis")
    frame_numbers = list(range(first_frame, stop))
    edges = _validate_band_edges(luma_bands)
    mask_names = [name for name, _ in mask_percentiles]
    selection, selection_report = build_flat_selection(
        source, clean, frame_numbers, bits, block_size, mask_percentiles,
        edges, min_reference_sigma_8bit)
    scale = float(1 << (bits - 8))
    band_count = len(edges) - 1

    descriptors = {
        "source_residual": _describe_texture(
            lambda frame: (
                source.luma(frame).astype(np.float32)
                - clean.luma(frame).astype(np.float32)),
            frame_numbers, selection, scale, band_count, mask_names,
            block_size, spectrum_bins, max_lag, minimum_blocks)
    }
    for label, (grain_on, grain_off) in arm_readers.items():
        descriptors[label] = _describe_texture(
            lambda frame, on=grain_on, off=grain_off: (
                on.luma(frame).astype(np.float32)
                - off.luma(frame).astype(np.float32)),
            frame_numbers, selection, scale, band_count, mask_names,
            block_size, spectrum_bins, max_lag, minimum_blocks)

    weights = selection_report[
        "source_luma_occupancy"]["weights_by_band"]
    comparisons = {
        f"{label}_vs_source": compare_descriptor_sets(
            descriptor, descriptors["source_residual"], weights)
        for label, descriptor in descriptors.items()
        if label != "source_residual"
    }
    pairwise = {}
    for left, right in itertools.combinations(arms, 2):
        pairwise[f"{right}_vs_{left}"] = compare_descriptor_sets(
            descriptors[right], descriptors[left], weights)
    mask_sensitivity = {
        "source_comparisons": {
            name: comparison_mask_sensitivity(comparison)
            for name, comparison in comparisons.items()
        },
        "pairwise_arm_comparisons": {
            name: comparison_mask_sensitivity(comparison)
            for name, comparison in pairwise.items()
        },
    }
    return {
        "schema": SCHEMA,
        "geometry": {
            "width": width,
            "height": height,
            "bits": bits,
            "first_frame": first_frame,
            "frames": len(frame_numbers),
        },
        "configuration": {
            "texture_is_amplitude_independent": True,
            "block_size": block_size,
            "spectrum_bins": spectrum_bins,
            "maximum_acf_lag": max_lag,
            "minimum_blocks_per_band": minimum_blocks,
            "luma_band_edges": list(edges),
        },
        "flat_selection": selection_report,
        "descriptors": descriptors,
        "comparisons": comparisons,
        "pairwise_arm_comparisons": pairwise,
        "mask_sensitivity": mask_sensitivity,
    }


def labelled_negative_gate(report, bad_label, good_label,
                           minimum_spectrum_tv=0.01,
                           minimum_acf_rmse=0.01,
                           minimum_occupancy_coverage=0.50):
    """Require a known-different texture pair to separate on every mask.

    This validates detector sensitivity only. It deliberately makes no claim
    that either arm is closer to the source; base fidelity is a separate gate.
    """
    descriptors = report.get("descriptors", {})
    for label in (bad_label, good_label):
        if label not in descriptors:
            raise ValueError(f"texture arm not found: {label}")
    weights = report["flat_selection"][
        "source_luma_occupancy"]["weights_by_band"]
    comparison = compare_descriptor_sets(
        descriptors[bad_label], descriptors[good_label], weights)
    masks = {}
    passed = True
    for mask_name, result in comparison.items():
        aggregate = result["occupancy_weighted"]
        spectrum_tv = aggregate["spectrum_total_variation"]
        acf_rmse = aggregate["acf_rmse"]
        enough_coverage = (
            result["occupancy_coverage"] >= minimum_occupancy_coverage)
        separated = (
            (spectrum_tv is not None and spectrum_tv >= minimum_spectrum_tv)
            or (acf_rmse is not None and acf_rmse >= minimum_acf_rmse)
        )
        mask_passed = enough_coverage and separated
        passed &= mask_passed
        masks[mask_name] = {
            "status": "PASS" if mask_passed else "FAIL",
            "occupancy_coverage": result["occupancy_coverage"],
            "spectrum_total_variation": spectrum_tv,
            "acf_rmse": acf_rmse,
            "separated": separated,
        }
    return {
        "status": "PASS" if passed else "FAIL",
        "purpose": "detector sensitivity, not source-fidelity ranking",
        "known_bad": bad_label,
        "known_good": good_label,
        "thresholds": {
            "minimum_spectrum_total_variation": minimum_spectrum_tv,
            "minimum_acf_rmse": minimum_acf_rmse,
            "minimum_occupancy_coverage": minimum_occupancy_coverage,
            "logic": "coverage AND (spectrum-TV OR ACF-RMSE), on every mask",
        },
        "masks": masks,
    }
