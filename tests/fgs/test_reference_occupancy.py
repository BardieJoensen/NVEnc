"""Native-code controls for the real-film model comparison's luma weights."""
from pathlib import Path
from fractions import Fraction
import copy
import subprocess
import tempfile
import unittest

import numpy as np

from reference_compare_real import (luma_occupancy, compare_model_timelines,
                                    source_preserved_frames)


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


class ModelTimelineTest(unittest.TestCase):
    @staticmethod
    def model(start, end, strength):
        return dict(start=start, end=end, apply_grain=True,
                    params=dict(scaling_shift=8, grain_scale_shift=0),
                    scaling_points=dict(y=[[0, strength], [255, strength]]))

    def test_different_clocks_and_unbounded_last_entry(self):
        fps = Fraction(24000, 1001)
        tick = lambda n: round(Fraction(n * 10000000, 1) / fps)
        candidate = [self.model(0, tick(3), 20), self.model(tick(3), tick(4), 40)]
        reference = [self.model(0, 1250000, 20), self.model(1250000, 2**63-1, 40)]
        result = compare_model_timelines(candidate, reference, np.ones((4, 256)), fps, [False]*4)
        self.assertEqual(result['rms_ratio'], 1.0)
        self.assertEqual([r['rms_ratio'] for r in result['frames']], [1.0]*4)
        bad = copy.deepcopy(candidate)
        for entry in bad:
            entry['scaling_points']['y'] = [[0, entry['scaling_points']['y'][0][1]//2],
                                          [255, entry['scaling_points']['y'][0][1]//2]]
        self.assertEqual(compare_model_timelines(bad, reference, np.ones((4, 256)), fps,
                                               [False]*4)['rms_ratio'], .5)

    def test_only_verified_source_can_replace_startup_models(self):
        model = [self.model(833333, 2**63-1, 20)]
        reference = [self.model(0, 2**63-1, 20)]
        result = compare_model_timelines(model, reference, np.ones((4, 256)), 24,
                                         [True, True, False, False])
        self.assertEqual(result['preserved_frames'], [0, 1])
        with self.assertRaisesRegex(ValueError, 'without preserved source'):
            compare_model_timelines(model, reference, np.ones((4, 256)), 24, [False]*4)
        with self.assertRaisesRegex(ValueError, 'insufficient'):
            compare_model_timelines([], reference, np.ones((4, 256)), 24, [True]*4)

    def test_actual_raw_pairs_and_short_decode(self):
        with tempfile.TemporaryDirectory() as name:
            source, clean = Path(name)/'source.raw', Path(name)/'clean.raw'
            source.write_bytes(bytes(range(24)))
            clean.write_bytes(bytes(range(12)) + bytes(12))
            self.assertEqual(source_preserved_frames(source, clean, 2, 2, 10, 2), [True, False])
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                source_preserved_frames(source, clean, 2, 2, 10, 3)


if __name__ == '__main__':
    unittest.main()
