import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from hdr_metadata_trace import canonical, compare, compare_rows, compare_streams, json_frames, json_metadata_row, metadata_row
from production_compare import sha


def mastering(values):
    node = ET.Element('side_data', type='Mastering display metadata')
    for key, value in values.items():
        ET.SubElement(node, 'side_datum', key=key, value=value)
    return node


class MetadataTests(unittest.TestCase):
    def test_streamed_json_keeps_nested_frames_across_chunk_boundaries(self):
        frames = [dict(pts_time=str(n), side_data_list=[dict(side_data_type='Dolby Vision Metadata',
                  nested=[dict(value='brace } and quote " and unicode \u2603', levels=[1, 2, 3])])]) for n in range(3)]
        document = json.dumps(dict(frames=frames), ensure_ascii=False)
        for chunk in [1, 7, 65536]:
            self.assertEqual(list(json_frames(io.StringIO(document), chunk_size=chunk)), frames)
        self.assertEqual(list(json_frames(io.StringIO('{"frames":[]}'))), [])

    def test_streamed_json_rejects_truncation_trailing_data_and_oversized_frames(self):
        for document in ['{"frames":[{}', '{"frames":[{},]}', '{"frames":[]} unexpected',
                         '{"streams":[]}', '{"frames":[42]}']:
            with self.assertRaises(ValueError):
                list(json_frames(io.StringIO(document), chunk_size=3))
        with self.assertRaisesRegex(ValueError, 'bounded'):
            list(json_frames(io.StringIO(json.dumps(dict(frames=[dict(value='x' * 1000)]))),
                             chunk_size=8, maximum_frame_chars=128))

    def test_json_static_rounding_and_dynamic_values(self):
        source = dict(pts_time='0', side_data_list=[dict(side_data_type='Mastering display metadata',
            red_x='34000/50000', min_luminance='1/10000', max_luminance='10000000/10000'),
            dict(side_data_type='Dolby Vision Metadata', nested=dict(value=1))])
        encoded = copy.deepcopy(source)
        encoded['side_data_list'][0].update(red_x='44564/65536', min_luminance='2/16384', max_luminance='256000/256')
        self.assertEqual(json_metadata_row(source, 0), json_metadata_row(encoded, 0))
        encoded['side_data_list'][1]['nested']['value'] = 2
        self.assertFalse(compare_rows([json_metadata_row(source, 0)], [json_metadata_row(encoded, 0)])['passed'])
        source['side_data_list'].append(source['side_data_list'][1])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            json_metadata_row(source, 0)

    def test_legacy_and_json_digests_cannot_be_misreported_as_metadata_damage(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/name for name in ['old', 'new']]
            for path, fmt in zip(paths, ['legacy-xml', 'ffprobe-json-hdr-v1']):
                path.mkdir()
                trace = path/'frames.jsonl'
                trace.write_text('{}\n')
                (path/'report.json').write_text(json.dumps(dict(complete=True, trace_format=fmt,
                    trace_sha256=sha(trace))))
            with self.assertRaisesRegex(ValueError, 'formats differ'):
                compare(*paths)

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

    def test_remux_origin_shift_requires_explicit_opt_in_and_is_recorded(self):
        source = [dict(frame=i, pts=pts, metadata={'Dolby Vision Metadata': str(i)})
                  for i, pts in enumerate(['0.125', '0.167', '0.209'])]
        muxed = [dict(row, pts=pts) for row, pts in zip(source, ['0.000', '0.042', '0.084'])]
        self.assertFalse(compare_rows(source, muxed)['passed'])
        result = compare_rows(source, muxed, allow_common_origin_shift=True)
        self.assertTrue(result['passed'])
        self.assertEqual(result['frames'], 3)
        self.assertEqual(result['common_origin_shift_seconds'], -.125)
        self.assertEqual(result['common_origin_shift_fraction'], '-1/8')

    def test_origin_normalization_cannot_hide_cadence_metadata_or_frame_changes(self):
        source = [dict(frame=i, pts=pts, metadata={'Dolby Vision Metadata': str(i)})
                  for i, pts in enumerate(['0.125', '0.167', '0.209'])]
        muxed = [dict(row, pts=pts) for row, pts in zip(source, ['0.000', '0.042', '0.084'])]
        for change in ['cadence', 'metadata']:
            changed = copy.deepcopy(muxed)
            if change == 'cadence':
                changed[1]['pts'] = '0.043'
            else:
                changed[1]['metadata']['Dolby Vision Metadata'] = 'different'
            result = compare_rows(source, changed, allow_common_origin_shift=True)
            self.assertFalse(result['passed'])
            self.assertEqual(result['different_frames'], 1)
        with self.assertRaisesRegex(ValueError, 'lengths differ'):
            compare_rows(source, muxed[:-1], allow_common_origin_shift=True)
        with self.assertRaisesRegex(ValueError, 'reordered'):
            compare_rows(source, muxed[::-1], allow_common_origin_shift=True)
        muxed[1]['pts'] = None
        with self.assertRaisesRegex(ValueError, 'every timestamp'):
            compare_rows(source, muxed, allow_common_origin_shift=True)

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
