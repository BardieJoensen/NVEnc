import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/fgs'))
import fel_metadata as fm


def fixture():
    header = dict(rpu_type=2, rpu_format=18, vdr_rpu_profile=1,
        vdr_seq_info_present_flag=True, coefficient_data_type=0,
        coefficient_log2_denom=23, coefficient_log2_denom_length=23,
        vdr_rpu_normalized_idc=1, ext_mapping_idc_0_4=0, ext_mapping_idc_5_7=0,
        bl_bit_depth_minus8=2, el_bit_depth_minus8=2, vdr_bit_depth_minus8=4,
        bl_video_full_range_flag=False, disable_residual_flag=False,
        vdr_dm_metadata_present_flag=True, use_prev_vdr_rpu_flag=False,
        chroma_resampling_explicit_filter_flag=False, spatial_resampling_filter_flag=False,
        reserved_zero_3bits=0, el_spatial_resampling_filter_flag=True)
    dm = dict(compressed=False, signal_eotf=65535, signal_eotf_param0=0,
        signal_eotf_param1=0, signal_eotf_param2=0, signal_color_space=0,
        signal_bit_depth=12, signal_chroma_format=0, signal_full_range_flag=1,
        scene_refresh_flag=1, cmv29_metadata={'test_trims_and_bars': [123, 2081, 280],
            'ext_metadata_blocks': [{'Level1': dict(min_pq=0, max_pq=3079, avg_pq=100)},
                {'Level6': dict(max_display_mastering_luminance=4000,
                min_display_mastering_luminance=50, max_content_light_level=5000,
                max_frame_average_light_level=500)}]})
    dm.update({f'rgb_to_lms_coef{i}': v for i, v in enumerate(fm.LMS)})
    dm.update({f'ycc_to_rgb_coef{i}': v + 1 for i, v in enumerate(fm.YCC)})
    dm.update({f'ycc_to_rgb_offset{i}': v for i, v in enumerate(fm.OFFSETS)})
    mapping = dict(vdr_rpu_id=0, mapping_color_space=0, mapping_chroma_format_idc=0,
        num_x_partitions_minus1=0, num_y_partitions_minus1=0,
        nlq_method_idc='LinearDeadzone', nlq_num_pivots_minus2=0,
        nlq_pred_pivot_value=[0, 1023], nlq={'nlq_offset': [512, 512, 512],
            'vdr_in_max_int': [0] * 3, 'vdr_in_max': [1048576] * 3,
            'linear_deadzone_slope_int': [0] * 3, 'linear_deadzone_slope': [2048] * 3,
            'linear_deadzone_threshold_int': [0] * 3, 'linear_deadzone_threshold': [0] * 3},
        curves=[copy.deepcopy(fm.IDENTITY_CURVE) for _ in range(3)])
    source = dict(dovi_profile=7, el_type='FEL', header=header,
                  rpu_data_mapping=mapping, vdr_dm_data=dm)
    output = copy.deepcopy(source)
    output.pop('el_type'); output['dovi_profile'] = 8
    output['header'].update(disable_residual_flag=True, el_spatial_resampling_filter_flag=False)
    output['rpu_data_mapping'].pop('nlq_method_idc')
    for key in ['nlq_num_pivots_minus2', 'nlq_pred_pivot_value', 'nlq']:
        output['rpu_data_mapping'].pop(key)
    output['rpu_data_mapping']['curves'] = [copy.deepcopy(fm.IDENTITY_CURVE) for _ in range(3)]
    output['vdr_dm_data'].update({f'ycc_to_rgb_coef{i}': v for i, v in enumerate(fm.YCC)})
    return source, output


