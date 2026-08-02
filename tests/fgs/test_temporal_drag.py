#!/usr/bin/env python3
import os
import sys
import unittest

import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import temporal_drag  # noqa: E402


HEIGHT, WIDTH, BLOCK = 128, 256, 8


def random_frames(count=12, seed=4):
    rng = np.random.default_rng(seed)
    return [rng.normal(500.0, 80.0, (HEIGHT, WIDTH)) for _ in range(count)]


def previous_blend(source, alpha):
    output = [source[0].copy()]
    output.extend((1.0 - alpha) * source[index] + alpha * source[index - 1]
                  for index in range(1, len(source)))
    return output


def blur_horizontal(frame, radius):
    padded = np.pad(frame, ((0, 0), (radius, radius)), mode="edge")
    cumulative = np.pad(
        np.cumsum(padded, axis=1, dtype=np.float64), ((0, 0), (1, 0)))
    diameter = 2 * radius + 1
    return (cumulative[:, diameter:] - cumulative[:, :-diameter]) / diameter


class TemporalProjectionTests(unittest.TestCase):
    def test_recovers_exact_previous_frame_blend(self):
        source = random_frames()
        result = temporal_drag.measure_arrays(
            source, previous_blend(source, 0.15), BLOCK)["projection"]
        self.assertAlmostEqual(result["joint_previous"], 0.15, places=10)
        self.assertAlmostEqual(result["joint_next"], 0.0, places=10)
        self.assertAlmostEqual(result["lag_asymmetry"], 0.15, places=10)

    def test_unchanged_base_has_zero_projection(self):
        source = random_frames()
        result = temporal_drag.measure_arrays(source, source, BLOCK)["projection"]
        self.assertAlmostEqual(result["joint_previous"], 0.0, places=12)
        self.assertAlmostEqual(result["joint_next"], 0.0, places=12)
        self.assertAlmostEqual(result["lag_asymmetry"], 0.0, places=12)

    def test_centred_temporal_blur_loads_both_directions(self):
        source = random_frames()
        base = [source[0].copy()]
        base.extend(
            0.8 * source[index]
            + 0.1 * source[index - 1]
            + 0.1 * source[index + 1]
            for index in range(1, len(source) - 1))
        base.append(source[-1].copy())
        result = temporal_drag.measure_arrays(source, base, BLOCK)["projection"]
        self.assertAlmostEqual(result["joint_previous"], 0.1, places=10)
        self.assertAlmostEqual(result["joint_next"], 0.1, places=10)
        self.assertAlmostEqual(result["lag_asymmetry"], 0.0, places=10)

    def test_spatial_blur_can_fool_old_beta_but_not_asymmetry(self):
        y, x = np.mgrid[:HEIGHT, :WIDTH]
        source = []
        base = []
        for index in range(12):
            frame = np.full((HEIGHT, WIDTH), 128.0)
            moving = ((y > 20) & (y < 108)
                      & (x > 40 + 4 * index) & (x < 120 + 4 * index))
            frame[moving] = 828.0
            source.append(frame)
            base.append(blur_horizontal(frame, radius=8))
        result = temporal_drag.measure_arrays(source, base, BLOCK)["projection"]
        # The old one-direction beta falsely looks like a large temporal blend.
        self.assertGreater(result["previous_beta"], 0.20)
        # Joint previous/next loading exposes the symmetric spatial mechanism.
        self.assertLess(abs(result["lag_asymmetry"]), 0.02)
        self.assertGreater(result["joint_previous"], 0.20)
        self.assertGreater(result["joint_next"], 0.20)

    def test_exposure_lag_is_detected_but_is_not_ghosting(self):
        rng = np.random.default_rng(9)
        texture = np.linspace(100.0, 900.0, WIDTH)[None, :].repeat(HEIGHT, axis=0)
        offsets = rng.normal(0.0, 30.0, 12)
        source = [texture + offset for offset in offsets]
        result = temporal_drag.measure_arrays(
            source, previous_blend(source, 0.2), BLOCK)["projection"]
        self.assertAlmostEqual(result["lag_asymmetry"], 0.2, places=10)


if __name__ == "__main__":
    unittest.main()
