#!/usr/bin/env python3
"""Identical spatial statistics: moving repeated texture versus fresh grain.

The retained range-only encoder is a negative control. An encoder which simply
disables synthesis fails the independent-grain arm. No copyrighted fixture is
needed. Native decoder differences isolate synthesis from ordinary compression.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import mixed_source_regression as mixed

W,H,FRAMES=mixed.W,mixed.H,96

def generate(path,bits,repeated):
    rng=np.random.default_rng(20260916)
    base=np.repeat([64,112,160,208],W//4)[None,:]+np.zeros((H,W))
    def texture():
        z=rng.normal(size=(H,W))
        z=.5*z+.125*(np.roll(z,1,0)+np.roll(z,-1,0)+np.roll(z,1,1)+np.roll(z,-1,1))
        return z*(6/z.std())
    fixed=texture()
    dtype=np.uint8 if bits==8 else np.dtype('<u2')
    with path.open('wb') as stream:
        csp='420mpeg2' if bits==8 else '420p10'
        stream.write(f'YUV4MPEG2 W{W} H{H} F24:1 Ip A1:1 C{csp}\n'.encode())
        for n in range(FRAMES):
            # Two pixels per picture is covered by the finite source matcher.
            noise=np.roll(fixed,2*n,axis=1) if repeated else texture()
            y=base+noise
            stream.write(b'FRAME\n')
            for plane in [y,np.full((H//2,W//2),128),np.full((H//2,W//2),128)]:
                stream.write(np.rint(np.clip(plane,0,255)*(1<<(bits-8))).astype(dtype).tobytes())

def measure(source,video,bits,directory):
    streams=[mixed.decode(path,grain,bits,directory/(name+'.log')) for path,grain,name in
             [(source,0,'source'),(video,1,'on'),(video,0,'off')]]
    rows=[]
    roi=np.s_[96:448,40:200]
    try:
        for n in range(FRAMES):
            s,on,off=[next(stream)[0] for stream in streams]
            rows.append(dict(frame=n,synthesis_rms=float(np.sqrt(np.mean((on-off)**2))),
                source_sigma=float(s[roi].std()),output_sigma=float(on[roi].std()),
                source_rms=float(np.sqrt(np.mean((on-s)**2)))))
        assert all(next(stream,None) is None for stream in streams)
    finally:
        for stream in streams:stream.close()
    return dict(frames=rows,peak_synthesis=max(r['synthesis_rms'] for r in rows),
        median_settled_synthesis=float(np.median([r['synthesis_rms'] for r in rows[-24:]])),
        median_settled_variance_ratio=float(np.median([r['output_sigma']/r['source_sigma'] for r in rows[-24:]])))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nvencc',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expect-rejected',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    results=[]
    for bits in [8,10]:
        for policy in ['cqp','qvbr']:
            arms={}
            for repeated in [True,False]:
                kind='repeated' if repeated else 'independent'
                d=a.output/f'{bits}-{policy}-{kind}';d.mkdir()
                source,video=d/'source.y4m',d/'video.mkv';generate(source,bits,repeated)
                rate=['--cqp','20'] if policy=='cqp' else ['--qvbr','34','--max-bitrate','50000','--preset','quality','--tune','hq','--lookahead','32','--lookahead-level','3','--aq','--aq-temporal']
                command=[str(a.nvencc),'--avsw','-i',str(source),'--codec','av1',*rate,'--output-depth',str(bits),
                    '--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral','--colormatrix','bt709','--colorprim','bt709',
                    '--transfer','bt709','--colorrange','limited','--log-level','debug','-o',str(video)]
                (d/'command.json').write_text(json.dumps(command,indent=2)+'\n')
                with (d/'encode.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
                result=measure(source,video,bits,d)
                result.update(source_sha256=hashlib.file_digest(source.open('rb'),'sha256').hexdigest(),
                    output_sha256=hashlib.file_digest(video.open('rb'),'sha256').hexdigest())
                arms[kind]=result
            checks=dict(repeated_texture_preserved=arms['repeated']['peak_synthesis']<=.25,
                independent_grain_synthesized=arms['independent']['median_settled_synthesis']>1,
                independent_variance_preserved=.65<=arms['independent']['median_settled_variance_ratio']<=1.5)
            results.append(dict(bits=bits,policy=policy,arms=arms,checks=checks,passed=all(checks.values())))
    passed=all(not r['checks']['repeated_texture_preserved'] if a.expect_rejected else r['passed'] for r in results)
    report=dict(passed=passed,expected='rejection' if a.expect_rejected else 'pass',results=results,
        encoder=str(a.nvencc),encoder_sha256=hashlib.file_digest(a.nvencc.open('rb'),'sha256').hexdigest())
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=passed,checks=[r['checks'] for r in results])))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
