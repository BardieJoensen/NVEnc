#!/usr/bin/env python3
"""Truthful bounded execution receipt for the reviewed R11 analyzer."""
import datetime as dt,hashlib,json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
PY=P.parents[1]/'analysis-venv/bin/python'
def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=h,size=p.stat().st_size)
def main():
 run=P/'analysis-run-1';run.mkdir(exist_ok=False)
 cmd=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11',str(PY),str(P/'analyze.py'),str(P/'admitted-1/admission.json'),str(run/'result.json')]
 paths=[P/'analyze.py',P/'validate.py',P/'admitted-1/admission.json',Path(__file__),PY]
 receipt={'status':'prepared','argv':cmd,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'identity_before':[ident(p) for p in paths]}
 def save():(run/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 save()
 try:
  assert ident(P/'analyze.py')['sha256']=='44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e'
  t=time.monotonic()
  with (run/'analysis.log').open('x') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
  receipt.update(returncode=r.returncode,seconds=time.monotonic()-t,log=ident(run/'analysis.log'))
  assert r.returncode==0
  receipt['identity_after']=[ident(p) for p in paths];assert receipt['identity_before']==receipt['identity_after']
  receipt.update(status='complete',result=ident(run/'result.json'))
 except BaseException as e:
  receipt.update(status='failed',error=repr(e));raise
 finally:
  receipt['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat();save()
 print(json.dumps(receipt))
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
