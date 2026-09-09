import copy
import unittest

from dovi_conversion_regression import validate_mel_reference


def pair():
    source = dict(dovi_profile=7, el_type='MEL',
                  header=dict(disable_residual_flag=False, el_spatial_resampling_filter_flag=True,
                              coefficient_log2_denom=23),
                  vdr_dm_data=dict(source_max_pq=3696, cmv29_metadata={'level1': [12, 2949, 819]}),
                  rpu_data_mapping=dict(curves=[{'pivots': [0, 1023]}] * 3,
                                        nlq={'vdr_in_max_int': [1, 1, 1]}, nlq_method_idc='LinearDeadzone'))
    result = copy.deepcopy(source)
    result['dovi_profile'] = 8
    del result['el_type']
    result['header'].update(disable_residual_flag=True, el_spatial_resampling_filter_flag=False)
    result['rpu_data_mapping'] = {'curves': result['rpu_data_mapping']['curves']}
    return [source], [result]


class IndependentReferenceTests(unittest.TestCase):
    def test_single_layer_conversion_keeps_picture_mapping_and_display_metadata(self):
        a, b = pair()
        validate_mel_reference(a, b, 1)

    def test_one_fel_frame_cannot_be_treated_as_mel(self):
        a, b = pair()
        a.append(copy.deepcopy(a[0])); b.append(copy.deepcopy(b[0]))
        a[1]['el_type'] = 'FEL'
        with self.assertRaisesRegex(ValueError, 'MEL source on every frame'):
            validate_mel_reference(a, b, 2)

    def test_changed_dynamic_metadata_or_reshaping_is_not_normalization(self):
        for section, key, value in [
            ('vdr_dm_data', 'source_max_pq', 1000),
            ('rpu_data_mapping', 'curves', []),
            ('header', 'coefficient_log2_denom', 22),
        ]:
            a, b = pair()
            b[0][section][key] = value
            with self.assertRaises(ValueError):
                validate_mel_reference(a, b, 1)

    def test_partial_or_unconverted_reference_is_rejected(self):
        a, b = pair()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate_mel_reference(a, b, 2)
        b[0]['dovi_profile'] = 7
        with self.assertRaisesRegex(ValueError, 'single-layer'):
            validate_mel_reference(a, b, 1)


if __name__ == '__main__':
    unittest.main()
