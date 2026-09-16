from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).parents[2]/'tools/fgs'))
import native_source_audit as m


class NativeCoverage(unittest.TestCase):
    def planes(self):
        return [np.zeros((3,9,13),dtype='<u2')]+[np.zeros((3,5,7),dtype='<u2') for _ in range(2)]

    def test_all_pixels_including_odd_chroma_edges(self):
        m.validate_window(self.planes(),[1,1.04,1.08],[1,1.04,1.08],13,9)

    def test_missing_frame_fails(self):
        with self.assertRaisesRegex(ValueError,'frame coverage'):
            m.validate_window(self.planes(),[1,1.04],[1,1.04,1.08],13,9)

    def test_wrong_timestamp_and_nonfinite_fail(self):
        for times in ([1,1.04,1.09],[1,float('nan'),1.08]):
            with self.assertRaisesRegex(ValueError,'timestamps'):
                m.validate_window(self.planes(),times,[1,1.04,1.08],13,9)

    def test_missing_chroma_edge_fails(self):
        p=self.planes();p[2]=p[2][:,:,:-1]
        with self.assertRaisesRegex(ValueError,'spatial'):
            m.validate_window(p,[1,1.04,1.08],[1,1.04,1.08],13,9)

    def test_wrong_component_depth_fails(self):
        with self.assertRaisesRegex(ValueError,'format'):
            m.validate_window([p.astype('uint8') for p in self.planes()],[1,1.04,1.08],[1,1.04,1.08],13,9)

    def test_window_does_not_include_rounded_endpoint(self):
        _,times=m.select_interval(self.planes(),[87.901,87.941,87.981],87.901,87.98100000000001)
        self.assertEqual(times,[87.901,87.941])

    def test_grain_free_changed_picture_fails(self):
        a=self.planes();b=self.planes();a[0][0,2,3]=256
        with self.assertRaisesRegex(ValueError,'grain-free'):
            m.native_noise(a,b,[0,1,1])

    def test_uniform_shift_is_distinct_from_noise(self):
        a=self.planes();b=self.planes();a[0][1,:,:]=512
        r=m.native_noise(a,b,[0,1,1])
        self.assertEqual(r['Y']['noise_rms'],[0,0,0]);self.assertEqual(r['Y']['mean_shift'],[0,2,0])

    def test_colour_plane_noise_is_measured(self):
        a=self.planes();b=self.planes();a[1][2,:,::2]=1024
        r=m.native_noise(a,b,[0,0,1]);self.assertGreater(r['U']['noise_rms'][2],1)
        self.assertEqual(r['V']['noise_rms'],[0,0,0])


if __name__=='__main__':unittest.main()
