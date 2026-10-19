#!/usr/bin/env python3
"""Verify final patch composition, binary identities, and recorded tool provenance."""
import pathlib,tarfile,hashlib,json,shutil,subprocess,sys
from study import ROOT,HERE,x
check=ROOT/'patch-check';check.mkdir()
with tarfile.open('/media/merged-storage/cold-storage/docker-apps/pantheon-independent-investigation/svt-source.tar.gz') as a:
 for m in a.getmembers():
  rel=pathlib.PurePosixPath(m.name).parts[1:]
  if not rel:continue
  if m.isfile():
   p=check.joinpath(*rel);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(a.extractfile(m).read())
for p in [HERE.parent/'pantheon-causal-20261019/svt-causal.patch',HERE/'svt-quantization.patch',HERE/'svt-absolute.patch']:
 with p.open('rb') as f:subprocess.run(['patch','-p1','--batch'],cwd=check,stdin=f,check=True,stdout=subprocess.DEVNULL)
changed=['coding_loop.c','full_loop.c','pantheon_quant.h','pantheon_alloc.h','pantheon_trace.h','dlf_process.c','enc_dec_process.c','entropy_coding.c','rc_process.c','resource_coordination_process.c','rest_process.c','temporal_filtering.c']
hashes={}
for name in changed:
 rel=pathlib.Path('Source/Lib/Codec')/name;a=(check/rel).read_bytes();b=(ROOT/'svt-source'/rel).read_bytes();assert a==b;hashes[str(rel)]=hashlib.sha256(b).hexdigest()
shutil.rmtree(check)
x.dump(ROOT/'patch-validation.json',{'all12_patched_files_match_build_source':True,'sha256':hashes})
cmds={
 'ffmpeg':['ffmpeg','-version'],
 'compiler':['cc','--version'],
 'cmake':['cmake','--version'],
 'nvidia':['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],
 'vmaf_commit':['git','-C','/home/bardie/git-repos/vmaf','rev-parse','HEAD'],
 'ffvship_image':['docker','image','inspect',x.campaign.FFVSHIP_IMG,'--format','{{.Id}}'],
 'svt_quant':[ROOT/'SvtAv1EncApp-quant','--version'],
 'svt_absolute':[ROOT/'svt-source/Bin/Release/SvtAv1EncApp','--version'],
 'analysis_packages':[ROOT/'analysis-venv/bin/python','-m','pip','freeze'],
}
versions={}
for k,cmd in cmds.items():
 p=subprocess.run(list(map(str,cmd)),text=True,capture_output=True);versions[k]={'argv':list(map(str,cmd)),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
versions['vmaf_binary_sha256']=hashlib.sha256(pathlib.Path(x.campaign.VMAF).read_bytes()).hexdigest()
versions['campaign_sha256']=hashlib.sha256((x.REPO/'tests/fgs/campaign.py').read_bytes()).hexdigest()
x.dump(ROOT/'tool-provenance.json',versions)
print('All12 patched source files match composition; tool provenance saved')
