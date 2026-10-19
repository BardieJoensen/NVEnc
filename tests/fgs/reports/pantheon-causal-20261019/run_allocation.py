#!/usr/bin/env python3
"""One map, fixed -12 qindex intervention; only bitrate calibrated afterward."""
import sys,json,os,pathlib,hashlib
import grain_model as g
x=g.x
def run(case):
    d=x.ROOT/case;target=json.loads((d/'validity.json').read_text())['source_mbps'];fps=x.CASES[case][2]
    a=json.loads((d/'b-trace-command.json').read_text())['argv'];a[6]=str(x.ROOT/'svt-source/Bin/Release/SvtAv1EncApp')
    a=a[:a.index('-o')];request=int(a[a.index('--tbr')+1]);os.environ['PANTHEON_ALLOCATION_MAP']=str(d/'allocation-map.bin')
    # Resume completed calibration attempts without overwriting evidence.
    history=[]
    for p in sorted(d.glob('b-allocation-try*-command.json')):
        old=json.loads(p.read_text())['argv']
        if '--tbr' not in old:continue
        ivf=pathlib.Path(old[old.index('-b')+1])
        history.append((int(old[old.index('--tbr')+1]),x.rate(ivf,fps),ivf.stem))
    # Actual image recon always enabled, matching the controlled baseline.
    # Bracket request after the initial multiplicative attempts oscillated.
    for i in range(len(history)+1,9):
        if history:
            best=min(history,key=lambda row:abs(row[1]/target-1))
            if abs(best[1]/target-1)<=.01:request,rate,tag=best;td=d/(tag+'-trace');break
            lo=[r for r in history if r[1]<target];hi=[r for r in history if r[1]>target]
            if lo and hi:
                lower=max(lo,key=lambda r:r[1]);upper=min(hi,key=lambda r:r[1]);request=round((lower[0]+upper[0])/2)
            else:request=round(history[-1][0]*target/history[-1][1])
        tag=f'b-allocation-try{i}';b=a.copy();b[b.index('-b')+1]=str(d/(tag+'.ivf'));b[b.index('--tbr')+1]=str(request);b+=['-o','/dev/null']
        td=d/(tag+'-trace');td.mkdir(exist_ok=True);os.environ['PANTHEON_TRACE_DIR']=str(td);os.environ['PANTHEON_TRACE_IMAGES_OFF']='1'
        x.dump(d/(tag+'-environment.json'),{'PANTHEON_ALLOCATION_MAP':str(d/'allocation-map.bin'),'PANTHEON_TRACE_DIR':str(td),'PANTHEON_TRACE_IMAGES_OFF':'1','map_sha256':hashlib.sha256((d/'allocation-map.bin').read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(pathlib.Path(b[6]).read_bytes()).hexdigest()})
        x.run(b,d,tag);rate=x.rate(d/(tag+'.ivf'),fps);history.append((request,rate,tag));print(case,tag,rate,'target',target,flush=True)
        if abs(rate/target-1)<=.01:break
        request=round(request*target/rate)
    assert abs(rate/target-1)<=.01
    os.environ.pop('PANTHEON_TRACE_DIR',None);os.environ.pop('PANTHEON_TRACE_IMAGES_OFF',None);os.environ.pop('PANTHEON_ALLOCATION_MAP',None)
    if not (d/(tag+'.mkv')).exists():x.run(['ffmpeg','-v','error','-i',d/(tag+'.ivf'),'-c','copy',d/(tag+'.mkv')],d,tag+'-remux')
    rate=x.rate(d/(tag+'.mkv'),fps);assert abs(rate/target-1)<=.01
    x.dump(d/'b-allocation-selection.json',{'selected':str(d/(tag+'.mkv')),'target_mbps':target,'actual_mbps':rate,'relative_error':abs(rate/target-1),'map':str(d/'allocation-map.bin'),'qindex_delta':-12,'request_kbps':request,'trace':str(td)})
if __name__=='__main__':run(sys.argv[1])
