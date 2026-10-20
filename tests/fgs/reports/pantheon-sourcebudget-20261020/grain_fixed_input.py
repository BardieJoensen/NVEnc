#!/usr/bin/env python3
"""One frozen-pair, fixed-input native legal-grain discriminator; no estimator."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import numpy as np
from scipy.ndimage import minimum_filter,maximum_filter
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'pantheon-independent-20261019'))
from texture import desc,x
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
ARCH=Path('/media/merged-storage/cold-storage/docker-apps')
W,H=1920,1080
D=ROOT/'parent/grain-fixed-input';D.mkdir(parents=True,exist_ok=False)
F=ROOT/'fixtures/e05-1440';R=ROOT/'worker/runs/e05-1440/preset0-1x0'
selector=ARCH/'pantheon-causal-20261019/e05-1440/a-heldout-controls.json'
tool=ARCH/'pantheon-quantization-20261019/grain_probe'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(p):return {'path':str(p),'sha256':sha(p)}
def dump(n,v):(D/n).write_text(json.dumps(v,indent=2)+'\n')
command=json.loads((R/'command.json').read_text());dv=json.loads((R/'decoder-validation.json').read_text())
assert sha(R/'recon.yuv')==command['recon']['sha256']==dv['app_recon']['sha256']
assert sha(R/'out.ivf')==command['output']['sha256']
assert dv['all336_allplanes_app_dav1d_NVDEC_exact']
assert sha(F/'source.yuv')==json.loads((F/'fresh-validation.json').read_text())['source_raw']['sha256']
S=np.memmap(F/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))
B=np.memmap(R/'recon.yuv',dtype='<u2',mode='r',shape=(336,W*H*3//2))
old=json.loads(selector.read_text())['tiles'];pairs=[]
for n in sorted({r['frame'] for r in old}):
    frame=B[n+96,:W*H].reshape(H,W);src=S[n,:W*H].reshape(H,W);rows=[]
    for r in (v for v in old if v['frame']==n):
        xx,yy=r['x'],r['y'];z=frame[yy:yy+32,xx:xx+32]
        sd=desc(src[yy:yy+32,xx:xx+32].astype(np.float32)/4)
        assert sd==r['source'], 'Frozen source descriptors must match exactly.'
        rows.append({**{k:r[k] for k in ('frame','x','y','kind','source')},'new_base':desc(z.astype(float)/4),
                     'hist':np.bincount(z.ravel(),minlength=1024)/1024})
    quiet=[r for r in rows if r['kind']=='quiet']
    texture=[r for r in rows if r['kind']=='flat_texture' and r['source']['hf_sigma']>.4 and r['new_base']['hf_sigma']<.5*r['source']['hf_sigma']]
    for q in quiet:
        for t in texture:
            if abs(q['new_base']['mean']-t['new_base']['mean'])>.5:continue
            overlap=float(np.minimum(q['hist'],t['hist']).sum())
            if overlap<.5:continue
            pair={'frame':n,'overlap':overlap}
            for label,r in [('quiet',q),('texture',t)]:
                pair[label]={k:v for k,v in r.items() if k!='hist'}
                pair[label]['base_codes']={str(i):float(v) for i,v in enumerate(r['hist']) if v}
            pairs.append(pair)
pairs.sort(key=lambda p:(-p['overlap'],p['frame'],p['quiet']['y'],p['quiet']['x'],p['texture']['y'],p['texture']['x']))
assert pairs
p=pairs[0];n=p['frame'];br=B[n+96,:W*H].reshape(H,W);sr=S[n,:W*H].reshape(H,W).astype(float)/4
flat=minimum_filter(br,3)==maximum_filter(br,3);yy,xx=np.indices(br.shape);flat&=(xx%32>=2)&(yy%32>=2)
codes=sorted(set(map(int,p['quiet']['base_codes']))&set(map(int,p['texture']['base_codes'])))
code_rows=[]
for code in codes:
    row={'code':code,'counts':{}}
    for label in ('quiet','texture'):
        cx,cy=p[label]['x'],p[label]['y'];m=flat[cy+2:cy+30,cx+2:cx+30]&(br[cy+2:cy+30,cx+2:cx+30]==code)
        row['counts'][label]=int(m.sum())
    code_rows.append(row)
chosen=sorted(code_rows,key=lambda r:(-min(r['counts'].values()),r['code']))[0]
assert min(chosen['counts'].values())>1,'Insufficient population for a conditional variance estimate.'
code=chosen['code'];masks={};controls={}
for label in ('quiet','texture'):
    cx,cy=p[label]['x'],p[label]['y'];m=flat[cy+2:cy+30,cx+2:cx+30]&(br[cy+2:cy+30,cx+2:cx+30]==code);masks[label]=m
    hp=x.high_pass(sr[cy:cy+32,cx:cx+32])[1:-1,1:-1]
    amp=float(hp[m].std()*np.sqrt(8/5))
    controls[label]={'xy':[cx,cy],'count':int(m.sum()),'conditional_source_hf':amp,'interval_10pct':[amp*.9,amp*1.1],
                     'source':desc(sr[cy:cy+32,cx:cx+32]),'base':desc(br[cy:cy+32,cx:cx+32].astype(float)/4)}
provenance={k:identity(v) for k,v in {'script':__file__,'source':F/'source.yuv','base':R/'recon.yuv','ivf':R/'out.ivf',
    'selector':selector,'base_decoder_validation':R/'decoder-validation.json','native_tool':tool,
    'native_source':tool.with_suffix('.c'),'native_build':tool.parent/'grain-probe-build-command.json',
    'dav1d_library':Path('/lib/x86_64-linux-gnu/libdav1d.so.7').resolve()}.items()}
selection={'pairs':pairs,'selected_pair_index':0,'all_common_codes':code_rows,'selected_code':chosen,'controls':controls,'provenance':provenance,
    'selection_rule':'Highest histogram overlap, coordinate tie break; code maximizing smaller population, smaller-code tie break. No source-amplitude selection.'}
dump('selection.json',selection)
# Same preserved native executable verifies its own decoded base against the known frame.
baseout=D/'native-base.yuv';grainout=D/'white16.yuv';model=D/'white16.txt'
seeds=[(12345+i*7919)%65536 for i in range(32)]
model.write_text('\n'.join(' '.join(map(str,[seed,10,0,7,0,2,0,16,255,16]+[0]*24+[0]+[0]*25+[0]+[0]*25)) for seed in seeds)+'\n')
for tag,mode,out in [('native-base',0,baseout),('white16',2,grainout)]:
    argv=[str(tool),str(R/'out.ivf'),str(out),str(mode),str(n+96),'1']+([str(model)] if mode else [])
    x.run(argv,D,tag)
    assert 'base_before_after_exact=32' in (D/(tag+'.log')).read_text()
    assert out.stat().st_size==32*W*H*3
base=np.memmap(baseout,dtype='<u2',mode='r',shape=(32,W*H*3//2))
assert all(np.array_equal(frame,B[n+96]) for frame in base)
grain=np.memmap(grainout,dtype='<u2',mode='r',shape=(32,W*H*3//2));stats=[];crops={}
for label in controls:
    cx,cy=controls[label]['xy'];crops[label+'_source']=S[n,:W*H].reshape(H,W)[cy:cy+32,cx:cx+32].copy()
    crops[label+'_base']=br[cy:cy+32,cx:cx+32].copy();crops[label+'_mask']=masks[label]
    crops[label+'_grain_output']=np.stack([g[:W*H].reshape(H,W)[cy:cy+32,cx:cx+32] for g in grain])
for i,seed in enumerate(seeds):
    row={'seed':seed,'regions':{}}
    for label in controls:
        a=crops[label+'_grain_output'][i].astype(float)/4;b=crops[label+'_base'].astype(float)/4;m=masks[label]
        hp=x.high_pass(a)[1:-1,1:-1];diff=a-b;dhp=x.high_pass(diff)[1:-1,1:-1]
        assert np.array_equal(hp[m],dhp[m]),'Matched base neighborhoods must have zero HF.'
        amp=float(hp[m].std()*np.sqrt(8/5));lo,hi=controls[label]['interval_10pct']
        row['regions'][label]={'conditional_output_hf':amp,'conditional_isolated_grain_hf':float(dhp[m].std()*np.sqrt(8/5)),
            'output':desc(a),'isolated_grain':desc(diff),'conditional_endpoint_occupancy':float(np.mean(((a[2:30,2:30]<=16)|(a[2:30,2:30]>=235))[m])),
            'within_source_interval':lo<=amp<=hi}
    row['both_intervals']=all(z['within_source_interval'] for z in row['regions'].values());stats.append(row)
np.savez_compressed(D/'crops-and-masks.npz',**crops)
result={'selection':identity(D/'selection.json'),'model':identity(model),'native_base_matches_validated_allplanes':True,
        'raw_outputs':{'base':identity(baseout),'grain':identity(grainout)},'stats':stats,
        'summary':{label:{'mean':float(np.mean([r['regions'][label]['conditional_output_hf'] for r in stats])),
                          'min':min(r['regions'][label]['conditional_output_hf'] for r in stats),
                          'max':max(r['regions'][label]['conditional_output_hf'] for r in stats),
                          'interval_hits':sum(r['regions'][label]['within_source_interval'] for r in stats)} for label in controls},
        'both_interval_hits':sum(r['both_intervals'] for r in stats),'crops':identity(D/'crops-and-masks.npz'),
        'scope':'One legal white-AR/scale16 probe on one unchanged frame/base; not exhaustive AR/scale/seed or a deployable encode.'}
dump('result.json',result)
print(json.dumps({'selection':{'frame':n,'code':code,'controls':controls,'pair_count':len(pairs)},'summary':result['summary'],'both_interval_hits':result['both_interval_hits']},indent=2))
del base,grain
baseout.unlink();grainout.unlink() # only these reproducible outputs created in this run
