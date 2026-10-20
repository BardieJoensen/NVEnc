#!/usr/bin/env python3
"""Guarded scratch-only R9 hooks; require a pristine pinned source copy."""
from pathlib import Path
import hashlib,json,subprocess,difflib
R=Path(__file__).resolve().parent;S=R/'source'
assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()=='59d1a025698f2ca7b4c4b0e833937dd15e382494'
assert not subprocess.check_output(['git','-C',str(S),'status','--porcelain=v1','--untracked-files=all'],text=True)
original={};changed={}
def get(n):original[n]=(S/n).read_text();return original[n]
def replace(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b,1)
n='Source/Lib/Codec/CMakeLists.txt';s=get(n);changed[n]=replace(s,'        full_loop.c','        pb_trace.c\n        pb_trace.h\n        full_loop.c')
n='Source/Lib/Codec/coding_loop.c';s='#include "pb_trace.h"\n'+get(n)
a='    prepare_input_picture(scs, pcs, ctx, input_picture, sb_org_x, sb_org_y);'
changed[n]=replace(s,a,a+'\n    pb_source(pcs, ctx->input_sample16bit_buffer, sb_org_x, sb_org_y, is_16bit);')
n='Source/Lib/Codec/enc_dec_process.c';s='#include "pb_trace.h"\n'+get(n)
a='            svt_aom_get_recon_pic(pcs, &recon_ptr, is_16bit);'
s=replace(s,a,a+'\n            pb_post(pcs, recon_ptr);')
a='                if (do_recode) {\n                    // Deallocate the palette data'
b='''                if (pcs->ppcs->picture_number == 216) {
                    EbPictureBufferDesc *pb_recon;
                    svt_aom_get_recon_pic(pcs, &pb_recon, ed_ctx->is_16bit);
                    pb_attempt(pcs, pb_recon, do_recode);
                }
                if (do_recode) {
                    // Deallocate the palette data'''
changed[n]=replace(s,a,b)
n='Source/Lib/Globals/enc_handle.c';s='#include "pb_trace.h"\n'+get(n)
a='    svt_enc_handle_stop_threads(enc_handle_ptr);'
changed[n]=replace(s,a,a+'\n    pb_finish(&enc_handle_ptr->scs_instance_array[0]->scs->static_config, enc_handle_ptr->encode_instance_total_count);')
for name in ('pb_trace.c','pb_trace.h'):
 n='Source/Lib/Codec/'+name;original[n]='';assert not (S/n).exists();changed[n]=(R/name).read_text()
patch=''.join(''.join(difflib.unified_diff(original[n].splitlines(keepends=True),changed[n].splitlines(keepends=True),fromfile='a/'+n,tofile='b/'+n)) for n in changed)
(R/'boundary.patch').write_text(patch)
for n,s in changed.items():(S/n).write_text(s)
rows=[]
for p in sorted(S.rglob('*')):
 rel=p.relative_to(S)
 if '.git' in rel.parts:continue
 assert not p.is_symlink()
 if p.is_file():rows.append([str(rel),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()])
assert len(rows)==1789
(R/'source-manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
(R/'patch-provenance.json').write_text(json.dumps({'source_commit':'59d1a025698f2ca7b4c4b0e833937dd15e382494','patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'files':{n:{'before_sha256':hashlib.sha256(original[n].encode()).hexdigest(),'after_sha256':hashlib.sha256(changed[n].encode()).hexdigest()} for n in changed}},indent=2)+'\n')
print('patched',len(changed),'files; manifest',hashlib.sha256((R/'source-manifest.json').read_bytes()).hexdigest())
