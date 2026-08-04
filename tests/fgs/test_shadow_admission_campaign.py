#!/usr/bin/env python3

import unittest

import shadow_admission_campaign as shadow


POLICY = {
    "name": "test",
    "routing_authority": False,
    "cross_frame_correlation_max": 0.127,
    "anisotropy_mismatch_max": 0.032,
}


def entry(correlation=0.1, anisotropy=0.02, status="OK"):
    return {
        "status": status,
        "film_like_evidence": {
            "cross_frame_correlation": {"mean": correlation}},
        "model_fidelity": {
            "distance": {"held_out": {"anisotropy_abs": anisotropy}}},
    }


class ShadowAdmissionTests(unittest.TestCase):
    def test_both_axes_are_required_at_inclusive_boundary(self):
        accepted = shadow.shadow_entry(entry(0.127, 0.032), POLICY)
        correlation_reject = shadow.shadow_entry(entry(0.128, 0.01), POLICY)
        anisotropy_reject = shadow.shadow_entry(entry(0.01, 0.033), POLICY)
        self.assertIs(accepted["would_admit"], True)
        self.assertIs(correlation_reject["would_admit"], False)
        self.assertIs(anisotropy_reject["would_admit"], False)

    def test_insufficient_is_not_a_rejection(self):
        result = shadow.shadow_entry(
            entry(status="INSUFFICIENT_COVERAGE"), POLICY)
        self.assertIsNone(result["would_admit"])
        self.assertEqual(result["status"], "INSUFFICIENT_COVERAGE")

    def test_shadow_never_emits_a_routing_verdict(self):
        report = shadow.shadow_report(
            {"entries": [entry()], "summary": {}}, POLICY)
        self.assertIsNone(report["routing_verdict"])
        self.assertIs(report["changes_output"], False)
        self.assertEqual(report["interval_counts"]["admit"], 1)

    def test_scene_inconsistency_stays_visible(self):
        rows = [
            {"title": "Film", "reference_class": "film-positive",
             "shadow": {"title_diagnostic": {"would_admit": True}}},
            {"title": "Film", "reference_class": "film-positive",
             "shadow": {"title_diagnostic": {"would_admit": False}}},
        ]
        summary = shadow.corpus_summary(rows)
        self.assertFalse(summary["by_title"]["Film"]["scene_consistent"])
        self.assertIsNone(summary["routing_verdict"])


if __name__ == "__main__":
    unittest.main()
