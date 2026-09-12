"""Software CLI controls for the optional, read-only AV1 transition scanner.

FGS_TRANSITIONS_BINARY=/path/to/grain-transitions python3 tests/fgs/test_grain_transitions.py
Real-grain/reference equivalence additionally uses retained private regressions.
"""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('FGS_TRANSITIONS_BINARY'), 'native scanner binary not supplied')
class TransitionsCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='fgs-transitions-controls-')
        cls.root = Path(cls.temp.name)
        cls.binary = os.environ['FGS_TRANSITIONS_BINARY']
        ffmpeg = os.environ.get('FGS_TRANSITIONS_FFMPEG', '/usr/bin/ffmpeg')
        for name, codec, options in (
                ('plain', 'libaom-av1', ['-cpu-used', '8']),
                ('h264', 'libx264', ['-preset', 'ultrafast'])):
            subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                            'testsrc2=s=96x64:r=24:d=1', '-vf', 'setpts=PTS+10/TB',
                            '-c:v', codec, '-threads', '1', *options,
                            str(cls.root / (name + '.mkv'))],
                           check=True, capture_output=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def scan(self, path):
        result = subprocess.run([self.binary, str(path)], capture_output=True,
                                text=True, timeout=30)
        summary = json.loads(result.stderr.splitlines()[-1])
        return result, summary

    def test_no_grain_sequence_keeps_exact_displayed_coverage_and_offset(self):
        result, summary = self.scan(self.root / 'plain.mkv')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['displayed_frames'], 24)
        self.assertEqual(summary['packets'], 24)
        rows = list(csv.DictReader(io.StringIO(result.stdout)))
        self.assertEqual(len(rows), 24)
        self.assertEqual(int(rows[0]['pts_ms']), 10000)
        self.assertEqual([int(r['frame']) for r in rows], list(range(24)))
        times = [int(r['pts_ms']) for r in rows]
        self.assertTrue(all(b > a for a, b in zip(times, times[1:])))
        self.assertTrue(all(int(r['apply_grain']) == int(r['effective_grain']) == 0 for r in rows))

    def test_missing_and_non_av1_files_cannot_complete(self):
        for path in (self.root / 'missing.mkv', self.root / 'h264.mkv'):
            with self.subTest(path=path):
                result, summary = self.scan(path)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(summary['complete'])

    def test_interrupted_container_is_not_a_completed_audit(self):
        data = (self.root / 'plain.mkv').read_bytes()
        truncated = self.root / 'interrupted.mkv'
        truncated.write_bytes(data[:len(data) // 2])
        result, summary = self.scan(truncated)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(summary['complete'])

    @unittest.skipUnless(Path('/dev/full').exists(), 'requires the POSIX full device')
    def test_failed_csv_write_cannot_report_success(self):
        with open('/dev/full', 'w') as output:
            result = subprocess.run([self.binary, str(self.root / 'plain.mkv')],
                                    stdout=output, stderr=subprocess.PIPE, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stderr.splitlines()[-1])['complete'])


if __name__ == '__main__':
    unittest.main()
