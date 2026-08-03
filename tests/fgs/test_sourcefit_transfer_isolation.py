#!/usr/bin/env python3
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np


os.sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sourcefit_transfer_isolation as isolate


class SourceFitTransferIsolationTest(unittest.TestCase):
    def test_analysis_changes_only_model_source(self):
        residual = isolate.analysis_command(
            Path("nvencc"), Path("clip.mkv"), Path("base.y4m"),
            Path("table.tbl"), "residual")
        source = isolate.analysis_command(
            Path("nvencc"), Path("clip.mkv"), Path("base.y4m"),
            Path("table.tbl"), "source")
        self.assertNotIn("modelsrc=on", " ".join(residual))
        self.assertIn("modelsrc=on", " ".join(source))
        self.assertEqual(len(residual), len(source))

    def test_fixed_encode_has_no_analyser(self):
        command = isolate.fixed_encode_command(
            Path("nvencc"), Path("base.y4m"), Path("out.mkv"),
            Path("table.tbl"), 29)
        self.assertIn("--film-grain-table", command)
        self.assertNotIn("--av1-film-grain", command)
        self.assertEqual(command[command.index("--qvbr") + 1], "29")

    def test_none_table_is_a_plain_fixed_base_encode(self):
        command = isolate.fixed_encode_command(
            Path("nvencc"), Path("base.y4m"), Path("out.mkv"), None, 34)
        self.assertNotIn("--film-grain-table", command)
        self.assertNotIn("--av1-film-grain", command)

    def test_size_decomposition_is_factorial(self):
        sizes = {
            "residual-base_none-table": 90,
            "residual-base_residual-table": 100,
            "residual-base_source-table": 120,
            "source-base_none-table": 99,
            "source-base_residual-table": 110,
            "source-base_source-table": 132,
        }
        result = isolate.size_decomposition(sizes)
        self.assertEqual(result["combined_source_vs_residual_percent"], 32.0)
        self.assertEqual(result["base_effect_percent"]["none"], 10.0)
        self.assertEqual(result["base_effect_percent"]["residual"], 10.0)
        self.assertEqual(result["source_table_effect_percent"]["residual"], 20.0)
        self.assertEqual(result["source_table_effect_percent"]["source"], 20.0)

    def test_raw_base_comparison_is_sample_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left.y4m"
            right = Path(directory) / "right.y4m"
            header = b"YUV4MPEG2 W4 H2 F24:1 Ip A1:1 C420p10\n"
            chroma = np.array([400, 401, 402, 403], dtype="<u2").tobytes()
            left_frames = (
                np.array([0, 4, 8, 12, 16, 20, 24, 28], dtype="<u2"),
                np.array([32, 36, 40, 44, 48, 52, 56, 60], dtype="<u2"),
            )
            right_frames = (
                np.array([0, 3, 8, 10, 16, 20, 24, 28], dtype="<u2"),
                np.array([32, 36, 40, 44, 52, 52, 56, 60], dtype="<u2"),
            )
            for path, frames in ((left, left_frames), (right, right_frames)):
                with path.open("wb") as handle:
                    handle.write(header)
                    for values in frames:
                        handle.write(b"FRAME\n")
                        handle.write(values.tobytes())
                        handle.write(chroma)
            result = isolate.compare_y4m_bases(left, right, 2)
        self.assertEqual(result["luma"]["samples"], 16)
        self.assertEqual(result["luma"]["changed_samples"], 3)
        self.assertEqual(result["luma"]["delta_histogram"], {
            "-2": 1, "-1": 1, "4": 1})
        self.assertAlmostEqual(result["luma"]["signed_mean_10bit_codes"], 1 / 16)
        self.assertEqual(result["chroma"]["changed_samples"], 0)

    def test_raw_base_comparison_labels_same_arm_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "left.y4m"
            right = Path(directory) / "right.y4m"
            payload = np.zeros(12, dtype="<u2").tobytes()
            for path in (left, right):
                with path.open("wb") as handle:
                    handle.write(b"YUV4MPEG2 W4 H2 F24:1 Ip A1:1 C420p10\n")
                    handle.write(b"FRAME\n")
                    handle.write(payload)
            result = isolate.compare_y4m_bases(
                left, right, 1, direction="repeat 2 minus repeat 1")
        self.assertEqual(result["direction"], "repeat 2 minus repeat 1")
        self.assertEqual(result["luma"]["changed_samples"], 0)


if __name__ == "__main__":
    unittest.main()
