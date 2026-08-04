#!/usr/bin/env python3
"""Report evidence needed before a source-fitted grain model is admitted.

Source fitting answers a deliberately narrow question: what spatial texture is
present in source-selected flat blocks?  It does not answer whether that texture
is photochemical/digital camera grain rather than codec residue, line art, or
moving graphics.  This report keeps the three decisions separate for every AOM
film-grain-table entry:

* ``model_fidelity`` compares the signalled AV1 model with source temporal
  texture after static-picture cancellation;
* ``film_like_evidence`` reports signal energy, frame-to-frame persistence,
  isotropy and stability without reducing them to an unvalidated score; and
* ``coverage`` reports exactly how many frame pairs and blocks support either.

Fixed luma bands are mandatory.  A whole-title mean previously hid opposite
errors in dark and bright film, so sparse bands are reported as insufficient
rather than silently pooled into populated ones.  This script is an admission
*measurement*, not a production router: it emits no pass/fail threshold.

Example:
  python3 tests/fgs/sourcefit_admission_report.py \
      --source clip.mkv --table bilateral-source.tbl \
      --json-out admission.json
"""

import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ar_acf  # noqa: E402
import filmgrn  # noqa: E402
import model_gate  # noqa: E402
from source_fit import (  # noqa: E402
    blockwise, detrend_blocks, production_flat_blocks, select_flat,
    static_flat_blocks,
)
from strength_selection_report import probe_size  # noqa: E402

FFMPEG = os.environ.get("FGS_FFMPEG", "/usr/local/bin/ffmpeg")
FFPROBE = os.environ.get("FGS_FFPROBE", "/usr/local/bin/ffprobe")
TABLE_TICKS_PER_SECOND = 10_000_000.0


def frame_times(path):
    """Return display-order packet times, normalised to the first packet."""
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_packets", "-show_entries", "packet=pts_time", "-of", "json",
         path], check=True, capture_output=True, text=True)
    packets = json.loads(result.stdout).get("packets", [])
    times = sorted({float(packet["pts_time"]) for packet in packets
                    if packet.get("pts_time") is not None})
    if len(times) < 2:
        raise RuntimeError(f"{path}: fewer than two unique video timestamps")
    origin = times[0]
    return [value - origin for value in times]


def evenly_spaced(values, count):
    if count <= 0 or not values:
        return []
    if len(values) <= count:
        return list(values)
    positions = np.linspace(0, len(values) - 1, count)
    return list(dict.fromkeys(values[int(round(position))]
                              for position in positions))


def entry_frame_pairs(entry, times, count):
    """Choose adjacent display-frame pairs wholly inside one table interval."""
    start = entry["start"] / TABLE_TICKS_PER_SECOND
    end = entry["end"] / TABLE_TICKS_PER_SECOND
    candidates = [
        index for index in range(len(times) - 1)
        if times[index] + 1e-9 >= start and times[index + 1] < end - 1e-9
    ]
    return evenly_spaced(candidates, count) if count else candidates


def decode_pair_stream(path, width, height, indices, bits):
    """Decode selected adjacent pairs while retaining only two full frames.

    A 600-frame 1080p 10-bit clip is over 2 GiB as luma arrays.  Admission
    needs broad temporal coverage, so a streaming reader is safer than making
    the sampling rule depend on available RAM.
    """
    wanted = set(indices)
    if not wanted:
        return
    last = max(wanted) + 1
    pix_fmt = "gray" if bits == 8 else f"gray{bits}le"
    command = [
        FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-i", path,
        "-map", "0:v:0", "-vf", "extractplanes=y", "-fps_mode", "passthrough",
        "-frames:v", str(last + 1), "-pix_fmt", pix_fmt, "-f", "rawvideo", "-",
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dtype = np.uint8 if bits == 8 else np.dtype("<u2")
    frame_bytes = width * height * np.dtype(dtype).itemsize
    previous = None
    try:
        for frame in range(last + 1):
            raw = process.stdout.read(frame_bytes)
            if len(raw) != frame_bytes:
                error = process.stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"{path}: decoded {frame} frames, expected {last + 1}: {error}")
            current = np.frombuffer(raw, dtype).reshape(height, width)
            if frame - 1 in wanted:
                yield frame - 1, previous, current
            previous = current
    except BaseException:
        if process.stdout:
            process.stdout.close()
        if process.poll() is None:
            process.terminate()
        process.wait()
        if process.stderr:
            process.stderr.close()
        raise
    if process.stdout:
        process.stdout.close()
    error = process.stderr.read().decode("utf-8", errors="replace")
    returncode = process.wait()
    if returncode:
        raise RuntimeError(f"FFmpeg exited {returncode}: {error}")


