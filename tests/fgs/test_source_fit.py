#!/usr/bin/env python3
import os
import tempfile
import unittest

import numpy as np

import source_fit
import strength_selection_report
import temporal_grain_report


class SourceFitFlatSelectionTests(unittest.TestCase):
    def test_flat_scores_api_matches_full_metrics(self):
        rng = np.random.default_rng(7)
        frame = rng.normal(512.0, 8.0, (96, 128))
        score, sigma = source_fit.flat_scores(frame, 10)
        full_score, full_sigma, strict = source_fit.flat_metrics(frame, 10)
        np.testing.assert_array_equal(score, full_score)
        np.testing.assert_array_equal(sigma, full_sigma)
        self.assertEqual(score.shape, strict.shape)

    def test_production_selection_contains_every_eligible_strict_block(self):
        rng = np.random.default_rng(11)
        frame = rng.normal(512.0, 6.0, (128, 160))
        blocks, score, sigma = source_fit.production_flat_blocks(frame, 10)
        _score, _sigma, strict = source_fit.flat_metrics(frame, 10)
        eligible_strict = ((sigma >= 2.0) & (sigma <= 200.0)
                           & (score > 0.0) & strict)
        selected = np.zeros(score.shape, dtype=bool)
        for row, col in blocks:
            selected[row, col] = True
        self.assertTrue(np.all(selected[eligible_strict]))

    def test_production_selection_adds_top_decile(self):
        rng = np.random.default_rng(19)
        frame = rng.normal(512.0, 12.0, (320, 320))
        blocks, score, sigma = source_fit.production_flat_blocks(frame, 10)
        eligible_candidates = int(((sigma >= 2.0) & (sigma <= 200.0)
                                   & (score >= 0.5)).sum())
        self.assertGreaterEqual(len(blocks), min(score.size // 10, eligible_candidates))


class TemporalLeakTests(unittest.TestCase):
    def test_temporal_report_plane_geometry_keeps_block_grid(self):
        self.assertEqual(
            temporal_grain_report.plane_geometry(3840, 2160, "y"),
            (3840, 2160, 32))
        self.assertEqual(
            temporal_grain_report.plane_geometry(3840, 2160, "u"),
            (1920, 1080, 16))
        self.assertEqual(
            temporal_grain_report.plane_geometry(1919, 1079, "v"),
            (960, 540, 16))

    def test_parse_encoded_arms(self):
        self.assertEqual(
            strength_selection_report.parse_encoded_arms(
                ["q25=/tmp/q25.mkv", "q34=/tmp/arm=34.mkv"]),
            {"q25": "/tmp/q25.mkv", "q34": "/tmp/arm=34.mkv"})
        with self.assertRaises(ValueError):
            strength_selection_report.parse_encoded_arms(["missing-label"])
        with self.assertRaises(ValueError):
            strength_selection_report.parse_encoded_arms(
                ["q29=/tmp/a.mkv", "q29=/tmp/b.mkv"])

    def test_temporal_leak_ignores_static_base_error(self):
        """Spatial base energy is not necessarily retained grain.

        A static denoiser error is deliberately added only to the clean base.
        Spatial subtraction must under-predict the missing grain because it
        subtracts that error. Consecutive-frame base differencing cancels it and
        recovers the known retained-grain fraction.
        """
        rng = np.random.default_rng(23)
        shape = (64, 64)
        retain = 0.35
        picture = np.full(shape, 512.0)
        y, x = np.mgrid[:shape[0], :shape[1]]
        static_error = 12.0 * np.sin(x * 2.0 * np.pi / 9.0)
        grain_a = rng.normal(0.0, 20.0, shape)
        grain_b = rng.normal(0.0, 20.0, shape)
        source = picture + grain_a
        next_source = picture + grain_b
        clean = picture + static_error + retain * grain_a
        next_clean = picture + static_error + retain * grain_b
        blocks = [(row, col) for row in range(2) for col in range(2)]

        row = strength_selection_report.measure(
            source, next_source, clean, next_clean, blocks)

        self.assertAlmostEqual(row["temporal_leak_ratio"], retain, delta=0.03)
        self.assertAlmostEqual(
            row["temporal_target_ratio"], np.sqrt(1.0 - retain * retain),
            delta=0.03)
        self.assertLess(row["amplitude_ratio"],
                        row["temporal_target_ratio"] - 0.10)

    def test_y4m_selected_reader_seeks_over_unselected_payloads(self):
        width, height, bits = 4, 2, 10
        frames = [
            (np.arange(width * height, dtype=np.uint16) + index * 100)
            .reshape(height, width)
            for index in range(4)
        ]
        chroma = np.zeros(width * height // 2, dtype=np.uint16)
        with tempfile.NamedTemporaryFile(suffix=".y4m", delete=False) as handle:
            path = handle.name
            handle.write(b"YUV4MPEG2 W4 H2 F24:1 Ip A1:1 C420p10\n")
            for index, frame in enumerate(frames):
                handle.write(f"FRAME Xindex={index}\n".encode("ascii"))
                handle.write(frame.astype("<u2").tobytes())
                handle.write(chroma.astype("<u2").tobytes())
        try:
            selected = strength_selection_report.decode_y4m_selected(
                path, width, height, [1, 3], bits)
            np.testing.assert_array_equal(selected[1], frames[1])
            np.testing.assert_array_equal(selected[3], frames[3])
            self.assertEqual(list(selected), [1, 3])
        finally:
            os.unlink(path)

    def test_post_encode_variance_closure(self):
        rng = np.random.default_rng(29)
        shape = (256, 256)
        retain = 0.30
        target = np.sqrt(1.0 - retain * retain)
        picture = np.full(shape, 512.0)
        grain_a = rng.normal(0.0, 20.0, shape)
        grain_b = rng.normal(0.0, 20.0, shape)
        synth_a = rng.normal(0.0, 20.0 * target, shape)
        synth_b = rng.normal(0.0, 20.0 * target, shape)
        source = picture + grain_a
        next_source = picture + grain_b
        encoded_off = picture + retain * grain_a
        next_encoded_off = picture + retain * grain_b
        # Exercise the decoder's unsigned storage. The values stay in range,
        # while on-off contains both positive and negative grain deltas.
        encoded_off = np.rint(encoded_off).astype(np.uint16)
        next_encoded_off = np.rint(next_encoded_off).astype(np.uint16)
        encoded_on = np.rint(encoded_off + synth_a).astype(np.uint16)
        next_encoded_on = np.rint(next_encoded_off + synth_b).astype(np.uint16)
        blocks = [(row, col) for row in range(8) for col in range(8)]

        row = strength_selection_report.measure_encoded(
            source, next_source, encoded_on, next_encoded_on,
            encoded_off, next_encoded_off, blocks)

        self.assertAlmostEqual(row["post_leak_ratio"], retain, delta=0.02)
        self.assertAlmostEqual(row["post_target_ratio"], target, delta=0.02)
        self.assertAlmostEqual(row["synth_ratio"], target, delta=0.02)
        self.assertAlmostEqual(row["total_ratio"], 1.0, delta=0.03)
        self.assertAlmostEqual(row["closure_error"], 0.0, delta=0.02)


if __name__ == "__main__":
    unittest.main()
