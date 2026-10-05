#!/usr/bin/env python3
"""Compare repeated schema-2 NVENC input traces for one fixed fixture.

The caller must require successful encodes and independently check frame counts.
IVF hashes deliberately do not participate in this FGS input identity rule.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

if not __debug__:
    raise RuntimeError('Trace validation requires assertions; do not use Python -O')

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

GRAIN_BITS = [('applyGrain', 1), ('chromaScalingFromLuma', 1), ('overlapFlag', 1),
              ('clipToRestrictedRange', 1), ('grainScalingMinus8', 2), ('arCoeffLag', 2),
              ('numYPoints', 4), ('numCbPoints', 4), ('numCrPoints', 4),
              ('arCoeffShiftMinus6', 2), ('grainScaleShift', 2), ('reserved1', 8)]

GRAIN_ARRAYS = [('pointYValue', 14), ('pointYScaling', 14), ('pointCbValue', 10),
                ('pointCbScaling', 10), ('pointCrValue', 10), ('pointCrScaling', 10),
                ('arCoeffsYPlus128', 24), ('arCoeffsCbPlus128', 25), ('arCoeffsCrPlus128', 25), ('reserved2', 2)]

GRAIN_TAIL = [('cbMult', 1), ('cbLumaMult', 1), ('cbOffset', 2),
              ('crMult', 1), ('crLumaMult', 1), ('crOffset', 2)]

def grain_check(grain):
    if grain is None:
        return
    keys = {'object_hex', 'object_bytes', 'object_md5'} | {k for k, _ in GRAIN_BITS + GRAIN_TAIL} | {k + '_hex' for k, _ in GRAIN_ARRAYS}
    assert isinstance(grain, dict) and set(grain) == keys, 'Unknown/missing grain fields'
    assert re.fullmatch('[0-9a-f]{312}', grain['object_hex']), 'Wrong SDK grain bytes'
    raw = bytes.fromhex(grain['object_hex'])
    # Installed SDK layout: one LE uint32 bitfield word, packed byte arrays,
    # then cb/cr uint8,uint8,uint16. GCC x86-64 size is 156 bytes. Reject other
    # layouts instead of silently interpreting a different SDK/ABI.
    assert len(raw) == grain['object_bytes'] == 156
    assert hashlib.md5(raw).hexdigest() == grain['object_md5']
    word, shift = int.from_bytes(raw[:4], 'little'), 0
    for key, bits in GRAIN_BITS:
        assert type(grain[key]) is int and grain[key] == (word >> shift) & ((1 << bits) - 1), key
        shift += bits
    offset = 4
    for key, count in GRAIN_ARRAYS:
        assert grain[key + '_hex'] == raw[offset:offset + count].hex(), key
        offset += count
    for key, count in GRAIN_TAIL:
        assert type(grain[key]) is int and grain[key] == int.from_bytes(raw[offset:offset + count], 'little'), key
        offset += count
    assert offset == len(raw)
    assert grain['numYPoints'] <= 14 and grain['numCbPoints'] <= 10 and grain['numCrPoints'] <= 10

def grain_fields(grain):
    # Named SDK fields, excluding reserved/ABI bytes. Full arrays are retained,
    # including unused tails: this is a defined-field comparison, not a claim
    # that every differing unused array value changes AV1 synthesis semantics.
    return None if grain is None else {k: v for k, v in grain.items()
        if k not in ('object_hex', 'object_bytes', 'object_md5', 'reserved1', 'reserved2_hex')}

def inspect_trace(path, item, encoded):
    frames = item['frames']
    values = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(values) == frames + 1, 'Trace missing/extra rows'
    header, rows = values[0], values[1:]
    assert set(header) == {'type', 'schema', 'hash', 'capture', 'metadata_capture', 'padding_policy', 'visible_policy', 'enableFilmGrainParams', 'initial_grain'}, 'Unknown/missing trace header fields'
    assert header['type'] == 'header' and type(header['schema']) is int and header['schema'] == 2 and header['hash'] == 'md5'
    assert header['capture'] == 'after_NvEncLockBitstream_and_unmap_before_recycle'
    assert header['metadata_capture'] == 'before_NvEncEncodePicture'
    assert header['padding_policy'] == 'observe_full_pitch_no_initialization_or_normalization'
    assert header['visible_policy'] == 'stored_Y_then_interleaved_UV_bytes_including_P010_low_bits'
    assert type(header['enableFilmGrainParams']) is int and header['enableFilmGrainParams'] in (0, 1)
    assert header['enableFilmGrainParams'] == 1 and header['initial_grain'] is not None, 'This FGS runner requires configured grain parameters'
    grain_check(header['initial_grain'])
    keys = {'type', 'frameIdx', 'inputFrameId', 'timestamp', 'duration', 'pic_version',
            'encodePicFlags', 'pictureStruct', 'bufferFmt', 'width', 'height', 'pitch',
            'visible_row_bytes', 'rows', 'surface_md5', 'visible_md5', 'y_md5', 'uv_md5',
            'padding_md5', 'filmGrainParamsUpdate', 'grain'}
    for index, row in enumerate(rows):
        assert set(row) == keys, 'Unknown/missing trace fields'
        assert row['type'] == 'submit' and row['frameIdx'] == index
        numeric = keys - {'type', 'grain', 'surface_md5', 'visible_md5', 'y_md5', 'uv_md5', 'padding_md5'}
        assert all(type(row[k]) is int and row[k] >= 0 for k in numeric)
        assert row['width'] == encoded['width'] > 0 and row['height'] == encoded['height'] > 0
        assert not row['width'] % 2 and not row['height'] % 2 and row['pictureStruct'] == 1
        assert item['output_depth'] in (8, 10)
        assert row['bufferFmt'] == (1 if item['output_depth'] == 8 else 65536)
        assert row['visible_row_bytes'] == row['width'] * (1 if item['output_depth'] == 8 else 2)
        assert row['pitch'] >= row['visible_row_bytes']
        assert row['rows'] == row['height'] * 3 // 2
        assert row['filmGrainParamsUpdate'] in (0, 1)
        assert bool(row['filmGrainParamsUpdate']) == (row['grain'] is not None), 'Inconsistent grain pointer/update'
        assert not row['filmGrainParamsUpdate'] or header['enableFilmGrainParams'], 'Update without configured grain'
        for key in ('surface_md5', 'visible_md5', 'y_md5', 'uv_md5', 'padding_md5'):
            assert re.fullmatch('[0-9a-f]{32}', row[key]), key
        grain_check(row['grain'])
        if row['pitch'] == row['visible_row_bytes']:
            assert row['padding_md5'] == hashlib.md5(b'').hexdigest()
            assert row['surface_md5'] == row['visible_md5']
    if 'width' in item:
        assert encoded['width'] == item['width'] and encoded['height'] == item['height'], 'Wrong fixture geometry'
    # Full-pitch identity is kept distinct from visible bytes and grain objects;
    # no normalization of observed padding or SDK reserved fields is applied.
    visible = [{k: v for k, v in row.items() if k not in ('surface_md5', 'padding_md5')} for row in rows]
    return {'path': str(path), 'sha256': digest(path), 'header': header, 'frames': frames,
            'sequence_sha256': canonical(values), 'visible_sequence_sha256': canonical([header, *visible]),
            'surface_sequence_sha256': canonical([r['surface_md5'] for r in rows]),
            'grain_sequence_sha256': canonical([header['initial_grain'], *[
                [r['filmGrainParamsUpdate'], r['grain']] for r in rows]]),
            'grain_fields_sequence_sha256': canonical([header['enableFilmGrainParams'], grain_fields(header['initial_grain']), *[
                [r['filmGrainParamsUpdate'], grain_fields(r['grain'])] for r in rows]]),
            'frame_rows': rows}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', type=Path, action='append', required=True)
    parser.add_argument('--candidate', type=Path, action='append', required=True)
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--depth', type=int, choices=(8, 10), default=10)
    args = parser.parse_args()
    if min(len(args.production), len(args.candidate)) < 2:
        parser.error('At least two repeats per binary are required')
    paths = args.production + args.candidate
    if len({p.resolve() for p in paths}) != len(paths):
        parser.error('Every repeat must name a distinct trace file')
    if min(args.frames, args.width, args.height) <= 0:
        parser.error('Expected frame count and geometry must be positive')
    item = dict(frames=args.frames, width=args.width, height=args.height, output_depth=args.depth)
    encoded = dict(width=args.width, height=args.height)
    records = [inspect_trace(p, item, encoded) for p in paths]
    stable = len({r['sequence_sha256'] for r in records}) == 1
    first_difference = None
    reference = records[0]
    for other in records[1:]:
        if reference['header'] != other['header']:
            first_difference = dict(path=other['path'], location='header')
            break
        for index, (a, b) in enumerate(zip(reference['frame_rows'], other['frame_rows'])):
            fields = [key for key in a if a[key] != b[key]]
            if fields:
                first_difference = dict(path=other['path'], frame=index, differing_fields=fields)
                break
        if first_difference:
            break
    print(json.dumps(dict(submission_identity_pass=stable,
        production_repeats=len(args.production), candidate_repeats=len(args.candidate),
        expected_frames=args.frames, first_difference=first_difference,
        traces=[{k:v for k,v in r.items() if k not in ('frame_rows','header')} for r in records]), indent=2))
    return 0 if stable else 1

if __name__ == '__main__':
    raise SystemExit(main())