def selected_patches(frame, nextframe, blocks, bits, luma_bins):
    """Return temporal patches and semantic-evidence diagnostics."""
    grid_a = blockwise(np.asarray(frame, dtype=np.float64))
    grid_b = blockwise(np.asarray(nextframe, dtype=np.float64))
    maximum = float((1 << bits) - 1)
    scale_8bit = float(1 << max(bits - 8, 0))
    patches = []
    bands = []
    correlations = []
    sigmas = []
    variance_ratios = []
    for row, col in blocks:
        raw_a = grid_a[row, col]
        raw_b = grid_b[row, col]
        a = detrend_blocks(raw_a[None, None])[0, 0]
        b = detrend_blocks(raw_b[None, None])[0, 0]
        temporal = (a - b) / math.sqrt(2.0)
        patches.append(temporal)
        mean_luma = float(raw_a.mean()) / maximum
        bands.append(min(luma_bins - 1, max(0, int(mean_luma * luma_bins))))
        variance_a = float(np.mean(a * a))
        variance_b = float(np.mean(b * b))
        temporal_variance = float(np.mean(temporal * temporal))
        denominator = math.sqrt(max(variance_a * variance_b, 0.0))
        correlations.append(
            float(np.mean(a * b)) / denominator if denominator > 1e-12 else 0.0)
        sigmas.append(math.sqrt(max(temporal_variance, 0.0)) / scale_8bit)
        spatial_variance = 0.5 * (variance_a + variance_b)
        variance_ratios.append(
            temporal_variance / spatial_variance if spatial_variance > 1e-12 else 0.0)
    return {
        "patches": np.asarray(patches),
        "bands": np.asarray(bands, dtype=np.int16),
        "cross_frame_correlations": correlations,
        "sigma_8bit": sigmas,
        "temporal_spatial_variance_ratio": variance_ratios,
    }


def model_patches(entry, count, seed, sigma, bits):
    """Synthesize exact quantised/Round2 AR texture as square 32x32 patches."""
    lag = entry["params"]["ar_coeff_lag"]
    shift = entry["params"]["ar_coeff_shift"]
    coeffs = entry["ar_coeffs"]["y"]
    patches = []
    for offset in range(count):
        rng = np.random.default_rng(seed + offset)
        field, _clipped = ar_acf.generate_field(
            coeffs, lag, shift, rng, model_gate.BLOCK + lag,
            model_gate.BLOCK + 2 * lag, sigma, bits)
        patches.append(field)
    return np.asarray(patches)


def mean_sd(values):
    if not values:
        return {"mean": None, "sd": None}
    return {"mean": float(np.mean(values)), "sd": float(np.std(values))}


STOCHASTIC_FEATURES = (
    "excess_kurtosis",
    "absolute_to_rms",
    "absolute_skewness",
    "quadrant_energy_cv",
    "grid4_gradient_ratio",
    "grid8_gradient_ratio",
    "grid16_gradient_ratio",
)


def _grid_gradient_ratio(patches, period):
    """Boundary/non-boundary gradient energy for aligned codec grids."""
    horizontal = np.diff(patches, axis=2) ** 2
    vertical = np.diff(patches, axis=1) ** 2
    positions = np.arange(patches.shape[1] - 1)
    boundary = (positions + 1) % period == 0
    interior = ~boundary
    boundary_energy = 0.5 * (
        horizontal[:, :, boundary].mean(axis=(1, 2))
        + vertical[:, boundary, :].mean(axis=(1, 2)))
    interior_energy = 0.5 * (
        horizontal[:, :, interior].mean(axis=(1, 2))
        + vertical[:, interior, :].mean(axis=(1, 2)))
    return boundary_energy / np.maximum(interior_energy, 1e-12)


