"""Compare an explicitly requested encoder joint probe with the NumPy oracle.

Run manually after successful drain. This checks measurements, not picture
quality. Independent source/frame identity checks remain a separate requirement.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from joint_collect_reference import block_reference, read_frame, rounded

MOMENTS = ('source', 'base', 'sourceBase', 'colourSource', 'colourBase',
           'colourSourceBase', 'colourLagSource', 'colourLagBase',
           'colourLagSourceBase', 'colourLagBaseSource')
GROUP_DTYPE = np.dtype([('blocks', '<u8'), ('observations', '<u8'),
                       ('other', '<u8'), ('moments', '<f8', (2251,))])
TOLERANCE = 5e-6  # Same predeclared source-energy bound as standalone collection.


def compare_frame(path):
    case = json.loads(path.read_text())
    assert case['schema'] == 1 and case['group_count'] == 80
    assert case['group_bytes'] == GROUP_DTYPE.itemsize and case['moment_count'] == 2251
    assert case['source']['complete'] and case['base']['complete']
    for key in ('width', 'height', 'depth', 'shift', 'frame_id', 'pts', 'epoch'):
        assert case['source'][key] == case['base'][key], key
    assert case['frame_id'] == case['source']['frame_id']
    source, base, previous = [read_frame(case[k]) for k in ('source', 'base', 'previous')]
    if case['scene_reset']:
        assert previous is None, 'A scene reset must invalidate every previous plane'
    if case['stage'] == 'source_fallback':
        assert all(np.array_equal(s, b) for s, b in zip(source, base))
    native = [rounded(s, b, r) for s, b, r in zip(source, base, case['retain'])]
    maximum = (1 << case['source']['depth']) - 1
    assert all(int(a.min()) >= 0 and int(a.max()) <= maximum
               for frame in (source, base) for a in frame)
    upper = (native[0][::2, ::2] + native[0][::2, 1::2] + 1) // 2
    assert case['lookup_y'] == np.bincount(native[0].ravel(), minlength=1024).tolist()
    assert case['lookup_c'] == np.bincount(upper.ravel(), minlength=1024).tolist()
    width, height = case['source']['width'], case['source']['height']
    tiles = [(x, y, p) for p in (1, 2) for y in range(0, height//2-31, 32)
             for x in range(0, width//2-31, 32)]
    assert case['tiles'] == len(tiles)
    cpu = np.zeros(80, dtype=GROUP_DTYPE)
    common = np.zeros(80, dtype=GROUP_DTYPE) if 'common_groups_file' in case else None
    reasons = {}
    for tile in tiles:
        block = block_reference(case, source, base, previous, tile, native)
        reason = str(block['reasons'])
        reasons[reason] = reasons.get(reason, 0) + 1
        if not block['observations']:
            continue
        index = (tile[2]-1)*40 + block['check_fold']*20 + block['brightness_group']
        groups = [cpu[index]]
        if common is not None and not block['other_colour_reasons']:
            groups.append(common[index])
        moments = np.concatenate([block[k].ravel() for k in MOMENTS])
        for group in groups:
            group['blocks'] += 1
            group['observations'] += 676
            group['other'] += block['other_colour_reasons'] == 0
            group['moments'] += moments
    worst = 0.
    populations = [('groups_file', cpu)] + ([('common_groups_file', common)] if common is not None else [])
    for name, expected in populations:
        binary = Path(case[name])
        assert binary.stat().st_size == 80*GROUP_DTYPE.itemsize
        gpu = np.fromfile(binary, dtype=GROUP_DTYPE)
        for key in ('blocks', 'observations', 'other'):
            assert np.array_equal(expected[key], gpu[key]), (path, name, key)
        for index, (c, g) in enumerate(zip(expected, gpu)):
            norm = max(1., float(c['moments'][:676].reshape(26, 26).diagonal().max()))
            error = float(np.abs(c['moments']-g['moments']).max()) / norm
            assert np.isfinite(error) and error <= TOLERANCE, (path, name, index, error)
            worst = max(worst, error)
    binary = Path(case['groups_file'])
    return dict(frame=case['frame_id'], stage=case['stage'], scene_reset=case['scene_reset'],
                previous_complete=case['previous']['complete'], tiles=len(tiles),
                accepted=int(cpu['blocks'].sum()), reasons=reasons, maximum_group_error=worst,
                common_accepted=int(common['blocks'].sum()) if common is not None else None,
                common_groups_sha256=hashlib.sha256(Path(case['common_groups_file']).read_bytes()).hexdigest() if common is not None else None,
                record_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                groups_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())


def compare(directory, output):
    status = json.loads((directory/'status.json').read_text())
    manifest = json.loads((directory/'manifest.json').read_text())
    assert status['complete'] and sorted(status['captured_frames']) == sorted(manifest['frames'])
    result = dict(complete=False, matrix_energy_relative_tolerance=TOLERANCE, frames=[],
                  source_identity_independently_verified=False)
    try:
        for frame in sorted(manifest['frames']):
            row = compare_frame(directory/f'frame-{frame}.json')
            result['frames'].append(row)
            print(frame, row['stage'], row['accepted'], row['maximum_group_error'], flush=True)
        result['complete'] = True
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    compare(args.directory, args.output)
