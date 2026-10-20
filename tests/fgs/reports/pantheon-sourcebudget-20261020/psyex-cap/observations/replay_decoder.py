#!/usr/bin/env python3
"""R18 cap replay using the accepted R10 native decoder and fixed provenance."""
import argparse, datetime as dt, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
HERE = Path(__file__).resolve().parent
P18 = ROOT/'parent/psyex-cap-r18'
R10 = ROOT/'parent/aom-decoder-r10-v2'
RUN = P18/'run.py'; RUN_SHA='ebfce2b97bd8002db2e866086ed44ac8dece936d64bfeaa01062f29dc5bf6bb3'
PROV = P18/'provenance.py'; PROV_SHA='b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f'
READER = P18/'read_cap_trace.py'; READER_SHA='08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8'
PINS = R10/'completed-build-pins.json'; PINS_SHA='4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5'
CAP_SHA='6c90d0a52582d82fd6c0697848aad9cdcfd1c7cc84b72c4643321342ec660587'
CAP_OUTER_SHA='a3650328b7a792080c0a3eeead0214165c88951b54543c6b5fbb75f1dd959207'
BIND_SHA='4ae3911b52a192e89f70504ad4088c3fc46266150742fee61195f145b8ffb47f'
BINDER_SHA='2fcce467cbd6ef3a09f5adb076db47289472ed93441cabc3e89bcc08e05e235d'
FRAME=1920*1080*3; N=336
CAP_OUTER_ARGS=['cap','cap-1',str(P18/'build-1/completed-build-pins.json'),'c0e389a6ca98513c5b4117b48dab02552b7f21ea978585974243f747803e1fe7','--control',str(P18/'runs/baseline-1/command.json'),'--control-sha','b912affabfc3dce44b63675b7a7fd68b92decb9d876a293d09509c7e9c4b5887','--parent',str(P18/'runs/pass1-1/command.json'),'--parent-sha','b5f32616ab2122863b09e40df1fcc18ac6f19dffba7c430a4ff086b0579bef2a']

def ident(p):
 p=Path(p).resolve(); h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return {'path':str(p),'size':p.stat().st_size,'sha256':h.hexdigest()}
def exact(row,sha=None):
 if set(row)!= {'path','size','sha256'}: raise RuntimeError('bad identity')
 if ident(row['path'])!=row or (sha and row['sha256']!=sha): raise RuntimeError('identity mismatch')
 return Path(row['path'])
def load(name,path,sha):
 if ident(path)['sha256']!=sha: raise RuntimeError(f'{name} hash mismatch')
 sp=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

