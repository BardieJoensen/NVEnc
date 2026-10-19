#!/usr/bin/env python3
"""Scratch-only real final-EncDec FP retention on the absolute-q diagnostic map."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'Source/Lib/Codec/full_loop.c';s=p.read_text()
helper=r'''
static int pq_keep_fp(PictureControlSet *pcs, ModeDecisionContext *ctx, int is_encode_pass, int component, int q) {
 const char *path=getenv("PANTHEON_KEEP_FP_MAP");
 if(!path || !is_encode_pass || component!=COMPONENT_LUMA)return 0;
 static _Thread_local int16_t *map;
 if(!map){map=malloc(336*510*2);FILE *f=fopen(path,"rb");if(!f||!map)abort();if(fread(map,2,336*510,f)!=336*510||fgetc(f)!=EOF)abort();fclose(f);}
 if(pcs->ppcs->picture_number>=336 || pcs->scs->sb_size!=64 || pcs->sb_total_count!=510)abort();
 int index=(ctx->sb_origin_y/64)*30+ctx->sb_origin_x/64;
 if(index<0||index>=510)abort();
 int wanted=map[pcs->ppcs->picture_number*510+index];
 if(wanted<0)return 0;
 if(wanted!=q){fprintf(stderr,"Keep-FP qindex not realized: %d != %d\n",q,wanted);abort();}
 return 1;
}
static uint64_t pq_coeff_hash(const int32_t *q,const int32_t *dq,int n){
 uint64_t h=1469598103934665603ULL;for(int i=0;i<n;i++){h^=(uint32_t)q[i];h*=1099511628211ULL;h^=(uint32_t)dq[i];h*=1099511628211ULL;}return h;
}
'''
anchor='uint8_t svt_aom_quantize_inv_quantize(PictureControlSet* pcs';assert s.count(anchor)==1
s=s.replace(anchor,helper+'\n'+anchor)
anchor='    const int pq_active=pq.f && is_encode_pass && component_type==COMPONENT_LUMA;';assert s.count(anchor)==1
s=s.replace(anchor,'    const int keep_fp=pq_keep_fp(pcs,ctx,is_encode_pass,component_type,q_index);\n    if(keep_fp && !perform_rdoq)abort();\n'+anchor)
start=s.index('    if(pq_active){pq_write("initial_qcoeff"')
end=s.index('    if (!ctx->rate_est_ctrls.update_skip_ctx_dc_sign_ctx)',start)
block=s[start:end]
block='    uint64_t keep_hash=keep_fp?pq_coeff_hash(quant_coeff,recon_coeff,n_coeffs):0;\n    uint16_t keep_eob=*eob;\n'+block
assert block.count('if (perform_rdoq && *eob != 0)')==2
block=block.replace('if (perform_rdoq && *eob != 0)', 'if (!keep_fp && perform_rdoq && *eob != 0)')
block=block.replace('if (component_type == COMPONENT_LUMA && ctx->coeff_shaving_ctrls.enabled', 'if (!keep_fp && component_type == COMPONENT_LUMA && ctx->coeff_shaving_ctrls.enabled')
block+=r'''
    if(keep_fp){
      uint64_t final_hash=pq_coeff_hash(quant_coeff,recon_coeff,n_coeffs);
      if(final_hash!=keep_hash || *eob!=keep_eob)abort();
      const char *log=getenv("PANTHEON_KEEP_FP_LOG");if(!log)abort();FILE *f=fopen(log,"a");if(!f)abort();
      fprintf(f,"%llu,%u,%u,%d,%d,%u,%llu,%llu\n",(unsigned long long)pcs->ppcs->picture_number,ctx->sb_origin_x,ctx->sb_origin_y,q_index,n_coeffs,*eob,(unsigned long long)keep_hash,(unsigned long long)final_hash);fclose(f);
    }
    if(pq_active){char k[100];snprintf(k,sizeof(k),"{\"keep_fp\":%d}",keep_fp);pq_json("retention_meta",k);}
'''
s=s[:start]+block+s[end:];p.write_text(s)
