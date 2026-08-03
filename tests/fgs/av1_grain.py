#!/usr/bin/env python3
"""Exact selected-block AV1 film-grain synthesis helpers for offline audits.

This is a small NumPy port of the normative operations exercised by libaom's
``grain_synthesis.c``: the fixed Gaussian sequence, 16-bit LFSR, AR templates,
32x32/16x16 template selection, overlap, scaling LUT, rounding and output
clipping. It intentionally synthesises only requested 4:2:0 blocks; that is
enough for the FGS metrics and avoids materialising an entire 4K grain plane.

The Gaussian sequence is read from a pinned libaom source checkout made by
``build_aom_reference.sh``.  Keeping the normative data in its upstream source
avoids a second 2048-value copy in this repository.
"""
import re

import numpy as np

from source_fit import BS


TEMPLATE_HEIGHT = 73
TEMPLATE_WIDTH = 82
TEMPLATE_OFFSET = 9
CHROMA_BLOCK_SIZE = BS // 2
CHROMA_TEMPLATE_HEIGHT = 38
CHROMA_TEMPLATE_WIDTH = 44
CHROMA_TEMPLATE_OFFSET = 6
GRAIN_MIN_BY_BITS = {8: -128, 10: -512, 12: -2048}


def load_gaussian_sequence(path):
    """Read libaom's normative 2048-value AV1 Gaussian sequence."""
    with open(path, encoding="utf-8") as handle:
        source = handle.read()
    match = re.search(
        r"gaussian_sequence\s*\[\s*2048\s*\]\s*=\s*\{(.*?)\};",
        source, flags=re.DOTALL)
    if not match:
        raise ValueError(f"{path}: AV1 gaussian_sequence[2048] not found")
    values = [int(value) for value in re.findall(r"-?\d+", match.group(1))]
    if len(values) != 2048:
        raise ValueError(f"{path}: Gaussian sequence has {len(values)} values, expected 2048")
    return np.asarray(values, dtype=np.int64)


def random_number(register, bits):
    """Advance the AV1 16-bit LFSR and return ``bits`` high bits."""
    bit = ((register >> 0) ^ (register >> 1) ^
           (register >> 3) ^ (register >> 12)) & 1
    register = (register >> 1) | (bit << 15)
    return register, (register >> (16 - bits)) & ((1 << bits) - 1)


def init_random_generator(luma_line, seed):
    register = int(seed) & 0xffff
    luma_number = luma_line >> 5
    register ^= ((luma_number * 37 + 178) & 255) << 8
    register ^= ((luma_number * 173 + 105) & 255)
    return register


def ar_taps(lag):
    taps = []
    for row in range(-lag, 0):
        for col in range(-lag, lag + 1):
            taps.append((row, col))
    for col in range(-lag, 0):
        taps.append((0, col))
    return taps


def generate_luma_template(entry, gaussian, bit_depth):
    """Generate the exact 73x82 integer luma template for one AV1 frame."""
    if not entry["scaling_points"]["y"]:
        return np.zeros((TEMPLATE_HEIGHT, TEMPLATE_WIDTH), dtype=np.int64)
    params = entry["params"]
    register = int(entry["random_seed"]) & 0xffff
    gaussian_shift = 12 - bit_depth + params["grain_scale_shift"]
    gaussian_round = (1 << gaussian_shift) >> 1
    template = np.empty((TEMPLATE_HEIGHT, TEMPLATE_WIDTH), dtype=np.int64)
    for row in range(TEMPLATE_HEIGHT):
        for col in range(TEMPLATE_WIDTH):
            register, index = random_number(register, 11)
            template[row, col] = (
                int(gaussian[index]) + gaussian_round) >> gaussian_shift

    lag = params["ar_coeff_lag"]
    shift = params["ar_coeff_shift"]
    rounding = 1 << (shift - 1)
    coefficients = entry["ar_coeffs"]["y"]
    taps = ar_taps(lag)
    if len(coefficients) != len(taps):
        raise ValueError(
            f"luma coefficient count {len(coefficients)} != {len(taps)} for lag {lag}")
    grain_min = GRAIN_MIN_BY_BITS[bit_depth]
    grain_max = -grain_min - 1
    # The normative implementation always leaves three rows/columns of AR
    # stabilisation padding, even when the signalled lag is smaller than 3.
    for row in range(3, TEMPLATE_HEIGHT):
        for col in range(3, TEMPLATE_WIDTH - 3):
            weighted = sum(
                coefficient * template[row + drow, col + dcol]
                for coefficient, (drow, dcol) in zip(coefficients, taps))
            value = template[row, col] + ((weighted + rounding) >> shift)
            template[row, col] = min(max(value, grain_min), grain_max)
    return template


