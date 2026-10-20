import importlib.util, json, hashlib, subprocess, sys
from pathlib import Path
import numpy as np
r=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020')
p=r/'analyze_psyex_boundary.py'
spec=importlib.util.spec_from_file_location('pb_analysis',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
y=np.zeros((32,32),float); z=np.random.default_rng(72).normal(80,1,(32,32))
def row(a,outside):
 planes={'y':a,'u':a[:16,:16],'v':a[:16,:16]}
 return {'kind':'flat_texture','outside_target':outside,'stages':{s:{'luma':m.luma_pair(a,a),'pixels':m.pixel_errors(planes,planes)} for s in m.STAGES}}
rows=[row(z,False),row(y,True)];s=m.summarize(rows)
assert len(s)==10
for stage in m.STAGES:
 assert s['all|outside=false'][stage]['tiles']==2
 assert s['all|outside=true'][stage]['tiles']==1
 assert s['quiet|outside=false'][stage]['tiles']==0
 assert s['all|outside=true'][stage]['acf1_abs_error']=={'total':1,'evaluable':0,'mean':None,'p95':None}
 assert s['all|outside=false'][stage]['acf1_abs_error']['evaluable']==1
 assert s['all|outside=false'][stage]['luma_mse']['mean']==0
assert np.array_equal(m.luma8(np.array([0,64,235,255.])),[0,64,235,255])
for script in (r/'validate_psyex_boundary.py',p):
 cmd=[sys.executable,'-O',str(script),'--help'];result=subprocess.run(cmd,capture_output=True,text=True)
 assert result.returncode!=0 and 'Do not disable admission assertions' in result.stderr
 print(json.dumps({'argv':cmd,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}))
print(json.dumps({'status':'passed','argv':sys.argv,'python':m.ident(sys.executable),'helpers':{'analyze':m.ident(m.REPORT/'analyze.py'),'texture':m.ident(m.INDEP/'texture.py'),'high_pass':m.ident(Path(m.analyze_mod.x.__file__))},'script':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'checks':['all/outside population','missing quiet groups','constant/None ACF','source self-MSE','-O rejection both scripts']}))
