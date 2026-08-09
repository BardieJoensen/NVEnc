#!/usr/bin/env python3
import os
from pathlib import Path
import unittest


os.sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tail_architecture_gate as gate  # noqa: E402
import temporal_grain_report as temporal  # noqa: E402


class TailArchitectureGateTest(unittest.TestCase):
    def test_source_and_response_have_one_architectural_delta(self):
        self.assertEqual(
            gate.fgs_options("source"),
            gate.fgs_options("candidate-control") + ",modelsrc=on")
        source = gate.arm_environment("source", {"PATH": "/bin"})
        response = gate.arm_environment("response", {"PATH": "/bin"})
        self.assertEqual(source, {
            "PATH": "/bin", "NVENC_FGS_TEST_SOURCE_STATIC": "on"})
        expected = dict(source)
        expected["NVENC_FGS_TEST_TEXTURE_LEAK"] = "response"
        self.assertEqual(response, expected)

    def test_ambient_research_hooks_are_removed_from_every_arm(self):
        inherited = {
            "PATH": "/bin",
            "NVENC_FGS_TEST_MIN_NOISE": "999",
            "NVENC_FGS_TEST_MOTION_CENTERED": "paired",
        }
        for arm in gate.ARMS:
            with self.subTest(arm=arm):
                environment = gate.arm_environment(arm, inherited)
                self.assertNotIn("NVENC_FGS_TEST_MIN_NOISE", environment)
                self.assertNotIn("NVENC_FGS_TEST_MOTION_CENTERED", environment)

    def test_binary_control_boundary(self):
        production, candidate = Path("prod"), Path("candidate")
        for arm in ("plain", "production"):
            self.assertEqual(gate.binary_for(arm, production, candidate), production)
        for arm in ("candidate-control", "source", "response"):
            self.assertEqual(gate.binary_for(arm, production, candidate), candidate)

    def test_encode_reproduces_current_flow_operating_point(self):
        command = gate.encode_command(
            Path("nvencc"), Path("reel.mkv"), Path("out.mkv"),
            Path("out.tbl"), "response", 34)
        expected_pairs = {
            "--qvbr": "34", "--max-bitrate": "50000",
            "--preset": "quality", "--tune": "hq",
            "--lookahead": "32", "--lookahead-level": "3",
        }
        for option, value in expected_pairs.items():
            self.assertEqual(command[command.index(option) + 1], value)
        for switch in ("--aq", "--aq-temporal"):
            self.assertIn(switch, command)
        self.assertEqual(
            command[command.index("--av1-film-grain") + 1],
            gate.FGS + ",modelsrc=on")

    def test_plain_has_no_fgs_or_table(self):
        command = gate.encode_command(
            Path("nvencc"), Path("reel.mkv"), Path("out.mkv"),
            None, "plain", 30)
        self.assertNotIn("--av1-film-grain", command)
        self.assertNotIn("--film-grain-table-out", command)

    def test_animation_and_ordinary_qvbr_are_frozen(self):
        catalog = gate.title_map()
        self.assertEqual(catalog["Korra_S02E12"].qvbr, 34)
        self.assertEqual(catalog["Korra_S02E07"].qvbr, 34)
        for name in (
                "HIMYM_S04E17", "Abbott_S02E02", "Planet_Earth_S01E06",
                "HIMYM_S09E15", "Trying_S02E06"):
            self.assertEqual(catalog[name].qvbr, 30)

    def test_extract_is_lossless_progressive_without_deinterlacing(self):
        command = gate.extract_command(
            Path("ffmpeg"), Path("source.mkv"), Path("clip.mkv"), 10.0, 120,
            {"color_range": "tv", "color_space": "bt709"})
        self.assertEqual(command[command.index("-c:v") + 1], "ffv1")
        self.assertEqual(command[command.index("-pix_fmt") + 1], "yuv420p10le")
        self.assertEqual(command[command.index("-fps_mode") + 1], "passthrough")
        self.assertIn("setfield=prog", command[command.index("-vf") + 1])
        joined = " ".join(command)
        for forbidden in ("yadif", "bwdif", "deinterlace", "minterpolate"):
            self.assertNotIn(forbidden, joined)

    def test_soft_telecine_override_changes_timestamps_not_pixels(self):
        title = gate.title_map()["Planet_Earth_S01E06"]
        command = gate.extract_command(
            Path("ffmpeg"), Path("source.mkv"), Path("clip.mkv"), 10.0, 120,
            {}, title.decoded_rate)
        filters = command[command.index("-vf") + 1]
        self.assertIn("setpts=N*1001/24000/TB", filters)
        self.assertNotIn("fps=", filters)
        self.assertEqual(command[command.index("-r") + 1], "24000/1001")
        self.assertEqual(command[command.index("-fps_mode") + 1], "cfr")

    def test_thin_temporal_frames_are_recorded_not_replaced(self):
        rows = [(6, list(range(12))), (18, list(range(2))),
                (30, list(range(8)))]
        usable, skipped = temporal.partition_static_frames(
            rows, skip_thin=True, minimum_frames=2)
        self.assertEqual([frame for frame, _ in usable], [6, 30])
        self.assertEqual(skipped, [{"frame": 18, "static_blocks": 2}])
        with self.assertRaises(ValueError):
            temporal.partition_static_frames(rows, skip_thin=False)
        usable, skipped = temporal.partition_static_frames(
            [(6, []), (12, [])], skip_thin=True, minimum_frames=0)
        self.assertEqual(usable, [])
        self.assertEqual(len(skipped), 2)

    def test_temporal_grid_is_frozen_and_stays_inside_each_scene(self):
        self.assertEqual(gate.SAMPLE_OFFSETS, tuple(range(6, 115, 6)))
        self.assertLess(max(gate.SAMPLE_OFFSETS) + 1, 120)
        self.assertEqual(
            gate.MEASUREMENT_VERSION, "scene-grid-v3-ratio-of-means")

    def test_temporal_command_records_sparse_scenes_before_grading(self):
        encoded = {arm: Path(f"{arm}.mkv") for arm in gate.ARMS}
        command = gate.temporal_command(
            Path("report.py"), Path("source.mkv"), encoded, "y", [6, 12],
            Path("out.json"), minimum_frames=0)
        self.assertEqual(command[command.index("--minimum-frames") + 1], "0")


if __name__ == "__main__":
    unittest.main()
