#!/usr/bin/env python3
"""R11 fail-closed actual-stage admission. No quality/repair conclusions."""
import argparse,hashlib,json,struct,sys,re,math
from pathlib import Path
import numpy as np
R=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
P=R/'parent/psyex-coeff-r11';D=R/'parent/aom-decoder-r10-v2'
R9=R/'parent/psyex-boundary-r9'
ROIS=((1200,650,200,100),(950,50,250,180),(160,600,500,480))
APPROVED_REPLAY_SHA='f9023e688eeacbc0c1b42defe879c0a3d93be072ea8e77e5fb4f565a4bb96747'
APPROVED_PINS_SHA='f32ace44e5e449ce0898b6566cc9bb3195a8daa2fcb0b9d7f20b0e0d8b3c54d8'
def strict_json(b):
 def pairs(xs):
  d={}
  for k,v in xs:
   assert k not in d,('duplicate key',k)
   d[k]=v
  return d
 def bad(x):raise ValueError(x)
 def finite(x):
  v=float(x);assert math.isfinite(v),('nonfinite',x)
  return v
 return json.loads(b,object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)
def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=h,size=p.stat().st_size)
def exact(d):
 assert ident(d['path'])==d,d
 return Path(d['path'])
def dump(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=2,allow_nan=False)+'\n')
def records(path,magic):
 b=path.read_bytes();pos=0;seq=0
 while pos<len(b):
  assert pos+64<=len(b)
  m,v,k,g,p,s,n,l=struct.unpack_from('<8Q',b,pos);pos+=64
  assert m==magic and v==1 and p==216 and s==seq and 0<n<8192 and l<=2**30
  assert pos+n+l<=len(b)
  meta=strict_json(b[pos:pos+n]);pos+=n
  yield k,g,meta,memoryview(b)[pos:pos+l],pos
  pos+=l;seq+=1
 assert pos==len(b) and seq
def inter(x,y,w,h):
 return any(x<X+W and x+w>X and y<Y+H and y+h>Y for X,Y,W,H in ROIS)
def stage_contract(t):
 """Require actual branch sequence derived from captured inputs and prior EOB."""
 stages=t['stages'];info=t['info'];z=t['begin'];rd=bool(info['initial_rdoq']);i=0
 def take(name):
  nonlocal i
  assert i<len(stages) and stages[i]['stage']==name,(t['begin'],name,[s['stage'] for s in stages])
  s=stages[i];assert bool(s['rdoq'])==rd;i+=1;return s
 cur=take('scalar_fp' if rd and info['fp_y'] else 'scalar_b')
 if rd and cur['eob']:
  fraction=cur['eob']*100//(z['w']*z['h'])
  if fraction>=info['eob_th']:
   rd=False;cur=take('requant_b')
  elif fraction>=info['eob_fast_th']:cur=take('fast_opt')
 if rd and cur['eob']:cur=take('optimize_b')
 if cur['eob'] and z['type']!=9:cur=take('noise_normalization') # IDTX=9 in pinned definitions.h
 final=take('final');assert i==len(stages)
 assert final['eob']==cur['eob'] and np.array_equal(final['q'],cur['q']) and np.array_equal(final['dq'],cur['dq'])
 assert np.array_equal(final['inverse'],cur['inverse'])
