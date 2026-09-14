#!/usr/bin/env python3
"""Prepare and strictly verify Dolby metadata for an already reconstructed PQ picture.

This does not reconstruct pixels, crop, retime, encode or install media. Only
the qualified P7 FEL / PQ / BT.2020 family is accepted. Output is a single-layer
RPU suitable for the encoder's Profile 10.1 path, not a finished AV1 stream.
"""
import argparse
from copy import deepcopy
import hashlib
from fractions import Fraction
from itertools import zip_longest
import json
from pathlib import Path
import subprocess
from fel_parameter_bounds import verify as verify_parameter_bounds


YCC = [9574, 0, 13802, 9574, -1540, -5348, 9574, 17610, 0]
OFFSETS = [16777216, 134217728, 134217728]
LMS = [7222, 8771, 390, 2654, 12430, 1300, 0, 422, 15962]
IDENTITY_CURVE = dict(num_pivots_minus2=0, pivots=[0, 1023], mapping_idc='Polynomial',
                      poly_order_minus1=[0], linear_interp_flag=[False],
                      poly_coef_int=[[0, 1]], poly_coef=[[0, 0]])


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def json_array(handle):
    """Read dovi_tool's top-level array without loading a film's JSON into RAM."""
    decoder = json.JSONDecoder()
    buffer = ''
    eof = False
    def fill():
        nonlocal buffer, eof
        part = handle.read(65536)
        eof = not part
        buffer += part
    def trim():
        nonlocal buffer
        buffer = buffer.lstrip()
        while not buffer and not eof:
            fill()
            buffer = buffer.lstrip()
    trim()
    if not buffer.startswith('['):
        raise ValueError('RPU export must be a JSON array')
    buffer = buffer[1:]
    first = True
    while True:
        trim()
        if buffer.startswith(']'):
            buffer = buffer[1:]
            trim()
            if buffer:
                raise ValueError('Trailing data after RPU array')
            return
        if not first:
            if not buffer.startswith(','):
                raise ValueError('Missing RPU array separator or closing bracket')
            buffer = buffer[1:]
            trim()
            if buffer.startswith(']'):
                raise ValueError('Trailing comma in RPU array')
        while True:
            try:
                row, end = decoder.raw_decode(buffer)
                break
            except json.JSONDecodeError as error:
                if eof or len(buffer) > 16 * 1024 * 1024:
                    raise ValueError('Invalid or oversized RPU JSON entry') from error
                fill()
        if not isinstance(row, dict):
            raise ValueError('RPU entry must be an object')
        buffer = buffer[end:]
        first = False
        yield row


def require_fields(actual, expected, where):
    for key, value in expected.items():
        if key not in actual or actual[key] != value:
            raise ValueError(f'{where}: unsupported {key}={actual.get(key)!r}, expected {value!r}')


def verify_reconstruction_contract(source):
    """Reject mapping forms outside the pinned FelBaker qualification."""
    require_fields(source['header'], dict(coefficient_log2_denom=23,
        coefficient_log2_denom_length=23, vdr_rpu_normalized_idc=1,
        ext_mapping_idc_0_4=0, ext_mapping_idc_5_7=0), 'reconstruction coefficients')
    mapping = source['rpu_data_mapping']
    require_fields(mapping, dict(nlq_num_pivots_minus2=0,
        nlq_pred_pivot_value=[0, 1023]), 'reconstruction residual')
    curves = mapping['curves']
    if len(curves) != 3:
        raise ValueError('Exactly three reconstruction curves are required')
    for channel, curve in enumerate(curves):
        segments = curve['num_pivots_minus2'] + 1
        deltas = curve['pivots']
        if not (1 <= segments <= 8 and len(deltas) == segments + 1
                and 0 <= deltas[0] <= 1023 and all(v >= 0 for v in deltas[1:])
                and deltas[0] < sum(deltas) <= 1023):
            raise ValueError('Unsupported reconstruction pivot layout')
        if curve['mapping_idc'] == 'Polynomial':
            if (curve['linear_interp_flag'] != [False] * segments
                    or len(curve['poly_order_minus1']) != segments
                    or any(n not in (0, 1) for n in curve['poly_order_minus1'])):
                raise ValueError('Unqualified polynomial order or interpolation')
        elif curve['mapping_idc'] == 'MMR' and channel != 0:
            if (len(curve['mmr_order_minus1']) != segments
                    or any(n not in (0, 1, 2) for n in curve['mmr_order_minus1'])):
                raise ValueError('Unqualified MMR order')
        else:
            raise ValueError('Unsupported reconstruction mapping method')
    if len(mapping['nlq']['nlq_offset']) != 3 or any(
            not 0 <= v <= 1023 for v in mapping['nlq']['nlq_offset']):
        raise ValueError('Invalid enhancement-layer neutral codes')
    dm = source['vdr_dm_data']
    levels = [b['Level1'] for version in ['cmv29_metadata', 'cmv40_metadata']
              for b in dm.get(version, {}).get('ext_metadata_blocks', []) if 'Level1' in b]
    if len(levels) != 1 or not (0 <= levels[0]['min_pq'] <= levels[0]['max_pq'] <= 4095
                              and 0 <= levels[0]['avg_pq'] <= 4095):
        raise ValueError('Exactly one valid Level 1 block is required')
    # The pinned RGB converter uses signed 32-bit multiply/adds. Check each
    # partial sum over the entire possible 12-bit input range, including codes
    # outside nominal limited range; source-specific matrices remain supported.
    bounds = [(-(dm[f'ycc_to_rgb_offset{i}'] >> 12),
               65520 - (dm[f'ycc_to_rgb_offset{i}'] >> 12)) for i in range(3)]
    for row in range(3):
        low = high = 0
        for column, (a, b) in enumerate(bounds):
            coefficient = dm[f'ycc_to_rgb_coef{row * 3 + column}']
            x, y = sorted((coefficient * a, coefficient * b))
            low += x; high += y
            if min(x, low) < -(2**31) or max(y, high) >= 2**31:
                raise ValueError('Unqualified reconstruction matrix arithmetic range')


