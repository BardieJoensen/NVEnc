#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
RUN=ROOT/'worker/psyex-r15-real/runs/e05-1440/r15-tf0-publicqp1'
S=ROOT/'parent/scores/e05-1440'
R8T=S/'psyex-psyex-1x1-texture.json'; R15T=S/'r15-tf0-publicqp1-texture.json'
R15M=S/'metrics-cuda-r15-tf0-publicqp1.json'; SS=S/'ssimu2-r15-tf0-publicqp1.json'; BU=S/'butter-r15-tf0-publicqp1.json'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ident(p):p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def stats(x):
 x=np.asarray(x,float); assert x.size and np.isfinite(x).all()
 return {'n':int(x.size),'mean':float(x.mean()),'min':float(x.min()),'p1':float(np.percentile(x,1)),'p5':float(np.percentile(x,5)),'p95':float(np.percentile(x,95)),'max':float(x.max())}
def texture(p):
 d=json.loads(Path(p).read_text());out={}
 for roi in ('shirt','background'):
  rows=[r['roi'][roi] for r in d['frames']]
  out[roi]={'hf_relative_error':stats([(r['target']['hf_sigma']/r['source']['hf_sigma'])-1 for r in rows]),'acf1_abs_error':stats([abs(r['target']['acf1']-r['source']['acf1']) for r in rows]),'paired_hf_correlation':stats([r['paired_hf_correlation'] for r in rows]),'temporal_hf_corr_abs_error':stats([abs(r['target']['temporal_hf_corr']-r['source']['temporal_hf_corr']) for r in rows[1:]])}
 return out
def main(out):
 controls=json.loads((RUN/'controls.json').read_text()); quiet=[r for r in controls['tiles'] if r['kind']=='quiet'];assert len(quiet)==51
 signed=[]
 for r in quiet:signed.append((r['candidate']['hf_sigma']-r['source']['hf_sigma'],r['frame'],r['x'],r['y']))
 signed.sort(); mx=signed[-1]
 m=json.loads(R15M.read_text()); frames=m['frames']; assert len(frames)==240
 vals=lambda k:[r['metrics'][k] for r in frames]
 ss=[x[0] for x in json.loads(SS.read_text())];bu=json.loads(BU.read_text());assert len(ss)==len(bu)==240
 result={'status':'complete','inputs':{p.name:ident(p) for p in (RUN/'assessment.json',RUN/'controls.json',R8T,R15T,R15M,SS,BU)},'texture_240':{'R8':texture(R8T),'R15':texture(R15T)},'quiet_signed_hf':{'tiles':len(signed),'positive':sum(v[0]>0 for v in signed),'negative':sum(v[0]<0 for v in signed),'zero':sum(v[0]==0 for v in signed),'stats':stats([v[0] for v in signed]),'max_row':{'value':mx[0],'frame':mx[1],'x':mx[2],'y':mx[3]}},'campaign_tails':{'ssimu2':stats(ss),'butter_2norm':stats([x[0] for x in bu]),'butter_max':stats([x[2] for x in bu]),'vmaf':stats(vals('vmaf')),'vmaf_neg':stats(vals('vmaf_neg')),'psnr_y':stats(vals('psnr_y')),'cambi':stats(vals('cambi')),'cambi_full_reference':stats(vals('cambi_full_reference'))}}
 Path(out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':
 import sys;assert len(sys.argv)==2 and not Path(sys.argv[1]).exists();main(sys.argv[1])
