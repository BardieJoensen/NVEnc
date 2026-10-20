/* Scratch-only R10 decoder observations. No production installation. */
#ifndef PANTHEON_DECODER_H
#define PANTHEON_DECODER_H
#include "av1/decoder/decoder.h"
void p10_begin(AV1Decoder *pbi);
void p10_end(AV1Decoder *pbi, const uint8_t *start, const uint8_t *end, const uint8_t *input_end, int decoded);
void p10_leaf(const AV1_COMMON *cm, DecoderCodingBlock *dcb);
int p10_tu(const AV1_COMMON *cm, DecoderCodingBlock *dcb, int plane, int row, int col, TX_SIZE tx);
void p10_after(const AV1_COMMON *cm, DecoderCodingBlock *dcb, int plane, int row, int col, TX_SIZE tx, int id);
void p10_inter_skip(const AV1_COMMON *cm, DecoderCodingBlock *dcb);
#endif
#ifdef PANTHEON_DECODER_IMPLEMENTATION
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "av1/common/quant_common.h"
#include "av1/common/txb_common.h"
static FILE *p10_j, *p10_b;
static int p10_initialized, p10_event = -1, p10_coded = -1;
static int p10_leafid = -1, p10_tuid = -1;
static uint64_t p10_pos;
static void p10_fail(const char *s) { fprintf(stderr,"PANTHEON_R10_FATAL:%s\n",s); exit(91); }
static void p10_check(void) { if (ferror(p10_j) || ferror(p10_b)) p10_fail("write"); }
static uint64_t p10_bytes(const void *p, size_t n) {
  uint64_t o=p10_pos;
  if (n>64000000 || fwrite(p,1,n,p10_b)!=n) p10_fail("payload");
  p10_pos+=n; return o;
}
static int p10_target(void) { return p10_j && p10_event==314; }
static uint64_t p10_surface(const MACROBLOCKD *xd, int row, int col, int w, int h) {
  const struct macroblockd_plane *pd=&xd->plane[0];
  if (!(xd->cur_buf->flags & YV12_FLAG_HIGHBITDEPTH) || xd->bd!=10) p10_fail("surface_depth");
  const uint16_t *s=CONVERT_TO_SHORTPTR(pd->dst.buf)+(row*4)*pd->dst.stride+col*4;
  uint64_t o=p10_pos;
  for(int y=0;y<h;y++) p10_bytes(s+y*pd->dst.stride,(size_t)w*2);
  return o;
}
void p10_begin(AV1Decoder *pbi) {
  if(!p10_initialized) {
    p10_initialized=1; const char *dir=getenv("PANTHEON_R10_DIR");
    if(!dir || !*dir) return;
    if(sizeof(tran_low_t)!=4 || sizeof(uint16_t)!=2) p10_fail("native_types");
    uint16_t endian=1; if(*(uint8_t*)&endian!=1) p10_fail("endianness");
    char path[4096];
    if(snprintf(path,sizeof(path),"%s/trace.jsonl",dir)>=(int)sizeof(path)) p10_fail("path");
    p10_j=fopen(path,"wx"); if(!p10_j) p10_fail("trace_open");
    if(snprintf(path,sizeof(path),"%s/payload.bin",dir)>=(int)sizeof(path)) p10_fail("path");
    p10_b=fopen(path,"wbx"); if(!p10_b) p10_fail("payload_open");
    fprintf(p10_j,"{\"kind\":\"start\",\"schema\":1,\"target_event\":314,\"target_coded\":210}\n");
  }
  if(!p10_j) return;
  if(pbi->max_threads!=1 || pbi->row_mt!=0) p10_fail("thread_mode");
  if(++p10_event>=502) p10_fail("extra_event");
}
void p10_leaf(const AV1_COMMON *cm, DecoderCodingBlock *dcb) {
  if(!p10_target()) return;
  const MACROBLOCKD *xd=&dcb->xd; const MB_MODE_INFO *m=xd->mi[0];
  if(cm->width!=1920 || cm->height!=1080 || cm->width!=cm->superres_upscaled_width || cm->height!=cm->superres_upscaled_height ||
     xd->bd!=10 || is_intrabc_block(m)) {
    fprintf(stderr,"R10 leaf width=%d height=%d upscaled_w=%d upscaled_h=%d superres_enabled=%d denominator=%d bd=%d intrabc=%d\n",cm->width,cm->height,cm->superres_upscaled_width,cm->superres_upscaled_height,cm->seq_params->enable_superres,cm->superres_scale_denominator,xd->bd,is_intrabc_block(m));
    p10_fail("unsupported_leaf");
  }
  const int qbase=m->current_qindex;
  if(qbase!=xd->current_base_qindex) p10_fail("qindex_lifetime");
  const int inter=is_inter_block(m);
  const int q=av1_get_qindex(&cm->seg,m->segment_id,qbase);
  fprintf(p10_j,"{\"kind\":\"leaf\",\"id\":%d,\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"bsize\":%d,\"mode\":%d,\"inter\":%d,\"skip_mode\":%d,\"skip_txfm\":%d,\"segment\":%d,\"refs\":[%d,%d],\"mv\":[[%d,%d],[%d,%d]],\"motion_mode\":%d,\"coded_qindex\":%d,\"qbase\":%d,\"frame_base_q\":%d,\"delta_q_present\":%d,\"decoder_dequant\":[%d,%d],\"qm_level_y\":%d,\"using_qmatrix\":%d}\n",
    ++p10_leafid,xd->mi_col*4,xd->mi_row*4,block_size_wide[m->bsize],block_size_high[m->bsize],m->bsize,m->mode,is_inter_block(m),m->skip_mode,m->skip_txfm,m->segment_id,inter?m->ref_frame[0]:-1,inter?m->ref_frame[1]:-1,inter?m->mv[0].as_mv.row:0,inter?m->mv[0].as_mv.col:0,(inter&&m->ref_frame[1]>0)?m->mv[1].as_mv.row:0,(inter&&m->ref_frame[1]>0)?m->mv[1].as_mv.col:0,inter?m->motion_mode:-1,q,qbase,cm->quant_params.base_qindex,cm->delta_q_info.delta_q_present_flag,xd->plane[0].seg_dequant_QTX[m->segment_id][0],xd->plane[0].seg_dequant_QTX[m->segment_id][1],cm->quant_params.qmatrix_level_y,cm->quant_params.using_qmatrix);
  p10_check();
}
int p10_tu(const AV1_COMMON *cm, DecoderCodingBlock *dcb, int plane, int row, int col, TX_SIZE tx) {
  if(!p10_target() || plane) return -1;
  MACROBLOCKD *xd=&dcb->xd; const MB_MODE_INFO *m=xd->mi[0];
  if(tx<0 || tx>=TX_SIZES_ALL || row<0 || col<0) p10_fail("tu_enum");
  int x=xd->mi_col*4+col*4, y=xd->mi_row*4+row*4;
  if(x<0 || y<0 || x>=cm->width || y>=cm->height || col*4+tx_size_wide[tx]>block_size_wide[m->bsize] || row*4+tx_size_high[tx]>block_size_high[m->bsize]) p10_fail("nominal_tu_bounds");
  int w=AOMMIN(tx_size_wide[tx],cm->width-x), h=AOMMIN(tx_size_high[tx],cm->height-y);
  if(w<=0 || h<=0 || p10_leafid<0) p10_fail("tu_geometry");
  int eob=0,scan=-1,typ=-1,ncoeff=0; uint64_t co=p10_pos,qo=p10_pos; int qn=0;
  /* skip_txfm has no decoded EOB lifetime: never read stale metadata. */
  if(!m->skip_txfm) {
    typ=av1_get_tx_type(xd,PLANE_TYPE_Y,row,col,tx,cm->features.reduced_tx_set_used);
    const eob_info *e=dcb->eob_data[0]+dcb->txb_offset[0]; eob=e->eob;
    if(eob) {
      scan=e->max_scan_line; ncoeff=get_txb_wide(tx)*get_txb_high(tx);
      if(ncoeff<=0 || ncoeff>1024 || scan<0 || scan>=ncoeff || eob>av1_get_max_eob(tx)) p10_fail("coeff_bounds");
      co=p10_bytes(dcb->dqcoeff_block[0]+dcb->cb_offset[0],(size_t)ncoeff*4);
      const qm_val_t *qm=av1_get_iqmatrix(&cm->quant_params,xd,0,tx,typ);
      qo=p10_pos; if(qm) { qn=get_txb_wide(tx)*get_txb_high(tx); p10_bytes(qm,qn*sizeof(*qm)); }
    }
  }
  uint64_t po=p10_surface(xd,row,col,w,h); int id=++p10_tuid;
  fprintf(p10_j,"{\"kind\":\"tu\",\"id\":%d,\"leaf\":%d,\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"tx_size\":%d,\"tx_w\":%d,\"tx_h\":%d,\"tx_type\":%d,\"eob\":%d,\"max_scan\":%d,\"coeff_offset\":%llu,\"coeff_count\":%d,\"coeff_w\":%d,\"coeff_h\":%d,\"iqm_offset\":%llu,\"iqm_count\":%d,\"iqm_state\":%d,\"pred_offset\":%llu,\"sample_count\":%d}\n",id,p10_leafid,x,y,w,h,tx,tx_size_wide[tx],tx_size_high[tx],typ,eob,scan,(unsigned long long)co,ncoeff,get_txb_wide(tx),get_txb_high(tx),(unsigned long long)qo,qn,eob?(qn?1:0):-1,(unsigned long long)po,w*h);
  p10_check(); return id;
}
void p10_after(const AV1_COMMON *cm, DecoderCodingBlock *dcb, int plane, int row, int col, TX_SIZE tx,int id) {
  if(id<0) return;
  if(!p10_target() || plane || id!=p10_tuid) p10_fail("tu_lifetime");
  const MACROBLOCKD *xd=&dcb->xd;
  int w=AOMMIN(tx_size_wide[tx],cm->width-xd->mi_col*4-col*4),h=AOMMIN(tx_size_high[tx],cm->height-xd->mi_row*4-row*4);
  uint64_t o=p10_surface(xd,row,col,w,h);
  fprintf(p10_j,"{\"kind\":\"after\",\"tu\":%d,\"recon_offset\":%llu,\"sample_count\":%d}\n",id,(unsigned long long)o,w*h); p10_check();
}
void p10_inter_skip(const AV1_COMMON *cm, DecoderCodingBlock *dcb) {
  if(!p10_target()) return;
  const MACROBLOCKD *xd=&dcb->xd; const MB_MODE_INFO *m=xd->mi[0];
  if(!m->skip_txfm || !is_inter_block(m)) return;
  int w=AOMMIN(block_size_wide[m->bsize],cm->width-xd->mi_col*4),h=AOMMIN(block_size_high[m->bsize],cm->height-xd->mi_row*4);
  uint64_t po=p10_surface(xd,0,0,w,h);
  fprintf(p10_j,"{\"kind\":\"skip_inter\",\"leaf\":%d,\"pred_recon_offset\":%llu,\"sample_count\":%d}\n",p10_leafid,(unsigned long long)po,w*h);p10_check();
}
void p10_end(AV1Decoder *pbi,const uint8_t *start,const uint8_t *end,const uint8_t *input_end,int decoded) {
  if(!p10_j) return;
  AV1_COMMON *cm=&pbi->common;
  if(decoded!=1 || end<=start || end>input_end || !cm->cur_frame) p10_fail("decode_event");
  if(!cm->show_existing_frame) ++p10_coded;
  uint64_t o=p10_bytes(start,(size_t)(end-start));
  fprintf(p10_j,"{\"kind\":\"event\",\"event\":%d,\"coded_ordinal\":%d,\"show_existing\":%d,\"show_frame\":%d,\"showable\":%d,\"frame_type\":%d,\"order_hint\":%u,\"refresh\":%d,\"bytes_offset\":%llu,\"bytes_count\":%llu}\n",p10_event,p10_coded,cm->show_existing_frame,cm->show_frame,cm->show_existing_frame?-1:cm->showable_frame,cm->show_existing_frame?-1:cm->current_frame.frame_type,cm->current_frame.order_hint,cm->current_frame.refresh_frame_flags,(unsigned long long)o,(unsigned long long)(end-start));
  if(p10_target()) {
    if(p10_coded!=210 || cm->show_existing_frame || cm->show_frame || cm->current_frame.order_hint!=88 || cm->current_frame.refresh_frame_flags!=16) p10_fail("target_metadata");
    const YV12_BUFFER_CONFIG *b=&cm->cur_frame->buf;
    if(!(b->flags&YV12_FLAG_HIGHBITDEPTH) || b->y_crop_width!=1920 || b->y_crop_height!=1080 || b->uv_crop_width!=960 || b->uv_crop_height!=540) p10_fail("post_format");
    uint64_t fo=p10_pos;
    for(int pl=0;pl<3;pl++) {
      const uint16_t *s=CONVERT_TO_SHORTPTR(pl==0?b->y_buffer:pl==1?b->u_buffer:b->v_buffer);
      int w=pl==0?b->y_crop_width:b->uv_crop_width,h=pl==0?b->y_crop_height:b->uv_crop_height,stride=pl==0?b->y_stride:b->uv_stride;
      for(int y=0;y<h;y++) p10_bytes(s+y*stride,(size_t)w*2);
    }
    fprintf(p10_j,"{\"kind\":\"postloop\",\"offset\":%llu,\"bytes\":6220800}\n",(unsigned long long)fo);
  }
  p10_check();
  if(p10_event==501) {
    if(p10_coded!=335 || p10_leafid<0 || p10_tuid<0) p10_fail("incomplete");
    fprintf(p10_j,"{\"kind\":\"end\",\"events\":502,\"coded\":336,\"leaves\":%d,\"tus\":%d,\"payload_bytes\":%llu}\n",p10_leafid+1,p10_tuid+1,(unsigned long long)p10_pos);
    if(fflush(p10_j) || fflush(p10_b)) p10_fail("flush");
  }
}
#endif