def generate_chroma_template(entry, luma_template, gaussian, bit_depth, plane):
    """Generate one exact 38x44 integer 4:2:0 chroma grain template."""
    if plane not in ("cb", "cr"):
        raise ValueError(f"chroma plane must be cb or cr, got {plane}")
    params = entry["params"]
    if (not entry["scaling_points"][plane]
            and not params.get("chroma_scaling_from_luma", 0)):
        return np.zeros(
            (CHROMA_TEMPLATE_HEIGHT, CHROMA_TEMPLATE_WIDTH), dtype=np.int64)

    # AV1 deliberately uses separate, deterministically offset RNG states for
    # Cb and Cr rather than continuing from luma template generation.
    seed_line = 7 << 5 if plane == "cb" else 11 << 5
    register = init_random_generator(seed_line, entry["random_seed"])
    gaussian_shift = 12 - bit_depth + params["grain_scale_shift"]
    gaussian_round = (1 << gaussian_shift) >> 1
    template = np.empty(
        (CHROMA_TEMPLATE_HEIGHT, CHROMA_TEMPLATE_WIDTH), dtype=np.int64)
    for row in range(CHROMA_TEMPLATE_HEIGHT):
        for col in range(CHROMA_TEMPLATE_WIDTH):
            register, index = random_number(register, 11)
            template[row, col] = (
                int(gaussian[index]) + gaussian_round) >> gaussian_shift

    lag = params["ar_coeff_lag"]
    coefficients = entry["ar_coeffs"][plane]
    taps = ar_taps(lag)
    expected = len(taps) + (1 if entry["scaling_points"]["y"] else 0)
    if len(coefficients) != expected:
        raise ValueError(
            f"{plane} coefficient count {len(coefficients)} != {expected} "
            f"for lag {lag}")
    shift = params["ar_coeff_shift"]
    rounding = 1 << (shift - 1)
    grain_min = GRAIN_MIN_BY_BITS[bit_depth]
    grain_max = -grain_min - 1
    # AV1 keeps three template-padding rows/columns regardless of signalled
    # lag. For 4:2:0, the co-located luma predictor is a rounded 2x2 average
    # from the already-generated luma grain template.
    for row in range(3, CHROMA_TEMPLATE_HEIGHT):
        for col in range(3, CHROMA_TEMPLATE_WIDTH - 3):
            weighted = sum(
                coefficient * template[row + drow, col + dcol]
                for coefficient, (drow, dcol)
                in zip(coefficients[:len(taps)], taps))
            if len(coefficients) > len(taps):
                luma_row = ((row - 3) << 1) + 3
                luma_col = ((col - 3) << 1) + 3
                luma_average = int(
                    (luma_template[
                        luma_row:luma_row + 2,
                        luma_col:luma_col + 2].sum() + 2) >> 2)
                weighted += coefficients[-1] * luma_average
            value = template[row, col] + ((weighted + rounding) >> shift)
            template[row, col] = min(max(value, grain_min), grain_max)
    return template


def block_offsets(seed, block_rows, block_cols):
    """Return decoder-selected template offsets for every 32x32 block."""
    offsets = np.empty((block_rows, block_cols, 2), dtype=np.int16)
    for block_row in range(block_rows):
        register = init_random_generator(block_row * BS, seed)
        for block_col in range(block_cols):
            register, value = random_number(register, 8)
            offsets[block_row, block_col] = (value & 15, (value >> 4) & 15)
    return offsets


def _patch(template, offset):
    row = TEMPLATE_OFFSET + (int(offset[0]) << 1)
    col = TEMPLATE_OFFSET + (int(offset[1]) << 1)
    return template[row:row + BS + 2, col:col + BS + 2]