def stochastic_patch_summary(patches):
    """Amplitude-normalized distribution and codec-grid evidence per patch.

    Each descriptor is computed per 32x32 patch before aggregation. This keeps
    one high-energy patch from dominating the title and makes every shape
    statistic invariant to bit depth and grain amplitude. ``patch_rms`` is
    retained separately so a later report can test energy without smuggling it
    into the normalized descriptors.
    """
    patches = np.asarray(patches, dtype=np.float64)
    if patches.ndim != 3 or patches.shape[1:] != (model_gate.BLOCK,
                                                   model_gate.BLOCK):
        raise ValueError("stochastic patches must have shape (n, 32, 32)")
    if not len(patches):
        return None
    energy = np.mean(patches * patches, axis=(1, 2))
    usable = energy > 1e-12
    if not np.any(usable):
        return None
    patches = patches[usable]
    rms = np.sqrt(energy[usable])
    normalized = patches / rms[:, None, None]
    excess_kurtosis = np.mean(normalized ** 4, axis=(1, 2)) - 3.0
    absolute_to_rms = np.mean(np.abs(normalized), axis=(1, 2))
    absolute_skewness = np.abs(np.mean(normalized ** 3, axis=(1, 2)))
    half = model_gate.BLOCK // 2
    quadrant_energy = np.stack([
        np.mean(normalized[:, :half, :half] ** 2, axis=(1, 2)),
        np.mean(normalized[:, :half, half:] ** 2, axis=(1, 2)),
        np.mean(normalized[:, half:, :half] ** 2, axis=(1, 2)),
        np.mean(normalized[:, half:, half:] ** 2, axis=(1, 2)),
    ], axis=1)
    quadrant_energy_cv = (
        np.std(quadrant_energy, axis=1)
        / np.maximum(np.mean(quadrant_energy, axis=1), 1e-12))
    values = {
        "excess_kurtosis": excess_kurtosis,
        "absolute_to_rms": absolute_to_rms,
        "absolute_skewness": absolute_skewness,
        "quadrant_energy_cv": quadrant_energy_cv,
        "grid4_gradient_ratio": _grid_gradient_ratio(normalized, 4),
        "grid8_gradient_ratio": _grid_gradient_ratio(normalized, 8),
        "grid16_gradient_ratio": _grid_gradient_ratio(normalized, 16),
    }
    return {
        "blocks": int(len(normalized)),
        "patch_rms": mean_sd(rms.tolist()),
        "patch_rms_cv": float(np.std(rms) / max(np.mean(rms), 1e-12)),
        **{key: mean_sd(value.tolist()) for key, value in values.items()},
    }


def combine_stochastic(summaries):
    """Pool stochastic summaries exactly from count, mean and population SD."""
    summaries = [summary for summary in summaries if summary]
    blocks = sum(summary["blocks"] for summary in summaries)
    if not blocks:
        return None

    def combine_field(field):
        total = 0.0
        square = 0.0
        count = 0
        for summary in summaries:
            stats = summary[field]
            if stats["mean"] is None:
                continue
            n = summary["blocks"]
            total += stats["mean"] * n
            square += (stats["sd"] ** 2 + stats["mean"] ** 2) * n
            count += n
        if not count:
            return {"mean": None, "sd": None}
        mean = total / count
        variance = max(0.0, square / count - mean * mean)
        return {"mean": mean, "sd": math.sqrt(variance)}

    rms = combine_field("patch_rms")
    return {
        "blocks": blocks,
        "patch_rms": rms,
        "patch_rms_cv": (
            None if rms["mean"] in (None, 0.0)
            else rms["sd"] / rms["mean"]),
        **{field: combine_field(field) for field in STOCHASTIC_FEATURES},
    }


def patch_sample(patches, count):
    """Deterministic, order-preserving cap for descriptor-only patches."""
    if len(patches) <= count:
        return patches
    indices = evenly_spaced(list(range(len(patches))), count)
    return patches[indices]


def evidence_summary(records):
    return {
        "purpose": "diagnostic evidence only; no routing threshold is validated",
        "temporal_sigma_8bit": mean_sd([
            value for record in records for value in record["sigma_8bit"]]),
        "cross_frame_correlation": mean_sd([
            value for record in records
            for value in record["cross_frame_correlations"]]),
        "temporal_spatial_variance_ratio": mean_sd([
            value for record in records
            for value in record["temporal_spatial_variance_ratio"]]),
    }


