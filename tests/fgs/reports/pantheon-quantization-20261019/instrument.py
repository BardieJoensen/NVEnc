#!/usr/bin/env python3
"""Add read-only final-TU tracing to SVT4.2 after the prior causal patch."""
import pathlib,sys
s=pathlib.Path(sys.argv[1]);c=s/'Source/Lib/Codec'
def edit(name,old,new,count=1):
 p=c/name;t=p.read_text();assert t.count(old)==count,(name,t.count(old),old[:80]);p.write_text(t.replace(old,new))
(c/'pantheon_quant.h').write_text(r'''/* Isolated, environment-gated diagnostic. Never install. */
#ifndef PANTHEON_QUANT_H
#define PANTHEON_QUANT_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef struct { FILE *f; int w,h,tx,typ; uint16_t pred[4096] __attribute__((aligned(64))); } PqTrace;
extern _Thread_local PqTrace pq;
static void pq_write(const char *name,const void *p,uint32_t n,uint32_t size){
 if(!pq.f)return; char key[32]={0};snprintf(key,32,"%s",name);
 if(fwrite(key,32,1,pq.f)!=1 || fwrite(&n,4,1,pq.f)!=1 || fwrite(&size,4,1,pq.f)!=1 || fwrite(p,size,n,pq.f)!=n)abort();
}
static void pq_json(const char *name,const char *s){pq_write(name,s,strlen(s),1);}
void pq_counter(PictureControlSet*,ModeDecisionContext*,int32_t*,int,int,int);
void pq_recon(PictureControlSet*,ModeDecisionContext*,const char*,int32_t*,int,int,int);
#endif
''')
edit('coding_loop.c','#include "full_loop.h"','#include "full_loop.h"\n#include "pantheon_quant.h"')
# This function computes private copies only, before actual final luma coding.
helper=r'''
static void pq_begin(PictureControlSet *pcs,EncDecContext *ed,uint32_t x,uint32_t y,EbPictureBufferDesc *pred){
 if(pq.f)abort();
 const char *dir=getenv("PANTHEON_DETAIL_DIR"),*frames=getenv("PANTHEON_DETAIL_POC");
 if(!dir||!frames)return;
 char needle[32];snprintf(needle,32,",%llu,",(unsigned long long)pcs->ppcs->picture_number);
 if(!strstr(frames,needle))return;
 if(ed->bit_depth!=10||!ed->is_16bit||pcs->ppcs->is_overlay||pcs->ppcs->is_alt_ref)abort();
 ModeDecisionContext *md=ed->md_ctx;BlkStruct *b=ed->blk_ptr;
 int tx=tx_depth_to_tx_size[b->block_mi.tx_depth][ed->blk_geom->bsize];
 int typ=b->tx_type[ed->txb_itr],w=tx_size_wide[tx],h=tx_size_high[tx];
 char path[1024],meta[2048];snprintf(path,sizeof(path),"%s/%04llu-%04u-%04u.tu",dir,(unsigned long long)pcs->ppcs->picture_number,x,y);
 pq.f=fopen(path,"wb");if(!pq.f)abort();pq.w=w;pq.h=h;pq.tx=tx;pq.typ=typ;
 int seg=pcs->ppcs->frm_hdr.segmentation_params.segmentation_enabled ? pcs->ppcs->frm_hdr.segmentation_params.feature_data[b->segment_id][SEG_LVL_ALT_Q] : 0;
 int effective=pcs->ppcs->frm_hdr.delta_q_params.delta_q_present ? b->qindex : pcs->ppcs->frm_hdr.quantization_params.base_q_idx;
 effective=CLIP3(0,255,effective+seg);
 snprintf(meta,sizeof(meta),"{\"poc\":%llu,\"x\":%u,\"y\":%u,\"w\":%d,\"h\":%d,\"block_x\":%u,\"block_y\":%u,\"bsize\":%d,\"tx_size\":%d,\"tx_type\":%d,\"tx_depth\":%d,\"mode\":%d,\"skip_mode\":%d,\"md_skip\":%d,\"qindex\":%d,\"effective_qindex\":%d,\"frame_qindex\":%d,\"segment_offset\":%d,\"delta_q_present\":%d,\"bypass\":%d,\"preset\":%d}",
 (unsigned long long)pcs->ppcs->picture_number,x,y,w,h,ed->blk_org_x,ed->blk_org_y,ed->blk_geom->bsize,tx,typ,b->block_mi.tx_depth,b->block_mi.mode,b->block_mi.skip_mode,ed->md_skip_blk,b->qindex,effective,pcs->ppcs->frm_hdr.quantization_params.base_q_idx,seg,pcs->ppcs->frm_hdr.delta_q_params.delta_q_present,md->bypass_encdec,pcs->ppcs->enc_mode);
 pq_json("meta",meta);
 uint16_t input[4096] __attribute__((aligned(64)));int16_t residual[4096] __attribute__((aligned(64)));int32_t coeff[4096] __attribute__((aligned(64)))={0};uint64_t energy=0;
 EbPictureBufferDesc *in=ed->input_sample16bit_buffer;
 for(int j=0;j<h;j++)for(int i=0;i<w;i++){
  int k=j*w+i;
  input[k]=((uint16_t*)in->y_buffer)[(y-md->sb_origin_y+j)*in->y_stride+x-md->sb_origin_x+i];
  pq.pred[k]=((uint16_t*)pred->y_buffer)[(y+j)*pred->y_stride+x+i];residual[k]=(int)input[k]-pq.pred[k];
 }
 pq_write("input",input,w*h,2);pq_write("predictor",pq.pred,w*h,2);pq_write("prediction_residual",residual,w*h,2);
 svt_aom_estimate_transform(pcs,md,residual,w,coeff,0,tx,&energy,10,typ,PLANE_TYPE_Y,DEFAULT_SHAPE);
 pq_write("private_forward",coeff,w*h,4);
 pq_recon(pcs,md,"unquantized",coeff,av1_get_max_eob(tx),tx,typ);
 pq_counter(pcs,md,coeff,effective,tx,typ);
}
static void pq_end(PictureControlSet *pcs,EncDecContext *ed,uint32_t x,uint32_t y,EbPictureBufferDesc *recon){
 (void)pcs;(void)ed;if(!pq.f)return;uint16_t out[4096] __attribute__((aligned(64)));
 for(int j=0;j<pq.h;j++)for(int i=0;i<pq.w;i++)out[j*pq.w+i]=((uint16_t*)recon->y_buffer)[(y+j)*recon->y_stride+x+i];
 pq_write("actual_recon",out,pq.w*pq.h,2);fclose(pq.f);pq.f=NULL;
}
'''
edit('coding_loop.c','static void av1_encode_loop(',helper+'\nstatic void av1_encode_loop(')
p=c/'coding_loop.c';t=p.read_text();assert t.count('        // Encode Transform Unit -INTRA-')==2;p.write_text(t.replace('        // Encode Transform Unit -INTRA-','        pq_begin(pcs,ed_ctx,txb_origin_x,txb_origin_y,recon_buffer);\n        // Encode Transform Unit -INTRA-',1))
edit('coding_loop.c','        if (blk_ptr->block_mi.skip_mode == true) {','        pq_begin(pcs,ctx,txb_origin_x,txb_origin_y,recon_buffer);\n        if (blk_ptr->block_mi.skip_mode == true) {')
# Final luma reconstruction is already complete here; close before chroma.
pos='''    //**********************************
    // Chroma
    //**********************************
    if (component_mask & PICTURE_BUFFER_DESC_CHROMA_MASK) {'''
