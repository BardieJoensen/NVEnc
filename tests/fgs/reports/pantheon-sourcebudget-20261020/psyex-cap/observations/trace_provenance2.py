"""Admit a corrected observer replay without conflating the two build domains."""
from pathlib import Path
from read_cap_trace import fingerprint
import policy_provenance as policy

HERE = Path(__file__).resolve().parent
REPLAY_SHA = '8276cad4df501913b9e05604f91ceb91020fc56d7157cde0dd7146b63ef3626d'
POLICY_SHA = 'a7fa1a5f102444d2a1aa87cd21afbae8b09b13ed748036368e37c06d533b4792'
BUILD_INDEX_SHA = '067f1ef1d7af99f67c7829e13bd135d3b6e840678e034f3a64ca6e17a81b2361'


def validate(index_path, index_sha):
    assert fingerprint(HERE / 'policy_provenance.py')['sha256'] == POLICY_SHA
    assert fingerprint(HERE / 'replay_observer2.py')['sha256'] == REPLAY_SHA
    row = fingerprint(index_path)
    assert row['sha256'] == index_sha
    index = policy.old.read(row)
    assert set(index) == {'policy_index', 'observer_build_index', 'trace'}
    runs, original_index, policy_row = policy.policy(index['policy_index']['path'], index['policy_index']['sha256'])
    assert index['policy_index'] == policy_row
    build_row = index['observer_build_index']
    assert build_row['sha256'] == BUILD_INDEX_SHA
    build_index = policy.old.read(build_row)
    assert set(build_index) == {'pins', 'chain'}
    pins = policy.build(build_index['pins'], build_index['chain'], 'observer')
    item = index['trace']
    assert set(item) == {'inner', 'outer'}
    obj = policy.old.read(item['inner'])
    assert obj['status'] == 'complete' and obj['returncode'] == 0 and obj['mode'] == 'trace'
    assert obj['script'] == fingerprint(HERE / 'replay_observer2.py')
    assert obj['policy_index'] == policy_row and obj['observer_build_index'] == build_row
    assert obj['pins'] == build_index['pins']
    cap = runs['cap']
    assert obj['policy_pins'] == cap['pins']
    assert obj['parent'] == original_index['runs']['cap']['inner']
    assert obj['control'] == original_index['runs']['baseline']['inner']
    assert obj['observation_addendum'] == fingerprint(policy.ADDENDUM)
    for key in ('case', 'request_kbps', 'settings', 'input', 'validity', 'source_mbps', 'original_receipt', 'contract'):
        assert obj[key] == cap[key], key
    folder = HERE / 'runs' / obj['tag']
    assert Path(item['inner']['path']) == folder / 'command.json'
    expected = list(cap['argv'])
    expected[6] = pins['app']['path']
    for flag, name in (('--stats', 'pass.stats'), ('-b', 'out.ivf'), ('-o', 'recon.yuv')):
        expected[expected.index(flag)+1] = str(folder / name)
    assert obj['argv'] == expected
    expected_env = dict(LD_LIBRARY_PATH=str(Path(pins['library']['path']).parent), SVT_PANTHEON_R18_CAP='1')
    fds = []
    for key in ('SVT_PANTHEON_R18_FD', 'SVT_PANTHEON_BOUNDARY_FD', 'SVT_PANTHEON_COEFF_FD'):
        value = obj['environment'][key]
        assert value.isdigit() and int(value) >= 3
        fds.append(value)
        expected_env[key] = value
    assert len(set(fds)) == 3 and obj['environment'] == expected_env
    policy.old.outer(item['outer'], HERE / 'replay_observer2.py', REPLAY_SHA, [obj['tag']])
    assert obj['identity_before'] == obj['identity_after']
    assert len({x['path'] for x in obj['identity_after']}) == len(obj['identity_after'])
    for identity in obj['identity_after']:
        assert fingerprint(identity['path']) == identity
    assert obj['exact_policy_observer_neutrality'] is True
    assert set(obj['outputs']) == {'out.ivf', 'recon.yuv', 'pass.stats', 'encode.log', 'r18-trace.bin', 'boundary.bin', 'coeff.bin'}
    for name, identity in obj['outputs'].items():
        assert identity['path'] == str(folder / name)
        assert fingerprint(identity['path']) == identity
    for name in ('out.ivf', 'recon.yuv', 'pass.stats'):
        for key in ('size', 'sha256'):
            assert obj['outputs'][name][key] == cap['outputs'][name][key]
    for name in ('r18-trace.bin', 'boundary.bin', 'coeff.bin'):
        assert 64 < obj['outputs'][name]['size'] <= 512 * 2**20
    assert obj['resource_before']['free_bytes'] >= 160 * 2**30
    assert obj['resource_after']['free_bytes'] >= 120 * 2**30
    assert fingerprint(index_path) == row
    runs['trace'] = obj
    return runs, row
