from fractions import Fraction
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
from fel_prepare import clock
from fel_metadata import static_hdr_arguments


class PrepareTests(unittest.TestCase):
    def test_rounded_reordered_source_clock(self):
        packets = [{'pts_time': t} for t in ['0.000', '0.083', '0.042', '0.125']]
        result = clock(packets, Fraction(24000, 1001))
        self.assertEqual(result['frames'], 4)
        self.assertEqual(result['first_pts'], '0')

    def test_missing_duplicate_and_non_cfr_clock(self):
        for pts in [[], ['0', '0'], ['0', '0.0417', '0.125'], ['0', '0.050']]:
            with self.subTest(pts=pts), self.assertRaises(ValueError):
                clock([{'pts_time': t} for t in pts], Fraction(24000, 1001))

    def test_reconstructed_master_does_not_inherit_derived_bl_luminance(self):
        master = dict(red_x='34000/50000', red_y='16000/50000',
            green_x='13250/50000', green_y='34500/50000', blue_x='7500/50000', blue_y='3000/50000',
            white_point_x='15635/50000', white_point_y='16450/50000', max_luminance='1000/1')
        level6 = dict(max_display_mastering_luminance=4000, min_display_mastering_luminance=50,
                      max_content_light_level=6317, max_frame_average_light_level=945)
        args = static_hdr_arguments(master, level6)
        self.assertTrue(args[1].endswith('L(40000000,50)'))
        self.assertEqual(args[-2:], ['--max-cll', '6317,945'])
        level6.update(max_content_light_level=0, max_frame_average_light_level=0)
        self.assertEqual(len(static_hdr_arguments(master, level6)), 2)
        level6['max_display_mastering_luminance'] = 0
        with self.assertRaises(ValueError): static_hdr_arguments(master, level6)


if __name__ == '__main__': unittest.main()