def parse(path):
 tokens={};routes={};attempts=[];footer=None;gen=0;lasttoken=0
 for k,g,m,b,pos in records(path,0x314346504e5450):
  assert footer is None and g==gen and k in range(10,19)
  if k==10:
   assert not b and m['sb'] not in routes and 0<=m['sb']<510
   assert m['effective_mode']==m['parent_mode']==m['configured_mode']==4 and m['depth']==10
   assert m['picture_bypass']==m['md_bypass']==0 and m['decode_order']==210
   assert (m['x'],m['y'])==((m['sb']%30)*64,(m['sb']//30)*64)
   routes[m['sb']]=m
  elif k==11:
   t=m['token'];assert t>lasttoken and t not in tokens;lasttoken=t
   x,y,w,h,n=(m[a] for a in ('x','y','w','h','n'))
   assert 0<=x<1920 and 0<=y<1080 and x+w<=1920 and y+h<=1088
   assert w in (4,8,16,32,64) and h in (4,8,16,32,64) and n==min(w,32)*min(h,32)
   assert m['visible_w']==w and m['visible_h']==min(h,1080-y)
   assert inter(x,y,w,h) and len(b)==4*w*h and m['sb'] in routes
   assert m['ctx']==routes[m['sb']]['ctx'] and m['coeff_offset']%16==0 and m['coeff_offset']+w*h<=4096
   v=np.frombuffer(b,dtype='<u2').reshape(2,h,w);assert np.all(v<=1023)
   tokens[t]=dict(begin=m,generation=g,source=v[0],predictor=v[1],stages=[],payload_offsets={'begin':pos})
  elif k in (12,13,14,15,18):
   assert m['token'] in tokens;t=tokens[m['token']]
   assert t['generation']==g and 'commit' not in t
   z=t['begin'];w,h,n=z['w'],z['h'],z['n'];a=w*h
   if k==12:
    assert 'raw' not in t and not z['md_skip'] and not z['skip_mode'] and len(b)==4*a+4*n
    residual=np.frombuffer(b[:2*a],dtype='<i2').reshape(h,w)
    assert np.array_equal(residual,t['source'].astype('i4')-t['predictor'].astype('i4'))
    raw=np.frombuffer(b[2*a:2*a+4*n],dtype='<i4')
    inv=np.frombuffer(b[2*a+4*n:],dtype='<u2').reshape(h,w);assert np.all(inv<=1023)
    t.update(raw=raw,raw_inverse=inv,raw_eob=m['raw_eob']);t['payload_offsets']['raw']=pos
   elif k==13:
    assert 'raw' in t and 'info' not in t and not t['stages'] and m['depth']==10
    assert m['requested_qindex']==z['qindex']
    assert 0<=m['actual_qindex']<=255 and m['scan_count']==m['iscan_count']==n
    assert m['qm_count'] in (0,n) and m['iqm_count'] in (0,n) and m['table_entries']==8
    assert m['tables']==['quant_fp','round_fp','quant','quant_shift','zbin','round','dequant']
    assert len(b)==112+4*n+m['qm_count']+m['iqm_count']
    table=np.frombuffer(b[:112],dtype='<i2').reshape(7,8)
    scan=np.frombuffer(b[112:112+2*n],dtype='<i2');isc=np.frombuffer(b[112+2*n:112+4*n],dtype='<i2')
    assert np.array_equal(np.sort(scan),np.arange(n)) and np.array_equal(isc[scan],np.arange(n))
    nz=np.flatnonzero(t['raw'][scan]);assert t['raw_eob']==(int(nz[-1])+1 if len(nz) else 0)
    qm=bytes(b[112+4*n:112+4*n+m['qm_count']]);iqm=bytes(b[112+4*n+m['qm_count']:])
    t.update(info=m,tables=table,scan=scan,iscan=isc,qm=qm,iqm=iqm);t['payload_offsets']['info']=pos
   elif k==14:
    assert 'info' in t and 'end' not in t and m['ordinal']==len(t['stages']) and len(b)==8*n+2*a
    name=m['stage'];names=[s['stage'] for s in t['stages']]
    assert name not in names and 'final' not in names
    assert name in ('scalar_fp','scalar_b','fast_opt','requant_b','optimize_b','noise_normalization','final')
    assert names or name==('scalar_fp' if t['info']['initial_rdoq'] and t['info']['fp_y'] else 'scalar_b')
    if names: assert name not in ('scalar_fp','scalar_b')
    q=np.frombuffer(b[:4*n],dtype='<i4');dq=np.frombuffer(b[4*n:8*n],dtype='<i4')
    inv=np.frombuffer(b[8*n:],dtype='<u2').reshape(h,w);assert np.all(inv<=1023)
    nz=np.flatnonzero(q[t['scan']]);assert m['eob']==(int(nz[-1])+1 if len(nz) else 0)
    assert np.all(dq[q==0]==0)
    if not m['eob']:assert np.array_equal(inv,t['predictor'])
    t['stages'].append(dict(**m,q=q,dq=dq,inverse=inv,payload_offset=pos))
   elif k==15:
    assert 'end' not in t and len(b)==2*a
    skipped=z['md_skip'] or z['skip_mode'];assert bool(t['stages'])!=bool(skipped)
    assert m['stage_count']==len(t['stages']) and m['skip_mode']==z['skip_mode']
    rec=np.frombuffer(b,dtype='<u2').reshape(h,w);assert np.all(rec<=1023)
    if skipped:assert m['eob']==0 and np.array_equal(rec,t['predictor'])
    else:
     stage_contract(t)
     assert t['stages'][-1]['stage']=='final' and m['eob']==t['stages'][-1]['eob']
     assert np.array_equal(rec,t['stages'][-1]['inverse'])
    assert bool(m['has_coeff'])==bool(m['eob'])
    t.update(end=m,reconstruction=rec);t['payload_offsets']['end']=pos
   else:
    assert 'end' in t and not b and m['sb']==z['sb'] and m['tu_index']==z['tu_index']
    assert m['coeff_offset']==z['coeff_offset'] and m['eob']==t['end']['eob'] and m['type']==t['end']['type']
    assert m['qindex']==z['qindex'] and m['source_skip_mode']==z['skip_mode'] and m['mds_idx']==z['mds_idx']
    assert not m['source_skip_mode'] or (not m['source_block_has_coeff'] and not m['eob'])
    if 'info' in t:assert t['info']['actual_qindex']==m['qindex']
    if m['eob']:assert m['source_block_has_coeff'] and m['type']==z['type']
    t['commit']=m
  elif k==16:
   assert not b and m['recode'] in (0,1) and len(routes)==m['routes']==510
   current=[t for t in tokens.values() if t['generation']==g]
   assert len(current)==m['started']==m['ended'] and all('commit' in t for t in current)
   attempts.append(dict(generation=g,**m))
   if m['recode']:gen+=1;routes={}
  else:
   assert not b and m['status']=='complete' and m['accepted_generation']==g
   assert attempts and attempts[-1]['generation']==g and attempts[-1]['recode']==0
   current=[t for t in tokens.values() if t['generation']==g]
   assert len(current)==m['started']==m['ended'];footer=m
 assert footer and attempts[-1]['recode']==0
 return {k:v for k,v in tokens.items() if v['generation']==gen},dict(footer=footer,attempts=attempts,all_tokens=len(tokens))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('off',type=Path);ap.add_argument('on',type=Path);ap.add_argument('out',type=Path);ap.add_argument('--pins-sha',required=True);ap.add_argument('--replay-sha',required=True);a=ap.parse_args()
 assert not a.out.exists()
 assert a.replay_sha==APPROVED_REPLAY_SHA and a.pins_sha==APPROVED_PINS_SHA
 pp=P/'completed-build-pins.json';assert ident(pp)['sha256']==a.pins_sha
 pins=json.loads(pp.read_text());assert pins['status']=='build_complete' and pins['returncode']==0
 for obj in pins.values():
  if isinstance(obj,dict) and {'path','size','sha256'}<=obj.keys():exact(obj)
 cmds={}
 original_path=R/'worker/psyex-r8/runs/e05-1440/psyex-1x1/command.json'
 assert ident(original_path)['sha256']=='ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138'
 original=json.loads(original_path.read_text())
 for name,run in [('off',a.off),('on',a.on)]:
  d=json.loads((run/'command.json').read_text());assert d['status']=='neutral' and d['returncode']==0 and d['mode']==name
  assert d['pins']==ident(pp) and d['app']==pins['app'] and d['library']==pins['library']
  assert d['original_receipt']==ident(original_path)
  assert d['identity_before']==d['identity_after']
  for p,h in d['identity_after'].items():assert ident(p)['sha256']==h
  assert exact(d['script']) and d['script']['sha256']==a.replay_sha
  assert exact(d['out.ivf']) and d['out.ivf']['sha256']=='26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca'
  assert exact(d['recon.yuv']) and d['recon.yuv']['sha256']=='162c2eb85dc9d036912aa5c3a20e613d4ce0fe2ecbc0505ea96bd6d0288d7099' and d['recon.yuv']['size']==2090188800
  assert d['argv'][6]==pins['app']['path'] and d['argv'][d['argv'].index('--pass')+1]=='2'
  expected=list(original['commands']['pass2']);assert expected[6]==original['binary']['path']
  expected[6]=pins['app']['path']
  for flag,value in {'--stats':str(run/'pass.stats'),'-b':str(run/'out.ivf'),'-o':str(run/'recon.yuv')}.items():
   assert expected.count(flag)==1;expected[expected.index(flag)+1]=value
  assert d['argv']==expected
  exact(d['stats']);assert d['stats']['sha256']==original['stats']['sha256'] and d['stats']['path']==str(run/'pass.stats')
  env=d['environment'];assert env['LD_LIBRARY_PATH']==str(P/'build/bin')
  keys={'LD_LIBRARY_PATH'}
  if name=='on':
   keys|={'SVT_PANTHEON_BOUNDARY_FD','SVT_PANTHEON_COEFF_FD'}
   assert all(re.fullmatch('[0-9]+',env[k]) and int(env[k])>=3 for k in keys-{'LD_LIBRARY_PATH'})
   assert env['SVT_PANTHEON_BOUNDARY_FD']!=env['SVT_PANTHEON_COEFF_FD']
  assert set(env)==keys
  ld=d['ldd'];assert ld['returncode']==0 and ld['argv']==['/usr/bin/ldd',pins['app']['path']]
  found=re.search(r'libSvtAv1Enc\.so\.3\s+=>\s+(\S+)',ld['stdout'])
  assert found and Path(found.group(1)).resolve()==Path(pins['library']['path']).resolve()
  exact(d['log'])
  if name=='on':
   assert exact(d['observation'])==run/'boundary.bin' and exact(d['coefficient_observation'])==run/'coeff.bin'
  else:assert not (run/'boundary.bin').exists() and not (run/'coeff.bin').exists()
  cmds[name]=ident(run/'command.json')
 # Retain R9 generation and stage authority. Byte-identical normalized records permit
 # a different ordering of independent source SB observations, but no content changes.
 def boundary(p):
  out={}
  for k,g,m,b,pos in records(p,0x31594342504e5450):
   key=(g,k,m.get('sb_id',-1));assert key not in out
   out[key]=(m,hashlib.sha256(b).hexdigest())
  return out
 r9trace=R9/'runs/on-1/boundary.bin'
 assert ident(r9trace)['sha256']=='023247030b240a0ec68d88c39d5aef365fb06bb9e64a411aabdbbc6c8c491b8b'
 assert boundary(a.on/'boundary.bin')==boundary(r9trace)
 tokens,terminal=parse(a.on/'coeff.bin')
 adp=D/'admitted-1/admission.json';assert ident(adp)['sha256']=='4848fa5164df8ffbca7a2204de8f2df03982aed251fc7d2737709d5019e8de79'
 ad=json.loads(adp.read_text())
 for obj in ad['artifacts'].values():exact(obj)
 payload=exact(ad['payload']).read_bytes()
 units=json.loads((D/'admitted-1/units.json').read_text());leaves=json.loads((D/'admitted-1/leaves.json').read_text())
 umap=np.load(D/'admitted-1/unit.npy')
 src=np.fromfile(R9/'admitted-1/coding_input.yuv',dtype='<u2',count=1920*1080).reshape(1080,1920)
 # Hash below is the admitted full coding-input image, not a new extraction.
 assert ident(R9/'admitted-1/coding_input.yuv')['sha256']=='b8ad2257c0bab9febd99eeefc05156f64c059bf028a19e72443a24af7af92b68'
 pred=np.fromfile(D/'admitted-1/predictor.y',dtype='<u2').reshape(1080,1920)
 rec=np.fromfile(D/'admitted-1/preloop.y',dtype='<u2').reshape(1080,1920)
 cover=np.zeros((1080,1920),dtype='u1');matched=[];positive=set()
 for token,t in tokens.items():
  z=t['begin'];x,y,w,h=(z[k] for k in ('x','y','w','h'));vh=min(h,1080-y);sl=np.s_[y:y+vh,x:x+w]
  assert not np.any(cover[sl]);cover[sl]=1
  assert np.array_equal(t['source'][:vh],src[sl]) and np.array_equal(t['predictor'][:vh],pred[sl]) and np.array_equal(t['reconstruction'][:vh],rec[sl])
  ids=np.unique(umap[sl]);assert len(ids)==1
  u=units[int(ids[0])];leaf=leaves[u['leaf']]
  assert z['block_x']==leaf['x'] and z['block_y']==leaf['y'] and z['block_w']==leaf['w'] and z['block_h']==leaf['h']
  if u['eob']>0:
   assert u['category']==4 and u['id'] not in positive;positive.add(u['id'])
   assert (u['x'],u['y'],u['w'],u['h'],u['tx_w'],u['tx_h'])==(x,y,w,vh,w,h)
   assert not z['md_skip'] and not z['skip_mode'] and t['end']['eob']==u['eob']
   assert (z['tx'],z['type'],z['n'])==(u['tx_size'],u['tx_type'],u['coeff_count'])
   f=t['stages'][-1];dq=np.frombuffer(payload,dtype='<i4',count=z['n'],offset=u['coeff_offset'])
   assert np.array_equal(f['dq'],dq),(token,u['id'],'DQ')
   assert t['info']['actual_qindex']==u['coded_qindex']==t['commit']['qindex']
   assert t['tables'][6,:2].tolist()==leaf['decoder_dequant']
   assert t['info']['qm_level']==leaf['qm_level_y']
   iq=payload[u['iqm_offset']:u['iqm_offset']+u['iqm_count']]
   assert t['iqm']==iq
  else:
   assert t['end']['eob']==0 and np.array_equal(t['reconstruction'],t['predictor'])
  matched.append(dict(token=token,unit=u['id'],category=u['category'],begin=z,info=t.get('info'),end=t['end'],commit=t['commit'],payload_offsets=t['payload_offsets'],stages=[{k:v for k,v in s.items() if k not in ('q','dq','inverse')} for s in t['stages']]))
 expected={u['id'] for u in units if u['eob'] and inter(u['x'],u['y'],u['w'],u['h'])}
 assert positive==expected,(len(positive),len(expected),sorted(expected-positive))
 for x,y,w,h in ROIS:assert np.all(cover[y:y+h,x:x+w]==1)
 shirt={u['id'] for u in units if u['eob'] and u['x']<1400 and u['x']+u['w']>1200 and u['y']<750 and u['y']+u['h']>650}
 assert len(shirt)==24 and shirt<=positive
 targets=R/'worker/psyex-r11-targets/targets.json'
 assert ident(targets)['sha256']=='8090913807bf9574f70f49e0228927895b8a7ec5d5d0ef43d54528a37c1a61d9'
 frozen=json.loads(targets.read_text());assert sorted(frozen['shirt_eob_positive_ids'])==sorted(shirt)
 a.out.mkdir()
 dump(a.out/'tokens.json',matched)
 result=dict(status='admitted',scope='actual final EncDec stages and fixed-predictor local native inverse diagnostics; no repair or rate inference',
  tokens=len(tokens),positive_units=len(positive),shirt_positive_ids=sorted(shirt),terminal=terminal,
  commands=cmds,pins=ident(pp),script=ident(__file__),trace=ident(a.on/'coeff.bin'),boundary=ident(a.on/'boundary.bin'),
  decoder_admission=ident(adp),targets=ident(targets),token_manifest=ident(a.out/'tokens.json'),
  actual_committed_owner=True,all336_exact=True,source_predictor_preloop_exact=True,final_dq_eob_iqm_exact=True)
 dump(a.out/'admission.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
