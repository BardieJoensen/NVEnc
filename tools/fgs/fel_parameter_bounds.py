"""Conservative arithmetic bounds for the pinned FelBaker fixed-point path.

These bounds cover all possible input codes, not just sampled movie pixels.
The surrounding metadata contract fixes the layer depths and denominator.
"""


def verify(row):
    denominator = row['header']['coefficient_log2_denom']
    if denominator != 23: raise ValueError('Unqualified coefficient denominator')
    limit = 2**63 - 1
    def fixed(integer, fraction):
        if not 0 <= fraction < 2**denominator:
            raise ValueError('Coefficient fraction is outside its denominator')
        result = integer * 2**denominator + fraction
        if abs(result) > limit: raise ValueError('Coefficient exceeds fixed-point range')
        return result
    mapping = row['rpu_data_mapping']
    for curve in mapping['curves']:
        segments = curve['num_pivots_minus2'] + 1
        if curve['mapping_idc'] == 'Polynomial':
            if len(curve['poly_coef_int']) != segments or len(curve['poly_coef']) != segments:
                raise ValueError('Incomplete polynomial coefficients')
            for s in range(segments):
                integers, fractions = curve['poly_coef_int'][s], curve['poly_coef'][s]
                count = curve['poly_order_minus1'][s] + 2
                if len(integers) != count or len(fractions) != count:
                    raise ValueError('Incomplete polynomial order')
                # Horner results cannot exceed the sum of absolute coefficients
                # when 0 <= x/1024 < 1. Include the multiply before its shift.
                bound = sum(abs(fixed(i, f)) for i, f in zip(integers, fractions)) * 2**20
                if bound * 1023 > limit:
                    raise ValueError('Polynomial exceeds qualified arithmetic range')
        else:
            for key in ['mmr_constant_int', 'mmr_constant', 'mmr_coef_int', 'mmr_coef']:
                if len(curve[key]) != segments: raise ValueError('Incomplete MMR coefficients')
            for s in range(segments):
                bound = abs(fixed(curve['mmr_constant_int'][s], curve['mmr_constant'][s]))
                integers, fractions = curve['mmr_coef_int'][s], curve['mmr_coef'][s]
                order = curve['mmr_order_minus1'][s] + 1
                if len(integers) != order or len(fractions) != order:
                    raise ValueError('Incomplete MMR order')
                for ints, fracs in zip(integers, fractions):
                    if len(ints) != 7 or len(fracs) != 7: raise ValueError('Incomplete MMR products')
                    bound += sum(abs(fixed(i, f)) for i, f in zip(ints, fracs))
                if bound * 2**20 > limit:
                    raise ValueError('MMR exceeds qualified arithmetic range')
    nlq = mapping['nlq']
    keys = ['nlq_offset', 'vdr_in_max_int', 'vdr_in_max', 'linear_deadzone_slope_int',
            'linear_deadzone_slope', 'linear_deadzone_threshold_int', 'linear_deadzone_threshold']
    if any(len(nlq[k]) != 3 for k in keys): raise ValueError('Incomplete residual coefficients')
    for c in range(3):
        maximum = fixed(nlq['vdr_in_max_int'][c], nlq['vdr_in_max'][c]) * 2
        slope = fixed(nlq['linear_deadzone_slope_int'][c], nlq['linear_deadzone_slope'][c])
        threshold = fixed(nlq['linear_deadzone_threshold_int'][c], nlq['linear_deadzone_threshold'][c]) * 2
        if min(maximum, slope, threshold) < 0 or max(maximum, threshold) > limit:
            raise ValueError('Unqualified residual coefficient sign or range')
        # The native initializer builds 4096 entries even for ten-bit input.
        if 8192 * slope + threshold > limit or maximum >> 8 > 32767:
            raise ValueError('Residual lookup exceeds qualified arithmetic range')
