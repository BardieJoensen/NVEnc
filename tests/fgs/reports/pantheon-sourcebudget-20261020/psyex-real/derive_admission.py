#!/usr/bin/env python3
import hashlib, importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
ADM=ROOT/'parent/psyex-real-r15/admitted-1'
RUN=ROOT/'worker/psyex-r15-real/runs/e05-1440/r15-tf0-publicqp1'
HELP=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/analyze_psyex_boundary.py')
HELP_SHA='1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'
W,H=1920,1080
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ident(p):
    p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def y(path):
    a=np.fromfile(path,dtype='<u2'); assert a.size in (W*H,W*H*3//2)
    a=a[:W*H].reshape(H,W).astype(np.float64)/4
    assert np.isfinite(a).all() and a.min()>=0 and a.max()<=255.75
    return a
def main(out):
    assert sha(HELP)==HELP_SHA
    sp=importlib.util.spec_from_file_location('h',HELP); h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
    receipt=json.loads((RUN/'command.json').read_text()); admission=json.loads((ADM/'admission.json').read_text())
    assert admission['status']=='admitted' and receipt['status']=='encoded'
    surfaces={k:y(ADM/p) for k,p in {'original':'original.yuv','coding_input':'coding_input.yuv','predictor':'predictor.y','preloop':'preloop.y','postloop':'postloop.yuv'}.items()}
    tokens=json.loads((ADM/'tokens.json').read_text()); assert len(tokens)==4809
    q={int(t['info']['actual_qindex']) for t in tokens}; commitq={int(t['commit']['qindex']) for t in tokens}
    assert q==commitq=={4}; assert all(int(t['end']['eob'])>0 and int(t['end']['has_coeff'])==1 for t in tokens)
    assert all(int(t['begin']['skip_mode'])==0 and int(t['commit']['source_skip_mode'])==0 for t in tokens)
    result={'status':'complete','inputs':{'admission':ident(ADM/'admission.json'),'receipt':ident(RUN/'command.json'),'tokens':ident(ADM/'tokens.json'),'helper':ident(HELP)},
      'rate':{'actual_mbps':receipt['actual_mbps'],'source_mbps':receipt['source_mbps'],'ratio':receipt['actual_mbps']/receipt['source_mbps'],'within_source_ceiling':receipt['within_source_ceiling'],'two_pass_seconds':receipt['wall_seconds']},
      'population':{'tokens':len(tokens),'actual_qindex':sorted(q),'all_eob_positive':True,'all_has_coeff':True,'all_skip_mode_zero':True},
      'whole_luma':{'original_equals_coding_input':bool(np.array_equal(surfaces['original'],surfaces['coding_input'])),'preloop_equals_postloop':bool(np.array_equal(surfaces['preloop'],surfaces['postloop']))},'rois':{}}
    for name,(x0,y0,w,hgt) in BOXES.items():
      src=surfaces['original'][y0:y0+hgt,x0:x0+w]
      result['rois'][name]={}
      for stage,z in surfaces.items():
        crop=z[y0:y0+hgt,x0:x0+w]; d=h.luma_pair(src,crop)
        result['rois'][name][stage]={'mse':float(np.mean((crop-src)**2)),'hf_sigma':float(d['hf_sigma']),'acf1':None if d['acf1'] is None else float(d['acf1']),'hf_corr_source':None if d.get('hf_corr_source') is None else float(d['hf_corr_source'])}
    Path(out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':
    import sys; assert len(sys.argv)==2 and not Path(sys.argv[1]).exists();main(sys.argv[1])
