from pathlib import Path
import json,subprocess,re,shutil
import repeat_identity as h
r=Path(__file__).resolve().parent
seed_path=r/'reports/kernels-silo-plain-v2/report.json'
seed=json.loads(seed_path.read_text());case=seed['cases']['silo_partial']
assert seed['complete'] and not seed['all_matched'] and case['geometry']==[1918,802,24000,1001]
assert seed['deployed_binary_sha256']=='c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b'
base=case['base_argv'];assert '--av1-film-grain' not in base and base[base.index('--max-bitrate')+1]=='50000'
assert case['frames']==24 and case['output_depth']==10
rows={x['requested_vbr_kbps']:x for x in case['runs'] if x.get('complete')}
target=case['target_median_kbps']
assert rows[2092]['payload_kbps']<target*.97 and rows[2107]['payload_kbps']>target*1.03
pins={path:h.pin(path,p['sha256']) for path,p in seed['pins'].items()}
pins[str(seed_path)]=h.pin(seed_path,h.digest(seed_path))
dest=r/'reports/kernels-silo-plain-refinement';dest.mkdir(exist_ok=False)
report={'complete':False,'matched':False,'source_report':str(seed_path),'source_report_sha256':h.digest(seed_path),'script_sha256':h.digest(__file__),'pins':pins,'target_kbps':target,'relative_tolerance':.03,'requested_rates':list(range(2093,2107)),'runs':[],'note':'Exhaust the remaining integer VBR targets between observed under/over endpoints; unchanged source, frames, video settings and real max50000. No new FGS runs and no tolerance relaxation.'}
def save():
 tmp=dest/'report.json.tmp';tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(dest/'report.json')
def stable():
 for path,p in pins.items():
  assert h.identity(path)==p['stat'],path
save()
try:
 for rate in report['requested_rates']:
  stable();assert shutil.disk_usage(dest).free>3*(1<<30)
  directory=dest/f'vbr-{rate}';directory.mkdir();video=directory/'plain.ivf'
  command=base+['--vbr',str(rate),'-o',str(video)]
  row={'requested_vbr_kbps':rate,'argv':command,'directory':str(directory),'complete':False,'matched':False};report['runs'].append(row);save()
  with (directory/'encode.log').open('xb') as log:
   done=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=600)
  stable();row['returncode']=done.returncode;assert done.returncode==0
  text=(directory/'encode.log').read_text(errors='replace')
  assert int(re.findall(r'encoded\s+(\d+)\s+frames',text)[-1])==24
  assert tuple(map(int,re.findall(r'Bitrate\s+(\d+)\s+kbps\s+\(Max:\s*(\d+)\s+kbps\)',text)[-1]))==(rate,50000)
  row.update(h.inspect_ivf(video,24));assert [row[x] for x in ('width','height','rate','scale')]==case['geometry']
  row['relative_mismatch']=row['payload_kbps']/target-1
  row['matched']=abs(row['relative_mismatch'])<=.03
  if row['matched']:row.update(h.decoded_md5(seed['ffmpeg']['path'],video,row,10,24,600))
  row['complete']=True;report['matched']=row['matched'];save()
  print(rate,row['payload_kbps'],row['relative_mismatch'],flush=True)
  if row['matched']:break
 stable()
 for path,p in pins.items():h.pin(path,p['sha256'])
 report['complete']=True
 if not report['matched']:report['unresolved']='No remaining integer target in the measured bracket meets the unchanged three-percent band'
except BaseException as error:
 report['failure']=f'{type(error).__name__}: {error}';raise
finally:save()
raise SystemExit(0 if report['matched'] else 1)