def verify_frame(source, output):
    require_fields(source, dict(dovi_profile=7, el_type='FEL'), 'source')
    header = source['header']
    require_fields(header, dict(rpu_type=2, rpu_format=18, vdr_rpu_profile=1,
        vdr_seq_info_present_flag=True, coefficient_data_type=0,
        bl_bit_depth_minus8=2, el_bit_depth_minus8=2, vdr_bit_depth_minus8=4,
        bl_video_full_range_flag=False, disable_residual_flag=False,
        vdr_dm_metadata_present_flag=True, use_prev_vdr_rpu_flag=False,
        chroma_resampling_explicit_filter_flag=False, spatial_resampling_filter_flag=False,
        reserved_zero_3bits=0), 'source header')
    mapping = source['rpu_data_mapping']
    require_fields(mapping, dict(mapping_color_space=0, mapping_chroma_format_idc=0,
        num_x_partitions_minus1=0, num_y_partitions_minus1=0,
        nlq_method_idc='LinearDeadzone'), 'source mapping')
    verify_reconstruction_contract(source)
    verify_parameter_bounds(source)
    dm = source['vdr_dm_data']
    require_fields(dm, dict(compressed=False, signal_eotf=65535, signal_eotf_param0=0,
        signal_eotf_param1=0, signal_eotf_param2=0, signal_color_space=0,
        signal_bit_depth=12, signal_chroma_format=0, signal_full_range_flag=1), 'source display data')
    # FelBaker converts the source YCC matrix into PQ RGB. It does not apply a
    # custom RGB->LMS gamut transform: accepting one would mislabel its RGB.
    require_fields(dm, {f'rgb_to_lms_coef{i}': v for i, v in enumerate(LMS)}, 'source gamut')
    if dm.get('scene_refresh_flag') not in (0, 1):
        raise ValueError('Unsupported source scene refresh flag')
    expected_header = dict(header, disable_residual_flag=True, el_spatial_resampling_filter_flag=False)
    expected_mapping = dict(vdr_rpu_id=mapping['vdr_rpu_id'], mapping_color_space=0,
        mapping_chroma_format_idc=0, num_x_partitions_minus1=0, num_y_partitions_minus1=0,
        curves=[deepcopy(IDENTITY_CURVE) for _ in range(3)])
    expected_dm = dict(dm, signal_color_space=0)
    expected_dm.update({f'ycc_to_rgb_coef{i}': v for i, v in enumerate(YCC)})
    expected_dm.update({f'ycc_to_rgb_offset{i}': v for i, v in enumerate(OFFSETS)})
    expected_dm.update({f'rgb_to_lms_coef{i}': v for i, v in enumerate(LMS)})
    require_fields(output, dict(dovi_profile=8), 'converted RPU')
    if output.get('el_type') is not None:
        raise ValueError('Converted RPU still requires an enhancement layer')
    if output['header'] != expected_header:
        raise ValueError('Unexpected converted RPU header')
    if output['rpu_data_mapping'] != expected_mapping:
        raise ValueError('Converted RPU is not the exact identity mapping')
    if output['vdr_dm_data'] != expected_dm:
        raise ValueError('Converted RPU changed trims, active area or other display metadata')
    return bool(dm['scene_refresh_flag'])


