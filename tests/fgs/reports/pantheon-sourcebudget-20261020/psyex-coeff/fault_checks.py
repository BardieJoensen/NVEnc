#!/usr/bin/env python3
"""Exercise R11 parser rejection on derived malformed traces; preserve receipts."""
import argparse,hashlib,importlib.util,json,struct,time
from pathlib import Path
V=Path(__file__).with_name('validate.py')
EXPECTED='258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('trace',type=Path);ap.add_argument('out',type=Path);a=ap.parse_args()
 assert not a.out.exists() and hashlib.sha256(V.read_bytes()).hexdigest()==EXPECTED
 sp=importlib.util.spec_from_file_location('r11v_fault',V);v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v)
 baseline,terminal=v.parse(a.trace);assert baseline
 original=list(v.records(a.trace,0x314346504e5450))
 a.out.mkdir();results=[]
 cases=('missing_footer','missing_commit','missing_scalar','duplicate_begin','wrong_actual_q','wrong_generation','residual_corrupt')
 for case in cases:
  dst=a.out/(case+'.bin');edited=False
  with dst.open('xb') as f:
   seq=0
   def emit(k,g,m,b):
    nonlocal seq
    j=json.dumps(m,separators=(',',':')).encode()
    f.write(struct.pack('<8Q',0x314346504e5450,1,k,g,216,seq,len(j),len(b)));f.write(j);f.write(b);seq+=1
   for k,g,m,b,pos in original:
    m=dict(m)
    if not edited:
     if (case=='missing_footer' and k==17) or (case=='missing_commit' and k==18) or (case=='missing_scalar' and k==14 and m['stage'].startswith('scalar_')):
      edited=True;continue
     if case=='duplicate_begin' and k==11:emit(k,g,m,b);edited=True
     elif case=='wrong_actual_q' and k==13:m['actual_qindex']=(m['actual_qindex']+1)%256;edited=True
     elif case=='wrong_generation' and k==14:g+=1;edited=True
     elif case=='residual_corrupt' and k==12:
      q=bytearray(b);q[0]^=1;b=q;edited=True
    emit(k,g,m,b)
  assert edited
  start=time.monotonic()
  try:v.parse(dst)
  except (AssertionError,ValueError,KeyError) as e:
   results.append(dict(case=case,rejected=True,error_type=type(e).__name__,error=str(e)[:200],seconds=time.monotonic()-start,artifact=v.ident(dst)))
  else:raise AssertionError(('malformed trace accepted',case))
 result=dict(status='all_rejected',baseline_tokens=len(baseline),terminal=terminal,source=v.ident(a.trace),validator=v.ident(V),script=v.ident(__file__),cases=results,
             note='Malformed traces are reproducible derivatives. Hashes and mutation script retained; source trace unchanged.')
 (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'cases':len(results),'result':v.ident(a.out/'result.json')}))
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
