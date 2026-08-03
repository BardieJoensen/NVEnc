#!/usr/bin/env python3
import unittest
from pathlib import Path

from integrated_quality_report import COLOR, CROP, crop_command


class IntegratedQualityReportTests(unittest.TestCase):
    def test_reference_crop_has_no_av1_decoder_override(self):
        command = crop_command(
            Path("ffmpeg"), Path("source.mkv"), Path("reference.mkv"), 287)
        self.assertNotIn("libdav1d", command)
        self.assertIn(CROP, command)
        self.assertIn("287", command)

    def test_av1_crop_selects_normative_grain_state(self):
        base = crop_command(
            Path("ffmpeg"), Path("arm.mkv"), Path("base.mkv"), 288, 0)
        finished = crop_command(
            Path("ffmpeg"), Path("arm.mkv"), Path("finished.mkv"), 288, 1)
        self.assertIn("libdav1d", base)
        self.assertEqual(base[base.index("-filmgrain") + 1], "0")
        self.assertEqual(finished[finished.index("-filmgrain") + 1], "1")

    def test_crops_restore_explicit_hdr_color_metadata(self):
        command = crop_command(
            Path("ffmpeg"), Path("arm.mkv"), Path("out.mkv"), 288, 1)
        for value in COLOR:
            self.assertIn(value, command)
        self.assertIn("yuv420p10le", command)


if __name__ == "__main__":
    unittest.main()
