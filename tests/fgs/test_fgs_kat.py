#!/usr/bin/env python3
import unittest

import fgs_kat


class TestHookConfigurationTests(unittest.TestCase):
    def test_ordinary_kat_needs_no_research_configuration(self):
        self.assertEqual(
            fgs_kat.test_hook_configuration_errors({}, "", ""), [])

    def test_rejects_the_previous_false_green_configuration(self):
        errors = fgs_kat.test_hook_configuration_errors({
            "NVENC_FGS_TEST_SOURCE_STATIC": "on",
            "NVENC_FGS_TEST_TEXTURE_LEAK": "response",
        }, "", "")
        self.assertTrue(any("QVBR" in error for error in errors))
        self.assertTrue(any("modelsrc" in error for error in errors))

    def test_accepts_active_response_hook_configuration(self):
        self.assertEqual(fgs_kat.test_hook_configuration_errors({
            "NVENC_FGS_TEST_SOURCE_STATIC": "on",
            "NVENC_FGS_TEST_TEXTURE_LEAK": "response",
        }, "modelsrc=on", "29"), [])

    def test_texture_hook_requires_static_source_population(self):
        errors = fgs_kat.test_hook_configuration_errors({
            "NVENC_FGS_TEST_TEXTURE_LEAK": "dynamic",
        }, "modelsrc=on", "29")
        self.assertTrue(any("SOURCE_STATIC" in error for error in errors))

    def test_nonzero_retain_is_rejected(self):
        errors = fgs_kat.test_hook_configuration_errors({
            "NVENC_FGS_TEST_SOURCE_STATIC": "on",
        }, "modelsrc=on,retain=0.5", "29")
        self.assertTrue(any("retain=0" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
