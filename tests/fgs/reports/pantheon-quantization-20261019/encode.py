#!/usr/bin/env python3
import os,json,sys,hashlib
from study import ROOT,OLD,x
case,tag,kind=sys.argv[1:4];d=ROOT/case
args=json.loads((OLD/case/'b-trace-command.json').read_text())['argv']
a=[s.replace('/tmp/downloads/codex-work/pantheon-causal-20261019',str(ROOT)).replace('b-trace.ivf',tag+'.ivf').replace('b-trace-recon.yuv',tag+'-recon.yuv') for s in args]
if kind!='baseline':
 i=a.index('--rc');a[i+1]='0';i=a.index('--tbr');del a[i:i+2];a+=['--qp',kind,'--aq-mode','0']
trace=d/(tag+'-trace');detail=d/(tag+'-detail');trace.mkdir();detail.mkdir()
os.environ['PANTHEON_TRACE_DIR']=str(trace);os.environ['PANTHEON_TRACE_IMAGES_OFF']='1'
os.environ['PANTHEON_DETAIL_DIR']=str(detail);os.environ['PANTHEON_DETAIL_POC']= ',230,' if case=='e04' else ',216,'
x.dump(d/(tag+'-environment.json'),{k:v for k,v in os.environ.items() if k.startswith('PANTHEON_')})
x.run(a,d,tag)
x.run(['ffmpeg','-v','error','-i',d/(tag+'.ivf'),'-c','copy',d/(tag+'.mkv')],d,tag+'-remux')
v=json.loads((d/'validity.json').read_text());rate=x.rate(d/(tag+'.mkv'),v['fps'])
out={'rate_mbps':rate,'sha256':hashlib.sha256((d/(tag+'.ivf')).read_bytes()).hexdigest()}
if kind=='baseline':
 out['identical_prior_baseline']=(d/(tag+'.ivf')).read_bytes()==(d/'baseline.ivf').read_bytes()
 assert out['identical_prior_baseline']
x.dump(d/(tag+'-encode.json'),out);print(case,tag,out,flush=True)
