#!/usr/bin/env python3
"""R18 IVF->MKV and all336 decoder identity admission; no quality/playback claim."""
import argparse, datetime as dt, hashlib, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')).resolve()
P18=ROOT/'parent/psyex-cap-r18'; RUNNER=P18/'run.py'; RUNNER_SHA='ebfce2b97bd8002db2e866086ed44ac8dece936d64bfeaa01062f29dc5bf6bb3'
PINS_SHA='c0e389a6ca98513c5b4117b48dab02552b7f21ea978585974243f747803e1fe7'; PATCH_SHA='5f03edf1ba320c84006e65484e88742ffb60b2de422b73b10346ea90ca9ed5d0'; MANIFEST_SHA='f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca'
REPORT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020'); SHARED=REPORT/'validate_aom_qmax_decoders.py'; SHARED_SHA='bb2e0256100ad70e02753c0fc19c0cc62f2ed189f08d50335b3ab421983b5ca9'; N=336; W=1920; H=1080; FRAME_BYTES=W*H*3
PROVENANCE=P18/'provenance.py'; PROVENANCE_SHA='b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f'
READER=P18/'read_cap_trace.py'; READER_SHA='08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8'

def ident(p):
 p=Path(p).resolve(); return {'path':str(p),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'size':p.stat().st_size}
def check(row): assert ident(row['path'])=={k:row[k] for k in ('path','sha256','size')}
def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()
def load_runner():
 assert ident(RUNNER)['sha256']==RUNNER_SHA
 spec=importlib.util.spec_from_file_location('r18_run',RUNNER); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
def load_shared():
 assert ident(SHARED)['sha256']==SHARED_SHA
 spec=importlib.util.spec_from_file_location('shared',SHARED); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def launcher_tools():
 return {str(Path(p).resolve()): ident(p) for p in (sys.executable, "/usr/bin/nice", "/usr/bin/taskset")}

def load_provenance():
 assert ident(PROVENANCE)["sha256"] == PROVENANCE_SHA and ident(READER)["sha256"] == READER_SHA
 sys.path.insert(0, str(P18))
 spec=importlib.util.spec_from_file_location("r18_provenance", PROVENANCE); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def ivf_rows(path):
 b=Path(path).read_bytes(); assert b[:4]==b'DKIF' and len(b)>=32
 assert (int.from_bytes(b[12:14],'little'),int.from_bytes(b[14:16],'little'),int.from_bytes(b[16:20],'little'),int.from_bytes(b[20:24],'little'),int.from_bytes(b[24:28],'little'))==(W,H,24,1,N)
 rows=[]; pos=32
 for i in range(N):
  size=int.from_bytes(b[pos:pos+4],'little'); pts=int.from_bytes(b[pos+4:pos+12],'little'); pos+=12; assert size>0 and pts==i and pos+size<=len(b)
  rows.append({'index':i,'pts':pts,'size':size,'sha256':hashlib.sha256(b[pos:pos+size]).hexdigest()}); pos+=size
 assert pos==len(b); return rows

