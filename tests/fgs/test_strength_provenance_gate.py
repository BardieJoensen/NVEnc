#!/usr/bin/env python3
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


os.sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strength_provenance_gate as gate  # noqa: E402


class StrengthProvenanceGateTest(unittest.TestCase):
    def test_environments_clean_ambient_hooks_and_activate_one_treatment(self):
        inherited = {
            "PATH": "/bin",
            "NVENC_FGS_TEST_TEXTURE_LEAK": "response",
            gate.HOOK: "wrong",
        }
        control = gate.arm_environment(gate.CONTROL_ARM, inherited)
        self.assertEqual(control, {
            "PATH": "/bin", "NVENC_FGS_TEST_SOURCE_STATIC": "on"})
        for arm, value in gate.HOOK_VALUE.items():
            with self.subTest(arm=arm):
                env = gate.arm_environment(arm, inherited)
                self.assertEqual(env[gate.HOOK], value)
                self.assertEqual(env["NVENC_FGS_TEST_SOURCE_STATIC"], "on")
                self.assertNotIn("NVENC_FGS_TEST_TEXTURE_LEAK", env)

    def test_temporal_command_has_frozen_report_arms_once(self):
        encoded = {arm: Path(f"{arm}.mkv") for arm in gate.REPORT_ARMS}
        command = gate.temporal_command(
            Path("measure.py"), Path("reel.mkv"), encoded, "v", [6, 12],
            Path("out.json"))
        labels = [command[index + 1].split("=", 1)[0]
                  for index, token in enumerate(command) if token == "--arm"]
        self.assertEqual(tuple(labels), gate.REPORT_ARMS)
        self.assertEqual(command[command.index("--minimum-frames") + 1], "0")

    def test_log_validation_requires_exact_activation(self):
        common = (
            "fgs-model foo\n"
            "film-grain: fitting the test-only source model from temporally "
            "static blocks.\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "encode.log"
            path.write_text(common + gate.ACTIVATION["texture-residual-all"] + "\n")
            gate.validate_encode_log("texture-residual-all", path)
            with self.assertRaisesRegex(RuntimeError, "leaked"):
                gate.validate_encode_log(gate.CONTROL_ARM, path)
            path.write_text(common)
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                gate.validate_encode_log("texture-source-yu", path)

    def test_control_isolation_requires_all_three_artifacts(self):
        parent = {
            "video_stream_md5": "a",
            "base_pixel_sha256": "b",
            "table": {"identity": {"sha256": "c"}},
        }
        control = {
            "video_stream_md5": "a",
            "base_pixel_sha256": "b",
            "table": {"identity": {"sha256": "c"}},
        }
        self.assertTrue(gate.control_isolation(parent, control)["passed"])
        control["base_pixel_sha256"] = "changed"
        self.assertFalse(gate.control_isolation(parent, control)["passed"])

    def test_stream_texture_isolation_uses_actual_frame_side_data(self):
        entry = {
            "params": {"ar_coeff_lag": 3, "ar_coeff_shift": 7,
                       "grain_scale_shift": 1},
            "ar_coeffs": {"y": [1], "cb": [2], "cr": [3]},
        }
        changed = {
            "params": dict(entry["params"]),
            "ar_coeffs": {"y": [1], "cb": [2], "cr": [4]},
        }
        with mock.patch.object(
                gate.emission_audit, "probe_grain_entries",
                side_effect=[{0: entry, 2: entry}, {0: entry, 2: changed}]):
            result = gate.stream_texture_isolation(Path("a"), Path("b"), 3)
        self.assertEqual(result["jointly_grained_frames"], 2)
        self.assertEqual(result["all_texture_fields_identical_frames"], 1)
        self.assertEqual(result["ar_coefficients_identical_frames"]["cr"], 1)
        self.assertFalse(result["fully_isolated"])


if __name__ == "__main__":
    unittest.main()
