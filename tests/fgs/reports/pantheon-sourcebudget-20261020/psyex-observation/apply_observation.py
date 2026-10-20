#!/usr/bin/env python3
"""Apply the minimal parent-owned R8 observational hooks to a fresh pinned copy."""
from pathlib import Path
import difflib, hashlib, json, shutil, subprocess
R=Path(__file__).resolve().parent
S=R/'source'
assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()=='59d1a025698f2ca7b4c4b0e833937dd15e382494'
assert not subprocess.check_output(['git','-C',str(S),'status','--porcelain=v1','--untracked-files=all'],text=True)
original={};changed={}
def get(name):
 p=S/name;original[name]=p.read_text();return original[name]
def save(name,s):changed[name]=s

def replace(s,old,new):
 assert s.count(old)==1,(old[:100],s.count(old));return s.replace(old,new,1)
def add_include(s):
 return replace(s,'#include "psy_rd.h"','#include "psy_rd.h"\n#include "psy_observe.h"')

n='Source/Lib/Codec/CMakeLists.txt';s=get(n);s=replace(s,'        full_loop.c','        psy_observe.c\n        psy_observe.h\n        full_loop.c');save(n,s)
n='Source/Lib/Codec/full_loop.c';s=add_include(get(n))
start=s.index('static void svt_av1_optimize_b(');end=s.index('\n}',start)+2
part=s[start:end]
assert part.count('return;')==2
part=replace(part,'    int                    sharpness', '    PO_COUNT(pcs, ctx, PO_OPT_ENTER);\n    if (plane == 0) PO_COUNT(pcs, ctx, PO_OPT_LUMA);\n    int                    sharpness')
part=replace(part,'        if (skip_cost < non_skip_cost) {\n            return;', '        if (skip_cost < non_skip_cost) {\n            PO_COUNT(pcs, ctx, PO_OPT_EARLY_RATE);\n            return;')
part=replace(part,'        if (*eob == 0)\n            return;', '        if (*eob == 0) {\n            PO_COUNT(pcs, ctx, PO_OPT_EARLY_EOB);\n            return;\n        }')
part=replace(part,'    if (use_sharpness && delta_q_present && plane == 0) {', '    if (use_sharpness && delta_q_present && plane == 0) {\n        PO_COUNT(pcs, ctx, PO_OPT_GUARD);')
part=replace(part,'            rweight   = 0;', '            rweight   = 0;\n            PO_COUNT(pcs, ctx, PO_OPT_ZERO_WEIGHT);')
part=part[:-2]+'\n    PO_COUNT(pcs, ctx, PO_OPT_COMPLETE);\n}'
s=s[:start]+part+s[end:]
s=replace(s,'        svt_av1_perform_noise_normalization(', '        PO_COUNT(pcs, ctx, PO_NOISE_CALL);\n        svt_av1_perform_noise_normalization(')
save(n,s)

n='Source/Lib/Codec/product_coding_loop.c';s=add_include(get(n))
# Wrap only specified already-evaluated uint64_t terms; arguments and result type unchanged.
needles=[
 ('luma_fast_dist += get_svt_psy_full_dist(', 'PO_FAST_CALL', 'PO_FAST_NONZERO',2),
 ('txb_full_distortion_txt[DIST_SSD][tx_type][DIST_CALC_PREDICTION] += get_svt_psy_full_dist(', 'PO_TX_PRED_CALL','PO_TX_PRED_NONZERO',1),
 ('txb_full_distortion_txt[DIST_SSD][tx_type][DIST_CALC_RESIDUAL] += get_svt_psy_full_dist(', 'PO_TX_RECON_CALL','PO_TX_RECON_NONZERO',1),
 ('y_full_distortion[DIST_SSD][DIST_CALC_PREDICTION] += get_svt_psy_full_dist(', 'PO_FULL_PRED_CALL','PO_FULL_PRED_NONZERO',1),
 ('y_full_distortion[DIST_SSD][DIST_CALC_RESIDUAL] += get_svt_psy_full_dist(', 'PO_FULL_RECON_CALL','PO_FULL_RECON_NONZERO',1),
]
for needle,call,nonzero,expected in needles:
 assert s.count(needle)==expected,(needle,s.count(needle))
 pos=0
 for _ in range(expected):
  at=s.index(needle,pos);start=s.index('get_svt_psy_full_dist(',at);paren=start+len('get_svt_psy_full_dist');depth=0;end=None
  for i in range(paren,len(s)):
   if s[i]=='(':depth+=1
   elif s[i]==')':
    depth-=1
    if depth==0:end=i+1;break
  assert end and s[end]==';'
  expr=s[start:end]
  wrapped=f'psy_obs_term(pcs->picture_number, ctx->md_stage, {call}, {nonzero}, '+expr+')'
  s=s[:start]+wrapped+s[end:];pos=start+len(wrapped)