def _chroma_patch(template, offset):
    row = CHROMA_TEMPLATE_OFFSET + int(offset[0])
    col = CHROMA_TEMPLATE_OFFSET + int(offset[1])
    return template[
        row:row + CHROMA_BLOCK_SIZE + 1,
        col:col + CHROMA_BLOCK_SIZE + 1]


def _vertical_overlap(left, right, grain_min, grain_max):
    result = np.empty_like(right)
    result[:, 0] = (27 * left[:, 0] + 17 * right[:, 0] + 16) >> 5
    result[:, 1] = (17 * left[:, 1] + 27 * right[:, 1] + 16) >> 5
    return np.clip(result, grain_min, grain_max)


def _horizontal_overlap(top, bottom, grain_min, grain_max):
    result = np.empty_like(bottom)
    result[0] = (27 * top[0] + 17 * bottom[0] + 16) >> 5
    result[1] = (17 * top[1] + 27 * bottom[1] + 16) >> 5
    return np.clip(result, grain_min, grain_max)


def _single_vertical_overlap(left, right, grain_min, grain_max):
    return np.clip((23 * left + 22 * right + 16) >> 5, grain_min, grain_max)


def _single_horizontal_overlap(top, bottom, grain_min, grain_max):
    return np.clip((23 * top + 22 * bottom + 16) >> 5, grain_min, grain_max)


