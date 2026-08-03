#!/usr/bin/env python3
import unittest
from pathlib import Path

import bilateral_source_review


class BilateralSourceReviewTests(unittest.TestCase):
    def test_assignment_is_stable_and_complete(self):
        first = bilateral_source_review.assignment("Taxi_Driver")
        second = bilateral_source_review.assignment("Taxi_Driver")
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"A", "B"})
        self.assertEqual(set(first.values()), set(bilateral_source_review.ARMS))

    def test_command_forces_software_filmgrain_before_input(self):
        command = bilateral_source_review.build_command(
            Path("/usr/bin/ffmpeg"), Path("input.mkv"), Path("output.mkv"), 0)
        input_index = command.index("-i")
        self.assertLess(command.index("libdav1d"), input_index)
        self.assertLess(command.index("-filmgrain"), input_index)
        self.assertEqual(command[command.index("-filmgrain") + 1], "0")
        self.assertIn("crop=1920:1080:(iw-1920)/2:(ih-1080)/2", command)
        self.assertIn("ffv1", command)

    def test_input_paths_keep_separator_comparison_explicit(self):
        integrated = Path("/integrated")
        bilateral = Path("/bilateral")
        self.assertEqual(
            bilateral_source_review.input_for(
                "production bilateral/residual", "Casino", integrated, bilateral),
            Path("/integrated/Casino/production.mkv"))
        self.assertEqual(
            bilateral_source_review.input_for(
                "bilateral/source-fit", "Casino", integrated, bilateral),
            Path("/bilateral/Casino/bilateral-source.mkv"))


if __name__ == "__main__":
    unittest.main()
