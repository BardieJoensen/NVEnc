#!/usr/bin/env python3
import unittest
from pathlib import Path

import table_replay


class TableReplayTests(unittest.TestCase):
    def test_parse_tables_rejects_duplicate_label(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            table_replay.parse_tables(["a=/tmp/a.tbl", "a=/tmp/b.tbl"])

    def test_decode_uses_dav1d_and_explicit_grain_state(self):
        command = table_replay.decode_command(
            Path("/usr/local/bin/ffmpeg"), Path("/tmp/out.mkv"), 0)
        self.assertIn("libdav1d", command)
        self.assertEqual(command[command.index("-filmgrain") + 1], "0")
        self.assertIn("-xerror", command)


if __name__ == "__main__":
    unittest.main()
