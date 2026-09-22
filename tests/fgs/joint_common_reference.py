"""Manual CPU/native comparison of separate per-component and common cohorts.

The common cohort is selected from independent SOURCE gates before summing.
It does not turn sparse groups into qualified models or establish image quality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from joint_collect_reference import block_reference, read_frame, rounded
from joint_probe_reference import GROUP_DTYPE, MOMENTS, TOLERANCE


def compare(manifest_path, measured_path, output_path):
    manifest = json.loads(manifest_path.read_text())
    measured = json.loads(measured_path.read_text())
    assert measured['complete'] and len(manifest['cases']) == len(measured['cases'])
    report = dict(complete=False, tolerance=TOLERANCE, cases=[],
                  manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  measurement_sha256=hashlib.sha256(measured_path.read_bytes()).hexdigest())
    try:
        for case, gpu in zip(manifest['cases'], measured['cases']):
            assert case['id'] == gpu['id'] and gpu['common_groups_collected']
            source, base, previous = [read_frame(case[k]) for k in ('source', 'base', 'previous')]
            native = [rounded(s, b, f) for s, b, f in zip(source, base, case['retain'])]
            ordinary = np.zeros(80, dtype=GROUP_DTYPE)
            common = np.zeros(80, dtype=GROUP_DTYPE)
            for tile in case['tiles']:
                b = block_reference(case, source, base, previous, tile, native)
                if not b['observations']:
                    continue
                i = (tile[2]-1)*40 + b['check_fold']*20 + b['brightness_group']
                moments = np.concatenate([b[k].ravel() for k in MOMENTS])
                for group in [ordinary[i]] + ([common[i]] if not b['other_colour_reasons'] else []):
                    group['blocks'] += 1
                    group['observations'] += 676
                    group['other'] += b['other_colour_reasons'] == 0
                    group['moments'] += moments
            worst = 0.
            for name, cpu in [('groups', ordinary), ('common_groups', common)]:
                assert len(gpu[name]) == 80
                for i, (c, g) in enumerate(zip(cpu, gpu[name])):
                    for key, other in [('blocks', 'blocks'), ('observations', 'observations'),
                                       ('other', 'other_colour_supported_blocks')]:
                        assert int(c[key]) == g[other], (case['id'], name, i, key)
                    norm = max(1., float(c['moments'][:676].reshape(26, 26).diagonal().max()))
                    error = float(np.max(np.abs(c['moments']-g['moments']))) / norm
                    assert np.isfinite(error) and error <= TOLERANCE, (case['id'], name, i, error)
                    worst = max(worst, error)
            assert np.array_equal(common['blocks'], common['other'])
            mixed = (ordinary['other'] > 0) & (ordinary['other'] < ordinary['blocks'])
            # Dividing the full population's sums by the smaller count does
            # not produce the intersection's covariance, even at the same bin.
            shortcut_errors = []
            for i in np.flatnonzero(mixed):
                n = float(common[i]['observations'])
                actual = common[i]['moments'][2028:2037] / n
                incorrect = ordinary[i]['moments'][2028:2037] / n
                norm = max(1., float(np.max(np.abs(actual))))
                shortcut_errors.append(float(np.max(np.abs(actual-incorrect))) / norm)
            row = dict(id=case['id'], tiles=len(case['tiles']), ordinary_blocks=int(ordinary['blocks'].sum()),
                       common_blocks=int(common['blocks'].sum()), mixed_groups=int(mixed.sum()),
                       adequate_common_groups=[int(i) for i in np.flatnonzero(common['blocks'] >= 16)],
                       common_blocks_by_group=common['blocks'].tolist(), maximum_group_error=worst,
                       wrong_divisor_maximum_error=max(shortcut_errors, default=0.))
            report['cases'].append(row)
            print(case['id'], row['ordinary_blocks'], row['common_blocks'], worst, flush=True)
        assert any(c['common_blocks'] for c in report['cases'])
        assert any(c['ordinary_blocks'] > c['common_blocks'] > 0 for c in report['cases'])
        assert any(c['wrong_divisor_maximum_error'] > .08 for c in report['cases'])
        report['complete'] = True
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        output_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('measurement', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    compare(args.manifest, args.measurement, args.output)
