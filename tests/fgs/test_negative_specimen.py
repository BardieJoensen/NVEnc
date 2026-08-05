#!/usr/bin/env python3
"""Host-only tests for the negative-specimen harness.

These cover the decision arithmetic and the two safety behaviours that have
previously produced wrong results in this project: silently measuring the wrong
arm when a research hook is ignored, and mixing measurements taken against
different references.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import negative_specimen as ns


def axis(h1, h2, v1, v2):
    return {"h1": h1, "h2": h2, "v1": v1, "v2": v2}


def report(o_truth, c_axis, synth_axis, fgs_total=1.0, plain_total=0.5,
           fgs_err=0.20, plain_err=0.10):
    """Mirrors temporal_grain_report's real JSON: top-level truth, arms dict."""
    return {
        "truth": o_truth,
        "arms": {
            "C": {"total": {"axis": c_axis,
                            "amplitude_ratio": {"mean": 0.24}},
                  "total_axis_error_to_truth": {"mean": 0.21}},
            "C_plain": {"total": {"axis": c_axis,
                                  "amplitude_ratio": {"mean": plain_total}},
                        "total_axis_error_to_truth": {"mean": plain_err}},
            "C_fgs": {"synth": {"axis": synth_axis},
                      "total": {"axis": synth_axis,
                                "amplitude_ratio": {"mean": fgs_total}},
                      "total_axis_error_to_truth": {"mean": fgs_err}},
        },
    }


class AxisDistance(unittest.TestCase):
    def test_mean_absolute_difference(self):
        self.assertAlmostEqual(
            ns.axis_distance(axis(0.8, 0.4, 0.8, 0.4),
                             axis(0.9, 0.5, 0.7, 0.3)), 0.1)

    def test_missing_axes_are_skipped_not_zeroed(self):
        left = {"h1": 0.5, "h2": None, "v1": 0.5, "v2": 0.5}
        right = {"h1": 0.7, "h2": 0.9, "v1": 0.7, "v2": 0.7}
        self.assertAlmostEqual(ns.axis_distance(left, right), 0.2)

    def test_no_shared_axes_returns_none(self):
        self.assertIsNone(ns.axis_distance({"h1": None}, {"h1": 0.5}))


class TruthAxis(unittest.TestCase):
    def test_reads_top_level_truth(self):
        doc = report(axis(0.80, 0.40, 0.82, 0.44), axis(0.9, 0.7, 0.9, 0.7),
                     axis(0.85, 0.6, 0.85, 0.6))
        self.assertAlmostEqual(ns.truth_axis(doc)["h1"], 0.80)
        self.assertAlmostEqual(ns.truth_axis(doc)["h2"], 0.40)

    def test_arm_accessor_reaches_into_arms(self):
        doc = report(axis(0.8, 0.4, 0.8, 0.4), axis(0.9, 0.7, 0.9, 0.7),
                     axis(0.85, 0.6, 0.85, 0.6))
        self.assertIn("synth", ns.arm(doc, "C_fgs"))


class Verdict(unittest.TestCase):
    """The decisive test: which reference does synthesis resemble?"""

    def test_synthesis_tracking_codec_noise_is_flagged(self):
        # O grain is 0.80/0.43; codec noise is much more correlated at 0.91/0.75
        out = ns.verdict(report(axis(0.80, 0.43, 0.80, 0.43),
                                axis(0.91, 0.75, 0.91, 0.75),
                                axis(0.89, 0.72, 0.89, 0.72)),
                         "C_fgs", "C", "C_plain")
        self.assertEqual(out["synth_matches"], "codec_noise")
        self.assertLess(out["synth_to_c"], out["synth_to_o"])

    def test_synthesis_tracking_source_grain_is_not_flagged(self):
        out = ns.verdict(report(axis(0.80, 0.43, 0.80, 0.43),
                                axis(0.91, 0.75, 0.91, 0.75),
                                axis(0.79, 0.45, 0.79, 0.45)),
                         "C_fgs", "C", "C_plain")
        self.assertEqual(out["synth_matches"], "source_grain")
        self.assertLess(out["synth_to_o"], out["synth_to_c"])

    def test_verdict_reports_both_distances_not_just_the_winner(self):
        out = ns.verdict(report(axis(0.80, 0.43, 0.80, 0.43),
                                axis(0.91, 0.75, 0.91, 0.75),
                                axis(0.89, 0.72, 0.89, 0.72)),
                         "C_fgs", "C", "C_plain")
        for key in ("o_grain_axis", "c_noise_axis", "fgs_synth_axis",
                    "synth_to_o", "synth_to_c"):
            self.assertIn(key, out)


class IgnoredHookIsFatal(unittest.TestCase):
    """Commit 9c37ab62 exists because a KAT silently tested the wrong arm."""

    def test_ignoring_line_raises_when_hooks_expected(self):
        with self.assertRaises(RuntimeError) as caught:
            ns.run([sys.executable, "-c",
                    "print('film-grain: ignoring NVENC_FGS_TEST_TEXTURE_LEAK')"],
                   expect_hooks=True)
        self.assertIn("ignored", str(caught.exception))

    def test_ignoring_line_is_allowed_when_no_hooks_requested(self):
        out = ns.run([sys.executable, "-c", "print('ignoring something')"],
                     expect_hooks=False)
        self.assertIn("ignoring", out)

    def test_nonzero_exit_raises(self):
        with self.assertRaises(RuntimeError):
            ns.run([sys.executable, "-c", "import sys; sys.exit(3)"])


class FrozenProtocol(unittest.TestCase):
    """Guards against silently drifting from the pre-registration."""

    def test_rates_match_preregistration(self):
        self.assertEqual(tuple(ns.RATES), (44, 50))

    def test_frames_match_the_repo_standing_set(self):
        self.assertEqual(ns.FRAMES, "10,58,106,154,202,250")

    def test_candidate_arm_requires_both_hooks(self):
        self.assertEqual(ns.CANDIDATE_ENV["NVENC_FGS_TEST_SOURCE_STATIC"], "on")
        self.assertEqual(ns.CANDIDATE_ENV["NVENC_FGS_TEST_TEXTURE_LEAK"],
                         "response")
        self.assertIn("modelsrc=on", ns.FGS_OPTS)
        self.assertIn("denoiser=bilateral", ns.FGS_OPTS)


if __name__ == "__main__":
    unittest.main()
