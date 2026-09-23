"""Independent native NumPy oracle for complete-component GPU preservation counts.

Reads every pixel and storage bit, including partial borders. This is not an
encoder quality gate; range/curve interpretation remains a separate proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def storage_planes(frame):
    dtype = np.dtype('u1' if frame['depth'] == 8 else '<u2')
    planes = []
    for component, view in enumerate(frame['planes']):
        rows = frame['height'] // (2 if component else 1)
        columns = frame['width'] // (2 if component else 1)
        raw = np.fromfile(view['path'], dtype=dtype).reshape(rows, view['pitch'] // dtype.itemsize)
        planes.append(raw[:, view['offset'] // dtype.itemsize::view['stride']][:, :columns])
    return planes


def expected_counts(source, base):
    assert source['complete'] and base['complete']
    for field in ('width', 'height', 'depth', 'shift', 'frame_id', 'pts', 'epoch'):
        assert source[field] == base[field]
    result = []
    for stored_s, stored_b in zip(storage_planes(source), storage_planes(base)):
        s, b = [a.astype(np.uint32) >> source['shift'] for a in (stored_s, stored_b)]
        invalid = (s >= (1 << source['depth'])) | (b >= (1 << source['depth']))
        invalid |= ((stored_s | stored_b) & ((1 << source['shift']) - 1)) != 0
        result.append(dict(samples=int(s.size), changed_samples=int(np.count_nonzero(s != b)),
                           invalid_samples=int(np.count_nonzero(invalid)),
                           minimum=int(s.min()), maximum=int(s.max())))
    return result


def compare(manifest_path, measured_path, output_path):
    if output_path.exists():
        raise ValueError('comparison output must be new')
    manifest = json.loads(manifest_path.read_text()); measured = json.loads(measured_path.read_text())
    report = dict(complete=False, cases=[], samples=0, negative_calls_rejected=0,
                  manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  measured_sha256=hashlib.sha256(measured_path.read_bytes()).hexdigest())
    try:
        assert measured['complete'] and len(manifest['cases']) == len(measured['cases'])
        for case, row in zip(manifest['cases'], measured['cases']):
            assert case['id'] == row['id']
            assert row['inputs_unchanged'] and row['invalid_calls_preserve_output']
            assert row['negative_calls_rejected'] == 14
            counts = expected_counts(case['source'], case['base'])
            alias = expected_counts(case['source'], case['source'])
            assert counts == row['counts'], (case['id'], counts, row['counts'])
            assert alias == row['alias_counts'], (case['id'], 'aliased source')
            report['samples'] += 2 * sum(c['samples'] for c in counts)
            report['negative_calls_rejected'] += row['negative_calls_rejected']
            report['cases'].append(dict(id=case['id'], counts=counts, exact=True))
        report['complete'] = True
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        output_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path); parser.add_argument('measured', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(); compare(args.manifest, args.measured, args.output)
