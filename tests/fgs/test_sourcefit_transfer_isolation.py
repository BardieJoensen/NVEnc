#!/usr/bin/env python3
import os
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
