#!/usr/bin/env python3
"""GPU integration checks for grain-table finalization and exit status."""
import os
from pathlib import Path
import resource
import signal
import subprocess
import tempfile
import unittest

import numpy as np
import filmgrn


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ['NVENCC']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fgs-export-test-')
        self.root = Path(self.tmp.name)
        self.table = self.root / 'grain.tbl'
        self.clean = self.root / 'clean.y4m'
        self.grainy = self.root / 'grainy.y4m'
        rng = np.random.default_rng(20260905)
        for source, noisy in [(self.clean, False), (self.grainy, True)]:
            with source.open('wb') as out:
                out.write(b'YUV4MPEG2 W512 H256 F24:1 Ip A1:1 C420p10\n')
                for _ in range(8):
                    y = np.full((256, 512), 512.0)
                    if noisy:
                        y += rng.normal(0, 24, y.shape)
                    out.write(b'FRAME\n')
                    out.write(np.rint(y).astype('<u2').tobytes())
                    chroma = np.full((128, 256), 512, dtype='<u2').tobytes()
                    out.write(chroma)
                    out.write(chroma)

    def tearDown(self):
        self.tmp.cleanup()

    def encode(self, source, destination=None, table=None, limit=None):
        env = os.environ.copy()
        env['CUDA_CACHE_DISABLE'] = '1'
        def restrict_file_size():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
        cmd = [self.binary, '--codec', 'raw', '--output-depth', '10',
               '--av1-film-grain', 'denoise=auto,chroma=auto,denoiser=bilateral',
               '--film-grain-table-out', str(table or self.table),
               '-i', str(source), '-o', str(destination or '/dev/null')]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env,
                              preexec_fn=restrict_file_size if limit is not None else None)

    def assert_no_temporaries(self):
        self.assertEqual(list(self.root.glob('*.fgs-*.tmp')), [])

    def test_clean_reuse_replaces_grain_and_replays_as_off(self):
        result = self.encode(self.grainy)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(filmgrn.representative(filmgrn.load(self.table)))
        result = self.encode(self.clean)
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = filmgrn.load(self.table)
        self.assertTrue(entries)
        self.assertTrue(all(not entry['apply_grain'] for entry in entries))
        output = self.root / 'replayed.mkv'
        result = subprocess.run([self.binary, '--codec', 'av1', '--cqp', '20',
                                 '--output-depth', '10', '--film-grain-table', str(self.table),
                                 '-i', str(self.clean), '-o', str(output)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        decodes = []
        for grain in ['0', '1']:
            result = subprocess.run(['ffmpeg', '-v', 'error', '-c:v', 'libdav1d',
                                     '-filmgrain', grain, '-i', str(output), '-f', 'framemd5', '-'],
                                    capture_output=True, text=True, timeout=60, check=True)
            decodes.append([line for line in result.stdout.splitlines() if not line.startswith('#')])
        self.assertEqual(len(decodes[0]), 8)
        self.assertEqual(decodes[0], decodes[1])
        self.assert_no_temporaries()

    def test_invalid_destinations_fail(self):
        for destination in [self.root / 'absent/table.tbl', Path('/dev/full')]:
            result = self.encode(self.grainy, table=destination)
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertIn('film grain table', result.stderr)
        self.assert_no_temporaries()

    def test_final_flush_failure_fails_encode_and_preserves_old_table(self):
        self.table.write_text('previous table\n')
        result = self.encode(self.grainy, limit=0)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn('failed to write or flush film grain table', result.stderr)
        self.assertEqual(self.table.read_text(), 'previous table\n')
        self.assert_no_temporaries()

    def test_failed_video_output_does_not_publish_table(self):
        self.table.write_text('previous table\n')
        result = self.encode(self.grainy, destination=self.root / 'base.y4m', limit=0)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.table.read_text(), 'previous table\n')
        self.assert_no_temporaries()


if __name__ == '__main__':
    unittest.main()
