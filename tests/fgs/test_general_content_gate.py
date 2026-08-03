#!/usr/bin/env python3
import copy
import os
from pathlib import Path
import tempfile
import unittest


os.sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import filmgrn
import general_content_gate as gate


class GeneralContentGateTest(unittest.TestCase):
    def test_source_fit_is_the_only_analyser_option_delta(self):
        production = gate.fgs_options("candidate-control")
        source = gate.fgs_options("bilateral-source")
        self.assertEqual(source, production + ",modelsrc=on")
        self.assertIsNone(gate.fgs_options("plain"))

    def test_encode_command_reproduces_flow_operating_point(self):
        command = gate.encode_command(
            Path("/bin/nvencc"), Path("clip.mkv"), Path("out.mkv"),
            Path("out.tbl"), "bilateral-source", 34)
        self.assertIn("--qvbr", command)
        self.assertEqual(command[command.index("--qvbr") + 1], "34")
        for option in ("--preset", "--tune", "--aq", "--aq-temporal"):
            self.assertIn(option, command)
        self.assertEqual(command[command.index("--preset") + 1], "quality")
        self.assertEqual(command[command.index("--tune") + 1], "hq")
        grain = command[command.index("--av1-film-grain") + 1]
        self.assertEqual(
            grain,
            "denoise=auto,chroma=auto,denoiser=bilateral,modelsrc=on")

    def test_plain_command_has_no_fgs_or_table(self):
        command = gate.encode_command(
            Path("/bin/nvencc"), Path("clip.mkv"), Path("out.mkv"),
            None, "plain", 29)
        self.assertNotIn("--av1-film-grain", command)
        self.assertNotIn("--film-grain-table-out", command)

    def test_color_args_ignore_unknown_fields(self):
        self.assertEqual(gate.color_args({
            "color_range": "tv",
            "color_space": "bt709",
            "color_transfer": "unknown",
            "color_primaries": None,
        }), ["-color_range", "tv", "-colorspace", "bt709"])

    def test_table_summary_distinguishes_no_grain_and_grain(self):
        entry = {
            "start": 0,
            "end": 100,
            "apply_grain": True,
            "random_seed": 1,
            "update_parameters": True,
            "params": {
                "ar_coeff_lag": 0,
                "ar_coeff_shift": 6,
                "grain_scale_shift": 0,
                "scaling_shift": 8,
                "chroma_scaling_from_luma": 0,
                "overlap_flag": 1,
                "cb_mult": 0,
                "cb_luma_mult": 0,
                "cb_offset": 0,
                "cr_mult": 0,
                "cr_luma_mult": 0,
                "cr_offset": 0,
            },
            "scaling_points": {
                "y": [[0, 8], [255, 8]], "cb": [], "cr": []},
            "ar_coeffs": {"y": [], "cb": [0], "cr": [0]},
        }
        no_grain = copy.deepcopy(entry)
        no_grain["apply_grain"] = False
        no_grain["update_parameters"] = False
        no_grain["params"] = {}
        no_grain["scaling_points"] = {"y": [], "cb": [], "cr": []}
        no_grain["ar_coeffs"] = {"y": [], "cb": [], "cr": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table.tbl"
            filmgrn.write(path, [no_grain, entry])
            summary = gate.table_summary(path)
        self.assertEqual(summary["entries"], 2)
        self.assertEqual(summary["grain_updates"], 1)
        self.assertEqual(summary["grain_interval_fraction"], 0.5)
        self.assertEqual(summary["mean_scaling_points"]["y"], 2)
        self.assertAlmostEqual(
            summary["mean_normalized_curve_rms"]["y"], 8 / 256)


if __name__ == "__main__":
    unittest.main()