edit('coding_loop.c',pos,'    if (component_mask & PICTURE_BUFFER_DESC_LUMA_MASK) pq_end(pcs,ed_ctx,org_x,org_y,pred_samples);\n\n'+pos)
edit('full_loop.c','#include "full_loop.h"','#include "full_loop.h"\n#include "pantheon_quant.h"\n_Thread_local PqTrace pq;')
# Helpers placed before regular quantizer (all prototypes available).
helper=r'''
void pq_recon(PictureControlSet *pcs,ModeDecisionContext *ctx,const char *name,int32_t *coeff,int eob,int tx,int typ){
 if(!pq.f)return;uint16_t out[4096] __attribute__((aligned(64)));memcpy(out,pq.pred,pq.w*pq.h*2);
 if(eob)svt_aom_inv_transform_recon_wrapper(pcs,ctx,(uint8_t*)pq.pred,0,pq.w,(uint8_t*)out,0,pq.w,coeff,0,1,tx,typ,PLANE_TYPE_Y,eob);
 pq_write(name,out,pq.w*pq.h,2);
}
void pq_counter(PictureControlSet *pcs,ModeDecisionContext *ctx,int32_t *coeff,int effective,int tx,int typ){
 if(!pq.f)return;EncodeContext *ec=pcs->scs->enc_ctx;
 int qm=(IS_2D_TRANSFORM(typ)&&pcs->ppcs->frm_hdr.quantization_params.using_qmatrix)?pcs->ppcs->frm_hdr.quantization_params.qm[0]:NUM_QM_LEVELS-1;
 TxSize adjusted=aom_av1_get_adjusted_tx_size(tx);
 QuantParam qp={0};qp.log_scale=av1_get_tx_scale_tab[tx];qp.tx_size=tx;qp.qmatrix=pcs->ppcs->gqmatrix[qm][0][adjusted];qp.iqmatrix=pcs->ppcs->giqmatrix[qm][0][adjusted];
 int qs[3]={effective,MAX(1,effective-32),1};
 for(int k=0;k<3;k++){
 int q=qs[k];MacroblockPlane p={0};
 p.quant_qtx=ec->quants_bd.y_quant[q];p.quant_fp_qtx=ec->quants_bd.y_quant_fp[q];p.round_fp_qtx=ec->quants_bd.y_round_fp[q];p.quant_shift_qtx=ec->quants_bd.y_quant_shift[q];p.zbin_qtx=ec->quants_bd.y_zbin[q];p.round_qtx=ec->quants_bd.y_round[q];p.dequant_qtx=ec->deq_bd.y_dequant_qtx[q];
 int32_t qc[4096] __attribute__((aligned(64)))={0},dc[4096] __attribute__((aligned(64)))={0};uint16_t eob=0;char key[32],meta[256];
 svt_av1_highbd_quantize_b_facade(coeff,av1_get_max_eob(tx),&p,qc,dc,&eob,get_scan_order(tx,typ),&qp);
 snprintf(meta,sizeof(meta),"{\"q\":%d,\"eob\":%d,\"dequant_dc\":%d,\"dequant_ac\":%d,\"qm_level\":%d,\"log_scale\":%d}",q,eob,p.dequant_qtx[0],p.dequant_qtx[1],qm,qp.log_scale);
 snprintf(key,32,"scalar%d_meta",k);pq_json(key,meta);
 snprintf(key,32,"scalar%d_qcoeff",k);pq_write(key,qc,av1_get_max_eob(tx),4);
 snprintf(key,32,"scalar%d_dqcoeff",k);pq_write(key,dc,av1_get_max_eob(tx),4);
 snprintf(key,32,"scalar%d_recon",k);pq_recon(pcs,ctx,key,dc,eob,tx,typ);
 }
}
'''
edit('full_loop.c','uint8_t svt_aom_quantize_inv_quantize(PictureControlSet* pcs',helper+'\nuint8_t svt_aom_quantize_inv_quantize(PictureControlSet* pcs')
# Activate only on final luma call, never MD candidate or chroma calls.
anchor='''    if (perform_rdoq) {
#if CONFIG_ENABLE_HIGH_BIT_DEPTH'''
code='''    const int pq_active=pq.f && is_encode_pass && component_type==COMPONENT_LUMA;
    if(pq_active){char m[1024];snprintf(m,sizeof(m),"{\\\"effective_qindex\\\":%d,\\\"lambda\\\":%u,\\\"rdoq_enabled\\\":%d,\\\"shaving_enabled\\\":%d,\\\"dequant_dc\\\":%d,\\\"dequant_ac\\\":%d,\\\"qm_level\\\":%d,\\\"log_scale\\\":%d,\\\"eob_threshold\\\":%d,\\\"eob_fast_threshold\\\":%d}",q_index,lambda,perform_rdoq,ctx->coeff_shaving_ctrls.enabled,candidate_plane.dequant_qtx[0],candidate_plane.dequant_qtx[1],qmatrix_level,qparam.log_scale,ctx->rdoq_ctrls.eob_th,ctx->rdoq_ctrls.eob_fast_th);
    pq_json("quant_meta",m);pq_write("actual_forward",coeff,n_coeffs,4);}
'''
# Python escaping above emits escaped doublequotes inside C strings.
edit('full_loop.c',anchor,code+anchor)
for name,anchor in [('initial','    if (perform_rdoq && *eob != 0) {'),('rdoq','    // Apply coefficient shaving for luma after all quantization/RDOQ is complete.'),('final','    if (!ctx->rate_est_ctrls.update_skip_ctx_dc_sign_ctx) {')]:
 block=f'''    if(pq_active){{pq_write("{name}_qcoeff",quant_coeff,n_coeffs,4);pq_write("{name}_dqcoeff",recon_coeff,n_coeffs,4);pq_write("{name}_eob",eob,1,2);pq_recon(pcs,ctx,"{name}_recon",recon_coeff,*eob,txsize,tx_type);}}\n'''
 p=c/'full_loop.c';t=p.read_text();idx=t.index(anchor,t.index('uint8_t svt_aom_quantize_inv_quantize(PictureControlSet* pcs'));t=t[:idx]+block+t[idx:];p.write_text(t)
print('instrumented',s)
