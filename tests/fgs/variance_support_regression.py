#!/usr/bin/env python3
"""Thin highlights and non-flat smooth source regions beside genuine grain.

Keep the retained old encoder as a negative control. This is a bounded
developer fixture, not a visibility threshold or a production media validator.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import mixed_source_regression as mixed

W, H, FRAMES = mixed.W, mixed.H, mixed.FRAMES
REGIONS = {'highlight': (slice(120,128),slice(272,432)),
           'smooth': (slice(248,256),slice(512,672)),
           'genuine': (slice(320,480),slice(48,192))}


def generate(path, bits):
    rng = np.random.default_rng(20260916)
    base = np.repeat([64,112,160,208], W//4)[None,:] + np.zeros((H,W))
    scale = 1 << (bits-8)
    dtype = np.uint8 if bits == 8 else np.dtype('<u2')
    with path.open('wb') as stream:
        csp = '420mpeg2' if bits == 8 else '420p10'
        stream.write(f'YUV4MPEG2 W{W} H{H} F24:1 Ip A1:1 C{csp}\n'.encode())
        for n in range(FRAMES):
            y = base + rng.normal(0,6,(H,W))
            if not 32 <= n < 36:
                # Each eight-row region straddles the coarser 16/32-row
                # evidence. Neither is an exactly flat-source control.
                y[REGIONS['highlight']] = np.clip(234+rng.normal(0,1,(8,160)),16,235)
                y[REGIONS['smooth']] = 128+rng.normal(0,1.5,(8,160))
            u = 128+rng.normal(0,1.2,(H//2,W//2))
            v = 128+rng.normal(0,1.2,(H//2,W//2))
            stream.write(b'FRAME\n')
            for plane in (y,u,v):
                stream.write(np.rint(np.clip(plane,0,255)*scale).astype(dtype).tobytes())


def measure(source, candidate, bits, directory):
    streams = [mixed.decode(path, grain, bits, directory/(name+'.log'))
               for path,grain,name in ((source,0,'source'),(candidate,1,'on'),(candidate,0,'off'))]
    rows=[]
    try:
        for n in range(FRAMES):
            s,on,off = [next(stream)[0] for stream in streams]
            regions={}
            for name,roi in REGIONS.items():
                regions[name]=dict(source_sigma=float(s[roi].std()),
                    synthesis_sigma=float((on[roi]-off[roi]).std()),
                    total_sigma=float(on[roi].std()),
                    source_rms=float(np.sqrt(np.mean((on[roi]-s[roi])**2))))
            rows.append(dict(frame=n,smooth_source=not 32<=n<36,regions=regions))
        assert all(next(stream,None) is None for stream in streams)
    finally:
        for stream in streams:stream.close()
    checked=[r for r in rows if r['smooth_source']]
    peak={name:max(r['regions'][name]['synthesis_sigma'] for r in checked)
          for name in ('highlight','smooth')}
    background=float(np.median([r['regions']['genuine']['synthesis_sigma'] for r in rows[8:]]))
    total=float(np.median([r['regions']['genuine']['total_sigma'] for r in rows[8:]]))
    checks=dict(highlight_excess_bounded=peak['highlight']<=3.0,
                nonflat_excess_bounded=peak['smooth']<=4.0,
                genuine_synthesis_present=background>1.0,
                genuine_variance_present=total>3.0)
    return dict(checks=checks,passed=all(checks.values()),peak_added=peak,
                median_genuine_synthesis=background,median_genuine_total=total,frames=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nvencc',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expect-rejected',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for bits in (8,10):
        for policy in ('cqp','qvbr'):
            root=a.output/f'{bits}-{policy}';root.mkdir(exist_ok=False)
            source=root/'source.y4m';video=root/'video.mkv';generate(source,bits)
            rate=['--cqp','20'] if policy=='cqp' else ['--qvbr','34','--max-bitrate','50000','--preset','quality','--tune','hq','--lookahead','32','--lookahead-level','3','--aq','--aq-temporal']
            command=[str(a.nvencc),'--avsw','-i',str(source),'--codec','av1',*rate,
                '--output-depth',str(bits),'--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral',
                '--colormatrix','bt709','--colorprim','bt709','--transfer','bt709','--colorrange','limited',
                '--log-level','debug','--film-grain-table-out',str(root/'planned.tbl'),'-o',str(video)]
            (root/'command.json').write_text(json.dumps(command,indent=2)+'\n')
            with (root/'encode.log').open('w') as log:
                subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            r=measure(source,video,bits,root)
            r.update(bits=bits,policy=policy,source_sha256=hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),
                     video_sha256=hashlib.file_digest(video.open('rb'),'sha256').hexdigest())
            results.append(r)
    accepted=all((not r['checks']['highlight_excess_bounded'] or not r['checks']['nonflat_excess_bounded'])
                 if a.expect_rejected else r['passed'] for r in results)
    report=dict(passed=accepted,expected='rejection' if a.expect_rejected else 'pass',
                candidate=str(a.nvencc),candidate_sha256=hashlib.file_digest(a.nvencc.open('rb'),'sha256').hexdigest(),
                results=results)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=accepted,results=[{k:v for k,v in r.items() if k!='frames'} for r in results])))
    return 0 if accepted else 1


if __name__=='__main__':
    raise SystemExit(main())
