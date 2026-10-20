#!/usr/bin/env python3
"""Reuse the admitted R10 observer only if independently bound target matches."""
import argparse, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
R10=ROOT/'parent/aom-decoder-r10-v2'
PINS_SHA='4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5'
BINDER_SHA='34689de8b365801e762fd80a83ec9a349d88bb944c667e96da7bab9edce9323d'
ENCODER_SHA='8616fe44a383c8aaf1722d55891cdc040b7af6886a288fcf8817903794e42ce2'
FRAME=1920*1080*3

def ident(p):
    p=Path(p).resolve()
    with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),sha256=h,size=p.stat().st_size)

def exact(d):
    assert ident(d['path'])==d,d
    return Path(d['path'])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('encode_receipt',type=Path);ap.add_argument('encode_sha')
    ap.add_argument('binding',type=Path);ap.add_argument('binding_sha')
    ap.add_argument('out',type=Path);ap.add_argument('--trace',action='store_true')
    a=ap.parse_args();a.out.mkdir(exist_ok=False,parents=True)
    rec=dict(status='preflight',script=ident(__file__),argv=sys.argv,started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    def save(): (a.out/'command.json').write_text(json.dumps(rec,indent=2)+'\n')
    save()
    try:
        assert not any(os.environ.get(k) for k in ('LD_PRELOAD','LD_AUDIT','LD_LIBRARY_PATH','PANTHEON_R10_DIR'))
        assert shutil.disk_usage(ROOT).free>130*2**30
        assert ident(a.encode_receipt)['sha256']==a.encode_sha and ident(a.binding)['sha256']==a.binding_sha
        enc=json.loads(a.encode_receipt.read_text());b=json.loads(a.binding.read_text())
        assert enc['status']=='encoded' and enc['returncode']==0 and enc['executed_script']['sha256']==ENCODER_SHA
        assert b['status']=='bound' and b['encode_receipt']==ident(a.encode_receipt) and b['input_ivf']==enc['ivf_output']
        assert b['script']['sha256']==BINDER_SHA
        for k in ('script','events','command','trace_log','target_frame_obu','input_ivf'): exact(b[k])
        target=b['target_coded_event'];s=b['summary']
        # The unchanged native observer intentionally has these target guards.
        # A different mapping requires a fresh privately retargeted build.
        assert (target['event_index'],target['coded_ordinal'],target['show_frame'],target['order_hint'],target['refresh_frame_flags_normalized'])==(314,210,0,88,16),'new native observer target required'
        assert (s['frame_headers'],s['coded_non_show_existing'])==(502,336),'new native observer population required'
        assert enc['identity_before']==enc['identity_after']
        for path,sha in enc['identity_after'].items(): assert ident(path)['sha256']==sha
        for k in ('ivf_output','recon'):exact(enc[k])
        pp=R10/'completed-build-pins.json';assert ident(pp)['sha256']==PINS_SHA
        pins=json.loads(pp.read_text())
        for d in pins['files'].values():exact(d)
        app=exact(pins['files']['app']);lib=exact(pins['files']['library'])
        paths=[a.encode_receipt,a.binding,pp,app,lib,Path(__file__),Path(enc['ivf_output']['path']),Path(enc['recon']['path']),Path(b['script']['path'])]
        paths += [Path('/usr/bin')/k for k in ('nice','taskset','ldd')]
        before=[ident(p) for p in paths]
        ldd=subprocess.run(['/usr/bin/ldd',str(app)],capture_output=True,text=True)
        match=re.search(r'libaom\.so\S*\s+=>\s+(\S+)',ldd.stdout)
        assert ldd.returncode==0 and match and Path(match.group(1)).resolve()==lib
        (a.out/'ldd.txt').write_text(ldd.stdout+ldd.stderr)
        cmd=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11',str(app),'--i420','--rawvideo','--output-bit-depth=10','--threads=1','--row-mt=0','--summary','-o',str(a.out/'recon.yuv'),enc['ivf_output']['path']]
        env=os.environ.copy()
        if a.trace:env['PANTHEON_R10_DIR']=str(a.out)
        rec.update(status='running',trace=a.trace,encode_receipt=ident(a.encode_receipt),binding=ident(a.binding),build_pins=ident(pp),app=ident(app),library=ident(lib),input=enc['ivf_output'],expected_recon=enc['recon'],command=cmd,environment={'PANTHEON_R10_DIR':str(a.out)} if a.trace else {},inputs_before=before,ldd=ident(a.out/'ldd.txt'))
        save();t=time.monotonic()
        with (a.out/'decode.log').open('wb') as f:proc=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
        rec.update(returncode=proc.returncode,seconds=time.monotonic()-t,log=ident(a.out/'decode.log'))
        save();assert proc.returncode==0
        decoded=ident(a.out/'recon.yuv')
        assert decoded['sha256']==enc['recon']['sha256'] and decoded['size']==336*FRAME
        rec['recon']=decoded
        for name in ('trace.jsonl','payload.bin'):
            if a.trace: rec[name]=ident(a.out/name)
            else: assert not (a.out/name).exists()
        after=[ident(p) for p in paths];assert after==before
        rec.update(status='decoded',all336_allplanes_exact=True,inputs_after=after)
    except BaseException as e:
        rec.update(status='failed',error=repr(e));raise
    finally:
        rec['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat();save()
    print(json.dumps(dict(status=rec['status'],receipt=ident(a.out/'command.json'),seconds=rec['seconds'])))

if __name__=='__main__':
    if not __debug__:raise SystemExit('optimized Python prohibited')
    main()
