"""Software-only native CLI controls; requires a built inspector and libaom FFmpeg.

FGS_INSPECT_BINARY=/path/to/fgs-grain-inspect python3 tests/fgs/test_grain_inspect.py
No library media is opened or changed by these tests.
"""
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('FGS_INSPECT_BINARY'), 'native inspector binary not supplied')
class InspectorCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='fgs-inspect-controls-')
        cls.root = Path(cls.temp.name)
        cls.binary = os.environ['FGS_INSPECT_BINARY']
        cls.ffmpeg = os.environ.get('FGS_INSPECT_FFMPEG', '/usr/bin/ffmpeg')
        cls.clips = {}
        for name, pixel_format, transfer, matrix, primaries in (
            ('sdr', 'yuv420p', 'bt709', 'bt709', 'bt709'),
            ('pq', 'yuv420p10le', 'smpte2084', 'bt2020nc', 'bt2020'),
            ('hlg', 'yuv420p10le', 'arib-std-b67', 'bt2020nc', 'bt2020'),
            ('full12', 'yuv444p12le', 'smpte2084', 'bt2020nc', 'bt2020'),
            ('unknown', 'yuv420p', 'unknown', 'unknown', 'unknown'),
        ):
            path = cls.root / (name + '.mkv')
            command = [cls.ffmpeg, '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                       'color=c=gray:s=100x58:r=24:d=0.25', '-pix_fmt', pixel_format,
                       '-c:v', 'libaom-av1', '-cpu-used', '8', '-threads', '2', '-crf', '30',
                       '-color_trc', transfer, '-colorspace', matrix, '-color_primaries', primaries,
                       '-color_range', 'pc' if name == 'full12' else 'tv', str(path)]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            cls.clips[name] = path

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def inspect(self, name, *options, interval=(), success=True):
        output = self.root / (self.id().split('.')[-1] + '-' + Path(name).name + '.csv')
        if output.exists():
            output.unlink()
        result = subprocess.run([self.binary, *options, str(self.clips.get(name, name)),
                                 str(output), *map(str, interval)], capture_output=True, text=True, timeout=30)
        if not success:
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('"complete":true', result.stdout)
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        with output.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(rows)
        self.assertTrue(all(math.isfinite(float(x)) for row in rows for x in row.values()))
        return metadata, rows

    def test_sdr_pq_hlg_and_12bit_444_report_exact_coverage_and_no_fake_grain(self):
        for name in ('sdr', 'pq', 'hlg', 'full12'):
            with self.subTest(name=name):
                metadata, rows = self.inspect(name, '--extended')
                self.assertTrue(metadata['complete'])
                self.assertEqual(metadata['measured_frames'], 6)
                self.assertEqual(metadata['spatial_coverage_fraction'], 1)
                self.assertEqual(metadata['measured_pixels'], 6 * 100 * 58)
                self.assertEqual(metadata['units'], 'PU21_banding_glare')
                self.assertTrue(all(float(row[c + '_peak_score']) == 0 for row in rows
                                    for c in ('luma', 'red', 'green', 'blue')))
                if name == 'full12':
                    self.assertTrue(metadata['full_range'])
                    self.assertEqual(metadata['bit_depth'], 12)
                    self.assertEqual(metadata['pixel_layout'], 3)

    def test_unknown_colour_requires_explicit_recorded_assumption(self):
        self.inspect('unknown', '--extended', success=False)
        metadata, _ = self.inspect('unknown', '--extended', '--assume-bt709')
        self.assertTrue(metadata['assume_bt709_requested'])
        self.assertEqual(metadata['signalled_transfer'], 2)
        self.assertEqual(metadata['transfer'], 'sdr_gamma24')
        self.inspect('pq', '--extended', '--assume-bt709', success=False)

    def test_sampling_is_explicit_and_empty_intervals_cannot_complete(self):
        metadata, rows = self.inspect('sdr', '--extended', '--sample-period', '.125')
        self.assertEqual(metadata['decoded_frames'], 6)
        self.assertEqual(len(rows), 2)
        self.assertEqual(metadata['sample_period_seconds'], .125)
        self.inspect('sdr', '--extended', interval=(100, 101), success=False)
        for invalid in ('nan', '-1', '2junk'):
            self.inspect('sdr', '--extended', '--sample-period', invalid, success=False)

    def test_legacy_hdr_is_rejected_and_existing_output_is_preserved(self):
        self.inspect('pq', success=False)
        path = self.root / 'existing.csv'
        path.write_bytes(b'previous measurement')
        result = subprocess.run([self.binary, str(self.clips['sdr']), str(path)],
                                capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_bytes(), b'previous measurement')

    def test_ambiguous_video_requires_explicit_selection(self):
        multiple = self.root / 'multiple.mkv'
        subprocess.run([self.ffmpeg, '-v', 'error', '-nostdin', '-i', str(self.clips['sdr']),
                        '-map', '0:v:0', '-map', '0:v:0', '-c', 'copy', str(multiple)],
                       check=True, capture_output=True, timeout=30)
        self.inspect(str(multiple), '--extended', success=False)
        metadata, _ = self.inspect(str(multiple), '--extended', '--stream-index', '1')
        self.assertEqual(metadata['stream_index'], 1)

    def test_tile_dump_accounts_for_each_pixel_once(self):
        tiles = self.root / 'tiles.csv'
        metadata, _ = self.inspect('sdr', '--extended', '--sample-period', '1', '--tiles-csv', str(tiles))
        with tiles.open() as stream:
            rows = list(csv.DictReader(stream))
        counts = [0] * (100 * 58)
        for row in rows:
            if row['channel'] != '0':
                continue
            for y in range(int(row['y']), int(row['y']) + int(row['height'])):
                for x in range(int(row['x']), int(row['x']) + int(row['width'])):
                    counts[y * 100 + x] += 1
        self.assertEqual(metadata['measured_frames'], 1)
        self.assertTrue(all(count == 1 for count in counts))


if __name__ == '__main__':
    unittest.main()
