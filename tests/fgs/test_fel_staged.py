from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
from fel_validate_staged import packet_times


class StagedTests(unittest.TestCase):
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