def descriptor_summary(patches, model_descriptor):
    source = model_gate.describe(patches)
    return {
        "source_temporal": source,
        "signalled_model": model_descriptor,
        "distance": model_gate.distances(model_descriptor, source),
    }


def aggregate_entries(rows, luma_bins):
    """Block-weighted title diagnostic without manufacturing a verdict."""
    measured = [row for row in rows if row["status"] == "OK"]
    coverage = {
        "table_entries": len(rows),
        "measured_entries": len(measured),
        "insufficient_entries": len(rows) - len(measured),
        "requested_pairs": sum(
            row["coverage"]["requested_pairs"] for row in rows),
        "usable_pairs": sum(
            row["coverage"]["usable_pairs"] for row in rows),
        "static_blocks": sum(
            row["coverage"]["static_blocks"] for row in measured),
    }
    total_weight = coverage["static_blocks"]
    if not measured or total_weight <= 0:
        return {
            "coverage": coverage,
            "model_fidelity": None,
            "film_like_evidence": None,
            "luma_bands": {},
            "routing_verdict": None,
        }

    def weighted(extract):
        return float(sum(
            extract(row) * row["coverage"]["static_blocks"]
            for row in measured) / total_weight)

    source_lag1 = weighted(
        lambda row: row["model_fidelity"]["source_temporal"]["acf"][0])
    source_lag2 = weighted(
        lambda row: row["model_fidelity"]["source_temporal"]["acf"][1])
    model_lag1 = weighted(
        lambda row: row["model_fidelity"]["signalled_model"]["acf"][0])
    model_lag2 = weighted(
        lambda row: row["model_fidelity"]["signalled_model"]["acf"][1])
    stochastic = combine_stochastic([
        row["film_like_evidence"].get("stochastic") for row in measured])
    return {
        "coverage": coverage,
        "model_fidelity": {
            "source_temporal_lag1": source_lag1,
            "source_temporal_lag2": source_lag2,
            "signalled_model_lag1": model_lag1,
            "signalled_model_lag2": model_lag2,
            "lag1_delta": model_lag1 - source_lag1,
            "lag2_delta": model_lag2 - source_lag2,
            "acf_rmse": weighted(
                lambda row: row["model_fidelity"]["distance"]["gated"]["acf_rmse"]),
            "spectrum_total_variation": weighted(
                lambda row: row["model_fidelity"]["distance"]["gated"]["spectrum_tv"]),
            "anisotropy_abs": weighted(
                lambda row: row["model_fidelity"]["distance"]["held_out"]["anisotropy_abs"]),
            "diagonal_acf_lag1_abs": weighted(
                lambda row: row["model_fidelity"]["distance"]["held_out"][
                    "diagonal_acf_lag1_abs"]),
        },
        "film_like_evidence": {
            "purpose": "diagnostic evidence only; no routing threshold is validated",
            "temporal_sigma_8bit": weighted(
                lambda row: row["film_like_evidence"]["temporal_sigma_8bit"]["mean"]),
            "cross_frame_correlation": weighted(
                lambda row: row["film_like_evidence"]["cross_frame_correlation"]["mean"]),
            "source_gradient_anisotropy": weighted(
                lambda row: row["film_like_evidence"]["gradient_anisotropy"]),
            "stochastic": stochastic,
        },
        "luma_bands": {
            str(band): {
                "entries_with_descriptor_coverage": sum(
                    row["luma_bands"][str(band)]["status"] == "OK"
                    for row in measured),
                "measured_entries": len(measured),
                "stochastic": combine_stochastic([
                    row["luma_bands"][str(band)].get(
                        "film_like_evidence", {}).get("stochastic")
                    for row in measured
                    if row["luma_bands"][str(band)]["status"] == "OK"
                ]),
            }
            for band in range(luma_bins)
        },
        "routing_verdict": None,
    }


