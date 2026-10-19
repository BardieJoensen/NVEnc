#!/usr/bin/env python3
"""Expose production preprocessing via its existing raw diagnostic mode."""
import argparse, json
import investigate as x

def main(case):
    d=x.prepare(case)
    common=[x.NV,'--avsw','-i',d/'input.mkv','--codec','raw','--output-depth','10','--output-csp','yuv420','--colormatrix','bt709','--colorprim','bt709','--transfer','bt709','--colorrange','limited']
    for kind in ('converted','clean'):
        out=d/(kind+'.y4m')
        if not out.exists():
            extra=[] if kind=='converted' else ['--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral','--film-grain-table-out',d/'clean.tbl','--log-level','debug']
            x.run([*common,*extra,'-o',out],d,kind)
        x.decode(out,d/(kind+'-decoded.mkv'))
    h1=x.hashes(['ffmpeg','-v','error','-threads','4','-i',str(d/'converted-decoded.mkv'),'-pix_fmt','yuv420p10le'])
    h2=json.loads((d/'validity.json').read_text())['hashes_ref']
    x.dump(d/'conversion-check.json',{'production_raw_conversion_exact':h1==h2,'converted_hashes':h1})
    assert h1==h2
    x.score(case,d/'clean.y4m','clean')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('case',choices=x.CASES);a=ap.parse_args();main(a.case)