def main():
 if not __debug__: raise SystemExit('optimized Python prohibited')
 ap=argparse.ArgumentParser(); ap.add_argument('cap',type=Path); ap.add_argument('cap_sha'); ap.add_argument('outer',type=Path); ap.add_argument('outer_sha'); ap.add_argument('binding',type=Path); ap.add_argument('binding_sha'); ap.add_argument('out',type=Path); ap.add_argument('--trace',action='store_true'); ap.add_argument('--execute',action='store_true'); a=ap.parse_args()
 if a.out.exists(): raise SystemExit('refusing existing output')
 a.out.mkdir(parents=True); rec={'status':'preflight','script':ident(__file__),'argv':sys.argv,'trace':a.trace,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}; rp=a.out/'command.json'
 def save(): rp.write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n')
 save()
 try:
  if any(os.environ.get(k) for k in ('LD_PRELOAD','LD_AUDIT','LD_LIBRARY_PATH','PANTHEON_R10_DIR')): raise RuntimeError('loader/old observer override')
  free=shutil.disk_usage(ROOT).free
  if free<160*2**30: raise RuntimeError('preflight free-space floor')
  if a.cap_sha!=CAP_SHA or a.outer_sha!=CAP_OUTER_SHA or a.binding_sha!=BIND_SHA: raise RuntimeError('fixed receipt SHA mismatch')
  if a.cap.resolve()!=P18/'runs/cap-1/command.json' or a.outer.resolve()!=P18/'cap-1-execution.json' or a.binding.resolve()!=P18/'binding-1/result.json': raise RuntimeError('fixed receipt path mismatch')
  if ident(READER)['sha256']!=READER_SHA: raise RuntimeError('reader hash mismatch')
  cp=exact(ident(a.cap),CAP_SHA); op=exact(ident(a.outer),CAP_OUTER_SHA); bp=exact(ident(a.binding),BIND_SHA)
  cap=json.loads(cp.read_text()); outer=json.loads(op.read_text()); bind=json.loads(bp.read_text())
  if cap['status']!='complete' or cap['returncode']!=0 or cap['mode']!='cap' or cap['script']['sha256']!=RUN_SHA: raise RuntimeError('cap receipt mismatch')
  if cap['pins']['sha256']!='c0e389a6ca98513c5b4117b48dab02552b7f21ea978585974243f747803e1fe7': raise RuntimeError('cap build lineage mismatch')
  if bind['status']!='bound' or bind['script']['sha256']!=BINDER_SHA: raise RuntimeError('binding lineage mismatch')
  if bind['encode_receipt'] != ident(a.cap) or bind['input_ivf'] != cap['outputs']['out.ivf']: raise RuntimeError('binding receipt/input mismatch')
  for key in ('script','events','command','trace_log','target_frame_obu','input_ivf','helper','outer_execution','ffmpeg','command'):
   if key in bind: exact(bind[key])
  s=bind['summary'];
  if s.get('frame_headers')!=502 or s.get('coded_non_show_existing')!=336 or s.get('ivf_packets')!=336 or s.get('show_existing')!=166: raise RuntimeError('binding lifecycle mismatch')
  t=bind['target_coded_event'];
  if tuple(t[k] for k in ('event_index','coded_ordinal','packet_index','show_frame','order_hint','refresh_frame_flags_normalized'))!=(314,210,209,0,88,16): raise RuntimeError('target guard mismatch')
  # Exact accepted P18 parent command, reconstructed from fixed mode/tag/pin/control/pass1 constants.
  sys.path.insert(0,str(P18))
  prov=load('r18prov',PROV,PROV_SHA); run=load('r18run',RUN,RUN_SHA)
  if outer.get('command') != prov.PREFIX+[str(RUN),*CAP_OUTER_ARGS]: raise RuntimeError('outer command mismatch')
  prov.outer(ident(op),RUN,RUN_SHA,CAP_OUTER_ARGS)
  inner=run.read_receipt(str(cp),a.cap_sha,'cap')
  if inner['outputs']!=cap['outputs']: raise RuntimeError('inner receipt mismatch')
  pins=json.loads(exact(ident(PINS),PINS_SHA).read_text());
  for row in pins['files'].values(): exact(row)
  app=exact(pins['files']['app']); lib=exact(pins['files']['library'])
  ivf=exact(cap['outputs']['out.ivf']); expected=exact(cap['outputs']['recon.yuv'])
  if expected.stat().st_size!=N*FRAME: raise RuntimeError('reconstruction size')
  paths=[cp,op,bp,RUN,PROV,READER,PINS,app,lib,ivf,expected,Path('/usr/bin/nice'),Path('/usr/bin/taskset')]
  paths += [Path(x['path']) for x in cap.get('identity_before',[]) if Path(x['path']) not in paths]
  paths += [Path(x['path']) for x in bind.get('inputs_before',[]) if Path(x['path']) not in paths]
  paths += [Path(x['path']) for x in pins['files'].values() if Path(x['path']) not in paths]
  py=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/analysis-venv/bin/python'); paths += [py,Path('/usr/bin/ldd')]
  paths += [Path(__file__), Path(sys.executable)]
  paths=list({str(x.resolve()):x for x in paths}.values())
  before=[ident(x) for x in paths]
  ldd=subprocess.run(['/usr/bin/ldd',str(app)],capture_output=True,text=True)
  m=re.search(r'libaom\.so\S*\s+=>\s+(\S+)',ldd.stdout)
  if ldd.returncode or not m or Path(m.group(1)).resolve()!=lib.resolve(): raise RuntimeError('private libaom resolution mismatch')
  (a.out/'ldd.txt').write_text(ldd.stdout+ldd.stderr)
  cmd=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11',str(app),'--i420','--rawvideo','--output-bit-depth=10','--threads=1','--row-mt=0','--summary','-o',str(a.out/'recon.yuv'),str(ivf)]
  env=os.environ.copy();
  if a.trace: env['PANTHEON_R10_DIR']=str(a.out)
  rec.update(status='prepared',cap=ident(cp),outer=ident(op),binding=ident(bp),r10_pins=ident(PINS),app=ident(app),library=ident(lib),input_ivf=ident(ivf),expected_recon=ident(expected),command=cmd,environment={'PANTHEON_R10_DIR':str(a.out)} if a.trace else {},inputs_before=before,resource_before={'free':free},ldd=ident(a.out/'ldd.txt')); save()
  if not a.execute: rec['status']='prepared_no_execution'; return
  rec['status']='running'; save(); t0=time.monotonic(); log=a.out/'decode.log'
  with log.open('wb') as f: p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
  rec.update(returncode=p.returncode,seconds=time.monotonic()-t0,log=ident(log)); save()
  if p.returncode: raise RuntimeError(f'decoder rc={p.returncode}')
  got=ident(a.out/'recon.yuv');
  if got['sha256']!=ident(expected)['sha256'] or got['size']!=N*FRAME: raise RuntimeError('native reconstruction differs from cap')
  for name in ('trace.jsonl','payload.bin'):
   if a.trace and not (a.out/name).exists(): raise RuntimeError(f'trace output missing: {name}')
   if not a.trace and (a.out/name).exists(): raise RuntimeError(f'unexpected trace output: {name}')
  if a.trace:
   for name in ('trace.jsonl','payload.bin'):
    rec[name]=ident(a.out/name)
    if rec[name]['size'] <= 0: raise RuntimeError('empty native observation')
  after=[ident(x) for x in paths]
  resource_after=shutil.disk_usage(ROOT).free
  if resource_after<120*2**30: raise RuntimeError('postflight free-space floor')
  if before!=after: raise RuntimeError('input changed')
  rec.update(status='decoded',all336_allplanes_exact=True,recon=got,inputs_after=after,resource_after={'free':resource_after})
 except BaseException as e: rec.update(status='failed',error=repr(e)); raise
 finally: rec['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat(); save()
 print(json.dumps({'status':rec['status'],'receipt':ident(rp)}))
if __name__=='__main__': main()