def measure_pair(frame, source, next_source, bits, flat_selector,
                 flat_fraction, static_lo, static_hi,
                 minimum_pair_blocks, luma_bins, texture_blocks_per_pair,
                 texture_blocks_per_pair_band):
    # Decoder storage is unsigned.  Consecutive-frame differences legitimately
    # cross zero; convert before static_flat_blocks subtracts or negative deltas
    # wrap to ~65535 and every valid block disappears.
    source = np.asarray(source, dtype=np.float64)
    next_source = np.asarray(next_source, dtype=np.float64)
    if flat_selector == "production":
        candidates, _score, _sigma = production_flat_blocks(source, bits)
    else:
        candidates, _score, _sigma = select_flat(
            source, bits, flat_fraction)
    static = static_flat_blocks(
        source, next_source, candidates, lo=static_lo, hi=static_hi)
    record = {
        "frame": frame,
        "candidate_blocks": len(candidates),
        "static_blocks": len(static),
        "usable": len(static) >= minimum_pair_blocks,
    }
    if record["usable"]:
        selected = selected_patches(
            source, next_source, static, bits, luma_bins)
        # Coverage and energy diagnostics retain every block.  FFT/ACF texture
        # descriptors need a representative sample, not gigabytes of duplicate
        # 32x32 arrays.  Keep an unbiased pair-level sample plus a separate
        # fixed sample for every luma band so sparse bands stay visible.
        record.update({key: selected[key] for key in (
            "cross_frame_correlations", "sigma_8bit",
            "temporal_spatial_variance_ratio")})
        record["patches"] = patch_sample(
            selected["patches"], texture_blocks_per_pair)
        record["stochastic_evidence"] = stochastic_patch_summary(
            selected["patches"])
        record["band_patches"] = {
            str(band): patch_sample(
                selected["patches"][selected["bands"] == band],
                texture_blocks_per_pair_band)
            for band in range(luma_bins)
        }
        record["band_stochastic_evidence"] = {
            str(band): stochastic_patch_summary(
                selected["patches"][selected["bands"] == band])
            for band in range(luma_bins)
        }
    return record


