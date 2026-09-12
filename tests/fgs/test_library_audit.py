import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('library_audit', Path(__file__).parents[2]/'tools/fgs/library_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class HeaderCoverage(unittest.TestCase):
    def profile(self, flags, mutation=None, expected=None):
        rows=[]
        for i, flag in enumerate(flags):
            rows.append(dict(zip(audit.FIELDS, [i, i*40, i*.04, 0, flag, flag, 64*flag, 32*flag, 0, 8*flag])))
        if mutation: mutation(rows)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'frames.csv'
            with path.open('w') as f:
                w=csv.DictWriter(f, fieldnames=audit.FIELDS);w.writeheader();w.writerows(rows)
            return audit.profile_csv(path, dict(complete=True, errors=0, displayed_frames=len(flags), packets=len(flags)),expected)

    def test_longer_pulse_and_boundary_are_kept(self):
        r=self.profile([0]*10+[1]*24+[0]*10)
        self.assertEqual(r['on_off_transitions'],2)
        self.assertTrue({'longer_on','longer_on_end'} <= {w['kind'] for w in r['windows']})

    def test_continuously_enabled_colour_amplitude_jump(self):
        def change(rows):
            for row in rows[10:]:row['max_cb_scaling']=240
        r=self.profile([1]*25,change)
        self.assertEqual(r['on_off_transitions'],0)
        self.assertEqual(r['amplitude_changes'],1)
        self.assertIn('amplitude_change',[w['kind'] for w in r['windows']])

    def test_scaling_shift_normalized(self):
        def change(rows):
            for row in rows[10:]:
                row.update(scaling_shift=9,max_y_scaling=128,max_cb_scaling=64)
        self.assertEqual(self.profile([1]*25,change)['amplitude_changes'],0)

    def test_missing_final_frame_external_count_rejected(self):
        with self.assertRaisesRegex(ValueError,'coverage'):
            self.profile([1]*25,expected=26)

    def test_repeated_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError,'displayed time'):
            self.profile([1]*25,lambda r:r[8].update(seconds=r[7]['seconds']))

    def test_zero_grain_gets_controls_not_a_clear_verdict(self):
        r=self.profile([0]*200)
        self.assertEqual(r['grain_on_frames'],0)
        self.assertEqual(len(r['windows']),3)
        self.assertNotIn('verdict',r)


if __name__=='__main__':unittest.main()
