"""Explicit policy-build and observer-build provenance for the R18 correction."""
import importlib.util
import json
from pathlib import Path
from read_cap_trace import fingerprint
import provenance as old

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POLICY_INDEX_SHA = '10cf5a2006cdaf5660627e79def9da43a947ebe0d7ba967b5a288b20e440d067'
OBSERVER_PREP_SHA = '9e76dd20d762bf2270ec19cbc8c874d829dccbc0d1c31a45eaf913919d9e9cef'
ADDENDUM = Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND18_OBSERVER_CORRECTION.md')
ADDENDUM_SHA = '3a4848fb219c874117ec43e80931356c96c5cc8c89d03b796ed79e3dd2531957'
BUILD_EXPECTED = {
    'policy': ('build-1', old.PINS_SHA, old.PREPARATION_SHA,
               'f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca',
               '5f03edf1ba320c84006e65484e88742ffb60b2de422b73b10346ea90ca9ed5d0',
               '5406b49c7adf70f5b1261f46d701186f15c0e17b89a87fddc32fc539e2b88e2c'),
    'observer': ('build-observer-2', 'b8f5e1353621974462b9d8840faaa53282c77312e470816932c80c6aae8cce82', OBSERVER_PREP_SHA,
                 '305f06b51bf94988bd9d6c1002cfa880736071799f52d38f3bc7c25f5248a22b',
                 'a53d222914c87e20cbedd12497774a93a375448c53a3fe78c60a93e616505024',
                 '566197111539997ad89180f6db36c969dc87fdf1aa9fcb4ff9e67adf058393ff'),
}


def dependencies():
    for name, digest in (
        ('run.py', old.RUN_SHA),
        ('provenance.py', 'b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f'),
        ('read_cap_trace.py', '08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8')):
        assert fingerprint(HERE / name)['sha256'] == digest
    assert fingerprint(old.OUTER)['sha256'] == old.OUTER_SHA
    assert fingerprint(ADDENDUM)['sha256'] == ADDENDUM_SHA


def build(row, chain, domain):
    dependencies()
    folder, pins_sha, prep_sha, manifest_sha, patch_sha, review_sha = BUILD_EXPECTED[domain]
    assert row['path'] == str(HERE / folder / 'completed-build-pins.json')
    if pins_sha is not None:
        assert row['sha256'] == pins_sha
    pins = old.read(row)
    assert pins['status'] == 'build_complete' and pins['returncode'] == 0
    for value in pins.values():
        if isinstance(value, dict) and {'path', 'size', 'sha256'} <= value.keys():
            assert fingerprint(value['path']) == value
    assert pins['source_manifest']['sha256'] == pins['manifest_before']['sha256'] == pins['manifest_after']['sha256'] == manifest_sha
    assert pins['patch']['sha256'] == patch_sha
    assert pins['implementation_review']['sha256'] == review_sha
    assert pins['preparation']['path'] == str(HERE / folder / 'preparation.json')
    assert pins['preparation']['sha256'] == prep_sha
    prep = old.read(pins['preparation'])
    build_root = HERE / folder
    assert set(chain) == {'prepare', 'build', 'pin'}
    old.outer(chain['prepare'], HERE / 'prepare_build.py',
              'f0c29f5be5bd910f7bf7ea04b021005fbdeb7dbfeb4730937386f4d6510b58e8',
              [prep['source'], prep['manifest']['path'], prep['manifest']['sha256'], build_root])
    old.outer(chain['build'], HERE / 'execute_build.py',
              '7f366b22bcd3d38bd87e32c7af58753925a4efd99920280fc7b47248531b6a32',
              [pins['preparation']['path'], pins['preparation']['sha256']])
    launch = old.read(fingerprint(build_root / 'launch.json'))
    assert launch['status'] == 'complete' and launch['returncode'] == 0
    assert launch['argv'] == ['/usr/bin/bash', prep['runner']['path']]
    assert launch['inputs_before'] == launch['inputs_after']
    assert {x['path'] for x in launch['inputs_before']} == {
        str(HERE / 'execute_build.py'), pins['preparation']['path'], prep['runner']['path'], '/usr/bin/bash'}
    for item in launch['inputs_after']:
        assert fingerprint(item['path']) == item
    old.outer(chain['pin'], HERE / 'pin_build.py',
              'dd5093a3cddd6e309e36e51f329dea2937c2591c8524c5659b55896655f84d9a',
              [build_root, prep_sha, pins['patch']['path'], patch_sha,
               pins['implementation_review']['path'], review_sha])
    source = Path(pins['source_root'])
    rows = []
    for path in sorted(source.rglob('*')):
        rel = path.relative_to(source)
        if '.git' in rel.parts:
            continue
        assert not path.is_symlink()
        if path.is_file():
            item = fingerprint(path)
            rows.append([str(rel), item['size'], item['sha256']])
    assert rows == old.read(pins['source_manifest'])
    return pins


def policy(path, digest):
    dependencies()
    row = fingerprint(path)
    assert row['sha256'] == digest == POLICY_INDEX_SHA
    index = old.read(row)
    assert set(index) == {'runs', 'build'} and set(index['runs']) == {'baseline', 'pass1', 'cap'}
    spec = importlib.util.spec_from_file_location('r18_original_runner', old.RUN)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runs = {}
    for mode in ('baseline', 'pass1', 'cap'):
        item = index['runs'][mode]
        assert set(item) == {'inner', 'outer'}
        obj = runner.read_receipt(item['inner']['path'], item['inner']['sha256'], mode)
        assert Path(item['inner']['path']).parent == HERE / 'runs' / obj['tag']
        args = [mode, obj['tag'], obj['pins']['path'], obj['pins']['sha256']]
        if mode == 'cap':
            assert obj['control'] == index['runs']['baseline']['inner']
            assert obj['parent'] == index['runs']['pass1']['inner']
            args += ['--control', obj['control']['path'], '--control-sha', obj['control']['sha256'],
                     '--parent', obj['parent']['path'], '--parent-sha', obj['parent']['sha256']]
        old.outer(item['outer'], old.RUN, old.RUN_SHA, args)
        runs[mode] = obj
    assert all(run['pins'] == runs['cap']['pins'] for run in runs.values())
    build(runs['cap']['pins'], index['build'], 'policy')
    assert fingerprint(path) == row
    return runs, index, row
