#!/usr/bin/env python3
"""Preserve completed R18 delivery evidence; exclude unfinished native-join draft."""
import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
OUT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/psyex-cap/observations')
FILES=['freeze_observations.py','policy_provenance.py','replay_observer2.py','trace_provenance2.py',
       'cap_semantics2.py','admit_cap_trace2.py','admit_cap_trace.py','read_cap_trace.py','provenance.py',
       'replay_decoder.py','trace-index-2.json','trace2-admission.json',
       'observer2-preview-execution.json','observer2-preview-execution.log',
       'observer2-replay-execution.json','observer2-replay-execution.log',
       'trace2-admission-execution.json','trace2-admission-execution.log',
       'native-off-execution.json','native-off-execution.log','native-on-execution.json','native-on-execution.log',
       'runs/trace-2/command.json','runs/trace-2/measured-runner.py','runs/trace-2/encode.log',
       'native-off/command.json','native-off/decode.log','native-off/ldd.txt',
       'native-on/command.json','native-on/decode.log','native-on/ldd.txt']
REVIEWS=['round18-observer2-replay-review.md','round18-trace2-admission-review.md',
         'round18-native-adapter-review.md','round18-native-v3-review.md','round18-native-release.md']
def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),size=p.stat().st_size,sha256=h)
def main():
 assert not OUT.exists()
 pairs=[(P/x,Path(x)) for x in FILES]+[(ROOT/'reviewer'/x,Path('reviews')/x) for x in REVIEWS]
 before=[(p,r,ident(p)) for p,r in pairs];rows=[]
 for p,r,identity in before:
  dest=OUT/r;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
  shutil.copyfile(p,dest);after=ident(dest)
  assert ident(p)==identity and (after['size'],after['sha256'])==(identity['size'],identity['sha256'])
  rows.append(dict(source=identity,frozen=dict(path=str(r),size=after['size'],sha256=after['sha256'])))
 trace=json.loads((P/'runs/trace-2/command.json').read_text())
 external=[row for key,row in trace['outputs'].items() if key!='encode.log']
 for arm in ('off','on'):
  rec=json.loads((P/('native-'+arm)/'command.json').read_text());external.append(rec['recon'])
  if arm=='on':external.extend([rec['trace.jsonl'],rec['payload.bin']])
 for row in external:assert ident(row['path'])==row
 (OUT/'manifest.json').write_text(json.dumps(dict(
  scope='Reviewed observer replay and nominal quantizer admission plus native off/on all-frame identity. Native coefficient/source join and adversarial controls unfinished; no R18 quality or playback claim.',
  files=rows,bytes=sum(row['source']['size'] for row in rows),external=external),indent=2)+'\n')
 print(json.dumps(ident(OUT/'manifest.json')))
if __name__=='__main__':
 assert __debug__
 main()
