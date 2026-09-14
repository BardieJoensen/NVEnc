from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
from fel_validate_staged import packet_times, retained_clock


class StagedTests(unittest.TestCase):
    def test_library_clock_rejects_a_different_cut_offset_or_cadence(self):
        expected = dict(frames=4, fps='24000/1001', first_pts='0')
        packets = [{'pts_time': value} for value in ['0', '0.042', '0.083', '0.125']]
        self.assertEqual(retained_clock(packets, '24000/1001', expected)['frames'], 4)
        # HEVC decode-order packets may be reordered; the display clock matters.
        self.assertEqual(retained_clock(packets[::-1], '24000/1001', expected)['frames'], 4)
        for wrong in [packets[:-1], packets + [{'pts_time': '0.167'}],
                      packets[:2] + packets[3:], packets[:3] + [packets[2]],
                      [{'pts_time': value} for value in ['0.010', '0.052', '0.093', '0.135']]]:
            with self.subTest(packets=wrong), self.assertRaises(ValueError):
                retained_clock(wrong, '24000/1001', expected)
        with self.assertRaises(ValueError):
            retained_clock(packets, '25', expected)

    def test_audio_timing_check_detects_offset_with_unchanged_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp); source, shifted = d / 'source.mka', d / 'shifted.mka'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=440:duration=0.25', '-c:a', 'pcm_s16le', str(source)], check=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-copyts', '-itsoffset', '0.100',
                '-i', str(source), '-c', 'copy', str(shifted)], check=True)
            def payload(p):
                return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(p),
                    '-map', '0:a:0', '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'])
            self.assertEqual(payload(source), payload(shifted))
            one = packet_times(source, [0], d / 'source.log')
            two = packet_times(shifted, [0], d / 'shifted.log')
            self.assertEqual(one[0]['packets'], two[0]['packets'])
            self.assertNotEqual(one[0]['sha256'], two[0]['sha256'])


if __name__ == '__main__': unittest.main()
