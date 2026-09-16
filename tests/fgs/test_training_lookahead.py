"""GPU contract: lookahead must retain every picture, timestamp and drain tail."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np


class LookaheadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ['NVENCC']

    def test_short_and_trimmed_sequences_keep_order_and_timestamps(self):
        with tempfile.TemporaryDirectory(prefix='fgs-lookahead-') as temporary:
            root = Path(temporary)
            for bits in (8, 10):
                for count in (1, 2, 3, 4, 9):
                    with self.subTest(bits=bits, count=count):
                        source = root / 'source.y4m'
                        dtype = np.uint8 if bits == 8 else np.dtype('<u2')
                        header = f'YUV4MPEG2 W512 H256 F30000:1001 Ip A1:1 C{"420mpeg2" if bits == 8 else "420p10"}\n'.encode()
                        payloads = []
                        for frame in range(count):
                            # Constant planes bypass statistical modelling;
                            # distinct levels reveal duplicated/reordered tails.
                            y = np.full((256, 512), (48 + 12 * frame) << (bits - 8), dtype=dtype)
                            uv = np.full((128, 256), 128 << (bits - 8), dtype=dtype)
                            payloads.append(y.tobytes() + uv.tobytes() * 2)
                        source.write_bytes(header + b''.join(b'FRAME\n' + data for data in payloads))
                        for trim in (False, True):
                            expected = payloads[:-1] if trim and count > 1 else payloads
                            options = ['--trim', f'0:{len(expected)-1}'] if trim else []
                            common = [self.binary, '--avsw', '-i', str(source), '--output-depth', str(bits),
                                      '--av1-film-grain', 'denoise=auto,chroma=auto,denoiser=bilateral', *options]
                            raw = root / 'raw.y4m'
                            result = subprocess.run([*common, '--codec', 'raw', '-o', str(raw)], capture_output=True, text=True, timeout=60)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            with raw.open('rb') as stream:
                                self.assertTrue(stream.readline().startswith(b'YUV4MPEG2'))
                                for data in expected:
                                    self.assertTrue(stream.readline().startswith(b'FRAME'))
                                    self.assertEqual(stream.read(len(data)), data)
                                self.assertEqual(stream.read(1), b'')
                            video = root / 'video.mkv'
                            result = subprocess.run([*common, '--codec', 'av1', '--cqp', '20', '-o', str(video)], capture_output=True, text=True, timeout=60)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(video)], timeout=60))
                            pts = [float(f['best_effort_timestamp_time']) for f in probe['frames']]
                            self.assertEqual(len(pts), len(expected))
                            self.assertTrue(all(abs(t - n * 1001 / 30000) <= .0011 for n, t in enumerate(pts)), pts)


if __name__ == '__main__':
    unittest.main()
