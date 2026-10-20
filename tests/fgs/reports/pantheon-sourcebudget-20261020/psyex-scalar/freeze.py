from pathlib import Path
import hashlib,json,shutil
P=Path(__file__).resolve().parent; ROOT=P.parents[1]
D=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/psyex-scalar')
def ident(p):
 with p.open('rb') as f:s=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=s,size=p.stat().st_size)
files=['native.c','build.py','experiment.py','run.py','render.py','summarize.py','freeze.py','experiment-pre-review.py','build-2/receipt.json','build-2/inputs-before.json','build-2/inputs-after.json','build-2/exports.map','run-1-execution.json','run-1.log','run-1/receipt.json','run-1/baseline-control.json','visuals-1/manifest.json','build-1/SUPERSEDED.md']
m=[]
for name in files:
 src=P/name; dst=D/name; dst.parent.mkdir(parents=True,exist_ok=True)
 assert not dst.exists();shutil.copyfile(src,dst);assert ident(src)['sha256']==ident(dst)['sha256']
 m.append(dict(source=ident(src),frozen=ident(dst)))
for name in ['round12-outcome-review.md','round12-outcome/derive.py','round12-outcome/derived.json']:
 src=ROOT/'reviewer'/name;dst=D/name;dst.parent.mkdir(parents=True,exist_ok=True)
 assert not dst.exists();shutil.copyfile(src,dst);assert ident(src)['sha256']==ident(dst)['sha256']
 m.append(dict(source=ident(src),frozen=ident(dst)))
(D/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(len(m),'exact copies')
