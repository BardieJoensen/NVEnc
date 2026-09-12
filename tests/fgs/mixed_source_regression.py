#!/usr/bin/env python3
"""Source-referenced regression for grain on clean foreground/chroma regions.

The same frame contains clean artwork and noisy background at equal luma,
plus noisy regions at other levels. Tests both output depths and quiet-region
reappearance. An all-grain-off candidate fails the independent noisy regions.
Run a retained bad encoder with --expect-rejected to qualify the detector.
No external media fixtures are required; generation is deterministic.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

W, H, FRAMES = 960, 544, 64
LEVELS = [64, 112, 160, 208]


def generate(path, bits):
    rng = np.random.default_rng(20260912)
    scale = 1 << (bits - 8)
    dtype = np.uint8 if bits == 8 else np.dtype('<u2')
    base = np.repeat(LEVELS, W // 4)[None, :] + np.zeros((H, W))
    with path.open('wb') as target:
        csp = '420mpeg2' if bits == 8 else '420p10'
        target.write(f'YUV4MPEG2 W{W} H{H} F24:1 Ip A1:1 C{csp}\n'.encode())
        for n in range(FRAMES):
            y = base + rng.normal(0, 3, (H, W))
            u = 128 + rng.normal(0, 1.2, (H//2, W//2))
            v = 128 + rng.normal(0, 1.2, (H//2, W//2))
            if not 32 <= n < 36:
                y[96:224, 272:432] = 112
                # Source chroma is clean while co-located luma remains noisy.
                u[48:112, 256:336] = 128
                v[160:224, 136:216] = 128
            target.write(b'FRAME\n')
            for plane in [y, u, v]:
                target.write(np.rint(plane * scale).astype(dtype).tobytes())


def decode(video, grain, bits, log):
    cmd = ['ffmpeg', '-v', 'error', '-xerror', '-threads', '2']
    if video.suffix != '.y4m':
        cmd += ['-c:v', 'libdav1d', '-filmgrain', str(grain)]
    cmd += ['-i', str(video), '-an', '-sn', '-dn',
           '-pix_fmt', 'yuv420p' if bits == 8 else 'yuv420p10le',
           '-f', 'rawvideo', '-']
    (log.with_suffix('.command.json')).write_text(json.dumps(cmd, indent=2)+'\n')
    with log.open('w') as stream:
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stream)
        dtype = np.uint8 if bits == 8 else np.dtype('<u2')
        count = W * H * 3 // 2
        try:
            while True:
                raw = child.stdout.read(count * np.dtype(dtype).itemsize)
                if not raw:
                    break
                if len(raw) != count * np.dtype(dtype).itemsize:
                    raise RuntimeError('Truncated decoded frame')
                a = np.frombuffer(raw, dtype=dtype).astype(np.float32) / (1 << (bits-8))
                yield [a[:W*H].reshape(H,W), a[W*H:W*H*5//4].reshape(H//2,W//2), a[W*H*5//4:].reshape(H//2,W//2)]
            if child.wait(timeout=30):
                raise RuntimeError('Independent decoder failed')
        finally:
            child.stdout.close()
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=30)


def measure(video, bits, directory):
    on = decode(video, 1, bits, directory/'grain-on.log')
    off = decode(video, 0, bits, directory/'grain-off.log')
    quiet = [(slice(128,192),slice(304,400)), (slice(64,96),slice(272,320)), (slice(176,208),slice(152,200))]
    noisy = [(slice(256,480),slice(40,200)), (slice(128,240),slice(20,100)), (slice(128,240),slice(20,100))]
    rows = []
    try:
        for n in range(FRAMES):
            a,b=next(on),next(off)
            rows.append(dict(frame=n,quiet_source=not 32<=n<36,
                quiet_sigma=[float(a[p][quiet[p]].std()) for p in range(3)],
                quiet_added=[float((a[p][quiet[p]]-b[p][quiet[p]]).std()) for p in range(3)],
                noisy_added=[float((a[p][noisy[p]]-b[p][noisy[p]]).std()) for p in range(3)],
                noisy_total=[float(a[p][noisy[p]].std()) for p in range(3)]))
        if next(on,None) is not None or next(off,None) is not None:
            raise RuntimeError('Unexpected extra displayed frame')
    finally:
        on.close();off.close()
    peak=np.max([r['quiet_sigma'] for r in rows if r['quiet_source']],axis=0)
    added=np.max([r['quiet_added'] for r in rows if r['quiet_source']],axis=0)
    background=np.median([r['noisy_added'] for r in rows[8:]],axis=0)
    total=np.median([r['noisy_total'] for r in rows[8:]],axis=0)
    checks=dict(no_invented_grain=bool(np.all(added<=.3)),
                genuine_grain_present=bool(np.all(background>np.array([.5,.15,.15]))),
                background_variance_preserved=bool(np.all(total>np.array([1.5,.4,.4]))))
    return dict(bits=bits,frames=len(rows),peak_quiet_sigma=peak.tolist(),peak_quiet_added=added.tolist(),
                median_background_grain_sigma=background.tolist(),median_background_total_sigma=total.tolist(),
                checks=checks,passed=all(checks.values()),per_frame=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nvencc',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expect-rejected',action='store_true')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for bits in [8,10]:
        directory=args.output/str(bits);directory.mkdir(exist_ok=True)
        source,video=directory/'source.y4m',directory/'candidate.mkv'
        if video.exists():raise RuntimeError('Refusing to overwrite retained trial')
        generate(source,bits)
        cmd=[str(args.nvencc),'--avsw','-i',str(source),'--codec','av1','--cqp','20',
             '--output-depth',str(bits),'--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral',
             '--colormatrix','bt709','--colorprim','bt709','--transfer','bt709','--colorrange','limited',
             '--log-level','debug','--film-grain-table-out',str(directory/'planned.tbl'),'-o',str(video)]
        (directory/'encode-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        with (directory/'encode.log').open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        result=measure(video,bits,directory)
        # Separate FGS from ordinary lossy chroma prediction/quantization. In
        # this fixture conventional NVENC also leaves up to one native code
        # of chroma variation. Compare with that independently encoded control
        # and require the unencoded filter output itself to preserve the source.
        controls={}
        for label,raw in [('conventional',False),('raw',True)]:
            cd=directory/label;cd.mkdir(exist_ok=True)
            control=cd/('output.y4m' if raw else 'output.mkv')
            cc=[str(args.nvencc),'--avsw','-i',str(source),'--codec','raw' if raw else 'av1',
                '--output-depth',str(bits),'--log-level','debug','--colormatrix','bt709',
                '--colorprim','bt709','--transfer','bt709','--colorrange','limited','-o',str(control)]
            if raw:cc+=['--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral',
                       '--film-grain-table-out',str(cd/'planned.tbl')]
            else:cc+=['--cqp','20']
            (cd/'encode-command.json').write_text(json.dumps(cc,indent=2)+'\n')
            with (cd/'encode.log').open('w') as log:
                subprocess.run(cc,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            controls[label]=measure(control,bits,cd)
        result['controls']=controls
        result['checks']['raw_source_preserved']=bool(np.all(np.array(controls['raw']['peak_quiet_sigma'])<=.3))
        result['checks']['encoded_source_preserved']=bool(np.all(np.array(result['peak_quiet_sigma'])
            <=np.array(controls['conventional']['peak_quiet_sigma'])+.3))
        result['checks']['quiet_source_preserved']=all(result['checks'][k] for k in
            ['no_invented_grain','raw_source_preserved','encoded_source_preserved'])
        result['passed']=all(result['checks'].values())
        result['source_sha256']=hashlib.file_digest(source.open('rb'),'sha256').hexdigest()
        result['video_sha256']=hashlib.file_digest(video.open('rb'),'sha256').hexdigest()
        results.append(result)
    report=dict(candidate=str(args.nvencc),candidate_sha256=hashlib.file_digest(args.nvencc.open('rb'),'sha256').hexdigest(),
                expected='rejection' if args.expect_rejected else 'pass',results=results)
    report['passed']=all((not r['checks']['quiet_source_preserved'] if args.expect_rejected else r['passed']) for r in results)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
    for result in results:print(json.dumps({k:v for k,v in result.items() if k not in ('per_frame','controls')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
