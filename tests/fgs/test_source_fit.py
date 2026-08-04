#!/usr/bin/env python3
import os
import tempfile
import unittest
from unittest import mock

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

    def test_temporal_selection_builds_a_mask_for_every_frame_pair(self):
        frames = [np.full((64, 160), value, dtype=np.float64)
                  for value in (10.0, 20.0)]
        nextframes = [frame + 1.0 for frame in frames]
        candidates = [(row, col) for row in range(2) for col in range(5)]
        masks = [candidates[:8], candidates[2:]]
        score = np.arange(10, dtype=np.float64).reshape(2, 5)
        sigma = np.full((2, 5), 4.0)

        with mock.patch.object(
                source_fit, "select_flat",
                side_effect=[(candidates, score, sigma)] * 2) as select, \
             mock.patch.object(
                 source_fit, "static_flat_blocks",
                 side_effect=masks) as static:
            selected, diagnostics = source_fit.temporal_block_masks(
                frames, nextframes, bits=10)

        self.assertEqual(selected, masks)
        self.assertEqual(select.call_count, 2)
        self.assertEqual(static.call_count, 2)
        np.testing.assert_array_equal(select.call_args_list[0].args[0], frames[0])
        np.testing.assert_array_equal(select.call_args_list[1].args[0], frames[1])
        np.testing.assert_array_equal(static.call_args_list[0].args[1], nextframes[0])
        np.testing.assert_array_equal(static.call_args_list[1].args[1], nextframes[1])
        self.assertEqual([row["static_count"] for row in diagnostics], [8, 8])

    def test_temporal_selection_rejects_a_sparse_later_pair(self):
        frames = [np.zeros((64, 160)), np.ones((64, 160))]
        candidates = [(row, col) for row in range(2) for col in range(5)]
        score = np.ones((2, 5))
        sigma = np.ones((2, 5))
        with mock.patch.object(
                source_fit, "select_flat",
                side_effect=[(candidates, score, sigma)] * 2), \
             mock.patch.object(
                 source_fit, "static_flat_blocks",
                 side_effect=[candidates[:8], candidates[:7]]):
            with self.assertRaisesRegex(SystemExit, "sample pair 1"):
                source_fit.temporal_block_masks(
                    frames, [frame.copy() for frame in frames], bits=10)


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
        self.assertEqual(
            strength_selection_report.plane_geometry(3840, 2160, "u"),
            (1920, 1080, 16))

    def test_temporal_luma_bands_respect_sample_depth(self):
        frame_10 = np.zeros((32, 64), dtype=np.uint16)
        frame_10[:, :32] = 255
        frame_10[:, 32:] = 768
        bands_10 = temporal_grain_report.masks_by_luma(
            frame_10, [(0, 0), (0, 1)], 4, bits=10)
        self.assertEqual(bands_10, [[(0, 0)], [], [], [(0, 1)]])

        frame_16 = frame_10 * 64
        bands_16 = temporal_grain_report.masks_by_luma(
            frame_16, [(0, 0), (0, 1)], 4, bits=16)
        self.assertEqual(bands_16, bands_10)

    def test_temporal_decode_extracts_luma_before_gray_conversion(self):
        completed = mock.Mock(stdout=b"\0" * 4, stderr=b"")
        with mock.patch.object(
                temporal_grain_report.subprocess, "run",
                return_value=completed) as run:
            temporal_grain_report.decode_selected(
                "input.mkv", 2, 1, [0], plane="y", bits=10)
        filters = run.call_args.args[0][run.call_args.args[0].index("-vf") + 1]
        self.assertIn("extractplanes=y", filters)

    def test_temporal_report_records_zero_energy_without_texture(self):
        truth = {"sigma": 4.0, "h1": 0.2, "v1": 0.2,
                 "h2": 0.1, "v2": 0.1}
        self.assertIsNone(temporal_grain_report.average_acf([None, None]))
        ratio = temporal_grain_report.ratio_rows([None], [truth])
        self.assertEqual(ratio, {"mean": 0.0, "sd": 0.0})
        self.assertTrue(np.isnan(temporal_grain_report.lag1(None)))

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
        cb = [
            np.arange(width * height // 4, dtype=np.uint16) + 1000 + index * 10
            for index in range(4)
        ]
        cr = [
            np.arange(width * height // 4, dtype=np.uint16) + 2000 + index * 10
            for index in range(4)
        ]
        with tempfile.NamedTemporaryFile(suffix=".y4m", delete=False) as handle:
            path = handle.name
            handle.write(b"YUV4MPEG2 W4 H2 F24:1 Ip A1:1 C420p10\n")
            for index, frame in enumerate(frames):
                handle.write(f"FRAME Xindex={index}\n".encode("ascii"))
                handle.write(frame.astype("<u2").tobytes())
                handle.write(cb[index].astype("<u2").tobytes())
                handle.write(cr[index].astype("<u2").tobytes())
        try:
            selected = strength_selection_report.decode_y4m_selected(
                path, width, height, [1, 3], bits)
            np.testing.assert_array_equal(selected[1], frames[1])
            np.testing.assert_array_equal(selected[3], frames[3])
            self.assertEqual(list(selected), [1, 3])
            selected_u = strength_selection_report.decode_y4m_selected(
                path, width, height, [0, 2], bits, plane="u")
            selected_v = strength_selection_report.decode_y4m_selected(
                path, width, height, [0, 2], bits, plane="v")
            np.testing.assert_array_equal(selected_u[0], cb[0].reshape(1, 2))
            np.testing.assert_array_equal(selected_u[2], cb[2].reshape(1, 2))
            np.testing.assert_array_equal(selected_v[0], cr[0].reshape(1, 2))
            np.testing.assert_array_equal(selected_v[2], cr[2].reshape(1, 2))
        finally:
            os.unlink(path)

    def test_sparse_frame_expression_coalesces_adjacent_pairs(self):
        expression = strength_selection_report.selection_expression(
            [0, 1, 2, 8, 10, 11])
        self.assertEqual(
            expression,
            "between(n\\,0\\,2)+eq(n\\,8)+between(n\\,10\\,11)")
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            strength_selection_report.selection_expression([1, 0])

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
