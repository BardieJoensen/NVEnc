#!/usr/bin/env python3
"""Original, raw denoised, new matched-rate base/final, and existing library."""
import argparse, json
import investigate as x
import stages, texture

def main(case):
    d=x.prepare(case);cfg,ts,fps=x.CASES[case]
    stages.main(case);texture.analyze(case,'clean',d/'clean-decoded.mkv')
    target=json.loads((d/'validity.json').read_text())['source_mbps']
    enc,tag=x.encode(case,'nv-fgs',target)
    x.score(case,enc,tag)
    x.score(case,enc,tag+'-base',grain=0)
    texture.analyze(case,tag,d/(tag+'-decoded.mkv'),d/(tag+'-base-decoded.mkv'))
    texture.analyze(case,tag+'-base',d/(tag+'-base-decoded.mkv'))
    for grain,label in [(0,'library-base'),(1,'library-on')]:
        out=d/(label+'.mkv')
        if not out.exists():
            x.run(['ffmpeg','-v','error','-c:v','libdav1d','-threads','4','-filmgrain',grain,'-ss',ts,'-i',cfg['library'],'-map','0:v:0','-frames:v',x.N,'-an','-sn','-c:v','ffvhuff','-threads','4','-pix_fmt','yuv420p10le',*x.COLOR,out],d,label+'-extract')
        x.score(case,out,label,pre=0)
    texture.analyze(case,'library-on',d/'library-on.mkv',d/'library-base.mkv')
    texture.analyze(case,'library-base',d/'library-base.mkv')
    pk=x.packets(cfg['library'],f'{ts-15}%{ts+15}')
    sel=sorted([p for p in pk if float(p['pts_time'])>=ts],key=lambda p:float(p['pts_time']))[:x.N]
    assert len(sel)==x.N
    x.dump(d/'library-packets.json',{'packets':sel,'mbps':sum(int(p['size']) for p in sel)*8/(x.N/fps)/1e6})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case',choices=[c for c in x.CASES if c.startswith('e05')]);a=p.parse_args();main(a.case)
