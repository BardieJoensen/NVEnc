#!/usr/bin/env python3
"""R15 structural parsers; only independently supplied event identities vary."""
import json,struct,math,hashlib
import numpy as np
W,H=1920,1080
FRAME=W*H*3
ROIS=((1200,650,200,100),(950,50,250,180),(160,600,500,480))
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

def decoder_layout(a,w,h):
 # Pinned SVT inverse reads input[c] then advances by txfm_size_col (width).
 # Pinned libaom inverse reads input[c * txfm_size_row + r] (column-major).
 # Both truncate each 64-point axis to 32 coefficient samples before packing.
 return np.asarray(a).reshape(min(h,32),min(w,32)).T.ravel()

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

def parse_coeff(path, expected_decode_order):
 tokens={};routes={};attempts=[];footer=None;gen=0;lasttoken=0
 for k,g,m,b,pos in records(path,0x314346504e5450):
  assert footer is None and g==gen and k in range(10,19)
  if k==10:
   assert not b and m['sb'] not in routes and 0<=m['sb']<510
   assert m['effective_mode']==m['parent_mode']==m['configured_mode']==4 and m['depth']==10
   assert m['picture_bypass']==m['md_bypass']==0 and m['decode_order']==expected_decode_order
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

def parse_decoder(run, expected_event, expected_coded, expected_events, expected_coded_count):
 rows=[json.loads(l) for l in (run/'trace.jsonl').read_text().splitlines()]
 assert rows[0]==dict(kind='start',schema=1,target_event=expected_event,target_coded=expected_coded)
 assert rows[-1]['kind']=='end' and sum(r['kind']=='end' for r in rows)==1
 raw=(run/'payload.bin').read_bytes(); pos=0; leaves=[];units=[];events=[];post=None;pending=None;active=None
 owner=np.full((H,W),-1,dtype=np.int32);umap=owner.copy();catmap=np.zeros((H,W),dtype=np.uint8)
 pred=np.zeros((H,W),dtype='<u2');recon=pred.copy()
 def take(o,n):
  nonlocal pos
  assert o==pos and n>=0 and pos+n<=len(raw),(o,n,pos,len(raw));b=raw[pos:pos+n];pos+=n;return b
 def rect(x,y,w,h):
  assert all(type(v)==int for v in (x,y,w,h));assert 0<=x<W and 0<=y<H and w>0 and h>0
  return x,y,min(w,W-x),min(h,H-y)
 def fillunit(u,pr,re):
  x,y,w,h=u['x'],u['y'],u['w'],u['h'];sl=np.s_[y:y+h,x:x+w]
  assert np.all(owner[sl]==u['leaf']) and np.all(umap[sl]==-1),(u,'unit overlap/ownership')
  assert pr.size==re.size==w*h and np.all(pr<=1023) and np.all(re<=1023)
  if u['category']<4:assert np.array_equal(pr,re),(u,'absent residual changed samples')
  u['id']=len(units);units.append(u);umap[sl]=u['id'];catmap[sl]=u['category'];pred[sl]=pr.reshape(h,w);recon[sl]=re.reshape(h,w)
 for r in rows[1:-1]:
  k=r['kind']
  if k=='leaf':
   assert pending is None and len(events)==expected_event and r['id']==len(leaves)
   x,y,w,h=rect(r['x'],r['y'],r['w'],r['h']);sl=np.s_[y:y+h,x:x+w]
   assert not np.any(owner[sl]>=0);owner[sl]=r['id']
   assert r['skip_mode'] in (0,1) and r['skip_txfm'] in (0,1) and r['inter'] in (0,1)
   assert not r['skip_mode'] or r['skip_txfm']
   assert 0<=r['coded_qindex']<=255 and 0<=r['segment']<8
   leaves.append(r);active=r
  elif k=='tu':
   assert pending is None and active and r['leaf']==active['id'] and len(events)==expected_event
   x,y,w,h=rect(r['x'],r['y'],r['tx_w'],r['tx_h']);assert (w,h)==(r['w'],r['h'])
   assert x>=active['x'] and y>=active['y'] and x+w<=min(W,active['x']+active['w']) and y+h<=min(H,active['y']+active['h'])
   assert r['sample_count']==w*h
   n=r['coeff_count'];eob=r['eob'];assert 0<=eob<=r['coeff_w']*r['coeff_h']
   cb=take(r['coeff_offset'],n*4)
   if eob:
    assert not active['skip_txfm'] and n==r['coeff_w']*r['coeff_h'] and 0<=r['max_scan']<n and 0<=r['tx_type']<16
    co=np.frombuffer(cb,dtype='<i4');assert np.any(co!=0) and co[r['max_scan']]!=0 and np.all(co[r['max_scan']+1:]==0)
   else:assert n==0 and r['max_scan']==-1 and r['tx_type']==(-1 if active['skip_txfm'] else 0)
   assert r['iqm_state']==(-1 if not eob else 1 if r['iqm_count'] else 0)
   if not eob:assert r['iqm_count']==0
   assert r['iqm_count'] in (0,r['coeff_w']*r['coeff_h'])
   qb=take(r['iqm_offset'],r['iqm_count']);pr=np.frombuffer(take(r['pred_offset'],w*h*2),dtype='<u2')
   cat=1 if active['skip_mode'] else 2 if active['skip_txfm'] else 4 if eob else 3
   u={**r,'category':cat,'coded_qindex':active['coded_qindex'],'trace_tu_id':r['id'],'dequant_coeff_sha256':hashlib.sha256(cb).hexdigest() if cb else None,'iqm_sha256':hashlib.sha256(qb).hexdigest() if qb else None}
   pending=(u,pr)
  elif k=='after':
   assert pending is not None and r['tu']==pending[0]['trace_tu_id'] and r['sample_count']==pending[0]['sample_count']
   re=np.frombuffer(take(r['recon_offset'],r['sample_count']*2),dtype='<u2');fillunit(pending[0],pending[1],re);pending=None
  elif k=='skip_inter':
   assert pending is None and active and active['id']==r['leaf'] and active['skip_txfm'] and active['inter'] and len(events)==expected_event
   x,y,w,h=rect(active['x'],active['y'],active['w'],active['h']);assert r['sample_count']==w*h
   pr=np.frombuffer(take(r['pred_recon_offset'],w*h*2),dtype='<u2')
   u=dict(leaf=r['leaf'],x=x,y=y,w=w,h=h,category=1 if active['skip_mode'] else 2,eob=0,coded_qindex=active['coded_qindex'],trace_tu_id=None,pred_offset=r['pred_recon_offset'])
   fillunit(u,pr,pr)
  elif k=='event':
   assert pending is None and r['event']==len(events)
   b=take(r['bytes_offset'],r['bytes_count']);events.append((r,b))
  elif k=='postloop':
   assert len(events)==expected_event+1 and post is None and r['bytes']==FRAME
   post=take(r['offset'],FRAME)
  else:raise AssertionError(('unexpected record',k))
 assert pending is None and pos==len(raw)==rows[-1]['payload_bytes'] and post is not None
 assert len(events)==rows[-1]['events']==expected_events and rows[-1]['coded']==expected_coded_count
 assert len(leaves)==rows[-1]['leaves'] and len([u for u in units if u['trace_tu_id'] is not None])==rows[-1]['tus']
 assert np.all(owner>=0) and np.all(umap>=0) and np.all((catmap>=1)&(catmap<=4))
 tids=[u['trace_tu_id'] for u in units if u['trace_tu_id'] is not None];assert tids==list(range(len(tids)))
 return dict(leaves=leaves,units=units,owner=owner,unit=umap,category=catmap,predictor=pred,preloop=recon,postloop=post,events=events,terminal=rows[-1])
