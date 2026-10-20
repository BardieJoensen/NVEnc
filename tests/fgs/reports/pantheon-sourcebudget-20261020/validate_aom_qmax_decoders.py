#!/usr/bin/env python3
"""Validate all336 decoded samples; no quality or playback claim."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT', '/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
RUN = ROOT / 'worker/aom-qmax-r7/runs/e05-1440/qmax-qmax8-r3-1'
V = RUN / 'decoder-validation'
N, FRAME_BYTES = 336, 1920*1080*3
EXPECTED = {'out.mkv': 'eecce0255ae52caf357d088d930ea4b237496f0b8676efdc6c990ec394bc3ea2',
            'out.ivf': '16aa2b72b4ef0f66b4bc172dd44f7505f682957434677a38db439e8ff9e292f2',
            'command.json': '7df965d84e0d4ecedb7c94df6743a4cedaf113948f50afa4ae34eb59321e12a8'}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def identity(path):
    path = Path(path).absolute()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return {'path': str(path), 'sha256': h.hexdigest(), 'size': path.stat().st_size}


def capture(argv):
    p = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, (argv, p.stderr)
    return {'argv': argv, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def tools():
    result = {}
    for name in ('ffmpeg', 'ffprobe'):
        path = '/usr/bin/' + name
        result[name] = {'file': identity(path), 'version': capture([path, '-version'])}
    libraries = {}
    ldd = capture(['/usr/bin/ldd', '/usr/bin/ffmpeg'])
    for line in ldd['stdout'].splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[1] == '=>' and fields[0].startswith(('libaom.', 'libdav1d.')):
            path = Path(fields[2])
            libraries[fields[0]] = {'file': identity(path), 'realpath': str(path.resolve())}
    assert any(k.startswith('libaom.') for k in libraries)
    assert any(k.startswith('libdav1d.') for k in libraries)
    result['libraries'] = libraries
    result['gpu'] = {'file': identity('/usr/bin/nvidia-smi'), 'driver': capture([
        '/usr/bin/nvidia-smi', '--query-gpu=driver_version,name,uuid', '--format=csv,noheader'])}
    result['decoders'] = capture(['/usr/bin/ffmpeg', '-hide_banner', '-decoders'])
    for name in ('libdav1d', 'libaom-av1', 'av1_cuvid'):
        assert re.search(r'\s' + re.escape(name) + r'\s', result['decoders']['stdout'])
    return result


def parse_framemd5(path):
    rows, tb = [], None
    for line in Path(path).read_text().splitlines():
        if line.startswith('#tb '):
            match = re.fullmatch(r'#tb\s+0:\s+(\d+)/(\d+)', line)
            assert match and tb is None, line
            tb = tuple(map(int, match.groups()))
            assert tb == (1, 24), tb
        if not line or line.startswith('#'):
            continue
        fields = [s.strip() for s in line.split(',')]
        assert len(fields) == 6, fields
        stream, dts, pts, duration, size = map(int, fields[:5])
        assert (stream, dts, pts, duration, size) == (0, len(rows), len(rows), 1, FRAME_BYTES)
        assert re.fullmatch('[0-9a-f]{32}', fields[5]), fields[5]
        rows.append(fields[5])
    assert tb == (1, 24) and len(rows) == N, (tb, len(rows))
    return rows


def raw_hashes(path):
    hashes = []
    with Path(path).open('rb') as f:
        for _ in range(N):
            b = f.read(FRAME_BYTES)
            assert len(b) == FRAME_BYTES
            hashes.append(hashlib.md5(b).hexdigest())
        assert not f.read(1)
    return hashes


def main():
    forbidden = ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT', 'AOM_TU_TRACE_FD',
                 'AOM_TRACE_PATH', 'AOM_TRACE_FD', 'AOM_NEUTRALIZE_SOURCE')
    assert not any(os.environ.get(k) for k in forbidden)
    assert shutil.disk_usage(ROOT).free >= 130 * 2**30
    assert not V.exists(), 'Refusing overwrite'
    inputs = {k: identity(RUN/k) for k in EXPECTED}
    assert {k: v['sha256'] for k, v in inputs.items()} == EXPECTED
    parent = json.loads((RUN/'command.json').read_text())
    assert parent['status'] == 'diagnostic_encoded' and parent['returncode'] == 0
    V.mkdir()
    receipt = {'status': 'started', 'started_utc': utc(), 'commands': [],
               'input_ivf': inputs['out.ivf'], 'output': inputs['out.mkv'],
               'run_receipt': inputs['command.json'], 'frame_count': N,
               'geometry': [1920, 1080], 'frame_bytes': FRAME_BYTES,
               'scope': 'Sample identity only; no quality or playback claim.'}
    def save():
        (V/'decoder-validation.json').write_text(json.dumps(receipt, indent=2)+'\n')
    save()
    try:
        script_path = V/'measured-validator.py'
        shutil.copyfile(__file__, script_path)
        receipt['script'] = identity(script_path)
        receipt['source_script'] = identity(__file__)
        assert receipt['script']['sha256'] == receipt['source_script']['sha256']
        receipt['identity_before'] = tools()
        expected = parent['expected_identity']
        for name in ('ffmpeg', 'ffprobe'):
            assert receipt['identity_before'][name]['file']['sha256'] == expected[name+'_sha256']
        for name, lib in receipt['identity_before']['libraries'].items():
            if name.startswith('libaom.'):
                assert lib['file']['sha256'] == expected['linked_libaom'][lib['file']['path']]['sha256']
        save()
        probe = capture(['/usr/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
                         '-show_streams', '-show_packets', '-of', 'json', str(RUN/'out.mkv')])
        probe_path = V/'input-probe-command.json'
        probe_path.write_text(json.dumps(probe, indent=2)+'\n')
        receipt['input_probe'] = identity(probe_path)
        data = json.loads(probe['stdout'])
        assert len(data['streams']) == 1
        stream = data['streams'][0]
        assert [stream[k] for k in ('codec_name', 'width', 'height', 'pix_fmt')] == ['av1', 1920, 1080, 'yuv420p10le']
        assert [stream[k] for k in ('color_range', 'color_space', 'color_transfer', 'color_primaries')] == ['tv', 'bt709', 'bt709', 'bt709']
        assert stream['time_base'] == '1/1000' and stream['r_frame_rate'] == '24/1'
        packets = data['packets']
        assert len(packets) == N
        assert all(p['stream_index'] == 0 for p in packets)
        assert [p['pts'] for p in packets] == [(i*1000+12)//24 for i in range(N)]
        base = ['nice', '-n', '10', 'taskset', '-c', '8-11', '/usr/bin/ffmpeg',
                '-hide_banner', '-v', 'error', '-n', '-threads', '4']
        output = ['-map', '0:v:0', '-frames:v', str(N), '-pix_fmt', 'yuv420p10le',
                  '-c:v', 'rawvideo', '-threads', '4']
        commands = [
            ('dav1d', base+['-c:v', 'libdav1d', '-filmgrain', '0', '-i', str(RUN/'out.mkv')]+output+['-f', 'rawvideo', str(V/'dav1d-decoded.yuv')]),
            ('libaom', base+['-c:v', 'libaom-av1', '-i', str(RUN/'out.mkv')]+output+['-f', 'framemd5', str(V/'libaom.framemd5')]),
            ('nvdec', base+['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda', '-c:v', 'av1_cuvid', '-i', str(RUN/'out.mkv'), '-vf', 'hwdownload,format=p010le,format=yuv420p10le']+output+['-f', 'framemd5', str(V/'nvdec.framemd5')])]
        receipt['planned_commands'] = dict(commands)
        save()
        for name, argv in commands:
            log = V/(name+'.log')
            row = {'name': name, 'argv': argv, 'started_utc': utc()}
            receipt['commands'].append(row)
            save()
            started = time.monotonic()
            with log.open('w') as f:
                proc = subprocess.run(argv, cwd=V, stdout=f, stderr=subprocess.STDOUT)
            row.update(returncode=proc.returncode, seconds=time.monotonic()-started,
                       finished_utc=utc(), log=identity(log))
            if Path(argv[-1]).is_file():
                row['output'] = identity(argv[-1])
            command_path = V/(name+'-command.json')
            command_path.write_text(json.dumps(row, indent=2)+'\n')
            row['receipt'] = identity(command_path)
            save()
            assert proc.returncode == 0 and row['output']['size'] > 0, row
        hashes = raw_hashes(V/'dav1d-decoded.yuv')
        assert hashes == parse_framemd5(V/'libaom.framemd5') == parse_framemd5(V/'nvdec.framemd5')
        receipt['identity_after'] = tools()
        assert receipt['identity_after'] == receipt['identity_before']
        assert inputs == {k: identity(RUN/k) for k in EXPECTED}
        assert receipt['script'] == identity(script_path)
        assert receipt['source_script'] == identity(__file__)
        for row in receipt['commands']:
            for key in ('output', 'log', 'receipt'):
                assert row[key] == identity(row[key]['path'])
        receipt.update(status='admitted', all336_allplanes_libaom_dav1d_NVDEC_exact=True,
                       hashes=hashes, decoded_raw=identity(V/'dav1d-decoded.yuv'),
                       finished_utc=utc())
        save()
        print(json.dumps({'status': receipt['status'], 'frames': len(hashes)}))
    except BaseException as exc:
        receipt.update(status='failed', error=repr(exc), finished_utc=utc())
        save()
        raise


if __name__ == '__main__':
    main()
