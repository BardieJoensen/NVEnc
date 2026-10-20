#!/usr/bin/env python3
"""Replay the frozen cap policy with the independently reviewed observer fix."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_cap_trace import fingerprint
import policy_provenance as prov

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POLICY_SHA = 'a7fa1a5f102444d2a1aa87cd21afbae8b09b13ed748036368e37c06d533b4792'
BUILD_INDEX_SHA = '067f1ef1d7af99f67c7829e13bd135d3b6e840678e034f3a64ca6e17a81b2361'


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def identities(obj):
    if isinstance(obj, dict):
        if set(obj) == {'path', 'size', 'sha256'}:
            yield obj
        else:
            for value in obj.values():
                yield from identities(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from identities(value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tag')
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.tag)
    assert not any(k.startswith(('PANTHEON_', 'SVT_PANTHEON_', 'SVT_PSYEX_')) for k in os.environ)
    assert not any(os.environ.get(k) for k in ('LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT'))
    assert shutil.disk_usage(ROOT).free >= 160 * 2**30
    assert fingerprint(HERE / 'policy_provenance.py')['sha256'] == POLICY_SHA
    runs, index, index_row = prov.policy(HERE / 'policy-index-1.json', prov.POLICY_INDEX_SHA)
    build_index_row = fingerprint(HERE / 'observer-build-index-2.json')
    assert build_index_row['sha256'] == BUILD_INDEX_SHA
    build_index = prov.old.read(build_index_row)
    assert set(build_index) == {'pins', 'chain'}
    pins = prov.build(build_index['pins'], build_index['chain'], 'observer')
    cap = runs['cap']
    run = HERE / 'runs' / args.tag
    cmd = list(cap['argv'])
    assert cmd[:6] == ['/usr/bin/nice', '-n', '10', '/usr/bin/taskset', '-c', '0-7']
    assert cmd[6] == json.loads(Path(cap['pins']['path']).read_text())['app']['path']
    cmd[6] = pins['app']['path']
    for flag, name in (('--stats', 'pass.stats'), ('-b', 'out.ivf'), ('-o', 'recon.yuv')):
        assert cmd.count(flag) == 1
        cmd[cmd.index(flag) + 1] = str(run / name)
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(Path(pins['library']['path']).parent)
    env['SVT_PANTHEON_R18_CAP'] = '1'
    if args.preview:
        print(json.dumps(dict(argv=cmd, policy_index=index_row, observer_build_index=build_index_row,
                              control='Exact cap-1 IVF, all336 recon and stats required.'), indent=2))
        return
    run.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='prepared', mode='trace', tag=args.tag, argv=cmd,
                   script=fingerprint(__file__), policy_index=index_row,
                   observer_build_index=build_index_row, pins=build_index['pins'],
                   policy_pins=cap['pins'], parent=index['runs']['cap']['inner'],
                   control=index['runs']['baseline']['inner'],
                   contract=cap['contract'], observation_addendum=fingerprint(prov.ADDENDUM),
                   started_utc=utc(), outputs={},
                   scope='Observer replay only. Encoding cost and quality belong to immutable cap-1.')
    for name in ('case', 'request_kbps', 'settings', 'input', 'validity', 'source_mbps', 'original_receipt'):
        receipt[name] = cap[name]
    def save():
        (run / 'command.json').write_text(json.dumps(receipt, indent=2) + '\n')
    save()
    fds = []
    try:
        shutil.copyfile(__file__, run / 'measured-runner.py')
        shutil.copyfile(cap['outputs']['pass.stats']['path'], run / 'pass.stats')
        paths = {Path(x['path']).resolve() for x in identities([runs, index, build_index, pins])}
        paths.update(Path(x).resolve() for x in (str(Path(__file__)), str(run / 'measured-runner.py'),
                    str(run / 'pass.stats'), str(prov.ADDENDUM), str(HERE / 'policy_provenance.py'),
                    str(HERE / 'provenance.py'), str(HERE / 'read_cap_trace.py'),
                    index_row['path'], build_index_row['path'], sys.executable,
                    '/usr/bin/nice', '/usr/bin/taskset', '/usr/bin/ldd'))
        paths = sorted(paths)
        receipt['identity_before'] = [fingerprint(path) for path in paths]
        def ldd():
            p = subprocess.run(['/usr/bin/ldd', pins['app']['path']], env=env, capture_output=True, text=True)
            found = re.search(r'libSvtAv1Enc\.so\.3\s+=>\s+(\S+)', p.stdout)
            assert p.returncode == 0 and found and Path(found.group(1)).resolve() == Path(pins['library']['path']).resolve()
            return dict(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
        receipt['ldd_before'] = ldd()
        for variable, filename in (('SVT_PANTHEON_R18_FD', 'r18-trace.bin'),
                                   ('SVT_PANTHEON_BOUNDARY_FD', 'boundary.bin'),
                                   ('SVT_PANTHEON_COEFF_FD', 'coeff.bin')):
            fd = os.open(run / filename, os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_WRONLY, 0o644)
            fds.append(fd)
            env[variable] = str(fd)
        receipt['environment'] = {k: v for k, v in env.items() if k == 'LD_LIBRARY_PATH' or k.startswith('SVT_PANTHEON_')}
        receipt['resource_before'] = dict(free_bytes=shutil.disk_usage(ROOT).free, loadavg=Path('/proc/loadavg').read_text())
        receipt['status'] = 'running'
        save()
        started = time.monotonic()
        with (run / 'encode.log').open('x') as log:
            process = subprocess.run(cmd, cwd=run, env=env, stdout=log, stderr=subprocess.STDOUT, pass_fds=tuple(fds))
        receipt.update(returncode=process.returncode, seconds=time.monotonic()-started)
        for fd in fds:
            os.close(fd)
        fds.clear()
        for name in ('out.ivf', 'recon.yuv', 'pass.stats', 'encode.log', 'r18-trace.bin', 'boundary.bin', 'coeff.bin'):
            if (run / name).exists():
                receipt['outputs'][name] = fingerprint(run / name)
        save()
        assert process.returncode == 0
        for name in ('out.ivf', 'recon.yuv', 'pass.stats'):
            assert receipt['outputs'][name]['sha256'] == cap['outputs'][name]['sha256'], name
            assert receipt['outputs'][name]['size'] == cap['outputs'][name]['size'], name
        for name in ('r18-trace.bin', 'boundary.bin', 'coeff.bin'):
            assert 64 < receipt['outputs'][name]['size'] <= 512 * 2**20, name
        receipt['exact_policy_observer_neutrality'] = True
        receipt['ldd_after'] = ldd()
        # Loader addresses vary; verify the same resolved library independently above.
        prov.build(build_index['pins'], build_index['chain'], 'observer')
        receipt['identity_after'] = [fingerprint(path) for path in paths]
        assert receipt['identity_before'] == receipt['identity_after']
        receipt['resource_after'] = dict(free_bytes=shutil.disk_usage(ROOT).free, loadavg=Path('/proc/loadavg').read_text())
        assert receipt['resource_after']['free_bytes'] >= 120 * 2**30
        receipt.update(status='complete', ended_utc=utc())
        save()
        print(json.dumps(dict(receipt=fingerprint(run / 'command.json'), seconds=receipt['seconds'])))
    except BaseException as error:
        receipt.update(status='failed', error=repr(error), ended_utc=utc())
        save()
        raise
    finally:
        for fd in fds:
            os.close(fd)


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('optimized Python prohibited')
    main()
