import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
import fel_layer_order as order


def line(key, value): return f'[trace_headers @ test] 16 {key} 001 = {value}\n'
def fixture():
    return [line('nal_unit_type', 33), line('log2_max_pic_order_cnt_lsb_minus4', 2),
        line('nal_unit_type', 20), line('nuh_temporal_id_plus1', 1),
        line('first_slice_segment_in_pic_flag', 1),
        line('nal_unit_type', 20), line('nuh_temporal_id_plus1', 1),
        line('first_slice_segment_in_pic_flag', 0),
        line('nal_unit_type', 1), line('nuh_temporal_id_plus1', 1),
        line('first_slice_segment_in_pic_flag', 1), line('slice_pic_order_cnt_lsb', 2),
        line('nal_unit_type', 1), line('nuh_temporal_id_plus1', 1),
        line('first_slice_segment_in_pic_flag', 1), line('slice_pic_order_cnt_lsb', 1)]


class OrderTests(unittest.TestCase):
    def test_multislice_and_reordering(self):
        data = order.pictures(fixture())
        self.assertEqual(data['pictures'], [[20, 0, 1], [1, 2, 1], [1, 1, 1]])
        self.assertTrue(order.compare(data, data, 3)['complete'])

    def test_missing_and_different_layers(self):
        before = order.pictures(fixture())
        for column in [0, 1, 2]:
            after = copy.deepcopy(before); after['pictures'][2][column] += 1
            with self.assertRaises(ValueError): order.compare(before, after, 3)
        with self.assertRaises(ValueError): order.compare(before, before, 2)
        with self.assertRaises(ValueError): order.pictures(fixture()[:-1])

    def test_open_gop_or_changing_poc_width_is_held(self):
        bad = [s.replace('nal_unit_type 001 = 20', 'nal_unit_type 001 = 21') for s in fixture()]
        bad.insert(5, line('slice_pic_order_cnt_lsb', 20))
        with self.assertRaises(ValueError): order.pictures(bad)
        with self.assertRaises(ValueError):
            order.pictures(fixture() + [line('log2_max_pic_order_cnt_lsb_minus4', 12)])

    def test_matching_layer_counts_cannot_hide_tail_picture_gaps(self):
        data = order.pictures(fixture())
        data['pictures'] = [[19, 0, 1], [1, 3, 1]]
        data['frames'] = 2
        with self.assertRaisesRegex(ValueError, 'POC coverage'): order.compare(data, data, 2)

    def test_each_idr_group_must_be_complete(self):
        data = order.pictures(fixture())
        data['pictures'] += [[20, 0, 1], [1, 2, 1], [1, 1, 1]]
        data['frames'] = 6
        self.assertEqual(order.compare(data, data, 6)['idr_groups'], 2)
        data['pictures'][1][1] = 3
        with self.assertRaisesRegex(ValueError, 'picture 0'): order.compare(data, data, 6)


if __name__ == '__main__': unittest.main()
