import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import chroma_amplitude_compare


def report(plane, actual, target, played, truth, blocks=100):
    def record(scale=1.0):
        return {
            "blocks": blocks,
            "sigma": {
                "actual": actual * scale,
                "target": target * scale,
                "played": played * scale,
                "truth": truth * scale,
            },
            "pixel_mismatches": 0,
        }

    return {
        "plane": plane,
        "bits": 10,
        "table_models_match_stream": True,
        "aggregate": record(),
        "luma_bins": [{"range": [0.0, 0.5], **record(0.5)}],
    }


class ChromaAmplitudeCompareTest(unittest.TestCase):
    def test_load_and_compare(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm, played in (("control", 3.6), ("candidate", 3.9)):
                path = root / arm / "Film"
                path.mkdir(parents=True)
                (path / "emission-u.json").write_text(json.dumps(
                    report("u", actual=played, target=4.0,
                           played=played, truth=4.0)))

            control = chroma_amplitude_compare.load_arm(
                root / "control", ("Film",), "u", "emission-{plane}.json")
            candidate = chroma_amplitude_compare.load_arm(
                root / "candidate", ("Film",), "u", "emission-{plane}.json")
            delta = chroma_amplitude_compare.compare(control, candidate)

            self.assertAlmostEqual(
                control["title_summary"]["played_ratio_error"]["mae"], 0.1)
            self.assertAlmostEqual(
                candidate["title_summary"]["played_ratio_error"]["mae"], 0.025)
            self.assertAlmostEqual(
                candidate["titles"][0]["played_sigma_error_8bit"], -0.025)
            self.assertAlmostEqual(
                delta["title_summary"]["played_ratio_error"]["mae"], -0.075)

    def test_rejects_normative_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Film"
            path.mkdir()
            value = report("v", 4.0, 4.0, 4.0, 4.0)
            value["aggregate"]["pixel_mismatches"] = 1
            (path / "emission-v.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "dav1d pixel mismatches"):
                chroma_amplitude_compare.load_arm(
                    Path(directory), ("Film",), "v", "emission-{plane}.json")


if __name__ == "__main__":
    unittest.main()
