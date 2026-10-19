#!/usr/bin/env python3
"""Run private FP exports; require exact byte identity against the original control."""
import json
import os
import subprocess
import sys
import time
from probe import ROOT, sha

case=sys.argv[1];delta=int(sys.argv[2]) if len(sys.argv)>2 else 8
assert delta in (8,12)
control=ROOT/'worker'/(case+'-q32-control')
out=ROOT/'parent'/(case+('-fp-private' if delta==8 else '-fp-q20-private'))
out.mkdir(exist_ok=False);(out/'detail').mkdir()
saved=json.loads((control/'command.json').read_text());cmd=saved['argv']
cmd[6]=str(ROOT/'parent-source/Bin/Release/SvtAv1EncApp')
cmd[cmd.index('-b')+1]=str(out/'out.ivf');cmd[cmd.index('-o')+1]=str(out/'recon.yuv')
env={k:v for k,v in os.environ.items() if not k.startswith('PANTHEON_')}
extra={'PANTHEON_DETAIL_DIR':str(out/'detail'),'PANTHEON_DETAIL_POC':saved['env']['PANTHEON_DETAIL_POC']}
extra['PANTHEON_FP_MIDDLE_DELTA']=str(delta)
env.update(extra);start=time.monotonic()
with (out/'encode.log').open('wb') as log:r=subprocess.run(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
record={'argv':cmd,'cwd':str(out),'env':extra,'seconds':time.monotonic()-start,'returncode':r.returncode,'binary_sha256':sha(ROOT/'parent-source/Bin/Release/SvtAv1EncApp')}
(out/'command.json').write_text(json.dumps(record,indent=2)+'\n')
assert r.returncode==0,(out/'encode.log').read_text()[-3000:]
record.update({'ivf_sha256':sha(out/'out.ivf'),'control_ivf_sha256':sha(control/'out.ivf'),
               'recon_sha256':sha(out/'recon.yuv'),'control_recon_sha256':sha(control/'recon.yuv')})
assert record['ivf_sha256']==record['control_ivf_sha256'] and record['recon_sha256']==record['control_recon_sha256']
(out/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
print(case,'private FP export complete; original stream/reconstruction unchanged',flush=True)
