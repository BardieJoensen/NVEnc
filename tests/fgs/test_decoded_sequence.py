import csv
from pathlib import Path
import tempfile
import unittest
import numpy as np
import decoded_sequence as sequence


class WholeSequenceChecks(unittest.TestCase):
    def fixture(self):
        data = dict(seconds=np.arange(48) / 24, grain_present=np.ones(48))
        for c in sequence.CHANNELS:
            data[c + '_score'] = np.full(48, .5)
            data[c + '_rms'] = np.ones(48)
            data[c + '_correlation'] = np.full(48, .5)
            data[c + '_dx'] = np.ones(48)
            data[c + '_dy'] = np.zeros(48)
        return data

    def test_late_chroma_only_burst_is_not_hidden_by_luma_or_percentiles(self):
        reference = self.fixture(); candidate = self.fixture()
        self.assertTrue(sequence.compare(candidate, reference)['passed'])
        candidate['blue_score'][-1] = 3.5
        result = sequence.compare(candidate, reference)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failures'][0]['channel'], 'blue')
        self.assertEqual(result['failures'][0]['frames'], 1)

    def test_reordered_grain_with_same_mean_is_a_temporal_regression(self):
        reference = self.fixture(); candidate = self.fixture()
        reference['luma_rms'][24:] = .5
        candidate['luma_rms'][:24] = .5
        self.assertEqual(candidate['luma_rms'].mean(), reference['luma_rms'].mean())
        failures = sequence.compare(candidate, reference)['failures']
        self.assertTrue(any(f['check'] == 'adjacent-frame grain change' for f in failures))
        candidate = self.fixture(); candidate['grain_present'][20:24] = 0
        self.assertTrue(any(f['check'] == 'grain scheduling changed'
                            for f in sequence.compare(candidate, self.fixture())['failures']))

    def test_equal_amplitude_and_score_do_not_hide_changed_texture_direction(self):
        reference = self.fixture(); candidate = self.fixture()
        candidate['red_correlation'][-1] *= -1
        candidate['blue_dx'][-1] = 0; candidate['blue_dy'][-1] = 1
        failures = sequence.compare(candidate, reference)['failures']
        self.assertTrue(any(f['check'] == 'correlation sign/strength changed' for f in failures))
        self.assertTrue(any(f['check'] == 'dominant offset changed' for f in failures))

    def test_duration_distinguishes_single_frame_from_sustained_failure(self):
        mask = np.zeros(240, dtype=bool); mask[[0, 20, 40]] = True; mask[120:168] = True
        self.assertEqual(sequence.runs(mask), dict(frames=51, measured_seconds=51/24,
                                                  runs=4, longest_run_seconds=2.))

    def test_missing_nonfinite_or_misaligned_rows_cannot_pass(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'frames.csv'
            fields = ['seconds', 'grain_present'] + [c + '_' + f for c in sequence.CHANNELS
                for f in ('rms', 'max_patch_rms', 'correlation', 'score', 'dx', 'dy')]
            for times in ([0, 1/24], [0, 2/24], [0, float('nan')], [0]):
                with path.open('w') as dest:
                    writer = csv.DictWriter(dest, fields); writer.writeheader()
                    for t in times:
                        row = dict.fromkeys(fields, 0); row['seconds'] = t; writer.writerow(row)
                if times == [0, 1/24]:
                    self.assertEqual(len(sequence.load(path, frames=2)['seconds']), 2)
                else:
                    with self.assertRaises(ValueError):
                        sequence.load(path, frames=2)


if __name__ == '__main__':
    unittest.main()
