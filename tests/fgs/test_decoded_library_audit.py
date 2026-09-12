import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

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

    def check_resource_pause(self, low_at_start):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name);binary=directory/'inspector';binary.write_bytes(b'pinned test inspector')
            headers=directory/'headers';out=directory/'decoded';manifest=directory/'manifest.json'
            items=[dict(key=key,version='v1',codec='av1',path=key) for key in ('a','b')]
            manifest.write_text(json.dumps(dict(schema='fgs_library_audit_v1',files=items)))
            for item in items:
                path=headers/item['key']/'v1';path.mkdir(parents=True)
                (path/'report.json').write_text(json.dumps(dict(status='complete')))
            argv=['audit',str(manifest),'--headers',str(headers),'--output-dir',str(out),
                  '--binary',str(binary),'--binary-sha256',m.audit.sha(binary)]
            free=(6*1024**3-1) if low_at_start else 12*1024**3
            with mock.patch.object(sys,'argv',argv), mock.patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=free)), \
                    mock.patch.object(m,'inspect_file',side_effect=m.AuditResourceUnavailable('reserve fell during window')) as inspect:
                self.assertEqual(m.main(),75)
            status=json.loads((out/'status.json').read_text())
            self.assertEqual(status['processed'],0)
            self.assertEqual(status['pending_files'],2)
            self.assertEqual(status['counts'],{})
            self.assertFalse(status['phase_complete'])
            self.assertFalse(status['audit_complete'])
            self.assertTrue(status['paused_reason'])
            self.assertEqual(inspect.call_count,0 if low_at_start else 1)

    def test_storage_reserve_does_not_turn_pending_files_into_errors(self):
        self.check_resource_pause(True)

    def test_mid_file_storage_pause_keeps_current_file_pending(self):
        self.check_resource_pause(False)

    def test_storage_reserve_boundary_is_unchanged(self):
        with mock.patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=6*1024**3)):
            m.require_storage(Path('.'))


if __name__=='__main__':unittest.main()