def main():
 if not __debug__: raise SystemExit('optimized Python prohibited')
 ap=argparse.ArgumentParser(); ap.add_argument('cap_command',type=Path); ap.add_argument('cap_sha'); ap.add_argument('outer_execution',type=Path); ap.add_argument('outer_sha'); ap.add_argument('pins',type=Path); ap.add_argument('pins_sha'); ap.add_argument('output',type=Path); a=ap.parse_args()
 assert not a.output.exists() and '/' not in a.output.name
 for k in ('LD_PRELOAD','LD_LIBRARY_PATH','LD_AUDIT','AOM_TRACE_FD','AOM_TRACE_PATH','AOM_NEUTRALIZE_SOURCE'): assert not os.environ.get(k),k
 assert shutil.disk_usage(ROOT).free>=160*2**30; a.output.mkdir()
 receipt={'status':'started','started_utc':utc(),'script':ident(__file__),'commands':[],'resource_before':{'free_bytes':shutil.disk_usage(ROOT).free,'loadavg':Path('/proc/loadavg').read_text()},'scope':'R18 media/decoder identity admission only; no native coefficient, quality, or playback claim.'}; outrec=a.output/'media-admission.json'; outrec.write_text(json.dumps(receipt,indent=2)+'\n')
 def save(): outrec.write_text(json.dumps(receipt,indent=2)+'\n')
 try:
  runner=load_runner(); shared=load_shared(); provenance=load_provenance(); assert ident(a.cap_command)['sha256']==a.cap_sha; raw=json.loads(a.cap_command.read_text()); assert raw['mode']=='cap'
  cap=runner.read_receipt(a.cap_command,a.cap_sha,'cap'); pins=json.loads(a.pins.read_text()); assert ident(a.pins)['sha256']==a.pins_sha==PINS_SHA and pins['status']=='build_complete' and pins['returncode']==0
  assert cap['pins']==ident(a.pins)
  for v in pins.values():
   if isinstance(v,dict) and {'path','sha256','size'}<=v.keys(): check(v)
  check(pins['patch']); assert pins['patch']['sha256']==PATCH_SHA; check(pins['source_manifest']); assert pins['source_manifest']['sha256']==MANIFEST_SHA
  assert ident(a.outer_execution)['sha256']==a.outer_sha
  outer_args=['cap',cap['tag'],cap['pins']['path'],cap['pins']['sha256'],'--control',cap['control']['path'],'--control-sha',cap['control']['sha256'],'--parent',cap['parent']['path'],'--parent-sha',cap['parent']['sha256']]
  outer=provenance.outer(ident(a.outer_execution),RUNNER,RUNNER_SHA,outer_args); receipt['outer']=ident(a.outer_execution); receipt['inputs']={'cap_command':ident(a.cap_command),'outer_execution':ident(a.outer_execution),'pins':ident(a.pins),'runner':ident(RUNNER),'shared':ident(SHARED),'patch':pins['patch'],'manifest':pins['source_manifest'],'provenance':ident(PROVENANCE),'reader':ident(READER)}
  ivf=Path(cap['outputs']['out.ivf']['path']); recon=Path(cap['outputs']['recon.yuv']['path']); check(cap['outputs']['out.ivf']); check(cap['outputs']['recon.yuv']); assert len(ivf_rows(ivf))==N; receipt['inputs'].update(ivf=ident(ivf),recon=ident(recon)); receipt['tools_before']=shared.tools(); receipt['launcher_tools_before']=launcher_tools(); receipt['resource_before']={'free_bytes':shutil.disk_usage(ROOT).free,'loadavg':Path('/proc/loadavg').read_text()}; save()
  remux=a.output/'out.mkv'; log=a.output/'remux.log'; argv=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11','/usr/bin/ffmpeg','-hide_banner','-v','error','-n','-i',str(ivf),'-map','0:v:0','-c:v','copy','-f','matroska',str(remux)]; row={'name':'remux','argv':argv,'started_utc':utc()}; receipt['commands'].append(row); save(); t=time.monotonic()
  with log.open('x') as f: p=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,cwd=a.output)
  row.update(returncode=p.returncode,seconds=time.monotonic()-t,ended_utc=utc(),log=ident(log)); assert p.returncode==0 and remux.exists(); row['output']=ident(remux); save()
  probe=a.output/'probe.json'; pargv=['/usr/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_packets','-of','json',str(remux)]; t=time.monotonic(); pp=subprocess.run(pargv,text=True,capture_output=True); probe.write_text(json.dumps({'argv':pargv,'returncode':pp.returncode,'stdout':pp.stdout,'stderr':pp.stderr,'seconds':time.monotonic()-t},indent=2)+'\n'); receipt['probe']=ident(probe); assert pp.returncode==0; data=json.loads(pp.stdout); assert len(data['streams'])==1; s=data['streams'][0]; assert [s[k] for k in ('codec_name','width','height','pix_fmt')]==['av1',W,H,'yuv420p10le']; assert [s[k] for k in ('color_range','color_space','color_transfer','color_primaries')]==['tv','bt709','bt709','bt709']; assert (s['time_base'],s['r_frame_rate'])==('1/1000','24/1'); packets=data['packets']; assert len(packets)==N and all(p['stream_index']==0 for p in packets); assert [p['pts'] for p in packets]==[(i*1000+12)//24 for i in range(N)]; payload=[int(p['size']) for p in packets]; receipt['packet_window']={'all336_mbps':sum(payload)*8/14/1e6,'scored96_336_mbps':sum(payload[96:])*8/10/1e6,'selected_sorted_positions':[96,336],'payload_bytes':payload}; save()
  expected=shared.raw_hashes(recon); receipt['app_frame_md5']=expected; base=['/usr/bin/nice','-n','10','/usr/bin/taskset','-c','8-11','/usr/bin/ffmpeg','-hide_banner','-v','error','-n','-threads','4']; out=['-map','0:v:0','-frames:v',str(N),'-pix_fmt','yuv420p10le','-c:v','rawvideo','-threads','4']; specs=[('dav1d',['-c:v','libdav1d','-filmgrain','0']),('libaom',['-c:v','libaom-av1']),('nvdec',['-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','av1_cuvid'])]
  for name,sel in specs:
   path=a.output/(name+'.framemd5'); lg=a.output/(name+'.log'); argv=base+sel+['-i',str(remux)]+(['-vf','hwdownload,format=p010le,format=yuv420p10le'] if name=='nvdec' else [])+out+['-f','framemd5',str(path)]; row={'name':name,'argv':argv,'started_utc':utc()}; receipt['commands'].append(row); save(); t=time.monotonic()
   with lg.open('x') as f: p=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,cwd=a.output)
   row.update(returncode=p.returncode,seconds=time.monotonic()-t,ended_utc=utc(),log=ident(lg)); assert p.returncode==0 and path.exists(); row['output']=ident(path); got=shared.parse_framemd5(path); assert got==expected, name; row['frame_md5']=got; save()
  # Persist all tool and input/output identity checks after every media command.
  receipt['tools_after']=shared.tools(); receipt['launcher_tools_after']=launcher_tools(); receipt['resource_after']={'free_bytes':shutil.disk_usage(ROOT).free,'loadavg':Path('/proc/loadavg').read_text()}; assert receipt['tools_before']==receipt['tools_after']; assert receipt['launcher_tools_before']==receipt['launcher_tools_after']; assert receipt['resource_after']['free_bytes']>=120*2**30;
  for row in receipt['commands']:
   check(row['log']); check(row['output'])
   assert receipt['inputs']=={**receipt['inputs'], 'cap_command':ident(a.cap_command),'outer_execution':ident(a.outer_execution),'pins':ident(a.pins),'runner':ident(RUNNER),'shared':ident(SHARED),'patch':pins['patch'],'manifest':pins['source_manifest'],'ivf':ident(ivf),'recon':ident(recon),'provenance':ident(PROVENANCE),'reader':ident(READER)}; assert shutil.disk_usage(ROOT).free>=120*2**30
  for value in receipt['inputs'].values(): check(value)
  check(receipt['outer']); check(receipt['probe']); assert receipt['script']==ident(__file__)
  receipt.update(status='admitted',finished_utc=utc(),outputs={'mkv':ident(remux),'recon':ident(recon)}); save()
 except BaseException as e:
  receipt['resource_after']={'free_bytes':shutil.disk_usage(ROOT).free,'loadavg':Path('/proc/loadavg').read_text()}; receipt.update(status='failed',error=repr(e),finished_utc=utc()); save(); raise
if __name__=='__main__': main()
