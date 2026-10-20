#!/usr/bin/env python3
"""Record an actual bounded Python subprocess, including failures."""
import argparse, datetime as dt, hashlib, json, subprocess, sys, time
from pathlib import Path

def ident(p):
    p=Path(p).resolve()
    with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),size=p.stat().st_size,sha256=h)

def main():
    p=argparse.ArgumentParser();p.add_argument('receipt',type=Path);p.add_argument('script',type=Path);p.add_argument('script_sha');p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args()
    assert not a.receipt.exists()
    log=a.receipt.with_suffix('.log');assert not log.exists()
    command=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11',sys.executable,str(a.script),*a.args]
    files=[Path(__file__),a.script,Path(sys.executable),Path('/usr/bin/nice'),Path('/usr/bin/taskset')]
    before=[ident(p) for p in files];assert ident(a.script)['sha256']==a.script_sha
    r=dict(status='running',command=command,inputs_before=before,started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    def save():a.receipt.write_text(json.dumps(r,indent=2)+'\n')
    save();t=time.monotonic()
    try:
        with log.open('wb') as f:proc=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
        r.update(returncode=proc.returncode,seconds=time.monotonic()-t,log=ident(log),inputs_after=[ident(p) for p in files])
        assert r['inputs_before']==r['inputs_after']
        r['status']='complete' if proc.returncode==0 else 'failed'
    except BaseException as e:r.update(status='failed',error=repr(e));raise
    finally:r['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat();save()
    print(json.dumps(r))
    raise SystemExit(r['returncode'])

if __name__=='__main__':
    if not __debug__:raise SystemExit('optimized Python prohibited')
    main()