class MetadataTests(unittest.TestCase):
    def test_custom_ycc_is_normalized_but_trims_are_preserved(self):
        self.assertTrue(fm.verify_frame(*fixture()))

    def test_unsafe_or_unqualified_sources_fail(self):
        changes = [('el_type', 'MEL'), ('dovi_profile', 5),
            ('header.use_prev_vdr_rpu_flag', True), ('header.bl_video_full_range_flag', True),
            ('header.chroma_resampling_explicit_filter_flag', True),
            ('header.vdr_bit_depth_minus8', 8), ('vdr_dm_data.compressed', True),
            ('vdr_dm_data.rgb_to_lms_coef1', 42), ('vdr_dm_data.signal_eotf', 1),
            ('rpu_data_mapping.num_x_partitions_minus1', 1)]
        for key, value in changes:
            with self.subTest(key=key):
                before, after = fixture()
                target = before
                parts = key.split('.')
                for part in parts[:-1]: target = target[part]
                target[parts[-1]] = value
                with self.assertRaises(ValueError): fm.verify_frame(before, after)

    def test_wrong_output_cannot_pass_on_a_profile_tag(self):
        for mode in ['old_rpu', 'mapping_retained', 'bad_chroma_curve', 'crop', 'trim', 'matrix', 'scene']:
            with self.subTest(mode=mode):
                before, after = fixture()
                if mode == 'old_rpu': after = copy.deepcopy(before)
                elif mode == 'mapping_retained': after['rpu_data_mapping'] = before['rpu_data_mapping']
                elif mode == 'bad_chroma_curve': after['rpu_data_mapping']['curves'][2]['poly_coef'][0][0] = 1
                elif mode in ['crop', 'trim']: after['vdr_dm_data']['cmv29_metadata'] = {mode: 0}
                elif mode == 'matrix': after['vdr_dm_data']['ycc_to_rgb_coef0'] += 1
                elif mode == 'scene': after['vdr_dm_data']['scene_refresh_flag'] = 0
                with self.assertRaises(ValueError): fm.verify_frame(before, after)

    def test_reconstruction_contract_rejects_unsupported_arithmetic(self):
        for mode in ['denominator', 'interpolation', 'luma_mmr', 'order', 'pivots',
                     'level1', 'matrix', 'neutral']:
            with self.subTest(mode=mode):
                before, after = fixture()
                curve = before['rpu_data_mapping']['curves'][0]
                if mode == 'denominator': before['header']['coefficient_log2_denom'] = 10
                elif mode == 'interpolation': curve['linear_interp_flag'][0] = True
                elif mode == 'luma_mmr': curve['mapping_idc'] = 'MMR'
                elif mode == 'order': curve['poly_order_minus1'][0] = 3
                elif mode == 'pivots': curve['pivots'] = [0, 4096]
                elif mode == 'level1': before['vdr_dm_data']['cmv29_metadata']['ext_metadata_blocks'].pop(0)
                elif mode == 'matrix':
                    before['vdr_dm_data'].update({f'ycc_to_rgb_coef{i}': 32767 for i in range(3)})
                elif mode == 'neutral': before['rpu_data_mapping']['nlq']['nlq_offset'][0] = 2048
                with self.assertRaises(ValueError): fm.verify_frame(before, after)

    def test_zero_width_polynomial_segment_from_last_knight_is_supported(self):
        before, after = fixture()
        curve = before['rpu_data_mapping']['curves'][0]
        curve.update(num_pivots_minus2=1, pivots=[0, 0, 1023],
            poly_order_minus1=[0, 1], linear_interp_flag=[False, False],
            poly_coef_int=[[-1, 0], [-1, 1, -1]],
            poly_coef=[[8336920, 0], [8336920, 854393, 7639009]])
        self.assertTrue(fm.verify_frame(before, after))

    def test_stream_parser_across_small_reads(self):
        class TinyReads(io.StringIO):
            def read(self, count=-1): return super().read(min(count, 7))
        text = json.dumps([fixture()[0]] * 3) + ' \n'
        self.assertEqual(len(list(fm.json_array(TinyReads(text)))), 3)
        for text in ['[{},]', '[{}', '[', '[] {}', '[{} {}]', '[4]', '{}', '']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                list(fm.json_array(TinyReads(text)))

    def test_every_frame_and_count_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp) / 'source.json', Path(temp) / 'output.json'
            before, after = fixture()
            src.write_text(json.dumps([before, before]))
            dst.write_text(json.dumps([after, after]))
            self.assertEqual(fm.verify(src, dst, 2)['scenes'], [0, 1])
            for count in [0, 1, 3]:
                with self.assertRaises(ValueError): fm.verify(src, dst, count)
            dst.write_text(json.dumps([after]))
            with self.assertRaises(ValueError): fm.verify(src, dst, 2)
            bad = copy.deepcopy(after); bad['vdr_dm_data']['scene_refresh_flag'] = 0
            dst.write_text(json.dumps([after, bad]))
            with self.assertRaisesRegex(ValueError, 'frame 1'): fm.verify(src, dst, 2)


if __name__ == '__main__': unittest.main()
