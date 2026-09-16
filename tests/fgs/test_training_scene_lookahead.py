"""GPU check: authoritative scene boundaries cannot qualify earlier grain."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
import filmgrn


class ScheduledLookaheadTests(unittest.TestCase):
    def test_same_statistics_scene_boundary_and_drain(self):
        binary = os.environ['NVENCC']
        with tempfile.TemporaryDirectory(prefix='fgs-scene-lookahead-') as tmp:
            root = Path(tmp)
            rng = np.random.default_rng(20260916)
            chroma = np.full((128, 256), 512, dtype='<u2').tobytes()
            frames = [np.rint(384 + rng.normal(0, 24, (256, 512))).astype('<u2').tobytes()
                      + chroma * 2 for _ in range(5)]
            source = root / 'source.y4m'
            source.write_bytes(b'YUV4MPEG2 W512 H256 F24:1 Ip A1:1 C420p10\n'
                               + b''.join(b'FRAME\n' + frame for frame in frames))
            schedule, table, raw = root / 'cuts.txt', root / 'grain.tbl', root / 'raw.y4m'
            for cut in (None, 1, 2, 4):
                with self.subTest(cut=cut):
                    cmd = [binary, '--avsw', '-i', str(source), '--codec', 'raw', '--output-depth', '10',
                           '--av1-film-grain', 'denoise=auto,chroma=auto,denoiser=bilateral',
                           '--film-grain-table-out', str(table), '-o', str(raw)]
                    if cut is not None:
                        schedule.write_text(f'FGS_SCENE_CUTS_V1 5\n{cut}\n')
                        cmd += ['--film-grain-scene-cuts', str(schedule)]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    decoded = []
                    with raw.open('rb') as stream:
                        self.assertTrue(stream.readline().startswith(b'YUV4MPEG2'))
                        for frame in frames:
                            self.assertTrue(stream.readline().startswith(b'FRAME'))
                            data = stream.read(len(frame))
                            self.assertEqual(len(data), len(frame))
                            decoded.append(data)
                        self.assertEqual(stream.read(1), b'')
                    self.assertTrue(any(e['apply_grain'] for e in filmgrn.load(table)))
                    if cut in (1, 2):
                        self.assertEqual(decoded[0], frames[0], 'future scene trained the opening picture')
                    elif cut == 4:
                        self.assertEqual(decoded[4], frames[4], 'tail scene borrowed preceding training')
                    else:
                        self.assertNotEqual(decoded[0], frames[0], 'control failed to corroborate real grain')


if __name__ == '__main__':
    unittest.main()