def verify(source_json, output_json, expected_frames):
    if expected_frames <= 0:
        raise ValueError('A positive independently checked frame count is required')
    scenes = []
    frames = 0
    authoring_level6 = None
    with Path(source_json).open() as src, Path(output_json).open() as dst:
        for frame, (before, after) in enumerate(zip_longest(json_array(src), json_array(dst))):
            if before is None or after is None or frame >= expected_frames:
                raise ValueError(f'RPU count mismatch at frame {frame}')
            try:
                if verify_frame(before, after):
                    scenes.append(frame)
                levels = [block['Level6']
                    for version in ['cmv29_metadata', 'cmv40_metadata']
                    for block in before['vdr_dm_data'].get(version, {}).get('ext_metadata_blocks', [])
                    if 'Level6' in block]
                if len(levels) != 1:
                    raise ValueError('Exactly one authoring Level 6 block is required')
                if authoring_level6 is None:
                    authoring_level6 = levels[0]
                elif levels[0] != authoring_level6:
                    raise ValueError('Changing authoring Level 6 metadata is not yet qualified')
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f'RPU frame {frame}: {error}') from error
            frames += 1
    if frames != expected_frames:
        raise ValueError(f'Incomplete RPU exports: {frames} of {expected_frames}')
    return dict(frames=frames, scenes=scenes, identity_mapping=True,
                display_metadata_preserved=True, source_gamut='BT.2020',
                reconstruction_contract='p7-fel-pq-bt2020-v2',
                native_arithmetic_bounds_checked=True,
                authoring_level6=authoring_level6,
                active_area_policy='unchanged; pixels must not be cropped')


def static_hdr_arguments(mastering, level6):
    """Use source display chromaticities and the reconstructed master levels.

    These are copied authoring values, not measurements of the lossy encode.
    A Dolby master may be 4000 nits even when its derived HDR10 BL is 1000.
    """
    xy = {}
    for key in ['red_x', 'red_y', 'green_x', 'green_y', 'blue_x', 'blue_y',
                'white_point_x', 'white_point_y']:
        value = Fraction(mastering[key]) * 50000
        if value < 0 or value > 50000 or value.denominator != 1:
            raise ValueError('Unsupported source mastering chromaticity: ' + key)
        xy[key] = int(value)
    maximum = level6['max_display_mastering_luminance']
    minimum = level6['min_display_mastering_luminance']
    if not (0 < maximum <= 10000 and 0 <= minimum < maximum * 10000):
        raise ValueError('Unsupported reconstructed master luminance')
    display = (f'G({xy["green_x"]},{xy["green_y"]})B({xy["blue_x"]},{xy["blue_y"]})'
        f'R({xy["red_x"]},{xy["red_y"]})WP({xy["white_point_x"]},{xy["white_point_y"]})'
        f'L({maximum * 10000},{minimum})')
    result = ['--master-display', display]
    peak, average = level6['max_content_light_level'], level6['max_frame_average_light_level']
    if not (0 <= peak <= 65535 and 0 <= average <= 65535):
        raise ValueError('Invalid authoring content-light metadata')
    if peak or average:
        result += ['--max-cll', f'{peak},{average}']
    return result


def prepare(source_rpu, directory, dovi_tool, expected_frames):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    original_hash = sha(source_rpu)
    report = dict(complete=False, source=str(source_rpu), source_sha256=original_hash,
                  tool=str(dovi_tool), tool_sha256=sha(dovi_tool), commands=[])
    def save():
        (directory / 'metadata-report.json').write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        config = directory / 'editor.json'
        # Do not copy the upstream example's crop=true: this pipeline keeps bars.
        config.write_text(json.dumps(dict(mode=2, remove_mapping=True)) + '\n')
        for args in [
            ['export', '-i', str(source_rpu), '-d', 'all=' + str(directory / 'source.json')],
            ['editor', '-i', str(source_rpu), '-j', str(config), '-o', str(directory / 'pq-rpu.bin')],
            ['export', '-i', str(directory / 'pq-rpu.bin'), '-d', 'all=' + str(directory / 'pq-rpu.json')],
        ]:
            command = [str(dovi_tool), *args]
            report['commands'].append(command)
            with (directory / f'command-{len(report["commands"])}.log').open('w') as log:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
        report.update(verify(directory / 'source.json', directory / 'pq-rpu.json', expected_frames))
        if sha(source_rpu) != original_hash:
            raise ValueError('Source RPU changed during preparation')
        report['output_sha256'] = sha(directory / 'pq-rpu.bin')
        # Published only after every source and output RPU has passed.
        (directory / 'scene-cuts.txt').write_text(f'FGS_SCENE_CUTS_V1 {expected_frames}\n'
            + ''.join(f'{frame}\n' for frame in report['scenes']))
        report['complete'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-rpu', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--dovi-tool', type=Path, required=True)
    parser.add_argument('--frames', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_rpu, args.output_dir, args.dovi_tool, args.frames), indent=2))
