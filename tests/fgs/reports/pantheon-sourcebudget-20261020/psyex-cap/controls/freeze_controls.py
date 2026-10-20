#!/usr/bin/env python3
"""Freeze completed R18 controls and the separately reviewed observer correction."""
import hashlib, json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/psyex-cap/controls')
FILES=['freeze_controls.py','policy-index-1.json','media_admission.py','bind_headers.py',
       'baseline-1-execution.json','baseline-1-execution.log','pass1-1-execution.json','pass1-1-execution.log',
       'cap-1-execution.json','cap-1-execution.log','trace-1-execution.json','trace-1-execution.log',
       'media-1-execution.json','media-1-execution.log','binding-1-execution.json','binding-1-execution.log',
       'media-1/media-admission.json','media-1/probe.json','binding-1/result.json',
       'prepare_observer2.py','observer2-preparation-execution.json','observer2-preparation-execution.log',
       'observer-freeze-2/observer-only.patch','observer-freeze-2/source-manifest.json','observer-freeze-2/receipt.json',
       'observer-build-index-2.json']
for tag in ('baseline-1','pass1-1','cap-1','trace-1'):
    FILES += ['runs/'+tag+'/'+name for name in ('command.json','encode.log','measured-runner.py')]
for prefix in ('build-observer-2-preparation','build-observer-2','build-observer-2-pin'):
    FILES += [prefix+'-execution.json',prefix+'-execution.log']
FILES += ['build-observer-2/'+name for name in ('preparation.json','launch.json','completed-build-pins.json',
           'build_runner.sh','measured-runner.sh','build-receipt.log','configure.log','build.log',
           'build-artifact-hashes.txt','tool-identities-before.txt','tool-identities-after.txt','app-ldd.txt','app-version.txt')]
REVIEWS=['round18-media-release.md','round18-binding-review.md','round18-binding-release-addendum.md',
         'round18-observer-rebuild-control.md','round18-observer2-source-review.md']

def ident(p):
    p=Path(p).resolve()
    with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),size=p.stat().st_size,sha256=h)

def main():
    assert not OUT.exists()
    pairs=[(HERE/x,Path(x)) for x in FILES]
    pairs += [(ROOT/'reviewer'/x,Path('reviews')/x) for x in REVIEWS]
    # Readonly preflight before creating the frozen package.
    captured=[(p,rel,ident(p)) for p,rel in pairs]
    rows=[]
    for p,rel,before in captured:
        target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists()
        shutil.copyfile(p,target);after=ident(target)
        assert before==ident(p) and (before['size'],before['sha256'])==(after['size'],after['sha256'])
        rows.append(dict(source=before,frozen=dict(path=str(rel),size=after['size'],sha256=after['sha256'])))
    external=[]
    for tag in ('baseline-1','pass1-1','cap-1','trace-1'):
        receipt=json.loads((HERE/'runs'/tag/'command.json').read_text())
        for name,row in receipt['outputs'].items():
            if name!='encode.log':
                assert ident(row['path'])==row;external.append(row)
    pins=json.loads((HERE/'build-observer-2/completed-build-pins.json').read_text())
    for name in ('app','library','cmakecache','build_ninja'):
        assert ident(pins[name]['path'])==pins[name];external.append(pins[name])
    manifest=dict(scope='Completed policy controls, media admission, independent display binding and observer-only correction/build. No trace delivery or quality admission.',
                  files=rows,bytes=sum(x['source']['size'] for x in rows),external=external)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(ident(OUT/'manifest.json')))

if __name__=='__main__':
    assert __debug__
    main()
