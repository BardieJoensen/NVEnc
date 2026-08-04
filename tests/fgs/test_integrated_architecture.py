#!/usr/bin/env python3
import unittest
from pathlib import Path

from integrated_architecture import (
    arm_environment,
    build_clean_command,
    build_encode_command,
    partial_path,
    publish_outputs,
)


class IntegratedArchitectureHarnessTests(unittest.TestCase):
    def test_partial_path_preserves_media_suffix(self):
        self.assertEqual(
            partial_path(Path("paired.mkv")), Path("paired.partial.mkv"))
        self.assertEqual(
            partial_path(Path("paired-clean.y4m")),
            Path("paired-clean.partial.y4m"))

    def test_production_arm_is_deployed_bilateral_configuration(self):
        command = build_encode_command(
            Path("prod"), Path("source.mkv"), Path("out.mkv"),
            Path("out.tbl"), "production")
        self.assertIn("denoise=auto,chroma=auto,denoiser=bilateral", command)
        self.assertNotIn("modelsrc=on", " ".join(command))

    def test_candidate_arm_uses_source_fit_and_one_reference(self):
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "causal")
        joined = " ".join(command)
        self.assertIn("denoiser=motion,motion-refs=1,modelsrc=on", joined)
        self.assertIn("--codec raw", joined)

    def test_bilateral_source_arm_changes_model_not_separator(self):
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "bilateral-source")
        joined = " ".join(command)
        self.assertIn(
            "denoiser=bilateral,modelsrc=on", joined)
        self.assertNotIn("denoiser=motion", joined)
        self.assertNotIn(
            "NVENC_FGS_TEST_MOTION_CENTERED",
            arm_environment("bilateral-source"))

    def test_source_static_arm_is_explicit_control(self):
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "bilateral-source-static")
        self.assertIn("denoiser=bilateral,modelsrc=on", " ".join(command))
        environment = arm_environment("bilateral-source-static")
        self.assertEqual(environment["NVENC_FGS_TEST_SOURCE_STATIC"], "on")
        self.assertNotIn("NVENC_FGS_TEST_CHROMA_LEAK", environment)

    def test_dynamic_texture_arm_layers_only_covariance_closure(self):
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "bilateral-source-texture-dynamic")
        joined = " ".join(command)
        self.assertIn("denoiser=bilateral,modelsrc=on", joined)
        self.assertNotIn("denoiser=motion", joined)
        environment = arm_environment(
            "bilateral-source-texture-dynamic")
        self.assertEqual(environment["NVENC_FGS_TEST_SOURCE_STATIC"], "on")
        self.assertEqual(
            environment["NVENC_FGS_TEST_TEXTURE_LEAK"], "dynamic")
        self.assertNotIn("NVENC_FGS_TEST_CHROMA_LEAK", environment)

    def test_chroma_closure_arms_change_only_test_environment(self):
        baseline = arm_environment("bilateral-source")
        global_closure = arm_environment("bilateral-source-chroma-global")
        local_closure = arm_environment("bilateral-source-chroma-local")
        independent = arm_environment(
            "bilateral-source-chroma-independent")
        self.assertNotIn("NVENC_FGS_TEST_CHROMA_LEAK", baseline)
        self.assertEqual(
            global_closure["NVENC_FGS_TEST_CHROMA_LEAK"], "global")
        self.assertEqual(
            local_closure["NVENC_FGS_TEST_CHROMA_LEAK"], "local")
        self.assertEqual(
            independent["NVENC_FGS_TEST_CHROMA_LEAK"], "independent")
        self.assertEqual(independent["NVENC_FGS_TEST_SOURCE_STATIC"], "on")
        for arm in (
            "bilateral-source-chroma-global",
            "bilateral-source-chroma-local",
            "bilateral-source-chroma-independent",
        ):
            command = build_clean_command(
                Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
                Path("raw.tbl"), arm)
            joined = " ".join(command)
            self.assertIn("denoiser=bilateral,modelsrc=on", joined)
            self.assertNotIn("denoiser=motion", joined)

    def test_paired_and_causal_differ_only_by_paired_environment(self):
        causal = arm_environment("causal")
        paired = arm_environment("paired")
        self.assertEqual(causal["NVENC_FGS_TEST_MOTION_THSAD"], "640")
        self.assertEqual(paired["NVENC_FGS_TEST_MOTION_THSAD"], "640")
        self.assertNotIn("NVENC_FGS_TEST_MOTION_CENTERED", causal)
        self.assertEqual(paired["NVENC_FGS_TEST_MOTION_CENTERED"], "paired")

    def test_balanced_arm_keeps_paired_motion_test_only(self):
        paired = arm_environment("paired")
        balanced = arm_environment("balanced")
        self.assertEqual(
            balanced["NVENC_FGS_TEST_MOTION_THSAD"],
            paired["NVENC_FGS_TEST_MOTION_THSAD"])
        self.assertEqual(
            balanced["NVENC_FGS_TEST_MOTION_CENTERED"], "paired-balanced")
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "balanced")
        self.assertIn(
            "denoiser=motion,motion-refs=1,modelsrc=on", " ".join(command))

    def test_motion_finish_arms_change_only_test_environment(self):
        balanced = arm_environment("balanced")
        detail = arm_environment("balanced-detail")
        nofinish = arm_environment("balanced-nofinish")
        self.assertNotIn("NVENC_FGS_TEST_MOTION_FINISH", balanced)
        self.assertEqual(detail["NVENC_FGS_TEST_MOTION_FINISH"], "detail")
        self.assertEqual(nofinish["NVENC_FGS_TEST_MOTION_FINISH"], "off")
        for candidate in (detail, nofinish):
            self.assertEqual(
                candidate["NVENC_FGS_TEST_MOTION_CENTERED"],
                balanced["NVENC_FGS_TEST_MOTION_CENTERED"])
            self.assertEqual(
                candidate["NVENC_FGS_TEST_MOTION_THSAD"],
                balanced["NVENC_FGS_TEST_MOTION_THSAD"])
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "balanced-detail")
        self.assertIn(
            "denoiser=motion,motion-refs=1,modelsrc=on", " ".join(command))

    def test_robust_median_arm_is_explicit_and_detail_aware(self):
        balanced = arm_environment("balanced-detail")
        robust = arm_environment("balanced-median-detail")
        self.assertEqual(
            robust["NVENC_FGS_TEST_MOTION_CENTERED"],
            "paired-balanced-median")
        self.assertEqual(robust["NVENC_FGS_TEST_MOTION_FINISH"], "detail")
        self.assertEqual(
            robust["NVENC_FGS_TEST_MOTION_THSAD"],
            balanced["NVENC_FGS_TEST_MOTION_THSAD"])
        command = build_clean_command(
            Path("candidate"), Path("source.mkv"), Path("clean.y4m"),
            Path("raw.tbl"), "balanced-median-detail")
        self.assertIn(
            "denoiser=motion,motion-refs=1,modelsrc=on", " ".join(command))

    def test_plain_arm_has_no_film_grain_options_or_table(self):
        command = build_encode_command(
            Path("prod"), Path("source.mkv"), Path("plain.mkv"), None,
            "plain")
        self.assertNotIn("--av1-film-grain", command)
        self.assertNotIn("--film-grain-table-out", command)

    def test_encode_command_can_override_calibrated_qvbr(self):
        command = build_encode_command(
            Path("candidate"), Path("source.mkv"), Path("out.mkv"),
            Path("out.tbl"), "bilateral-source-static", qvbr=34)
        self.assertEqual(command[command.index("--qvbr") + 1], "34")

    def test_publish_rejects_mismatched_output_lists(self):
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            publish_outputs([Path("one.partial.mkv")], [])


if __name__ == "__main__":
    unittest.main()
