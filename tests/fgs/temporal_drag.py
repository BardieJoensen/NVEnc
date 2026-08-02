#!/usr/bin/env python3
"""Measure directional temporal lag in a separator's base.

The first version regressed base error only onto the previous-frame direction.
That coefficient equals a literal blend fraction for the assumed model

    base_n = (1-a)*src_n + a*src_{n-1}

but a spatial blur on a translating edge can produce the same projection.  The
calibrated instrument jointly fits both temporal directions:

    err_n = b_prev*(src_{n-1}-src_n) + b_next*(src_{n+1}-src_n) + residual

A one-sided lag loads b_prev; a centred spatial/temporal blur loads both.  The
primary diagnostic is lag_asymmetry = b_prev - b_next.  This remains a temporal
lag detector, not a motion-vector failure counter: exposure/flicker lag and
other directionally asymmetric processing can also trigger it.

All fields are box-averaged first.  Without that control, removing temporally
independent grain creates a spurious positive previous-frame projection.
"""
import argparse
import json
import os
import subprocess

import numpy as np

from review_score import FFMPEG, aligned_frame_count

BS = int(os.environ.get("GHOST_BS", "8"))
BINS = ((0.0, 4.0), (4.0, 16.0), (16.0, 64.0), (64.0, float("inf")))


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def frames(path, n, width, height):
    """Yield n luma planes as float32, decoded to 10-bit gray."""
    p = subprocess.Popen(
        [FFMPEG, "-v", "error", "-nostdin", "-i", path, "-frames:v", str(n),
         "-pix_fmt", "gray10le", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = width * height * 2
    completed = False
    try:
        for index in range(n):
            buf = _read_exact(p.stdout, size)
            if len(buf) < size:
                stderr = p.stderr.read().decode(errors="replace")
                p.wait()
                raise RuntimeError(
                    f"{path}: short decode at frame {index}/{n}: {stderr[-2000:]}")
            yield np.frombuffer(buf, np.uint16).reshape(height, width).astype(np.float32)
        p.stdout.close()
        stderr = p.stderr.read().decode(errors="replace")
        status = p.wait()
        completed = True
        if status != 0:
            raise RuntimeError(f"{path}: decoder exited {status}: {stderr[-2000:]}")
    finally:
        if not completed:
            if p.stdout:
                p.stdout.close()
            p.kill()
            p.wait()


def box(a, width, height, block_size=BS):
    return a.reshape(
        height // block_size, block_size,
        width // block_size, block_size).mean(axis=(1, 3))


class ProjectionAccumulator:
    """Sufficient statistics for simple and joint previous/next regressions."""
    def __init__(self):
        self.previous2 = 0.0
        self.next2 = 0.0
        self.previous_next = 0.0
        self.error_previous = 0.0
        self.error_next = 0.0
        self.blocks = 0

    def add(self, error, previous, following, mask=None):
        if mask is not None:
            error, previous, following = error[mask], previous[mask], following[mask]
        error = np.asarray(error, dtype=np.float64)
        previous = np.asarray(previous, dtype=np.float64)
        following = np.asarray(following, dtype=np.float64)
        self.previous2 += float((previous * previous).sum())
        self.next2 += float((following * following).sum())
        self.previous_next += float((previous * following).sum())
        self.error_previous += float((error * previous).sum())
        self.error_next += float((error * following).sum())
        self.blocks += int(error.size)

    def result(self):
        previous_beta = (self.error_previous / self.previous2
                         if self.previous2 else None)
        next_beta = self.error_next / self.next2 if self.next2 else None
        normalizer = self.previous2 * self.next2
        determinant = normalizer - self.previous_next * self.previous_next
        condition = determinant / normalizer if normalizer else 0.0
        direction_correlation = (
            self.previous_next / np.sqrt(normalizer) if normalizer else None)
        joint_previous = joint_next = lag_asymmetry = symmetric = None
        if determinant > max(normalizer * 1e-9, 1e-12):
            joint_previous = (
                self.error_previous * self.next2
                - self.error_next * self.previous_next) / determinant
            joint_next = (
                self.error_next * self.previous2
                - self.error_previous * self.previous_next) / determinant
            lag_asymmetry = joint_previous - joint_next
            symmetric = 0.5 * (joint_previous + joint_next)
        return {
            "blocks": self.blocks,
            "previous_beta": previous_beta,
            "next_beta": next_beta,
            "joint_previous": joint_previous,
            "joint_next": joint_next,
            "lag_asymmetry": lag_asymmetry,
            "symmetric_projection": symmetric,
            "direction_correlation": direction_correlation,
            "joint_condition": condition,
        }


def _add_triplet(overall, binned, previous_source, source, next_source, base):
    error = base - source
    previous = previous_source - source
    following = next_source - source
    overall.add(error, previous, following)
    magnitude = np.maximum(np.abs(previous), np.abs(following))
    for accumulator, (low, high) in zip(binned, BINS):
        mask = (magnitude >= low) & (magnitude < high)
        if mask.any():
            accumulator.add(error, previous, following, mask)


def measure_arrays(source_frames, base_frames, block_size=BS):
    """Array entry point used by labelled controls and unit tests."""
    if len(source_frames) != len(base_frames):
        raise ValueError("source/base frame counts differ")
    if len(source_frames) < 3:
        raise ValueError("at least three frames are required")
    shape = np.asarray(source_frames[0]).shape
    if len(shape) != 2:
        raise ValueError("luma frames must be two-dimensional")
    height, width = shape
    if width % block_size or height % block_size:
        raise ValueError(
            f"{width}x{height} is not divisible by block size {block_size}")
    sources = []
    bases = []
    for index, (source, base) in enumerate(zip(source_frames, base_frames)):
        source, base = np.asarray(source), np.asarray(base)
        if source.shape != shape or base.shape != shape:
            raise ValueError(f"frame {index} shape differs from {shape}")
        sources.append(box(source, width, height, block_size))
        bases.append(box(base, width, height, block_size))
    overall = ProjectionAccumulator()
    binned = [ProjectionAccumulator() for _ in BINS]
    for index in range(1, len(sources) - 1):
        _add_triplet(overall, binned, sources[index - 1], sources[index],
                     sources[index + 1], bases[index])
    return _format_result(len(sources), block_size, overall, binned)


def _format_range(low, high):
    return f"{low:g}-{high:g}" if np.isfinite(high) else f">{low:g}"


def _format_result(frame_count, block_size, overall, binned):
    projection = overall.result()
    motion_bins = []
    for accumulator, (low, high) in zip(binned, BINS):
        row = {"range": _format_range(low, high), **accumulator.result()}
        motion_bins.append(row)
    # beta/bins retain the old JSON fields for readers that only display the
    # univariate previous projection.  New decisions must use projection.
    return {
        "frames": frame_count,
        "evaluated_frames": frame_count - 2,
        "box_size": block_size,
        "beta": projection["previous_beta"],
        "bins": [
            {"range": row["range"], "blocks": row["blocks"],
             "beta": row["previous_beta"]}
            for row in motion_bins],
        "projection": projection,
        "motion_bins": motion_bins,
    }


def probe(ref, base, n):
    available, ref_info, base_info = aligned_frame_count(ref, base, limit=n)
    if available != n:
        raise RuntimeError(
            f"requested {n} frames but the aligned pair contains {available}; "
            "pass the exact count rather than allowing a silent short decode")
    width, height = ref_info["width"], ref_info["height"]
    if width % BS or height % BS:
        raise RuntimeError(
            f"{width}x{height} is not divisible by GHOST_BS={BS}")
    rg = frames(ref, n, width, height)
    bg = frames(base, n, width, height)
    overall = ProjectionAccumulator()
    binned = [ProjectionAccumulator() for _ in BINS]
    window = []
    for index in range(n):
        try:
            source, base_frame = next(rg), next(bg)
        except StopIteration as error:
            raise RuntimeError(f"decoder stopped before frame {index}/{n}") from error
        window.append((box(source, width, height), box(base_frame, width, height)))
        if len(window) == 3:
            _add_triplet(overall, binned, window[0][0], window[1][0],
                         window[2][0], window[1][1])
            window.pop(0)
    for iterator, label in ((rg, ref), (bg, base)):
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            raise RuntimeError(f"{label}: decoder produced more than {n} frames")
    return _format_result(n, BS, overall, binned)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("base")
    parser.add_argument("frames", type=int)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = probe(args.reference, args.base, args.frames)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        temporary = f"{args.output}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
        os.replace(temporary, args.output)
    print(rendered)


if __name__ == "__main__":
    main()