def selected_grain_blocks(entry, gaussian, bit_depth, frame_shape, blocks):
    """Generate exact pre-scaled grain for selected aligned luma blocks."""
    height, width = frame_shape
    template = generate_luma_template(entry, gaussian, bit_depth)
    offsets = block_offsets(
        entry["random_seed"], (height + BS - 1) // BS, (width + BS - 1) // BS)
    grain_min = GRAIN_MIN_BY_BITS[bit_depth]
    grain_max = -grain_min - 1
    overlap = bool(entry["params"]["overlap_flag"])
    result = []
    for block_row, block_col in blocks:
        current = _patch(template, offsets[block_row, block_col])
        output = current[:BS, :BS].copy()
        vertical = None
        if overlap and block_col:
            left = _patch(template, offsets[block_row, block_col - 1])
            vertical = _vertical_overlap(
                left[:BS + 2, BS:BS + 2], current[:BS + 2, :2],
                grain_min, grain_max)
            output[:, :2] = vertical[:BS]
        if overlap and block_row:
            above = _patch(template, offsets[block_row - 1, block_col])
            top = above[BS:BS + 2, :BS].copy()
            if block_col:
                above_left = _patch(
                    template, offsets[block_row - 1, block_col - 1])
                top[:, :2] = _vertical_overlap(
                    above_left[BS:BS + 2, BS:BS + 2],
                    above[BS:BS + 2, :2], grain_min, grain_max)
            output[:2] = _horizontal_overlap(
                top, output[:2], grain_min, grain_max)
        result.append(output)
    if not result:
        return np.empty((0, BS, BS), dtype=np.int64)
    return np.stack(result)


def selected_chroma_grain_blocks(
        entry, gaussian, bit_depth, frame_shape, blocks, plane):
    """Generate exact pre-scaled 4:2:0 Cb/Cr grain for luma-grid blocks."""
    height, width = frame_shape
    luma_template = generate_luma_template(entry, gaussian, bit_depth)
    template = generate_chroma_template(
        entry, luma_template, gaussian, bit_depth, plane)
    offsets = block_offsets(
        entry["random_seed"], (height + BS - 1) // BS, (width + BS - 1) // BS)
    grain_min = GRAIN_MIN_BY_BITS[bit_depth]
    grain_max = -grain_min - 1
    overlap = bool(entry["params"]["overlap_flag"])
    result = []
    for block_row, block_col in blocks:
        current = _chroma_patch(template, offsets[block_row, block_col])
        output = current[:CHROMA_BLOCK_SIZE, :CHROMA_BLOCK_SIZE].copy()
        if overlap and block_col:
            left = _chroma_patch(template, offsets[block_row, block_col - 1])
            vertical = _single_vertical_overlap(
                left[:CHROMA_BLOCK_SIZE + 1, CHROMA_BLOCK_SIZE:
                     CHROMA_BLOCK_SIZE + 1],
                current[:CHROMA_BLOCK_SIZE + 1, :1],
                grain_min, grain_max)
            output[:, :1] = vertical[:CHROMA_BLOCK_SIZE]
        if overlap and block_row:
            above = _chroma_patch(template, offsets[block_row - 1, block_col])
            top = above[
                CHROMA_BLOCK_SIZE:CHROMA_BLOCK_SIZE + 1,
                :CHROMA_BLOCK_SIZE].copy()
            if block_col:
                above_left = _chroma_patch(
                    template, offsets[block_row - 1, block_col - 1])
                top[:, :1] = _single_vertical_overlap(
                    above_left[
                        CHROMA_BLOCK_SIZE:CHROMA_BLOCK_SIZE + 1,
                        CHROMA_BLOCK_SIZE:CHROMA_BLOCK_SIZE + 1],
                    above[
                        CHROMA_BLOCK_SIZE:CHROMA_BLOCK_SIZE + 1, :1],
                    grain_min, grain_max)
            output[:1] = _single_horizontal_overlap(
                top, output[:1], grain_min, grain_max)
        result.append(output)
    if not result:
        return np.empty(
            (0, CHROMA_BLOCK_SIZE, CHROMA_BLOCK_SIZE), dtype=np.int64)
    return np.stack(result)


def scaling_lut(points):
    """Build the exact 8-bit AV1 scaling LUT with integer interpolation."""
    if not points:
        return np.zeros(256, dtype=np.int64)
    points = sorted(points)
    lut = np.empty(256, dtype=np.int64)
    lut[:points[0][0]] = points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        delta_x = x1 - x0
        delta = (y1 - y0) * ((65536 + (delta_x >> 1)) // delta_x)
        x = np.arange(delta_x, dtype=np.int64)
        lut[x0:x1] = y0 + ((x * delta + 32768) >> 16)
    lut[points[-1][0]:] = points[-1][1]
    return lut


def scale_values(lut, pixels, bit_depth):
    """Apply AV1's high-bit-depth interpolation between 8-bit LUT entries."""
    pixels = np.asarray(pixels, dtype=np.int64)
    shift = bit_depth - 8
    indices = pixels >> shift
    if shift == 0:
        return lut[indices]
    low = pixels & ((1 << shift) - 1)
    right_indices = np.minimum(indices + 1, 255)
    delta = lut[right_indices] - lut[indices]
    interpolated = lut[indices] + ((delta * low + (1 << (shift - 1))) >> shift)
    return np.where(indices == 255, lut[255], interpolated)


def _selected_blocks(frame, blocks, block_size):
    height = frame.shape[0] // block_size * block_size
    width = frame.shape[1] // block_size * block_size
    grid = frame[:height, :width].reshape(
        height // block_size, block_size,
        width // block_size, block_size).transpose(0, 2, 1, 3)
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])
    return np.asarray(grid[rows, cols], dtype=np.int64)


def selected_chroma_scaling(
        base_luma, base_chroma, blocks, entry, bit_depth, plane):
    """Return exact chroma curve indices/scales for selected 4:2:0 blocks.

    ``entry`` must use the signed chroma multipliers exposed by decoded frame
    side data (rather than the biased unsigned values stored by filmgrn1).
    """
    if plane not in ("cb", "cr"):
        raise ValueError(f"chroma plane must be cb or cr, got {plane}")
    if not blocks:
        empty = np.empty(
            (0, CHROMA_BLOCK_SIZE, CHROMA_BLOCK_SIZE), dtype=np.int64)
        return {"indices": empty, "scales": empty, "base": empty}

    base_luma_blocks = _selected_blocks(base_luma, blocks, BS)
    base_chroma_blocks = _selected_blocks(
        base_chroma, blocks, CHROMA_BLOCK_SIZE)
    # The normative scaling lookup for 4:2:0 averages the two horizontally
    # co-located luma samples from the top line; it does not average vertically.
    average_luma = (
        base_luma_blocks[:, ::2, 0::2]
        + base_luma_blocks[:, ::2, 1::2] + 1) >> 1
    params = entry["params"]
    if params.get("chroma_scaling_from_luma", 0):
        chroma_mult, luma_mult, offset = 0, 64, 0
    else:
        prefix = "cb" if plane == "cb" else "cr"
        chroma_mult = params[f"{prefix}_mult"]
        luma_mult = params[f"{prefix}_luma_mult"]
        # Frame side data exposes the bias-removed offset in 8-bit units.
        offset = params[f"{prefix}_offset"] * (1 << (bit_depth - 8))
    indices = ((average_luma * luma_mult
                + base_chroma_blocks * chroma_mult) >> 6) + offset
    indices = np.clip(indices, 0, (256 << (bit_depth - 8)) - 1)
    curve_plane = "y" if params.get("chroma_scaling_from_luma", 0) else plane
    scales = scale_values(
        scaling_lut(entry["scaling_points"][curve_plane]), indices, bit_depth)
    return {"indices": indices, "scales": scales, "base": base_chroma_blocks}


def selected_chroma_response(
        base_luma, base_chroma, blocks, entry, gaussian, bit_depth, plane,
        identity_matrix=False):
    """Return exact 4:2:0 chroma deltas and their emission intermediates."""
    scaling = selected_chroma_scaling(
        base_luma, base_chroma, blocks, entry, bit_depth, plane)
    if not blocks:
        empty = scaling["base"]
        return {"delta": empty, "grain": empty, **scaling}
    base_chroma_blocks = scaling["base"]
    scales = scaling["scales"]
    indices = scaling["indices"]
    params = entry["params"]
    grain = selected_chroma_grain_blocks(
        entry, gaussian, bit_depth, base_luma.shape, blocks, plane)
    shift = params["scaling_shift"]
    noise = (scales * grain + (1 << (shift - 1))) >> shift
    if entry.get("limit_output_range", False):
        minimum = 16 << (bit_depth - 8)
        maximum = (235 if identity_matrix else 240) << (bit_depth - 8)
    else:
        minimum, maximum = 0, (1 << bit_depth) - 1
    delta = np.clip(
        base_chroma_blocks + noise, minimum, maximum) - base_chroma_blocks
    return {
        "delta": delta,
        "grain": grain,
        "indices": indices,
        "scales": scales,
        "base": base_chroma_blocks,
    }


def synthesize_selected_chroma(
        base_luma, base_chroma, blocks, entry, gaussian, bit_depth, plane,
        identity_matrix=False):
    """Return exact decoded 4:2:0 Cb/Cr deltas for selected luma blocks."""
    return selected_chroma_response(
        base_luma, base_chroma, blocks, entry, gaussian, bit_depth, plane,
        identity_matrix=identity_matrix)["delta"]


def synthesize_selected_luma(base, blocks, entry, gaussian, bit_depth):
    """Return exact decoded luma deltas for selected 32x32 blocks."""
    if not blocks:
        return np.empty((0, BS, BS), dtype=np.int64)
    base_grid = base[:base.shape[0] // BS * BS, :base.shape[1] // BS * BS]
    base_grid = base_grid.reshape(
        base.shape[0] // BS, BS, base.shape[1] // BS, BS).transpose(0, 2, 1, 3)
    rows = np.asarray([row for row, _col in blocks])
    cols = np.asarray([col for _row, col in blocks])
    base_blocks = np.asarray(base_grid[rows, cols], dtype=np.int64)
    grain = selected_grain_blocks(
        entry, gaussian, bit_depth, base.shape, blocks)
    lut = scaling_lut(entry["scaling_points"]["y"])
    scales = scale_values(lut, base_blocks, bit_depth)
    shift = entry["params"]["scaling_shift"]
    noise = (scales * grain + (1 << (shift - 1))) >> shift
    if entry.get("limit_output_range", False):
        minimum, maximum = 16 << (bit_depth - 8), 235 << (bit_depth - 8)
    else:
        minimum, maximum = 0, (1 << bit_depth) - 1
    return np.clip(base_blocks + noise, minimum, maximum) - base_blocks
