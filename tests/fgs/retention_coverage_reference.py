"""Replay whole-picture coverage against actual native rounded bases.

This intentionally supplies no invented population/model qualification. With
zero synthesis the only established proof is exact native source preservation.
The replay shows why zeroing a curve alone cannot approve a changed base.
Source-only tile classification is held fixed across all retention candidates;
every pixel, rejected population and partial border enters the native census.
This is CPU research tooling, not the future runtime GPU coverage collector.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from joint_collect_reference import block_reference, read_frame, rounded


def population_map(case, source, previous, component):
    height, width = source[component].shape
    populations = np.full((height, width), 3, dtype=np.int32)  # Partial borders.
    groups = np.full((height, width), 20, dtype=np.int32)
    strengths = np.full((height, width), 6, dtype=np.int32)
    counts = np.zeros((2, 20, 6), dtype=np.int32)
    signature = []
    # Classification sees source/previous only; the candidate base and fractions
    # cannot affect means, gates, checkerboard membership or strength population.
    classification = dict(case, base=case['source'], retain=[0, 0, 0])
    for y in range(0, height-31, 32):
        for x in range(0, width-31, 32):
            b = block_reference(classification, source, source, previous, (x, y, component),
                                source, collect_moments=False)
            reason = b['reasons']
            if 'variance' not in b:
                population, group, strength = 2, 20, 6
            else:
                population = 0 if reason == 0 else (1 if b['variance'][1] < .04 else 2)
                group = b['brightness_group']
                strength = int(np.searchsorted([.5, 2, 4, 8, 16], np.sqrt(b['variance'][1]), side='right'))
                if population == 0:
                    counts[b['check_fold'], group, strength] += 1
            sl = np.s_[y:y+32, x:x+32]
            populations[sl] = population; groups[sl] = group; strengths[sl] = strength
            signature.append((x, y, reason, group, strength))
    identity = hashlib.sha256(json.dumps(signature, separators=(',', ':')).encode()).hexdigest()
    return populations, groups, strengths, counts, identity


def prepare(probes, output):
    if output.exists():
        raise ValueError('census output must be new')
    result = dict(schema=1, scope=__doc__, cases=[], source_pins={}, classifications=[])
    for path in probes:
        record = json.loads(path.read_text())
        source, base, previous = [read_frame(record[k]) for k in ('source', 'base', 'previous')]
        assert source is not None and base is not None
        for key in ('width', 'height', 'depth', 'shift', 'frame_id', 'pts', 'epoch'):
            assert record['source'][key] == record['base'][key]
        maximum = (1 << record['source']['depth']) - 1
        for decoded in (source, base, previous):
            if decoded is not None:
                assert all(np.all((plane >= 0) & (plane <= maximum)) for plane in decoded)
        result['source_pins'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for kind in ('source', 'base', 'previous'):
            if record[kind]['complete']:
                for view in record[kind]['planes']:
                    p = Path(view['path']); result['source_pins'][str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        y = rounded(source[0], base[0], .1)
        lookup = (y[::2, ::2] + y[::2, 1::2] + 1)//2
        assert np.all((lookup >= 0) & (lookup < (1 << record['source']['depth'])))
        for component in (1, 2):
            population, group, strength, counts, identity = population_map(record, source, previous, component)
            result['classifications'].append(dict(frame=record['frame_id'], component=component,
                                                 source_blocks=counts.tolist(), population_sha256=identity))
            # Source population and native lookup are separate coordinates.
            # Never certify a native lookup solely from a tile's mean brightness.
            keys = (((population*21+group)*7+strength)*1024+lookup).ravel()
            unique, inverse, occupancy = np.unique(keys, return_inverse=True, return_counts=True)
            for fraction in (0, .1, .25, .5, .75, 1):
                retained = rounded(source[component], base[component], fraction)
                changed = source[component] != retained
                changed_counts = np.bincount(inverse, weights=changed.ravel(), minlength=len(unique)).astype(np.int64)
                cells = []
                for encoded, total, altered in zip(unique, occupancy, changed_counts):
                    code = int(encoded % 1024); coordinate = int(encoded//1024)
                    sigma_group = coordinate % 7; coordinate //= 7
                    source_group = coordinate % 21; pop = coordinate//21
                    train = check = 0
                    if pop == 0:
                        train, check = map(int, counts[:, source_group, sigma_group])
                    cells.append(dict(population=pop, source_brightness_group=source_group,
                                      source_strength_group=sigma_group, native_lookup=code, scaling=0,
                                      samples=int(total), changed_samples=int(altered), train_blocks=train,
                                      check_blocks=check, measured=0, passed=0))
                frame = {k: record['source'][k] for k in ('width', 'height', 'depth', 'frame_id', 'pts', 'epoch')}
                frame['population_id'] = int(identity[:15], 16) or 1
                result['cases'].append(dict(id=f"frame{record['frame_id']}-c{component}-r{fraction}",
                                          frame=frame, component=component, retain=fraction,
                                          population_sha256=identity, cells=cells,
                                          independent_expected=dict(samples=int(changed.size),
                                              changed_samples=int(changed.sum()),
                                              population_samples=np.bincount(population.ravel(), minlength=4).tolist())))
        print('prepared frame', record['frame_id'], flush=True)
    output.write_text(json.dumps(result, separators=(',', ':'))+'\n')


def compare(census, binary, measured, output):
    if measured.exists() or output.exists():
        raise ValueError('replay and comparison outputs must be new')
    subprocess.run([str(binary), str(census), str(measured)], check=True, timeout=120)
    expected = json.loads(census.read_text()); actual = json.loads(measured.read_text())
    result = dict(complete=False, scope='Zero-synthesis native-base coverage; no fitted model qualification',
                  census_sha256=hashlib.sha256(census.read_bytes()).hexdigest(),
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), cases=[])
    try:
        assert actual['complete'] and len(actual['cases']) == len(expected['cases'])
        identities = {}
        for c, a in zip(expected['cases'], actual['cases']):
            e = c['independent_expected']; changed = e['changed_samples']
            assert a['id'] == c['id']
            assert a['samples'] == e['samples'] and a['population_samples'] == e['population_samples']
            assert a['unproven_changed_samples'] == changed
            # A grouped cell mixes changed/unchanged pixels at the same lookup.
            # Exact-zero counters count only entirely unchanged cells. They are
            # diagnostic; every unproven changed sample still rejects the picture.
            assert a['supported_samples'] == a['unsupported_synthesis_samples'] == 0
            assert a['coverage_pass'] == (changed == 0) and a['reasons'] == (64 if changed else 0)
            k = (c['frame']['frame_id'], c['component'])
            prior = identities.setdefault(k, c['population_sha256'])
            assert prior == c['population_sha256'], 'retention changed source classification'
            result['cases'].append({k: v for k, v in a.items() if k != 'id'} | {'id': a['id']})
        result['complete'] = True
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        output.write_text(json.dumps(result, indent=2)+'\n')
    print('coverage replay passed:', len(result['cases']), 'native component candidates')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('output', type=Path); p.add_argument('probes', type=Path, nargs='+')
    p = commands.add_parser('compare'); p.add_argument('census', type=Path); p.add_argument('binary', type=Path)
    p.add_argument('measured', type=Path); p.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args.probes, args.output)
    else: compare(args.census, args.binary, args.measured, args.output)
