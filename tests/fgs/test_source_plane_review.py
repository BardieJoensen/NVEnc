import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('source_plane_review',Path(__file__).parents[2]/'tools/fgs/source_plane_review.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class SourceReview(unittest.TestCase):
    def test_constant_reader_time_offset_is_explicit(self):
        self.assertEqual(m.align_indices([.042,.083,.125],[0,.042,.083],.042),[(0,0),(1,1),(2,2)])

    def test_wrong_cadence_does_not_align(self):
        with self.assertRaises(ValueError):m.align_indices([0,.05,.1],[0,.042,.083],0)

    def test_duplicate_timestamps_fail(self):
        with self.assertRaises(ValueError):m.align_indices([0,.04,.04],[0,.04,.08],0)

    def test_partial_alignment_cannot_clear_a_window(self):
        # Three valid pairs must not silently hide the unmatched fourth frame.
        with self.assertRaisesRegex(ValueError,'every output picture'):
            m.align_indices([0,.04,.08],[0,.04,.08,.12],0)

    def test_empty_alignment_is_explicitly_ineligible(self):
        with self.assertRaises(ValueError):m.align_indices([],[],0)

    def test_chroma_only_pulse_is_measured(self):
        source=[np.full((4,32,32),32768,np.uint16),np.full((4,16,16),32768,np.uint16),np.full((4,16,16),32768,np.uint16)]
        on=[p.copy() for p in source]
        on[1][1,::2,:]+=1024
        on[1][1,1::2,:]-=1024
        r=m.measure_planes(source,on,source,[0,.04,.08,.12])
        self.assertEqual(r['planes'][0]['quiet_added_grain_over_3_pixels'],0)
        self.assertEqual(r['planes'][1]['quiet_added_grain_over_3_pixels'],256)
        self.assertEqual(r['planes'][1]['quiet_grain_change_over_1_pixels'],256)

    def test_source_texture_not_labelled_flat(self):
        source=[np.full((4,32,32),32768,np.uint16),np.full((4,16,16),32768,np.uint16),np.full((4,16,16),32768,np.uint16)]
        for p in source:p[:,::2,:]+=2048
        r=m.measure_planes(source,source,source,[0,.04,.08,.12])
        self.assertTrue(all(p['quiet_static_pixels']==0 for p in r['planes']))

    def test_uniform_superwhite_clipping_is_not_grain_texture(self):
        source=[np.full((4,32,32),249*256,np.uint16),np.full((4,16,16),32768,np.uint16),np.full((4,16,16),32768,np.uint16)]
        on=[p.copy() for p in source];on[0][1:]=235*256
        p=m.measure_planes(source,on,source,[0,.04,.08,.12])['planes'][0]
        self.assertEqual(p['quiet_added_grain_over_3_pixels'],0)
        self.assertEqual(p['endpoint_quiet_code_shift_over_3_pixels'],1024)
        self.assertEqual(p['peak_quiet_code_shift']['mean_difference'],[0,-14,-14,-14])

    def test_active_uniform_level_change_remains_reported(self):
        source=[np.full((4,32,32),128*256,np.uint16),np.full((4,16,16),32768,np.uint16),np.full((4,16,16),32768,np.uint16)]
        on=[p.copy() for p in source];on[0][1:]-=14*256
        p=m.measure_planes(source,on,source,[0,.04,.08,.12])['planes'][0]
        self.assertEqual(p['quiet_added_grain_over_3_pixels'],0)
        self.assertEqual(p['active_quiet_code_shift_over_3_pixels'],1024)


if __name__=='__main__':unittest.main()
