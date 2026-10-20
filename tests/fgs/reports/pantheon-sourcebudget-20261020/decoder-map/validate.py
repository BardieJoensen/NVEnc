#!/usr/bin/env python3
"""R10 fail-closed decoder trace admission. Does not judge quality."""
import argparse,hashlib,json,pathlib,sys
import numpy as np
R=pathlib.Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020');P=R/'parent/aom-decoder-r10-v2'
REPORT=pathlib.Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020')
HELPER=REPORT/'aom_tu_binding.py'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest()=='7d8be210357c70706ca17c8ecad81463b22b809455cc3c36944714c66cfd7935'
sys.path.insert(0,str(REPORT));from aom_tu_binding import ivf_packets,obus
PINS_SHA='4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5'
REPLAY_SHA='6961b25542cb28f84ce2ba2993196bd85239d36380654ab131c615b3db5f1781'
W,H=1920,1080;FRAME=W*H*3
EXPECTED_RECON='162c2eb85dc9d036912aa5c3a20e613d4ce0fe2ecbc0505ea96bd6d0288d7099'
def ident(p):
 p=pathlib.Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=h,size=p.stat().st_size)
def exact(d):
 assert ident(d['path'])==d,d
 return pathlib.Path(d['path'])
def dump(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=2,allow_nan=False)+'\n')
def parse(run):
 rows=[json.loads(l) for l in (run/'trace.jsonl').read_text().splitlines()]
 assert rows[0]==dict(kind='start',schema=1,target_event=314,target_coded=210)
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
   assert pending is None and len(events)==314 and r['id']==len(leaves)
   x,y,w,h=rect(r['x'],r['y'],r['w'],r['h']);sl=np.s_[y:y+h,x:x+w]
   assert not np.any(owner[sl]>=0);owner[sl]=r['id']
   assert r['skip_mode'] in (0,1) and r['skip_txfm'] in (0,1) and r['inter'] in (0,1)
   assert not r['skip_mode'] or r['skip_txfm']
   assert 0<=r['coded_qindex']<=255 and 0<=r['segment']<8
   leaves.append(r);active=r
  elif k=='tu':
   assert pending is None and active and r['leaf']==active['id'] and len(events)==314
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
   assert pending is None and active and active['id']==r['leaf'] and active['skip_txfm'] and active['inter'] and len(events)==314
   x,y,w,h=rect(active['x'],active['y'],active['w'],active['h']);assert r['sample_count']==w*h
   pr=np.frombuffer(take(r['pred_recon_offset'],w*h*2),dtype='<u2')
   u=dict(leaf=r['leaf'],x=x,y=y,w=w,h=h,category=1 if active['skip_mode'] else 2,eob=0,coded_qindex=active['coded_qindex'],trace_tu_id=None,pred_offset=r['pred_recon_offset'])
   fillunit(u,pr,pr)
  elif k=='event':
   assert pending is None and r['event']==len(events)
   b=take(r['bytes_offset'],r['bytes_count']);events.append((r,b))
  elif k=='postloop':
   assert len(events)==315 and post is None and r['bytes']==FRAME
   post=take(r['offset'],FRAME)
  else:raise AssertionError(('unexpected record',k))
 assert pending is None and pos==len(raw)==rows[-1]['payload_bytes'] and post is not None
 assert len(events)==rows[-1]['events']==502 and rows[-1]['coded']==336
 assert len(leaves)==rows[-1]['leaves'] and len([u for u in units if u['trace_tu_id'] is not None])==rows[-1]['tus']
 assert np.all(owner>=0) and np.all(umap>=0) and np.all((catmap>=1)&(catmap<=4))
 tids=[u['trace_tu_id'] for u in units if u['trace_tu_id'] is not None];assert tids==list(range(len(tids)))
 return dict(leaves=leaves,units=units,owner=owner,unit=umap,category=catmap,predictor=pred,preloop=recon,postloop=post,events=events,terminal=rows[-1])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('off',type=pathlib.Path);ap.add_argument('on',type=pathlib.Path);ap.add_argument('out',type=pathlib.Path);a=ap.parse_args();assert not a.out.exists()
 pins_path=P/'completed-build-pins.json';assert ident(pins_path)['sha256']==PINS_SHA
 pins=json.loads(pins_path.read_text())
 for obj in pins['files'].values():exact(obj)
 pristine=R/'worker/aom-decoder-r10-pristine/pristine-decode/receipt.json'
 assert ident(pristine)['sha256']=='320ff5df634943af69a2515d6e68016048860dbc5c72646b6357cfc1ae759a09'
 pr=json.loads(pristine.read_text());assert pr['status']=='decode_complete' and pr['returncode']==0
 for k in ('recon','aomdec','library','input'):exact(pr[k])
 assert pr['recon']['sha256']==EXPECTED_RECON and pr['recon']['size']==2090188800
 identities={}
 for name,run in [('off',a.off),('on',a.on)]:
  d=json.loads((run/'command.json').read_text());assert d['status']=='decoded' and d['returncode']==0 and d['all336_allplanes_exact'] is True
  assert d['trace']==(name=='on');assert exact(d['recon']).stat().st_size==2090188800 and d['recon']['sha256']==EXPECTED_RECON
  for key in ('app','library','ivf','script'):exact(d[key])
  assert d['app']==pins['files']['app'] and d['library']==pins['files']['library'] and d['build_pins']==ident(pins_path)
  assert d['script']['sha256']==REPLAY_SHA
  assert d['decode.log']==ident(run/'decode.log')
  assert d['ldd']==ident(run/'ldd.txt')
  for k in ('nice','taskset','ldd'):assert d['tools'][k]==ident('/usr/bin/'+k)
  expected_argv=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11',d['app']['path'],'--i420','--rawvideo','--output-bit-depth=10','--threads=1','--row-mt=0','--summary','-o',str(run/'recon.yuv'),d['ivf']['path']]
  assert d['argv']==expected_argv
  for k in ('trace.jsonl','payload.bin'):
   if name=='on':assert d[k]==ident(run/k)
   else:assert k not in d and not (run/k).exists()
  identities[name]=ident(run/'command.json')
 off=json.loads((a.off/'command.json').read_text());on=json.loads((a.on/'command.json').read_text());assert off['app']==on['app'] and off['library']==on['library'] and off['ivf']==on['ivf']
 x=parse(a.on)
 indep=R/'reviewer/round10-r8-binding/run-3/events.json';assert ident(indep)['sha256']=='680e65c0f406e5ed0e809af7a0d16eb15982eb4cf1d3fa54be984803d0548dde'
 binding=json.loads(indep.read_text());expected=binding['events'];assert len(expected)==502
 packets=ivf_packets(pathlib.Path(on['ivf']['path']).read_bytes());packet_consumed=[0]*336; coded=-1
 boundevents=[]
 for (got,b),want in zip(x['events'],expected):
  pi=want['packet_index'];start=packet_consumed[pi];assert b==packets[pi]['data'][start:start+len(b)],(pi,start,'consumed bytes')
  packed=obus(b);frames=[v for v in packed if v['type'] in (3,6)];assert len(frames)==1
  v=frames[0];key=want['obu'];assert v['type']==key['type'] and len(v['data'])==key['size'] and hashlib.sha256(v['data']).hexdigest()==key['sha256']
  assert start+v['start']==key['packet_start'] and start+v['end']==key['packet_end']
  assert packets[pi]['file_offset']+start+v['start']==key['file_offset'];packet_consumed[pi]+=len(b)
  assert got['event']==want['event_index'] and got['show_existing']==want['show_existing_frame']
  if not got['show_existing']:
   coded+=1;assert got['coded_ordinal']==coded==want['coded_ordinal']
   for k in ('frame_type','show_frame','order_hint'):assert got[k]==want[k],(k,got,want)
   assert got['refresh']==want['refresh_frame_flags_normalized']
   if 'showable_frame' in want:assert got['showable']==want['showable_frame']
  else:
   assert got['coded_ordinal']==coded and got['frame_type']==got['showable']==-1 and got['show_frame']==1
   linked=expected[want['resolved_event_index']];assert got['order_hint']==linked['order_hint']
  boundevents.append(dict(**got,packet_index=pi,packet_start=start,consumed_sha256=hashlib.sha256(b).hexdigest(),obu=key))
 assert coded==335 and packet_consumed==[len(p['data']) for p in packets]
 assert binding['displays'][216]['resolved_coded_ordinal']==210 if 'resolved_coded_ordinal' in binding['displays'][216] else binding['displays'][216]['coded_ordinal']==210
 r9=R/'parent/psyex-boundary-r9/admitted-1'
 expected_hashes={'preloop':'500f1b9e393329ad1ea8f8416ce1c385d87bac3944eb3fd87c25a9d7d5a5ed6f','postloop':'8e540b11034f78a76c6a7b7732c2386eee2b3647137dffab9ab5f1930fcd1985'}
 for stage in ('preloop','postloop'):assert ident(r9/(stage+'.yuv'))['sha256']==expected_hashes[stage]
 assert x['preloop'].tobytes()==(r9/'preloop.yuv').read_bytes()[:W*H*2],'preloop luma identity'
 assert x['postloop']==(r9/'postloop.yuv').read_bytes(),'postloop allplane identity'
 with pathlib.Path(on['recon']['path']).open('rb') as f:f.seek(216*FRAME);assert f.read(FRAME)==x['postloop']
 a.out.mkdir();art={}
 for k in ('leaves','units'):dump(a.out/(k+'.json'),x[k]);art[k]=ident(a.out/(k+'.json'))
 for k in ('owner','unit','category'):np.save(a.out/(k+'.npy'),x[k]);art[k]=ident(a.out/(k+'.npy'))
 for k in ('predictor','preloop'):x[k].tofile(a.out/(k+'.y'));art[k]=ident(a.out/(k+'.y'))
 (a.out/'postloop.yuv').write_bytes(x['postloop']);art['postloop']=ident(a.out/'postloop.yuv')
 dump(a.out/'bound-events.json',boundevents);art['events']=ident(a.out/'bound-events.json')
 result=dict(status='admitted',scope='Single-frame luma syntax/predictor diagnosis; no encoder execution or repair inference',dimensions=[W,H],input_frame=216,scored_frame=120,all336_allplanes_exact=True,complete_visible_luma_ownership=True,preloop_luma_exact_R9=True,postloop_allplanes_exact_R9=True,all502_events_independently_bound=True,absent_residual_predictor_equals_preloop=True,artifacts=art,commands=identities,pristine_receipt=ident(pristine),build_pins=ident(pins_path),trace=ident(a.on/'trace.jsonl'),payload=ident(a.on/'payload.bin'),independent_events=ident(indep),r9_stages={s:ident(r9/(s+'.yuv')) for s in ('original','coding_input','preloop','postloop')},script=ident(__file__),helper=ident(REPORT/'aom_tu_binding.py'),terminal=x['terminal'],category_pixels={str(k):int((x['category']==k).sum()) for k in (1,2,3,4)})
 dump(a.out/'admission.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('artifacts','r9_stages')},indent=2))
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
