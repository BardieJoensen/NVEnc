#!/usr/bin/env python3
"""Replace only verified identical R18 replay payload copies with hard links."""
import hashlib,json,os
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[1]
def ident(p):
 with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p.resolve()),size=p.stat().st_size,sha256=digest)
def main():
 out=P/'archive-deduplication.json';assert not out.exists()
 cap=json.loads((P/'runs/cap-1/command.json').read_text())
 r16=ROOT/'worker/psyex-r16-calibration-refine/runs/e05-1440/r16-refine-tbr10042'
 pairs=[(P/'runs/cap-1/recon.yuv',P/'runs/trace-2/recon.yuv'),
        (P/'runs/cap-1/recon.yuv',P/'native-off/recon.yuv'),
        (P/'runs/cap-1/recon.yuv',P/'native-on/recon.yuv'),
        (P/'runs/cap-1/out.ivf',P/'runs/trace-2/out.ivf'),
        (r16/'recon.yuv',P/'runs/baseline-1/recon.yuv'),
        (r16/'out.ivf',P/'runs/baseline-1/out.ivf')]
 rows=[]
 for source,target in pairs:
  assert source.is_file() and target.is_file() and not source.is_symlink() and not target.is_symlink()
  a,b=ident(source),ident(target)
  assert (a['size'],a['sha256'])==(b['size'],b['sha256'])
  assert source.stat().st_dev==target.stat().st_dev and source.stat().st_ino!=target.stat().st_ino
  temporary=target.with_name(target.name+'.dedup-temporary');assert not temporary.exists()
  os.link(source,temporary);os.replace(temporary,target)
  assert ident(target)==b and os.path.samefile(source,target)
  rows.append(dict(canonical=a,retained_alias=b,bytes_no_longer_duplicated=b['size']))
 out.write_text(json.dumps(dict(status='exact_payloads_hardlinked',rows=rows,bytes_no_longer_duplicated=sum(r['bytes_no_longer_duplicated'] for r in rows)),indent=2)+'\n')
 print(json.dumps(ident(out)))
if __name__=='__main__':
 assert __debug__
 main()
