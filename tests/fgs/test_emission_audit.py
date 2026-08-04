#!/usr/bin/env python3
import json
import unittest
from unittest import mock

import numpy as np

import av1_grain
import emission_audit


class EmissionAuditTests(unittest.TestCase):
    def test_probe_can_ignore_unselected_grain_off_interval(self):
        side_data = {
            "side_data_type": "Film grain parameters", "seed": "1",
        }
        frames = [
            {"side_data_list": [side_data]},
            {"side_data_list": []},
            {"side_data_list": [side_data]},
        ]
        completed = mock.Mock(stdout=json.dumps({"frames": frames}))
        with mock.patch.object(
                emission_audit.subprocess, "run", return_value=completed), \
                mock.patch.object(
                    emission_audit, "entry_from_side_data",
                    side_effect=lambda value: {"seed": int(value["seed"])}) as parse:
            entries = emission_audit.probe_grain_entries(
                "candidate.mkv", 3, required_frames={0, 2})
            self.assertEqual(sorted(entries), [0, 2])
            self.assertEqual(parse.call_count, 2)
            with self.assertRaisesRegex(ValueError, "frame 1"):
                emission_audit.probe_grain_entries("candidate.mkv", 3)

    def test_encoded_path_supports_labelled_and_single_stream_reports(self):
        self.assertEqual(
            emission_audit.encoded_path_for_arm(
                {"encoded_arms": {"q29": "/tmp/q29.mkv"}}, "q29"),
            "/tmp/q29.mkv")
        self.assertEqual(
            emission_audit.encoded_path_for_arm(
                {"encoded": "/tmp/paired.mkv"}, "encoded"),
            "/tmp/paired.mkv")
        with self.assertRaises(ValueError):
            emission_audit.encoded_path_for_arm(
                {"encoded": "/tmp/paired.mkv"}, "paired")

    def test_delivered_row_supports_both_closure_layouts(self):
        labelled = {"encoded_arms": {"q29": {"synth_ratio": 0.9}}}
        legacy = {"encoded": {"synth_ratio": 0.8}}
        self.assertIs(
            emission_audit.delivered_for_arm(labelled, "q29"),
            labelled["encoded_arms"]["q29"])
        self.assertIs(
            emission_audit.delivered_for_arm(legacy, "encoded"),
            legacy["encoded"])
        with self.assertRaises(ValueError):
            emission_audit.delivered_for_arm(legacy, "q29")

    def test_entry_for_frame_uses_table_timebase(self):
        entries = [
            {"start": 0, "end": 1_000_000},
            {"start": 1_000_000, "end": 2_000_000},
        ]
        self.assertIs(entries[0], emission_audit.entry_for_frame(
            entries, 2, 24, 1))
        self.assertIs(entries[1], emission_audit.entry_for_frame(
            entries, 3, 24, 1))

    def test_side_data_preserves_bitstream_seed_and_luma_model(self):
        side_data = {
            "seed": "7391",
            "ar_coeff_lag": 1,
            "ar_coeff_shift": 6,
            "grain_scale_shift": 2,
            "scaling_shift": 11,
            "overlap_flag": 1,
            "limit_output_range": 1,
            "chroma_scaling_from_luma": 0,
            "components": [{
                "y_points_value": "0 255",
                "y_points_scaling": "4 8",
                "ar_coeffs_y": "1 2 3 4",
            }, {
                "uv_points_value": "0 255",
                "uv_points_scaling": "3 5",
                "ar_coeffs_uv": "1 2 3 4 5",
                "uv_mult": 7,
                "uv_mult_luma": 8,
                "uv_offset": 9,
            }, {
                "uv_points_value": "0 255",
                "uv_points_scaling": "6 7",
                "ar_coeffs_uv": "5 4 3 2 1",
                "uv_mult": 10,
                "uv_mult_luma": 11,
                "uv_offset": 12,
            }],
        }
        entry = emission_audit.entry_from_side_data(side_data)
        self.assertEqual(entry["random_seed"], 7391)
        self.assertEqual(entry["scaling_points"]["y"], [[0, 4], [255, 8]])
        self.assertEqual(entry["scaling_points"]["cb"], [[0, 3], [255, 5]])
        self.assertEqual(entry["scaling_points"]["cr"], [[0, 6], [255, 7]])
        self.assertEqual(entry["ar_coeffs"]["y"], [1, 2, 3, 4])
        self.assertEqual(entry["ar_coeffs"]["cb"], [1, 2, 3, 4, 5])
        self.assertEqual(entry["params"]["cb_luma_mult"], 8)
        self.assertEqual(entry["params"]["cr_offset"], 12)
        self.assertTrue(entry["limit_output_range"])

    def test_table_match_accounts_for_normative_chroma_parameter_bias(self):
        stream = emission_audit.entry_from_side_data({
            "seed": "7391",
            "ar_coeff_lag": 0,
            "ar_coeff_shift": 6,
            "grain_scale_shift": 2,
            "scaling_shift": 11,
            "overlap_flag": 1,
            "limit_output_range": 1,
            "chroma_scaling_from_luma": 0,
            "components": [
                {"y_points_value": "0", "y_points_scaling": "4"},
                {"uv_points_value": "0", "uv_points_scaling": "3",
                 "ar_coeffs_uv": "5", "uv_mult": 0,
                 "uv_mult_luma": 64, "uv_offset": 0},
                {"uv_points_value": "0", "uv_points_scaling": "2",
                 "ar_coeffs_uv": "6", "uv_mult": 0,
                 "uv_mult_luma": 64, "uv_offset": 0},
            ],
        })
        table = {
            "params": dict(stream["params"]),
            "scaling_points": stream["scaling_points"],
            "ar_coeffs": stream["ar_coeffs"],
        }
        table["params"].update({
            "cb_mult": 128, "cb_luma_mult": 192, "cb_offset": 256,
            "cr_mult": 128, "cr_luma_mult": 192, "cr_offset": 256,
        })
        self.assertTrue(emission_audit.table_matches_stream(table, stream))

    def test_high_bit_depth_lut_interpolates_low_bits(self):
        lut = np.arange(256, dtype=np.int64) * 4
        pixels = np.asarray([0, 1, 2, 3, 4, 1020, 1023])
        self.assertEqual(
            av1_grain.scale_values(lut, pixels, 10).tolist(),
            [0, 1, 2, 3, 4, 1020, 1020])

    def test_chroma_scaling_uses_normative_horizontal_luma_average(self):
        luma = np.arange(32 * 32, dtype=np.int64).reshape(32, 32) % 1024
        chroma = np.full((16, 16), 777, dtype=np.int64)
        entry = {
            "params": {
                "chroma_scaling_from_luma": 0,
                "cb_mult": 0,
                "cb_luma_mult": 64,
                "cb_offset": 0,
            },
            "scaling_points": {
                "y": [[0, 0], [255, 255]],
                "cb": [[0, 0], [255, 255]],
                "cr": [],
            },
        }
        response = av1_grain.selected_chroma_scaling(
            luma, chroma, [(0, 0)], entry, 10, "cb")
        expected = (luma[::2, 0::2] + luma[::2, 1::2] + 1) >> 1
        np.testing.assert_array_equal(response["indices"][0], expected)
        # The signed chroma multiplier is zero, so changing Cb cannot move the
        # lookup coordinate despite chroma_scaling_from_luma being false.
        response_changed = av1_grain.selected_chroma_scaling(
            luma, chroma - 500, [(0, 0)], entry, 10, "cb")
        np.testing.assert_array_equal(
            response_changed["indices"], response["indices"])

    def test_chroma_rng_uses_plane_specific_normative_seed_offset(self):
        gaussian = np.arange(2048, dtype=np.int64) - 1024
        entry = {
            "random_seed": 7391,
            "params": {
                "ar_coeff_lag": 0,
                "ar_coeff_shift": 6,
                "grain_scale_shift": 0,
                "chroma_scaling_from_luma": 0,
            },
            "scaling_points": {
                "y": [[0, 1]], "cb": [[0, 1]], "cr": [[0, 1]],
            },
            "ar_coeffs": {"y": [], "cb": [0], "cr": [0]},
        }
        luma_template = av1_grain.generate_luma_template(entry, gaussian, 8)
        cb = av1_grain.generate_chroma_template(
            entry, luma_template, gaussian, 8, "cb")
        cr = av1_grain.generate_chroma_template(
            entry, luma_template, gaussian, 8, "cr")
        cb_register = av1_grain.init_random_generator(7 << 5, 7391)
        cr_register = av1_grain.init_random_generator(11 << 5, 7391)
        _cb_register, cb_index = av1_grain.random_number(cb_register, 11)
        _cr_register, cr_index = av1_grain.random_number(cr_register, 11)
        self.assertEqual(cb[0, 0], (int(gaussian[cb_index]) + 8) >> 4)
        self.assertEqual(cr[0, 0], (int(gaussian[cr_index]) + 8) >> 4)
        self.assertNotEqual(cb[0, 0], cr[0, 0])

    def test_lfsr_matches_known_first_step(self):
        register, value = av1_grain.random_number(7391, 8)
        self.assertEqual(register, 3695)
        self.assertEqual(value, 14)

    def test_oracle_seeds_are_repeatable_nonzero_and_spread(self):
        first = [emission_audit.oracle_seed(10, index) for index in range(32)]
        second = [emission_audit.oracle_seed(10, index) for index in range(32)]
        following = [emission_audit.oracle_seed(11, index) for index in range(32)]
        self.assertEqual(first, second)
        self.assertNotIn(0, first)
        self.assertGreaterEqual(len(set(first)), 31)
        self.assertNotEqual(first, following)

    def test_axis_stats_are_amplitude_invariant(self):
        blocks = np.arange(2 * 32 * 32, dtype=np.float64).reshape(2, 32, 32)
        first = emission_audit.selected_axis_stats(blocks)
        second = emission_audit.selected_axis_stats(blocks * 7.0)
        for key in first:
            self.assertAlmostEqual(first[key], second[key])

    def test_selected_luma_band_positions_use_fixed_ranges(self):
        source = np.zeros((64, 64), dtype=np.float64)
        source[:32, :32] = 32
        source[:32, 32:] = 96
        source[32:, :32] = 160
        source[32:, 32:] = 224
        blocks = [(0, 0), (0, 1), (1, 0), (1, 1)]
        ranges = [[0.0, 0.5], [0.5, 1.0]]
        self.assertEqual(
            emission_audit.selected_luma_band_positions(
                source, blocks, 8, ranges),
            [[0, 1], [2, 3]])


if __name__ == "__main__":
    unittest.main()
