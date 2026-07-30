#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texture_metrics


def write_yuv420(path, frames, bits=8):
    dtype = np.uint8 if bits == 8 else np.uint16
    with open(path, "wb") as output:
        for frame in frames:
            frame.astype(dtype).tofile(output)
            np.zeros((frame.shape[0] // 2, frame.shape[1] // 2),
                     dtype=dtype).tofile(output)
            np.zeros((frame.shape[0] // 2, frame.shape[1] // 2),
                     dtype=dtype).tofile(output)


class TextureMetricsTest(unittest.TestCase):
    def test_flat_selection_avoids_structured_guide(self):
        rng = np.random.default_rng(3)
        clean = np.full((128, 128), 96.0, dtype=np.float32)
        checker = (
            (np.indices((64, 128)).sum(axis=0) % 2) * 12.0)
        clean[64:] += checker
        source = clean + rng.normal(0.0, 3.0, clean.shape)
        metrics = texture_metrics.flat_block_metrics(source, clean, 8)
        flat_scores = metrics["structure_score"][:2].ravel()
        structured_scores = metrics["structure_score"][2:].ravel()
        self.assertLess(float(flat_scores.max()),
                        float(structured_scores.min()))

    def test_report_separates_white_and_correlated_texture_without_energy(self):
        rng = np.random.default_rng(5)
        frames = []
        clean_frames = []
        white_on_frames = []
        coarse_on_frames = []
        off_frames = []
        for _ in range(4):
            clean = np.full((128, 128), 96.0, dtype=np.float32)
            white = rng.normal(0.0, 4.0, clean.shape)
            coarse = (
                white + np.roll(white, 1, axis=0)
                + np.roll(white, 1, axis=1))
            coarse *= 4.0 / float(coarse.std())
            clean_frames.append(clean)
            frames.append(clean + white)
            off_frames.append(clean)
            white_on_frames.append(clean + white)
            coarse_on_frames.append(clean + coarse)

        with tempfile.TemporaryDirectory() as work:
            paths = {}
            for name, values in (
                    ("source", frames), ("clean", clean_frames),
                    ("white_on", white_on_frames),
                    ("coarse_on", coarse_on_frames), ("off", off_frames)):
                paths[name] = os.path.join(work, name + ".yuv")
                write_yuv420(paths[name], values)
            report = texture_metrics.analyze_raw_texture(
                paths["source"], paths["clean"],
                {
                    "white": (paths["white_on"], paths["off"]),
                    "coarse": (paths["coarse_on"], paths["off"]),
                },
                128, 128, 8, minimum_blocks=1)
        white = report["comparisons"]["white_vs_source"][
            "core"]["occupancy_weighted"]
        coarse = report["comparisons"]["coarse_vs_source"][
            "core"]["occupancy_weighted"]
        self.assertLess(white["spectrum_total_variation"], 0.01)
        self.assertLess(white["acf_rmse"], 0.01)
        self.assertGreater(
            coarse["spectrum_total_variation"],
            white["spectrum_total_variation"] + 0.05)
        self.assertGreater(
            coarse["acf_rmse"], white["acf_rmse"] + 0.05)
        white_sigma = report["descriptors"]["white"]["core"]["3"][
            "energy_diagnostic"]["sigma_8bit_p50"]
        coarse_sigma = report["descriptors"]["coarse"]["core"]["3"][
            "energy_diagnostic"]["sigma_8bit_p50"]
        self.assertAlmostEqual(white_sigma, coarse_sigma, delta=0.15)

    def test_sparse_luma_bands_are_na_not_passes(self):
        rng = np.random.default_rng(7)
        clean = [np.full((64, 64), 48.0, dtype=np.float32) for _ in range(2)]
        source = [frame + rng.normal(0.0, 2.0, frame.shape)
                  for frame in clean]
        with tempfile.TemporaryDirectory() as work:
            source_path = os.path.join(work, "source.yuv")
            clean_path = os.path.join(work, "clean.yuv")
            write_yuv420(source_path, source)
            write_yuv420(clean_path, clean)
            report = texture_metrics.analyze_raw_texture(
                source_path, clean_path,
                {"same": (source_path, clean_path)},
                64, 64, 8, minimum_blocks=1)
        bands = report["descriptors"]["same"]["core"]
        self.assertEqual(bands["0"]["status"], "N/A")
        self.assertEqual(bands["1"]["status"], "OK")
        self.assertEqual(bands["7"]["status"], "N/A")


if __name__ == "__main__":
    unittest.main()
