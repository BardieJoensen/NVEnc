#!/usr/bin/env python3
"""R16 final-owner support decomposition; gated on an admitted parent receipt."""
from __future__ import annotations
if not __debug__: raise SystemExit('optimized Python is rejected')
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020');W,H=1920,1080
PRODUCER_SHA='fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb';ORIGINAL_SHA='c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12'
PARSER_SHA='45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3';ANALYZE_SHA='44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e'
ROIS={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ident(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def exact(d):assert ident(d['path'])==d;return Path(d['path'])
def mod(p,n,h):
 assert ident(p)['sha256']==h;sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def main():
 script_before=ident(__file__)
 ap=argparse.ArgumentParser();ap.add_argument('admission',type=Path,nargs='?');ap.add_argument('admission_sha',nargs='?');ap.add_argument('out',type=Path,nargs='?');ap.add_argument('--schema-smoke',action='store_true');ap.add_argument('--control-r15',action='store_true');a=ap.parse_args()
 parser=mod(ROOT/'parent/psyex-real-r15/parsers.py','r16_parser',PARSER_SHA);an=mod(ROOT/'parent/psyex-coeff-r11/analyze.py','r11_analyze',ANALYZE_SHA);helper=mod(an.U,'r10_unit_helpers',an.USHA);h=helper.helper()
 if a.schema_smoke:
  old=ROOT/'parent/psyex-real-r15/admitted-1/admission.json';oa=json.loads(old.read_text());bd=json.loads(exact(oa['artifacts']['syntax_binding']).read_text());coded=int(bd['target_coded_event']['coded_ordinal']);ts,term=parser.parse_coeff(exact(oa['trace']),coded);jm={int(r['token']):r for r in json.loads(exact(oa['token_manifest']).read_text())};assert len(jm)==len(ts)==oa['tokens'] and set(jm)==set(ts);fm,cov=an.make_mosaics(ts);assert all(np.isfinite(fm[k][cov]).all() for k in fm);print(json.dumps({'status':'schema_smoke','tokens':len(ts),'coded_ordinal':coded,'covered_pixels':int(cov.sum())}));return
 if a.control_r15:
  a.admission=ROOT/'parent/psyex-real-r15/admitted-1/admission.json';a.admission_sha='10e7bc21ae29e3913fc022ae0d472929b829df0ef3cd6393fef46aa08cf66ecf';a.out=Path(__file__).resolve().parent/'control-r15-result';assert not a.out.exists();producer_expected='7dc554ff79d8b9c8b206e10f5326394dcc4483e5c679cfcb22529340aa7c9da4'
 else:
  assert a.admission and a.admission_sha and a.out and not a.out.exists();producer_expected=PRODUCER_SHA
 a.out.mkdir(parents=True)
 assert ident(a.admission)['sha256']==a.admission_sha;ad=json.loads(a.admission.read_text());assert ad.get('status')=='admitted' and ad.get('case')=='e05-1440'
 assert ad.get('script',{}).get('sha256')==producer_expected and sha(ad['script']['path'])==producer_expected
 for v in ad.values():
  if isinstance(v,dict) and {'path','sha256','size'}<=v.keys():exact(v)
 dec=json.loads(exact(ad['decoder_admission']).read_text()); sb=ad['source_boundaries'];
 for k in ('original','coding_input','preloop','postloop'):exact(sb[k])
 assert sb['original']['sha256']==ORIGINAL_SHA and sb['coding_input']['sha256']==ORIGINAL_SHA
 refs={k:helper.load_luma(exact(sb[k])) for k in ('original','coding_input','preloop','postloop')};assert np.array_equal(refs['original'],refs['coding_input'])
 tokpath=exact(ad['token_manifest']);joined=json.loads(tokpath.read_text());assert isinstance(joined,list)
 # The syntax-binding artifact supplies the dynamic coded ordinal; no R15 event index is assumed.
 binding=exact(ad['artifacts']['syntax_binding']);bd=json.loads(binding.read_text());assert bd['encode_receipt']==ad['artifacts']['original_receipt']
 coded=int(bd['target_coded_event']['coded_ordinal']);assert coded>=0
 coeff=exact(ad['trace']);tokens,terminal=parser.parse_coeff(coeff,coded);assert terminal==ad['terminal'] and len(tokens)==int(ad['tokens'])
 jmap={int(r['token']):r for r in joined};assert len(jmap)==len(joined)==int(ad['tokens']) and set(tokens)==set(jmap)
 for key,t in tokens.items():
  j=jmap[key]
  for field in ('begin','info','end','commit'): assert t.get(field)==j.get(field),(key,field)
  assert (bool(t['stages']) and isinstance(t['info'].get('actual_qindex'),int)) or (not t['stages'] and t['end']['eob']==0 and t['info'] is None)
 frames,covered=an.make_mosaics(tokens);assert all(np.isfinite(frames[k][covered]).all() for k in frames)
 assert np.all(covered[np.s_[650:750,1200:1400]]) and np.all(covered[np.s_[50:230,950:1200]]) and np.all(covered[np.s_[600:1080,160:660]])
 # Native final mosaic must equal the independently admitted preloop luma in every covered ROI.
 assert np.allclose(frames['final'][covered],refs['preloop'][covered],atol=0,rtol=0)
 rows=[];maskmaps={};result_rois={}
 for name,(rx,ry,rw,rh) in ROIS.items():
  maskmaps[name]={};groups={};region=np.zeros((rh,rw),bool)
  for key,t in tokens.items():
   z=t['begin'];x,y,w,h=(int(z[k]) for k in ('x','y','w','h'));ix0=max(x,rx);iy0=max(y,ry);ix1=min(x+w,rx+rw);iy1=min(y+h,ry+rh)
   if ix0>=ix1 or iy0>=iy1:continue
   sl=np.s_[iy0:iy1,ix0:ix1];loc=np.s_[iy0-ry:iy1-ry,ix0-rx:ix1-rx];assert not region[loc].any();region[loc]=True
   inv=bool(t['stages']);eob=int(t['end']['eob']);info=t.get('info');q=info.get('actual_qindex') if info is not None else None;joined_row=jmap[key];unit_id=joined_row['unit'];category=joined_row['category']
   assert inv or (q is None and eob==0)
   if eob>0: assert category==4
   if not inv: assert category in (1,2,3) or eob==0
   gkey=('invoked' if inv else 'uninvoked')+'_'+('positive_eob' if eob>0 else 'zero_eob');g=groups.setdefault(gkey,{'pixels':0,'units':0,'q_values':{},'geometry':{},'sse':{}});n=(iy1-iy0)*(ix1-ix0);g['pixels']+=n;g['units']+=1
   if q is not None:g['q_values'][str(q)]=g['q_values'].get(str(q),0)+n
   geom=f'{w}x{h}';g['geometry'][geom]=g['geometry'].get(geom,0)+n
   orig=refs['original'][sl];raw=frames['raw_executed'][sl];
   for stage,zv in [('raw_executed',raw),('scalar',frames['scalar'][sl]),('final',frames['final'][sl]),('preloop',refs['preloop'][sl]),('postloop',refs['postloop'][sl])]:
    g['sse'].setdefault(stage,{'vs_original':0.0,'vs_raw_executed':0.0});g['sse'][stage]['vs_original']+=float(np.square(zv-orig).sum());g['sse'][stage]['vs_raw_executed']+=float(np.square(zv-raw).sum())
   rows.append({'roi':name,'token':int(key),'xywh':[x,y,w,h],'visible_intersection':[ix0,iy0,ix1-ix0,iy1-iy0],'invoked':inv,'eob':eob,'actual_qindex':q,'unit':unit_id,'category':category,'stages':[s['stage'] for s in t['stages']]})
  assert np.all(region), (name,int(region.sum()),rw*rh);maskmaps[name]=region.astype('uint8').tolist();groups['_totals']={'pixels':rw*rh,'units':sum(v['units'] for k,v in groups.items() if k!='_totals')};
  result_rois[name]={'xywh':[rx,ry,rw,rh],'groups':groups,'coverage_pixels':int(region.sum())}
 out={'status':'complete','admission':ident(a.admission),'producer_sha':producer_expected,'script':script_before,'parser':ident(ROOT/'parent/psyex-real-r15/parsers.py'),'analyze_helper':ident(ROOT/'parent/psyex-coeff-r11/analyze.py'),'unit_helper':ident(an.U),'source_boundaries':sb,'token_manifest':ident(tokpath),'trace':ident(coeff),'terminal':terminal,'rois':result_rois,'rows':rows,'maskmaps':maskmaps,'limitations':['SSE is additive; no HF/ACF fraction is inferred.','This is support attribution, not a counterfactual repair or quality conclusion.']}
 (a.out/'result.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');(a.out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n');script_after=ident(__file__);assert script_before==script_after
 execution={'status':'complete','argv':sys.argv,'python':sys.executable,'script_before':script_before,'script_after':script_after,'admission':ident(a.admission),'result':ident(a.out/'result.json'),'rows':ident(a.out/'rows.json')};(a.out/'execution.json').write_text(json.dumps(execution,indent=2)+'\n');print(json.dumps({'status':'complete','result':ident(a.out/'result.json'),'rows':ident(a.out/'rows.json'),'execution':ident(a.out/'execution.json')}))
if __name__=='__main__':main()
