import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[2]/'tools/fgs'))
import decoded_library_audit as m


class Coverage(unittest.TestCase):
    def report(self, expected, change=None):
        rows=[]
        for time in (1.,1.04,1.08):
            r=dict(seconds=time,pixels=1920*1080,grain_present=0)
            for channel in ('luma','red','green','blue'):
                for field in ('rms','max_tile_rms','peak_score','peak_directional_score'):r[channel+'_'+field]=0
            rows.append(r)
        if change:change(rows)
        metadata=dict(schema='fgs_reference_full_v1',interval_complete=True,measured_frames=3,width=1920,height=1080,
            measured_pixels=1920*1080*3,clipped_base_pixels=0,clipped_grain_pixels=0,units='PU21_banding_glare')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'frames.csv'
            with p.open('w') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            return m.summarize(p,metadata,expected)

    def test_decoded_coverage_matches_headers(self):
        self.assertEqual(self.report([1.,1.04,1.08])['frames'],3)

    def test_missing_frame_is_not_complete(self):
        with self.assertRaisesRegex(RuntimeError,'coverage'):self.report([1.,1.04,1.08,1.12])

    def test_matching_counts_wrong_timestamps_fail(self):
        with self.assertRaisesRegex(RuntimeError,'timestamps'):self.report([1.,1.04,1.09])

    def test_partial_image_is_not_full_coverage(self):
        with self.assertRaisesRegex(RuntimeError,'spatial'):self.report([1.,1.04,1.08],lambda r:r[1].update(pixels=1000))

    def test_nonfinite_score_fails(self):
        with self.assertRaisesRegex(RuntimeError,'non-finite'):self.report([1.,1.04,1.08],lambda r:r[0].update(blue_rms=float('nan')))


if __name__=='__main__':unittest.main()
