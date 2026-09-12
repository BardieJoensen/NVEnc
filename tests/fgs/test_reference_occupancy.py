"""Native-code controls for the real-film model comparison's luma weights."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np

from reference_compare_real import luma_occupancy


def fixture(path, bits, range_name):
    values = np.arange(128).reshape(8, 16) * 2
    if bits == 10:
        values = values * 4 + (np.arange(128).reshape(8, 16) % 4)
    dtype = np.dtype('u1' if bits == 8 else '<u2')
    csp = '420jpeg' if bits == 8 else '420p10'
    with path.open('wb') as stream:
        stream.write(f'YUV4MPEG2 W16 H8 F24:1 Ip A1:1 C{csp} XCOLORRANGE={range_name}\nFRAME\n'.encode())
        stream.write(values.astype(dtype).tobytes())
        stream.write(np.full(64, 128 << (bits-8), dtype=dtype).tobytes())
    expected = np.bincount((values >> (bits-8)).ravel(), minlength=256) / values.size
    return expected


class ReferenceOccupancyTest(unittest.TestCase):
    def check_native(self, bits, range_name):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/'source.y4m'
            expected = fixture(path, bits, range_name)
            np.testing.assert_array_equal(luma_occupancy(str(path), 1), expected)

    def test_limited_8bit(self):
        self.check_native(8, 'LIMITED')

    def test_limited_10bit(self):
        self.check_native(10, 'LIMITED')

    def test_full_8bit(self):
        self.check_native(8, 'FULL')

    def test_full_10bit(self):
        self.check_native(10, 'FULL')

    def test_old_display_conversion_fails_native_control(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/'source.y4m'
            expected = fixture(path, 10, 'LIMITED')
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-threads', '2',
                '-i', str(path), '-frames:v', '1', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
            old = np.bincount(np.frombuffer(raw, dtype=np.uint8), minlength=256) / 128
            self.assertGreater(float(np.abs(old-expected).sum()), .2)

    def test_short_input_does_not_fall_back_to_unweighted_comparison(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/'source.y4m'
            fixture(path, 10, 'LIMITED')
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                luma_occupancy(str(path), 2)

    def test_invalid_input_is_not_silently_unweighted(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(RuntimeError):
                luma_occupancy(str(Path(name)/'missing.mkv'), 1)


if __name__ == '__main__':
    unittest.main()
