import unittest
from test_fel_metadata import fixture
from fel_parameter_bounds import verify


class ParameterBoundsTests(unittest.TestCase):
    def test_identity_and_residual_are_within_the_native_ranges(self):
        verify(fixture()[0])

    def test_polynomial_intermediate_multiply_is_checked(self):
        row, _ = fixture()
        row['rpu_data_mapping']['curves'][0]['poly_coef_int'][0][1] = 2000
        with self.assertRaisesRegex(ValueError, 'Polynomial exceeds'): verify(row)

    def test_mmr_accumulator_is_checked(self):
        row, _ = fixture()
        row['rpu_data_mapping']['curves'][1] = dict(num_pivots_minus2=0, pivots=[0, 1023],
            mapping_idc='MMR', mmr_order_minus1=[0], mmr_constant_int=[0], mmr_constant=[0],
            mmr_coef_int=[[[2**25] * 7]], mmr_coef=[[[0] * 7]])
        with self.assertRaisesRegex(ValueError, 'MMR exceeds'): verify(row)

    def test_residual_lut_cannot_wrap_its_storage(self):
        row, _ = fixture()
        row['rpu_data_mapping']['nlq']['vdr_in_max_int'][0] = 1
        with self.assertRaisesRegex(ValueError, 'Residual lookup'): verify(row)

    def test_incomplete_coefficient_array_is_not_truncated_by_zip(self):
        row, _ = fixture()
        row['rpu_data_mapping']['curves'][0]['poly_coef'][0].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete polynomial'): verify(row)


if __name__ == '__main__': unittest.main()
