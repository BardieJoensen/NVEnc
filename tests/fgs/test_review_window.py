#!/usr/bin/env python3
"""Completion, coverage, cache and concurrency contracts for bounded reviews."""
import argparse
import csv
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('review_window', ROOT / 'tools/fgs/review_window.py')
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class ReviewContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source, binary = self.root / 'source.mkv', self.root / 'inspector'
        source.write_bytes(b'original media')
        binary.write_bytes(b'pinned binary')
        self.args = argparse.Namespace(file=source, binary=binary, output_dir=self.root / 'review',
            start=0., duration=2., sample_period=.25, peak_nits=1000., sdr_white_nits=100.,
            assume_bt709=False, stream_index=None, timeout=10.)
        self.frames = dict(seconds=0, grain_present=1, tiles=2, pixels=96*48)
        for channel in review.CHANNELS:
            self.frames.update({channel+'_'+key: value for key, value in dict(
                peak_score=2, peak_x=0, peak_y=0, p95_tile_score=2, p99_tile_score=2,
                peak_directional_score=1, directional_x=0, directional_y=0).items()})
        self.tiles = [dict(seconds=0, x=x, y=0, width=48, height=48, channel=c,
                           rms=3, correlation=2/3, score=2, dx=1, dy=0, directional_score=1)
                      for x in (0, 48) for c in range(4)]
        self.metadata = dict(schema='fgs_reference_full_v1', interval_complete=True,
            measured_frames=1, width=96, height=48, transfer='sdr_gamma24',
            peak_nits=1000, sdr_white_nits=100, assume_bt709_requested=False)

    @staticmethod
    def dump(path, rows):
        with path.open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def native(self, command, **kwargs):
        self.dump(Path(command[-3]), [self.frames])
        self.dump(Path(command[command.index('--tiles-csv')+1]), self.tiles)
        return subprocess.CompletedProcess(command, 0, json.dumps(self.metadata))

    def test_complete_cache_restores_html_and_rechecks_artifact_hashes(self):
        with patch.object(review.subprocess, 'run', side_effect=self.native) as native:
            first = review.inspect(self.args)
            self.assertEqual(first['status'], 'complete')
            (self.args.output_dir / 'report.html').unlink()
            self.assertEqual(review.inspect(self.args), first)
            self.assertTrue((self.args.output_dir / 'report.html').is_file())
            self.assertEqual(native.call_count, 1)
            (self.args.output_dir / 'tiles.csv').write_text('torn artifact')
            review.inspect(self.args)
            self.assertEqual(native.call_count, 2)

    def test_duplicate_tile_cannot_replace_missing_coverage(self):
        self.tiles[-1] = dict(self.tiles[0])
        with patch.object(review.subprocess, 'run', side_effect=self.native):
            with self.assertRaisesRegex(RuntimeError, 'duplicate or invalid tile'):
                review.inspect(self.args)
        self.assertFalse((self.args.output_dir / 'report.json').exists())
        self.assertEqual(json.loads((self.args.output_dir / 'status.json').read_text())['status'], 'error')

    def test_partial_native_completion_is_not_a_report(self):
        self.metadata['interval_complete'] = False
        with patch.object(review.subprocess, 'run', side_effect=self.native):
            with self.assertRaisesRegex(RuntimeError, 'complete the requested interval'):
                review.inspect(self.args)

    def test_failed_rerun_does_not_display_a_stale_success_page(self):
        with patch.object(review.subprocess, 'run', side_effect=self.native):
            review.inspect(self.args)
            self.args.file.write_bytes(b'changed source')
            self.metadata['interval_complete'] = False
            with self.assertRaises(RuntimeError):
                review.inspect(self.args)
        self.assertIn('Review failed', (self.args.output_dir / 'report.html').read_text())

    def test_source_mutation_invalidates_complete_measurements(self):
        def mutate(command, **kwargs):
            result = self.native(command, **kwargs)
            self.args.file.write_bytes(b'replaced source')
            return result
        with patch.object(review.subprocess, 'run', side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, 'source or inspector changed'):
                review.inspect(self.args)

    def test_second_writer_cannot_clobber_current_status(self):
        self.args.output_dir.mkdir()
        status = self.args.output_dir / 'status.json'
        status.write_text('running first request')
        with (self.args.output_dir / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'another review'):
                review.inspect(self.args)
        self.assertEqual(status.read_text(), 'running first request')


if __name__ == '__main__':
    unittest.main()
