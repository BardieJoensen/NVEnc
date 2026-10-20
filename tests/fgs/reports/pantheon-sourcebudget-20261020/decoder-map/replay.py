#!/usr/bin/env python3
import argparse,hashlib,json,os,pathlib,subprocess,time,datetime,sys
R=pathlib.Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
PINS_SHA='4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5'
IVF=R/'worker/psyex-r8/runs/e05-1440/psyex-1x1/out.ivf'
def ident(p):
 p=pathlib.Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=h,size=p.stat().st_size)
def save(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
def main():
 a=argparse.ArgumentParser();a.add_argument('build',type=pathlib.Path);a.add_argument('out',type=pathlib.Path);a.add_argument('--trace',action='store_true');args=a.parse_args()
 assert not args.out.exists();args.out.mkdir(parents=True)
 d=dict(status='preflight',trace=args.trace,script=ident(__file__),argv=sys.argv)
 save(args.out/'command.json',d)
 try:
  assert not any(os.environ.get(k) for k in ('LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT','PANTHEON_R10_DIR'))
  app=ident(args.build/'aomdec');lib=ident(args.build/'libaom.so.3.8.2');ivf=ident(IVF)
  assert ivf['sha256']=='26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca'
  pins_path=pathlib.Path(__file__).resolve().parent/'completed-build-pins.json'
  assert ident(pins_path)['sha256']==PINS_SHA
  pins=json.loads(pins_path.read_text())
  for obj in pins['files'].values():assert ident(obj['path'])==obj,obj
  assert app==pins['files']['app'] and lib==pins['files']['library']
  tools={k:ident('/usr/bin/'+k) for k in ('nice','taskset','ldd')}
  ldd=subprocess.run(['/usr/bin/ldd',app['path']],capture_output=True,text=True,check=True).stdout
  (args.out/'ldd.txt').write_text(ldd)
  resolved=[str(pathlib.Path(x.strip().split('=>')[1].strip().split()[0]).resolve()) for x in ldd.splitlines() if 'libaom.so' in x and '=>' in x]
  assert resolved==[lib['path']],resolved
  cmd=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11',app['path'],'--i420','--rawvideo','--output-bit-depth=10','--threads=1','--row-mt=0','--summary','-o',str(args.out/'recon.yuv'),str(IVF)]
  env=os.environ.copy()
  if args.trace:env['PANTHEON_R10_DIR']=str(args.out)
  d=dict(status='running',argv=cmd,app=app,library=lib,ivf=ivf,script=ident(__file__),trace=args.trace,build_pins=ident(pins_path),tools=tools,ldd=ident(args.out/'ldd.txt'),start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  save(args.out/'command.json',d);t=time.monotonic()
  with (args.out/'decode.log').open('wb') as f:p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
  d.update(returncode=p.returncode,elapsed_seconds=time.monotonic()-t,status='decoded' if p.returncode==0 else 'failed')
  if (args.out/'recon.yuv').exists():d['recon']=ident(args.out/'recon.yuv')
  for name in ('trace.jsonl','payload.bin','decode.log'):
   if (args.out/name).exists():d[name]=ident(args.out/name)
  save(args.out/'command.json',d)
  if p.returncode!=0 or d.get('recon',{}).get('size')!=2090188800 or d.get('recon',{}).get('sha256')!='162c2eb85dc9d036912aa5c3a20e613d4ce0fe2ecbc0505ea96bd6d0288d7099':
   d['status']='validation_failed';save(args.out/'command.json',d);raise RuntimeError('decode/admission failed; see command receipt')
  d['all336_allplanes_exact']=True;save(args.out/'command.json',d)
  print(json.dumps(d,indent=2))
 except Exception as exc:
  d.update(status='validation_failed',error=repr(exc))
  for name in ('recon.yuv','trace.jsonl','payload.bin','decode.log','ldd.txt'):
   if (args.out/name).exists():d[name]=ident(args.out/name)
  save(args.out/'command.json',d)
  raise

if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
