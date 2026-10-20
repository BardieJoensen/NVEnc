#!/usr/bin/env python3
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
src=root/'source/Source/Lib/Codec'
def edit(name, old,new):
    p=src/name;s=p.read_text();assert s.count(old)==1,(name,old[:100],s.count(old));p.write_text(s.replace(old,new))
decls="""
void pc_route(PictureControlSet *,void *,unsigned,unsigned,unsigned);
void pc_begin(PictureControlSet *,void *,unsigned,unsigned,EbPictureBufferDesc *,unsigned,EbPictureBufferDesc *,unsigned);
void pc_skip(PictureControlSet *,void *,unsigned,unsigned,EbPictureBufferDesc *);
void pc_raw(PictureControlSet *,void *,const int16_t *,unsigned,const int32_t *);
int pc_qinfo(PictureControlSet *,void *,const int32_t *,unsigned,int,int,unsigned,unsigned,unsigned,unsigned,int,int,int,int,const void *,const void *);
void pc_stage(const char *,const int32_t *,const int32_t *,unsigned,int);
void pc_end(PictureControlSet *,void *,unsigned,unsigned,EbPictureBufferDesc *,unsigned);
void pc_commit(PictureControlSet *,void *,unsigned,unsigned,const void *);
"""
edit('pb_trace.h','#endif',decls+'\n#endif')
edit('pb_trace.c','static void die(', 'static void pc_attempt(int recode);\nstatic void pc_finish(void);\nstatic void die(')
edit('pb_trace.c','    if (recode) { ++generation;', '    pc_attempt(recode);\n    if (recode) { ++generation;')
edit('pb_trace.c','    REQUIRE(!fsync(fd));', '    pc_finish();\n    REQUIRE(!fsync(fd));')
p=src/'pb_trace.c';p.write_text(p.read_text()+'\n#include "pc_impl.h"\n')
shutil.copyfile(root/'pc_impl.c',src/'pc_impl.h')
edit('enc_dec_process.c','                        //  Encode Pass\n','                        // R11 route assertion precedes dispatch, including bypass paths.\n                        pc_route(pcs,ed_ctx,sb_index,sb_origin_x,sb_origin_y);\n                        //  Encode Pass\n')
edit('coding_loop.c',
     '    if (component_mask == PICTURE_BUFFER_DESC_FULL_MASK || component_mask == PICTURE_BUFFER_DESC_LUMA_MASK) {\n        if (ed_ctx->md_skip_blk)',
     '    if (component_mask == PICTURE_BUFFER_DESC_FULL_MASK || component_mask == PICTURE_BUFFER_DESC_LUMA_MASK) {\n        pc_begin(pcs,ed_ctx,org_x,org_y,input_samples,input_luma_offset,pred_samples,pred_luma_offset);\n        if (ed_ctx->md_skip_blk)')
edit('coding_loop.c','            blk_ptr->quant_dc.y[ed_ctx->txb_itr] = svt_aom_quantize_inv_quantize(',
     '            pc_raw(pcs,ed_ctx,(int16_t*)residual16bit->buffer_y+scratch_luma_offset,residual16bit->stride_y,(int32_t*)transform16bit->buffer_y+ed_ctx->coded_area_sb);\n            blk_ptr->quant_dc.y[ed_ctx->txb_itr] = svt_aom_quantize_inv_quantize(')
edit('coding_loop.c','    if (component_mask & PICTURE_BUFFER_DESC_LUMA_MASK) {\n        if ((blk_ptr->y_has_coeff',
     '    if (component_mask & PICTURE_BUFFER_DESC_LUMA_MASK) {\n        if(blk_ptr->skip_mode) pc_skip(pcs,ed_ctx,org_x,org_y,pred_samples);\n        if ((blk_ptr->y_has_coeff')
edit('coding_loop.c','                                                eob[0]);\n        }\n    }\n\n    //**********************************\n    // Chroma',
     '                                                eob[0]);\n        }\n        pc_end(pcs,ed_ctx,org_x,org_y,pred_samples,blk_ptr->skip_mode?0:eob[0]);\n    }\n\n    //**********************************\n    // Chroma')
edit('coding_loop.c','            svt_aom_move_blk_data(pcs, ctx, src_cu, dst_cu);\n',
     '            svt_aom_move_blk_data(pcs, ctx, src_cu, dst_cu);\n            pc_commit(pcs,ctx,sb_addr,final_blk_itr,dst_cu);\n')
p=src/'full_loop.c';p.write_text('#include "pb_trace.h"\n'+p.read_text())
edit('full_loop.c',
     '    if (perform_rdoq && ((!component_type && ctx->rdoq_ctrls.fp_q_y) || (component_type && ctx->rdoq_ctrls.fp_q_uv))) {',
     '    int pc_observe = is_encode_pass && component_type==COMPONENT_LUMA &&\n        pc_qinfo(pcs,ctx,coeff,qindex,q_index,segmentation_qp_offset,txsize,tx_type,bit_depth,lambda,txb_skip_context,dc_sign_context,perform_rdoq,qmatrix_level,&candidate_plane,&qparam);\n    const int pc_first_fp = perform_rdoq && ((!component_type && ctx->rdoq_ctrls.fp_q_y) || (component_type && ctx->rdoq_ctrls.fp_q_uv));\n    if (perform_rdoq && ((!component_type && ctx->rdoq_ctrls.fp_q_y) || (component_type && ctx->rdoq_ctrls.fp_q_uv))) {')
edit('full_loop.c',
     '    if (perform_rdoq && *eob != 0) {\n        int width',
     '    if(pc_observe) pc_stage(pc_first_fp?"scalar_fp":"scalar_b",quant_coeff,recon_coeff,*eob,perform_rdoq);\n    if (perform_rdoq && *eob != 0) {\n        int width')
edit('full_loop.c',
     '                (TranLow *)coeff, &candidate_plane, quant_coeff, (TranLow *)recon_coeff, eob, txsize, tx_type);\n        }',
     '                (TranLow *)coeff, &candidate_plane, quant_coeff, (TranLow *)recon_coeff, eob, txsize, tx_type);\n            if(pc_observe) pc_stage("fast_opt",quant_coeff,recon_coeff,*eob,perform_rdoq);\n        }')
edit('full_loop.c',
     '            }\n        }\n    }\n    if (perform_rdoq && *eob != 0) {\n        // Perform rdoq',
     '            }\n            if(pc_observe) pc_stage("requant_b",quant_coeff,recon_coeff,*eob,perform_rdoq);\n        }\n    }\n    if (perform_rdoq && *eob != 0) {\n        // Perform rdoq')
edit('full_loop.c',
     '                           (component_type == COMPONENT_LUMA) ? 0 : 1);\n    }\n\n    if (is_encode_pass',
     '                           (component_type == COMPONENT_LUMA) ? 0 : 1);\n        if(pc_observe) pc_stage("optimize_b",quant_coeff,recon_coeff,*eob,perform_rdoq);\n    }\n\n    if (is_encode_pass')
edit('full_loop.c',
     '            pcs);\n    }\n\n    if (!ctx->rate_est_ctrls.update_skip_ctx_dc_sign_ctx)',
     '            pcs);\n        if(pc_observe) pc_stage("noise_normalization",quant_coeff,recon_coeff,*eob,perform_rdoq);\n    }\n    if(pc_observe) pc_stage("final",quant_coeff,recon_coeff,*eob,perform_rdoq);\n\n    if (!ctx->rate_est_ctrls.update_skip_ctx_dc_sign_ctx)')
print('hooks installed')