# Identify the precise luma full-loop route, not unrelated quantizer calls.
pos=s.index('y_full_distortion[DIST_SSD][DIST_CALC_PREDICTION] += psy_obs_term(')
route=s.rfind('    if (ctx->mds_spatial_sse) {',0,pos);assert route>=0
s=s[:route]+s[route:].replace('    if (ctx->mds_spatial_sse) {','    if (ctx->mds_spatial_sse) {\n        PO_COUNT(pcs, ctx, PO_FULL_SPATIAL);',1)
pos=s.index('y_full_distortion[DIST_SSD][DIST_CALC_RESIDUAL] += psy_obs_term(')
el=s.index('    } else {\n        // LUMA DISTORTION',pos)
s=s[:el]+s[el:].replace('    } else {\n        // LUMA DISTORTION','    } else {\n        PO_COUNT(pcs, ctx, PO_FULL_TX_DOMAIN);\n        // LUMA DISTORTION',1)
save(n,s)

n='Source/Lib/Codec/rd_cost.c';s=get(n);s='#include "psy_observe.h"\n'+s
start=s.index('void svt_aom_full_cost(');end=s.index('\n}',start)+2;part=s[start:end]
part=replace(part,'    if (ctx->blk_skip_decision && cand_bf->block_has_coeff && is_inter_mode(cand_bf->cand->pred_mode)) {', '    if (ctx->blk_skip_decision && cand_bf->block_has_coeff && is_inter_mode(cand_bf->cand->pred_mode)) {\n        PO_COUNT(pcs, ctx, PO_ZERO_COMPARE);\n        if (ctx->mds_spatial_sse && pcs->scs->static_config.psy_rd > 0) PO_COUNT(pcs, ctx, PO_ZERO_SPATIAL_COMPARE);')
part=replace(part,'        if (skip_cost < non_skip_cost) {','        if (skip_cost < non_skip_cost) {\n            PO_COUNT(pcs, ctx, PO_ZERO_CHOICE);')
part=replace(part,'    if (cand_bf->cand->skip_mode_allowed == true) {','    if (cand_bf->cand->skip_mode_allowed == true) {\n        PO_COUNT(pcs, ctx, PO_SKIPMODE_COMPARE);\n        if (ctx->mds_spatial_sse && pcs->scs->static_config.psy_rd > 0) PO_COUNT(pcs, ctx, PO_SKIPMODE_SPATIAL_COMPARE);')
part=replace(part,'        if (skip_mode_cost <= mode_cost) {','        if (skip_mode_cost <= mode_cost) {\n            PO_COUNT(pcs, ctx, PO_SKIPMODE_CHOICE);')
s=s[:start]+part+s[end:];save(n,s)

n='Source/Lib/Codec/mode_decision.c';s=add_include(get(n))
for fn,amount in [('void svt_aom_product_full_mode_decision_light_pd1(', '1'),('uint32_t svt_aom_product_full_mode_decision(', 'candidate_total_count')]:
 start=s.index(fn);end=s.index('\n}',start)+2;part=s[start:end]
 needle='    ModeDecisionCandidate* cand = cand_bf->cand;'
 hook='''
    PO_COUNT(pcs, ctx, PO_MODE_CALL);
    psy_obs_add(pcs->picture_number, ctx->md_stage, PO_MODE_CANDIDATES, AMOUNT);
    if (ctx->hbd_md) PO_COUNT(pcs, ctx, PO_MODE_HBD);
    if (ctx->mds_spatial_sse) PO_COUNT(pcs, ctx, PO_MODE_SPATIAL);
    if (is_inter_mode(cand->pred_mode)) PO_COUNT(pcs, ctx, PO_MODE_INTER);
    else PO_COUNT(pcs, ctx, PO_MODE_INTRA);
    if (cand->skip_mode) PO_COUNT(pcs, ctx, PO_MODE_SKIP);
    if (cand_bf->block_has_coeff) PO_COUNT(pcs, ctx, PO_MODE_COEFF);'''.replace('AMOUNT',amount)
 part=replace(part,needle,needle+hook);s=s[:start]+part+s[end:]
save(n,s)

n='Source/Lib/Globals/enc_handle.c';s=get(n);s='#include "psy_observe.h"\n'+s
s=replace(s,'    svt_enc_handle_stop_threads(enc_handle_ptr);','    svt_enc_handle_stop_threads(enc_handle_ptr);\n    psy_obs_flush(&enc_handle_ptr->scs_instance_array[0]->scs->static_config, enc_handle_ptr->encode_instance_total_count);')
save(n,s)

for name in ('psy_observe.c','psy_observe.h'):
 dest='Source/Lib/Codec/'+name;assert not (S/dest).exists();original[dest]='';changed[dest]=(R/name).read_text()
patch=[]
for n,s in changed.items():
 patch.extend(difflib.unified_diff(original[n].splitlines(keepends=True),s.splitlines(keepends=True),fromfile='a/'+n if original[n] else '/dev/null',tofile='b/'+n))
 (S/n).write_text(s)
(R/'observation.patch').write_text(''.join(patch))
(R/'patch-provenance.json').write_text(json.dumps({'files':{n:{'before_sha256':hashlib.sha256(original[n].encode()).hexdigest() if original[n] else None,'after_sha256':hashlib.sha256(s.encode()).hexdigest()} for n,s in changed.items()},'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'patch_sha256':hashlib.sha256((R/'observation.patch').read_bytes()).hexdigest()},indent=2)+'\n')
print('Patched',len(changed),'files; all assertions passed')
