#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from unittest import mock


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import review_score  # noqa: E402


def probe(path, count=288, width=1920, height=1080, period=1 / 24):
    return {
        "path": path,
        "codec": "ffv1",
        "width": width,
        "height": height,
        "avg_frame_rate": "24/1",
        "pix_fmt": "yuv420p10le",
        "color_range": "tv",
        "color_space": "bt2020nc",
        "color_transfer": "smpte2084",
        "color_primaries": "bt2020",
        "timestamps": [index * period for index in range(count)],
    }


class AlignmentTests(unittest.TestCase):
    def test_accepts_equal_short_pair_and_reports_real_count(self):
        with mock.patch.object(
                review_score, "probe_video",
                side_effect=[probe("ref", 287), probe("dist", 287)]):
            count, _, _ = review_score.aligned_frame_count("ref", "dist")
        self.assertEqual(count, 287)

    def test_rejects_frame_count_mismatch(self):
        with mock.patch.object(
                review_score, "probe_video",
                side_effect=[probe("ref", 287), probe("dist", 288)]):
            with self.assertRaisesRegex(RuntimeError, "frame-count mismatch"):
                review_score.aligned_frame_count("ref", "dist")

    def test_rejects_dropped_frame_timeline(self):
        reference = probe("ref", 8)
        distorted = probe("dist", 8)
        distorted["timestamps"][4:] = [value + 1 / 24
                                        for value in distorted["timestamps"][4:]]
        with mock.patch.object(
                review_score, "probe_video", side_effect=[reference, distorted]):
            with self.assertRaisesRegex(RuntimeError, "timeline mismatch"):
                review_score.aligned_frame_count("ref", "dist")

    def test_rejects_dimension_mismatch_unless_transform_declared(self):
        pair = [probe("ref"), probe("dist", width=3840, height=2160)]
        with mock.patch.object(review_score, "probe_video", side_effect=pair):
            with self.assertRaisesRegex(RuntimeError, "dimension mismatch"):
                review_score.aligned_frame_count("ref", "dist")
        pair = [probe("ref"), probe("dist", width=3840, height=2160)]
        with mock.patch.object(review_score, "probe_video", side_effect=pair):
            count, _, _ = review_score.aligned_frame_count(
                "ref", "dist", allow_dimension_mismatch=True)
        self.assertEqual(count, 288)

    def test_explicit_limit_can_exceed_review_default(self):
        with mock.patch.object(
                review_score, "probe_video",
                side_effect=[probe("ref", 600), probe("dist", 600)]):
            count, _, _ = review_score.aligned_frame_count(
                "ref", "dist", limit=600)
        self.assertEqual(count, 600)


class ArtifactValidationTests(unittest.TestCase):
    def test_rejects_color_metadata_mismatch(self):
        reference = probe("ref")
        distorted = probe("dist")
        distorted["color_transfer"] = None
        with self.assertRaisesRegex(RuntimeError, "color metadata mismatch"):
            review_score.require_matching_color(reference, distorted)

    def test_accepts_matching_color_metadata(self):
        signature = review_score.require_matching_color(
            probe("ref"), probe("dist"))
        self.assertEqual(signature["color_transfer"], "smpte2084")

    def test_rejects_short_vmaf_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "score.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"frames": [{"metrics": {"vmaf": 1.0}}]}, handle)
            with self.assertRaisesRegex(RuntimeError, "scored 1 frames, expected 2"):
                review_score._validate_vmaf(path, 2, {"vmaf": "model"})

    def test_rejects_null_metric_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "score.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"frames": [{"metrics": {"vmaf": None}}]}, handle)
            with self.assertRaisesRegex(RuntimeError, "1 null frames"):
                review_score._validate_vmaf(path, 1, {"vmaf": "model"})


if __name__ == "__main__":
    unittest.main()
