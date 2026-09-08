import copy
import unittest
import xml.etree.ElementTree as ET

from hdr_metadata_trace import canonical, compare_rows, compare_streams, metadata_row


def mastering(values):
    node = ET.Element('side_data', type='Mastering display metadata')
    for key, value in values.items():
        ET.SubElement(node, 'side_datum', key=key, value=value)
    return node


class MetadataTests(unittest.TestCase):
    def test_av1_fixed_point_rounding_is_not_metadata_loss(self):
        source = mastering({'red_x': '34000/50000', 'green_y': '34500/50000',
                            'min_luminance': '1/10000', 'max_luminance': '10000000/10000'})
        encoded = mastering({'red_x': '44564/65536', 'green_y': '45220/65536',
                             'min_luminance': '2/16384', 'max_luminance': '256000/256'})
        self.assertEqual(canonical(source, True), canonical(encoded, True))
        encoded[0].set('value', '44566/65536')
        self.assertNotEqual(canonical(source, True), canonical(encoded, True))

    def test_missing_or_changed_dynamic_metadata_is_detected(self):
        frame = ET.fromstring('''<frame pts_time="0.042000"><side_data_list>
          <side_data type="Dolby Vision Metadata"><side_datum key="max_pq" value="2400"/></side_data>
          <side_data type="Dolby Vision RPU Data"/>
          </side_data_list></frame>''')
        reference = metadata_row(frame, 0)
        # The raw HEVC-only RPU is deliberately not required in an AV1 trace;
        # the parsed metadata remains mandatory, including nested field values.
        frame.find('side_data_list').remove(frame.find('./side_data_list/side_data[2]'))
        self.assertEqual(metadata_row(frame, 0), reference)
        frame.find('./side_data_list/side_data/side_datum').set('value', '2401')
        changed = metadata_row(frame, 0)
        self.assertFalse(compare_rows([reference], [changed])['passed'])
        missing = copy.deepcopy(reference)
        missing['metadata'] = {}
        self.assertFalse(compare_rows([reference], [missing])['passed'])

    def test_reordered_truncated_and_mistimed_frames_are_rejected(self):
        a = dict(frame=0, pts='0.000000', metadata={'Dolby Vision Metadata': 'a'})
        b = dict(frame=1, pts='0.042000', metadata={'Dolby Vision Metadata': 'b'})
        with self.assertRaisesRegex(ValueError, 'lengths differ'):
            compare_rows([a, b], [a])
        with self.assertRaisesRegex(ValueError, 'reordered'):
            compare_rows([a, b], [b, a])
        self.assertFalse(compare_rows([a], [dict(a, pts='0.042000')])['passed'])

    def test_duplicate_hdr_side_data_is_rejected(self):
        frame = ET.fromstring('''<frame pts_time="0"><side_data_list>
          <side_data type="Dolby Vision Metadata"/><side_data type="Dolby Vision Metadata"/>
          </side_data_list></frame>''')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            metadata_row(frame, 0)

    def test_dovi_profile_conversion_does_not_hide_missing_configuration(self):
        conf = dict(side_data_type='DOVI configuration record', dv_profile=8,
                    rpu_present_flag=1, el_present_flag=0, bl_present_flag=1,
                    dv_bl_signal_compatibility_id=1)
        source = dict(codec_name='hevc', side_data_list=[conf])
        encoded = dict(codec_name='av1', side_data_list=[dict(conf, dv_profile=10)])
        self.assertEqual(compare_streams(source, encoded), [])
        self.assertTrue(compare_streams(source, dict(codec_name='av1')))
        wrong = copy.deepcopy(encoded)
        wrong['side_data_list'][0]['dv_bl_signal_compatibility_id'] = 0
        self.assertTrue(compare_streams(source, wrong))


if __name__ == '__main__':
    unittest.main()
