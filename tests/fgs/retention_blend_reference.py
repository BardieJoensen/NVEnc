"""Independent native-pixel check for the manual CUDA retention blend harness.

Compares the actual output plane bytes with NumPy's separate float32 operations
and nearest-even rounding. This is not compressed-output/model qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from joint_collect_reference import read_frame, rounded


def compare(manifest_path, measured_path, output_path):
    if output_path.exists():
        raise ValueError('comparison output must be new')
    manifest = json.loads(manifest_path.read_text())
    measured = json.loads(measured_path.read_text())
    result = dict(complete=False, scope='Native pre-encode component blending only',
                  manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  measured_sha256=hashlib.sha256(measured_path.read_bytes()).hexdigest(),
                  valid_pixels_compared=0, invalid_samples=0, rejected_calls=0, cases=[])
    try:
        assert measured['complete'] and len(measured['cases']) == len(manifest['cases'])
        for case, row in zip(manifest['cases'], measured['cases']):
            assert case['id'] == row['id']
            assert row['inputs_unchanged'] and row['padding_unchanged']
            assert row['negative_calls_rejected'] == 14
            for key in ('width', 'height', 'depth', 'shift', 'frame_id', 'pts', 'epoch'):
                assert case['source'][key] == case['base'][key] == row['output'][key]
            source, base = read_frame(case['source']), read_frame(case['base'])
            actual = read_frame(dict(row['output'], complete=True))
            maximum = (1 << case['source']['depth']) - 1
            invalid_count = compared = 0
            for p, (s, b, a, fraction) in enumerate(zip(source, base, actual, case['retain'])):
                valid = (s <= maximum) & (b <= maximum)
                expected = rounded(s, b, fraction)
                assert np.array_equal(a[valid], expected[valid]), (case['id'], p, 'native rounding mismatch')
                invalid_count += int((~valid).sum())
                compared += int(valid.sum())
                if fraction == 0:
                    assert np.array_equal(a[valid], b[valid])
                if fraction == 1:
                    assert np.array_equal(a[valid], s[valid])
                # P010 storage must have exactly zero unused low bits.
                view = row['output']['planes'][p]
                if row['output']['shift'] == 6:
                    raw = np.fromfile(view['path'], dtype='<u2').reshape(a.shape[0], view['pitch']//2)
                    native = raw[:, view['offset']//2::view['stride']][:, :a.shape[1]]
                    assert np.all((native[valid] & 63) == 0)
            assert row['invalid_samples'] == invalid_count
            assert row['output']['complete'] == (invalid_count == 0)
            result['cases'].append(dict(id=case['id'], pixels=compared, invalid_samples=invalid_count,
                                        retain=case['retain'], output_semiplanar=case['output_semiplanar']))
            result['valid_pixels_compared'] += compared
            result['invalid_samples'] += invalid_count
            result['rejected_calls'] += row['negative_calls_rejected']
        result['complete'] = True
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        output_path.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('measured', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    compare(args.manifest, args.measured, args.output)