def analyse_entry(entry, pairs, pair_records, minimum_band_blocks, luma_bins,
                  model_patch_count, model_seed, model_sigma, bits):
    all_patches = [record["patches"] for record in pair_records
                   if record["usable"]]
    usable = [record for record in pair_records if record["usable"]]
    coverage = {
        "requested_pairs": len(pairs),
        "usable_pairs": len(usable),
        "static_blocks": sum(record["static_blocks"] for record in usable),
        "pairs": [{key: record[key] for key in (
            "frame", "candidate_blocks", "static_blocks", "usable")}
                  for record in pair_records],
    }
    if not all_patches:
        return {
            "status": "INSUFFICIENT_COVERAGE",
            "coverage": coverage,
            "model_fidelity": None,
            "film_like_evidence": None,
            "luma_bands": {},
        }

    patches = np.concatenate(all_patches)
    model = model_gate.describe(model_patches(
        entry, model_patch_count, model_seed, model_sigma, bits))
    pair_lag1 = [model_gate.describe(record_patches)["acf"][0]
                 for record_patches in all_patches]
    film_evidence = evidence_summary(usable)
    film_evidence["temporal_lag1_pair_stability"] = mean_sd(pair_lag1)
    film_evidence["gradient_anisotropy"] = model_gate.describe(
        patches)["anisotropy"]
    film_evidence["stochastic"] = combine_stochastic([
        record.get("stochastic_evidence") for record in usable])

    band_results = {}
    for band in range(luma_bins):
        per_pair = [record["band_patches"][str(band)]
                    for record in usable
                    if len(record["band_patches"][str(band)])]
        selected = (np.concatenate(per_pair) if per_pair
                    else np.empty((0, model_gate.BLOCK, model_gate.BLOCK)))
        key = str(band)
        if len(selected) < minimum_band_blocks:
            band_results[key] = {
                "status": "INSUFFICIENT_COVERAGE",
                "blocks": int(len(selected)),
            }
        else:
            band_results[key] = {
                "status": "OK",
                "blocks": int(len(selected)),
                "model_fidelity": descriptor_summary(selected, model),
                "film_like_evidence": {
                    "stochastic": combine_stochastic([
                        record["band_stochastic_evidence"][key]
                        for record in usable
                    ]),
                },
            }

    return {
        "status": "OK",
        "coverage": coverage,
        "model_fidelity": descriptor_summary(patches, model),
        "film_like_evidence": film_evidence,
        "luma_bands": band_results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--bits", type=int, default=10)
    parser.add_argument(
        "--pairs-per-entry", type=int, default=0,
        help="maximum evenly-spaced pairs per table entry; 0 scans every pair")
    parser.add_argument("--flat-selector", choices=("production", "top10"),
                        default="production")
    parser.add_argument("--flat-fraction", type=float, default=0.10)
    parser.add_argument("--static-lo", type=float, default=0.8)
    parser.add_argument("--static-hi", type=float, default=1.3)
    parser.add_argument("--minimum-pair-blocks", type=int, default=8)
    parser.add_argument("--minimum-band-blocks", type=int, default=16)
    parser.add_argument("--luma-bins", type=int, default=8)
    parser.add_argument(
        "--texture-blocks-per-pair", type=int, default=16,
        help="pair-balanced patch cap for whole-entry texture descriptors")
    parser.add_argument(
        "--texture-blocks-per-pair-band", type=int, default=4,
        help="per-luma-band patch cap per pair for band descriptors")
    parser.add_argument("--model-patches", type=int, default=24)
    parser.add_argument("--model-seed", type=int, default=1000)
    parser.add_argument("--model-sigma", type=float, default=4.0)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    for path in (args.source, args.table):
        if not os.path.isfile(path):
            parser.error(f"missing file: {path}")
    if (args.pairs_per_entry < 0 or args.luma_bins < 1
            or args.texture_blocks_per_pair < 1
            or args.texture_blocks_per_pair_band < 1):
        parser.error("pair limit must be non-negative and sample counts positive")

    width, height = probe_size(args.source)
    times = frame_times(args.source)
    entries = [entry for entry in filmgrn.load(args.table)
               if entry["apply_grain"] and entry["update_parameters"]]
    selections = [entry_frame_pairs(entry, times, args.pairs_per_entry)
                  for entry in entries]
    owner = {}
    for entry_index, pairs in enumerate(selections):
        for frame in pairs:
            if frame in owner:
                raise RuntimeError(
                    f"frame pair {frame} belongs to overlapping table entries")
            owner[frame] = entry_index
    pair_records = [[] for _entry in entries]
    for frame, source, next_source in decode_pair_stream(
            args.source, width, height, sorted(owner), args.bits):
        entry_index = owner[frame]
        pair_records[entry_index].append(measure_pair(
            frame, source, next_source, args.bits, args.flat_selector,
            args.flat_fraction, args.static_lo, args.static_hi,
            args.minimum_pair_blocks, args.luma_bins,
            args.texture_blocks_per_pair,
            args.texture_blocks_per_pair_band))

    rows = []
    for index, (entry, pairs, records) in enumerate(
            zip(entries, selections, pair_records)):
        measured = analyse_entry(
            entry, pairs, records, args.minimum_band_blocks, args.luma_bins,
            args.model_patches, args.model_seed + index * 100,
            args.model_sigma, args.bits)
        rows.append({
            "entry": index,
            "start_seconds": entry["start"] / TABLE_TICKS_PER_SECOND,
            "end_seconds": entry["end"] / TABLE_TICKS_PER_SECOND,
            "frames": pairs,
            **measured,
        })

    report = {
        "purpose": "source-fit admission evidence; never a routing verdict",
        "source": os.path.abspath(args.source),
        "table": os.path.abspath(args.table),
        "dimensions": [width, height],
        "bits": args.bits,
        "settings": {
            "pairs_per_entry": args.pairs_per_entry,
            "flat_selector": args.flat_selector,
            "flat_fraction": args.flat_fraction,
            "static_ratio": [args.static_lo, args.static_hi],
            "minimum_pair_blocks": args.minimum_pair_blocks,
            "minimum_band_blocks": args.minimum_band_blocks,
            "luma_bins": args.luma_bins,
            "texture_blocks_per_pair": args.texture_blocks_per_pair,
            "texture_blocks_per_pair_band": args.texture_blocks_per_pair_band,
        },
        "summary": aggregate_entries(rows, args.luma_bins),
        "entries": rows,
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        temporary = args.json_out + ".partial"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(encoded)
        os.replace(temporary, args.json_out)
    else:
        print(encoded, end="")
    summary_coverage = report["summary"]["coverage"]
    print(f"entries: {summary_coverage['measured_entries']} measured, "
          f"{summary_coverage['insufficient_entries']} insufficient", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
