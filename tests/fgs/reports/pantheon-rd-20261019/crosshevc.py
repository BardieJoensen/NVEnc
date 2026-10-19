#!/usr/bin/env python3
"""Bounded native 10-bit x265 slow/grain two-pass feasibility control."""
import json
import subprocess
import sys
import time
from pathlib import Path

from analyze import ROOT, x
from packet_window import measure, audit


case, tag, request = sys.argv[1], sys.argv[2], int(sys.argv[3])
assert case in ('e04', 'e05-1440') and tag.startswith('x265-grain-2x')
d = ROOT / 'parent/crosscodec' / case / tag
d.mkdir(parents=True, exist_ok=False)
ffmpeg = '/usr/bin/ffmpeg'
fixture = ROOT / 'fixtures' / case
src = fixture / 'input10.y4m'
source_stat = x.fingerprint(src)
hashes = x.hashes([ffmpeg, '-v', 'error', '-threads', '4', '-i', str(src),
                   '-frames:v', '336', '-pix_fmt', 'yuv420p10le'])
assert len(hashes) == 336
lift_hashes = x.hashes([ffmpeg, '-v', 'error', '-threads', '4', '-i', str(fixture / 'input.mkv'),
                        '-frames:v', '336', '-pix_fmt', 'yuv420p10le'])
assert hashes == lift_hashes
script_snapshot = x.fingerprint(__file__)
ffmpeg_version = subprocess.run([ffmpeg, '-version'], check=True, capture_output=True, text=True).stdout.splitlines()[:2]
ffmpeg_ldd = subprocess.run(['ldd', ffmpeg], check=True, capture_output=True, text=True).stdout
x.dump(d / 'input-validation.json', {
    'all336_input10_frames_present': True,
    'hashes': hashes,
    'input': source_stat,
    'scope': 'native 10-bit HEVC x265 slow/grain two-pass control',
})

stats = d / 'x265-pass'
common = [
    'nice', '-n', '10', 'taskset', '-c', '0-7', ffmpeg, '-hide_banner', '-v', 'info',
    '-threads', '4', '-f', 'yuv4mpegpipe', '-i', str(src), '-an', '-sn',
    '-frames:v', '336', '-fps_mode', 'passthrough', '-c:v', 'libx265',
    '-preset', 'slow', '-tune', 'grain', '-b:v', str(request * 1000),
    '-pix_fmt', 'yuv420p10le', '-threads', '4', '-x265-params',
    f'pass={{phase}}:stats={stats}:pools=4:frame-threads=2',
    *x.COLOR,
]
records = []
for phase in (1, 2):
    params = [p.replace('{phase}', str(phase)) for p in common]
    cmd = params + (['-f', 'null', '/dev/null'] if phase == 1 else [str(d / 'out.mkv')])
    start = time.monotonic()
    with (d / f'pass{phase}.log').open('wb') as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - start
    records.append({'argv': cmd, 'seconds': elapsed, 'returncode': proc.returncode})
    logtext = (d / f'pass{phase}.log').read_text(errors='replace')
    assert 'warning' not in logtext.lower() and 'unknown option' not in logtext.lower()
    if phase == 1:
        assert stats.is_file() and stats.stat().st_size > 0
        assert 'stats-write' in logtext
        stats_sha = __import__('hashlib').sha256(stats.read_bytes()).hexdigest()
    else:
        assert 'stats-read' in logtext
    x.dump(d / 'command.json', {
        'passes': records, 'ffmpeg': x.fingerprint(ffmpeg), 'input': source_stat,
        'request_kbps': request, 'target_multiple': 2, 'preset': 'slow',
        'tune': 'grain', 'pix_fmt': 'yuv420p10le', 'threads': 4,
        'x265_params': 'pass={phase}:stats=<output>/x265-pass:pools=4:frame-threads=2',
        'script': script_snapshot,
        'ffmpeg_version': ffmpeg_version,
        'ffmpeg_ldd_sha256': __import__('hashlib').sha256(ffmpeg_ldd.encode()).hexdigest(),
        'scope': 'native 10-bit HEVC x265 two-pass slow/grain; 336-frame statistics only',
    })
    assert proc.returncode == 0, (d / f'pass{phase}.log').read_text()[-4000:]

assert x.fingerprint(src) == source_stat
rate, selected, first = measure(d / 'out.mkv', x.CASES[case][2])
probe = x.probe(d / 'out.mkv')
s = probe['streams'][0]
assert s['codec_name'] == 'hevc' and s['pix_fmt'] == 'yuv420p10le'
assert (s['width'], s['height']) == (1920, 1080)
assert [s[k] for k in ['color_range', 'color_space', 'color_transfer', 'color_primaries']] == ['tv', 'bt709', 'bt709', 'bt709']
x.dump(d / 'validation.json', {
    'actual_mbps': rate, 'selected_packets': selected, 'probe': probe,
    'input': source_stat, 'output': x.fingerprint(d / 'out.mkv'),
    'seconds_total': sum(r['seconds'] for r in records),
    'input_hashes_equal_fixture_lift': True,
    'stats_sha256_after_pass1': stats_sha,
    'script_snapshot': script_snapshot,
    'ffmpeg_version': ffmpeg_version,
    'ffmpeg_ldd_sha256': __import__('hashlib').sha256(ffmpeg_ldd.encode()).hexdigest(),
})
print(case, tag, 'actual', rate, 'Mbps; two-pass wall seconds', sum(r['seconds'] for r in records), flush=True)
audit(case, tag)
