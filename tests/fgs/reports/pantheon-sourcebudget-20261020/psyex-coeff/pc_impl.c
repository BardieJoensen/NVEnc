/* R11 private observer. Included by pb_trace.c; never modifies encoder data. */
#include "enc_dec_process.h"
#include "full_loop.h"
#include "coefficients.h"
#include <stdarg.h>
#define PC_MAGIC UINT64_C(0x314346504e5450)
static pthread_once_t pc_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t pc_lock = PTHREAD_MUTEX_INITIALIZER;
static int pc_fd = -1;
static uint64_t pc_bytes, pc_seq, pc_token, pc_started, pc_ended;
static unsigned pc_gen, pc_accepted, pc_routes;
static unsigned char pc_seen[510];
typedef struct {
    uint64_t token;
    const BlkStruct *block;
    unsigned sb,offset,x,y,w,h,tu,n,eob,typ,done,committed;
    int32_t *q;
} PcOwner;
static PcOwner pc_owners[20000];
static unsigned pc_owner_count, pc_owner_map[510][256], pc_commit_offset[510], pc_committed;
typedef struct {
    int live, raw, info, final;
    uint64_t token;
    unsigned gen, x,y,w,h,n,tx,typ,skip,stages;
    PictureControlSet *pcs;
    EncDecContext *ed;
    const int32_t *raw_ptr;
    PcOwner *owner;
    DECLARE_ALIGNED(32, uint16_t, src[4096]);
    DECLARE_ALIGNED(32, uint16_t, pred[4096]);
    DECLARE_ALIGNED(32, uint16_t, inv[4096]);
    DECLARE_ALIGNED(32, int32_t, work[4096]);
} PcLocal;
static _Thread_local PcLocal pc;
static void pc_init(void) {
    const char *s=getenv("SVT_PANTHEON_COEFF_FD");
    if(!s) return;
    REQUIRE(active()); /* generation and final-output authority is R9 observer */
    char *end; errno=0; long n=strtol(s,&end,10);
    REQUIRE(!errno && *s && !*end && n>=3 && n<1048576 && n!=fd);
    struct stat st; int flags=fcntl((int)n,F_GETFL);
    REQUIRE(flags>=0 && (flags&O_APPEND) && (flags&O_ACCMODE)!=O_RDONLY);
    REQUIRE(!fstat((int)n,&st) && S_ISREG(st.st_mode) && !st.st_size);
    struct stat bt; REQUIRE(!fstat(fd,&bt));
    REQUIRE(st.st_dev!=bt.st_dev || st.st_ino!=bt.st_ino);
    pc_fd=fcntl((int)n,F_DUPFD_CLOEXEC,3); REQUIRE(pc_fd>=3);
}
static int pc_active(void) { REQUIRE(!pthread_once(&pc_once,pc_init)); return pc_fd>=0; }
static void pc_write(const void *v,size_t n) {
    REQUIRE(pc_bytes+n<=UINT64_C(1024)*1024*1024);
    const unsigned char *p=v;
    while(n) { ssize_t z=write(pc_fd,p,n); if(z<0 && errno==EINTR)continue;
        REQUIRE(z>0); p+=z;n-=z;pc_bytes+=z; }
}
static void pc_header(unsigned kind,uint64_t len,const char *format,...) {
    char meta[8192]; va_list ap; va_start(ap,format);
    int n=vsnprintf(meta,sizeof(meta),format,ap); va_end(ap);
    REQUIRE(n>0 && (size_t)n<sizeof(meta));
    uint64_t h[8]={PC_MAGIC,1,kind,pc_gen,216,pc_seq++,(uint64_t)n,len};
    pc_write(h,sizeof(h));pc_write(meta,n);
}
static void pc_copy(uint16_t *dst,const uint16_t *src,unsigned stride,unsigned w,unsigned h) {
    REQUIRE(src && stride>=w && w*h<=4096);
    for(unsigned y=0;y<h;++y) {
        for(unsigned x=0;x<w;++x) REQUIRE(src[y*stride+x]<=1023);
        memcpy(dst+y*w,src+y*stride,w*2);
    }
}
static int pc_intersects(unsigned x,unsigned y,unsigned w,unsigned h) {
    const unsigned rois[3][4]={{1200,650,200,100},{950,50,250,180},{160,600,500,480}};
    for(unsigned i=0;i<3;++i) {
        const unsigned *r=rois[i];
        if(x<r[0]+r[2] && x+w>r[0] && y<r[1]+r[3] && y+h>r[1])return 1;
    }
    return 0;
}
void pc_route(PictureControlSet *pcs,void *ctx,unsigned sb,unsigned x,unsigned y) {
    if(pcs->ppcs->picture_number!=216 || !pc_active())return;
    EncDecContext *ed=ctx;
    REQUIRE(!pthread_mutex_lock(&pc_lock));
    REQUIRE(!pc_accepted && pcs->enc_mode==4 && pcs->ppcs->enc_mode==4 && pcs->scs->static_config.enc_mode==4);
    REQUIRE(pcs->scs->static_config.encoder_bit_depth==10 && !pcs->pic_bypass_encdec && !ed->md_ctx->bypass_encdec);
    REQUIRE(pcs->scs->sb_size==64 && sb<510 && !pc_seen[sb]);
    REQUIRE(x==(sb%30)*64 && y==(sb/30)*64);
    pc_seen[sb]=1;++pc_routes;
    pc_header(10,0,"{\"sb\":%u,\"x\":%u,\"y\":%u,\"effective_mode\":%u,\"parent_mode\":%u,\"configured_mode\":%u,\"depth\":10,\"picture_bypass\":0,\"md_bypass\":0,\"fixed_partition\":%u,\"decode_order\":%" PRIu64 ",\"ctx\":%" PRIuPTR "}",
        sb,x,y,pcs->enc_mode,pcs->ppcs->enc_mode,pcs->scs->static_config.enc_mode,ed->md_ctx->fixed_partition,(uint64_t)pcs->ppcs->decode_order,(uintptr_t)ed);
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
void pc_begin(PictureControlSet *pcs,void *ctx,unsigned x,unsigned y,
              EbPictureBufferDesc *source,unsigned source_offset,
              EbPictureBufferDesc *pred,unsigned pred_offset) {
    if(pcs->ppcs->picture_number!=216 || !pc_active())return;
    EncDecContext *ed=ctx; const BlockGeom *g=ed->blk_geom; BlkStruct *b=ed->blk_ptr;
    unsigned w=g->tx_width[b->tx_depth],h=g->tx_height[b->tx_depth];
    REQUIRE(!pc.live);
    if(!pc_intersects(x,y,w,h))return;
    REQUIRE(ed->is_16bit && ed->bit_depth==10 && w && h && w<=64 && h<=64 && x+w<=1920 && y<1080 && y+h<=1088);
    REQUIRE((uint64_t)source_offset+(h-1)*source->stride_y+w<=source->luma_size);
    REQUIRE((uint64_t)pred_offset+(h-1)*pred->stride_y+w<=pred->luma_size);
    memset(&pc,0,sizeof(pc));pc.live=1;pc.pcs=pcs;pc.ed=ed;pc.x=x;pc.y=y;pc.w=w;pc.h=h;
    pc.tx=g->txsize[b->tx_depth];pc.typ=b->tx_type[ed->txb_itr];pc.skip=ed->md_skip_blk || b->skip_mode;
    pc.n=av1_get_max_eob(pc.tx); REQUIRE(pc.n<=1024 && pc.n==(w>32?32:w)*(h>32?32:h));
    pc_copy(pc.src,(uint16_t*)source->buffer_y+source_offset,source->stride_y,w,h);
    pc_copy(pc.pred,(uint16_t*)pred->buffer_y+pred_offset,pred->stride_y,w,h);
    REQUIRE(!pthread_mutex_lock(&pc_lock));
    unsigned sb=(y/64)*30+x/64; REQUIRE(!pc_accepted && pc_seen[sb]);
    pc.gen=pc_gen;pc.token=++pc_token;++pc_started;
    REQUIRE(pc_owner_count<20000 && ed->coded_area_sb<4096 && !(ed->coded_area_sb%16));
    REQUIRE(!pc_owner_map[sb][ed->coded_area_sb/16]);
    PcOwner *o=&pc_owners[pc_owner_count++];
    *o=(PcOwner){.token=pc.token,.block=b,.sb=sb,.offset=ed->coded_area_sb,.x=x,.y=y,.w=w,.h=h,.tu=ed->txb_itr,.n=pc.n};
    pc_owner_map[sb][ed->coded_area_sb/16]=pc_owner_count;pc.owner=o;
    pc_header(11,4*w*h,"{\"token\":%" PRIu64 ",\"sb\":%u,\"x\":%u,\"y\":%u,\"w\":%u,\"h\":%u,\"visible_w\":%u,\"visible_h\":%u,\"n\":%u,\"tx\":%u,\"type\":%u,\"block_x\":%u,\"block_y\":%u,\"block_w\":%u,\"block_h\":%u,\"tx_depth\":%u,\"tu_index\":%u,\"coeff_offset\":%u,\"md_skip\":%u,\"skip_mode\":%u,\"qindex\":%u,\"segment\":%u,\"pred_mode\":%u,\"mds_idx\":%u,\"ctx\":%" PRIuPTR "}",
        pc.token,sb,x,y,w,h,w,y+h>1080?1080-y:h,pc.n,pc.tx,pc.typ,ed->blk_org_x,ed->blk_org_y,g->bwidth,g->bheight,b->tx_depth,ed->txb_itr,ed->coded_area_sb,ed->md_skip_blk,b->skip_mode,b->qindex,b->segment_id,b->pred_mode,b->mds_idx,(uintptr_t)ed);
    pc_write(pc.src,2*w*h);pc_write(pc.pred,2*w*h);
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
void pc_skip(PictureControlSet *pcs,void *ctx,unsigned x,unsigned y,EbPictureBufferDesc *pred) {
    if(pcs->ppcs->picture_number!=216 || !pc_active())return;
    EncDecContext *ed=ctx;const BlockGeom *g=ed->blk_geom;BlkStruct *b=ed->blk_ptr;
    REQUIRE(b->skip_mode && ed->is_16bit);
    unsigned ix=g->tx_org_x[1][b->tx_depth][ed->txb_itr];
    unsigned iy=g->tx_org_y[1][b->tx_depth][ed->txb_itr];
    pc_begin(pcs,ctx,x,y,ed->input_sample16bit_buffer,ix+iy*SB_STRIDE_Y,pred,
        (pred->org_y+y)*pred->stride_y+pred->org_x+x);
}
/* Run on copies, with native inverse kernel and original native predictor.
   eob=0 explicitly copies prediction; no stale coefficient reads. */
static void pc_inverse(const int32_t *coeff,unsigned eob) {
    REQUIRE(pc.live && eob<=pc.n);
    memcpy(pc.inv,pc.pred,2*pc.w*pc.h);
    memset(pc.work,0,sizeof(pc.work));memcpy(pc.work,coeff,4*pc.n);
    REQUIRE(!svt_av1_is_lossless_segment(pc.pcs,pc.ed->blk_ptr->segment_id));
    if(eob) svt_aom_inv_transform_recon_wrapper(pc.pcs,pc.ed->md_ctx,(uint8_t*)pc.pred,0,pc.w,
        (uint8_t*)pc.inv,0,pc.w,pc.work,0,1,pc.tx,pc.typ,PLANE_TYPE_Y,eob);
}
void pc_raw(PictureControlSet *pcs,void *ctx,const int16_t *res,unsigned stride,const int32_t *raw) {
    if(!pc.live)return;
    REQUIRE(pc.pcs==pcs && pc.ed==ctx && !pc.skip && !pc.raw && stride>=pc.w);
    int16_t residual[4096];
    for(unsigned y=0;y<pc.h;++y)for(unsigned x=0;x<pc.w;++x){
        unsigned i=y*pc.w+x;residual[i]=res[y*stride+x];
        REQUIRE(residual[i]==(int)pc.src[i]-(int)pc.pred[i]);
    }
    const int16_t *scan=av1_scan_orders[pc.tx][pc.typ].scan;
    unsigned eob=0;for(unsigned i=0;i<pc.n;++i)if(raw[scan[i]])eob=i+1;
    pc_inverse(raw,eob);pc.raw=1;pc.raw_ptr=raw;
    REQUIRE(!pthread_mutex_lock(&pc_lock));REQUIRE(pc.gen==pc_gen);
    pc_header(12,4*pc.w*pc.h+4*pc.n,"{\"token\":%" PRIu64 ",\"raw_eob\":%u}",pc.token,eob);
    pc_write(residual,2*pc.w*pc.h);pc_write(raw,4*pc.n);pc_write(pc.inv,2*pc.w*pc.h);
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
int pc_qinfo(PictureControlSet *pcs,void *md,const int32_t *raw,unsigned requested,int actual,int seg,
             unsigned tx,unsigned typ,unsigned depth,unsigned lambda,int skipctx,int dcctx,
             int rdoq,int qmlevel,const void *mp,const void *qp) {
    if(!pc.live)return 0;
    REQUIRE(pc.pcs==pcs && pc.ed->md_ctx==md && pc.raw && !pc.info && raw==pc.raw_ptr);
    REQUIRE(tx==pc.tx && typ==pc.typ && depth==10 && actual>=0 && actual<=255);
    const MacroblockPlane *m=mp;const QuantParam *q=qp;ModeDecisionContext *c=md;
    REQUIRE(q->tx_size==pc.tx);
    const int16_t *tables[7]={m->quant_fp_qtx,m->round_fp_qtx,m->quant_qtx,m->quant_shift_qtx,m->zbin_qtx,m->round_qtx,m->dequant_qtx};
    unsigned qn=q->qmatrix?pc.n:0,in=q->iqmatrix?pc.n:0;
    REQUIRE(!pthread_mutex_lock(&pc_lock));REQUIRE(pc.gen==pc_gen);
    pc_header(13,112+4*pc.n+qn+in,
        "{\"token\":%" PRIu64 ",\"requested_qindex\":%u,\"actual_qindex\":%d,\"seg_delta\":%d,\"depth\":%u,\"lambda\":%u,\"txb_skip_context\":%d,\"dc_sign_context\":%d,\"initial_rdoq\":%d,\"fp_y\":%u,\"rdoq_level\":%u,\"satd_factor\":%u,\"eob_th\":%u,\"eob_fast_th\":%u,\"log_scale\":%d,\"qm_level\":%d,\"qm_count\":%u,\"iqm_count\":%u,\"tables\":[\"quant_fp\",\"round_fp\",\"quant\",\"quant_shift\",\"zbin\",\"round\",\"dequant\"],\"table_entries\":8,\"scan_count\":%u,\"iscan_count\":%u}",
        pc.token,requested,actual,seg,depth,lambda,skipctx,dcctx,rdoq,c->rdoq_ctrls.fp_q_y,c->rdoq_level,c->rdoq_ctrls.satd_factor,c->rdoq_ctrls.eob_th,c->rdoq_ctrls.eob_fast_th,q->log_scale,qmlevel,qn,in,pc.n,pc.n);
    for(unsigned i=0;i<7;++i){REQUIRE(tables[i]);pc_write(tables[i],16);}
    pc_write(av1_scan_orders[tx][typ].scan,2*pc.n);pc_write(av1_scan_orders[tx][typ].iscan,2*pc.n);
    if(qn)pc_write(q->qmatrix,qn);
    if(in)pc_write(q->iqmatrix,in);
    REQUIRE(!pthread_mutex_unlock(&pc_lock));pc.info=1;return 1;
}
void pc_stage(const char *stage,const int32_t *q,const int32_t *dq,unsigned eob,int rdoq) {
    REQUIRE(pc.live && pc.info && !pc.final);
    pc_inverse(dq,eob);
    REQUIRE(!pthread_mutex_lock(&pc_lock));REQUIRE(pc.gen==pc_gen);
    pc_header(14,8*pc.n+2*pc.w*pc.h,"{\"token\":%" PRIu64 ",\"stage\":\"%s\",\"ordinal\":%u,\"eob\":%u,\"rdoq\":%d}",
        pc.token,stage,pc.stages++,eob,rdoq);
    pc_write(q,4*pc.n);pc_write(dq,4*pc.n);pc_write(pc.inv,2*pc.w*pc.h);
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
    if(!strcmp(stage,"final")){
        pc.final=1;pc.owner->q=malloc(4*pc.n);REQUIRE(pc.owner->q);
        memcpy(pc.owner->q,q,4*pc.n);
    }
}
void pc_end(PictureControlSet *pcs,void *ctx,unsigned x,unsigned y,EbPictureBufferDesc *recon,unsigned eob) {
    if(!pc.live)return;
    REQUIRE(pc.pcs==pcs && pc.ed==ctx && pc.x==x && pc.y==y);
    REQUIRE((pc.skip && !pc.raw && !pc.info && !pc.final && !eob) || (!pc.skip && pc.raw && pc.info && pc.final));
    uint16_t samples[4096];unsigned offset=(recon->org_y+y)*recon->stride_y+recon->org_x+x;
    REQUIRE((uint64_t)offset+(pc.h-1)*recon->stride_y+pc.w<=recon->luma_size);
    pc_copy(samples,(uint16_t*)recon->buffer_y+offset,recon->stride_y,pc.w,pc.h);
    /* Only final EOB-positive units promise inverse use; skipped units predict. */
    REQUIRE(!memcmp(samples,pc.skip?pc.pred:pc.inv,2*pc.w*pc.h));
    REQUIRE(!pthread_mutex_lock(&pc_lock));REQUIRE(pc.gen==pc_gen);
    pc_header(15,2*pc.w*pc.h,"{\"token\":%" PRIu64 ",\"eob\":%u,\"type\":%u,\"has_coeff\":%u,\"skip_mode\":%u,\"stage_count\":%u}",
        pc.token,eob,pc.ed->blk_ptr->tx_type[pc.ed->txb_itr],(pc.ed->blk_ptr->y_has_coeff>>pc.ed->txb_itr)&1,pc.ed->blk_ptr->skip_mode,pc.stages);
    pc_write(samples,2*pc.w*pc.h);++pc_ended;pc.live=0;
    pc.owner->eob=eob;pc.owner->typ=pc.ed->blk_ptr->tx_type[pc.ed->txb_itr];pc.owner->done=1;
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
void pc_commit(PictureControlSet *pcs,void *ctx,unsigned sb,unsigned ordinal,const void *dest) {
    if(pcs->ppcs->picture_number!=216 || !pc_active())return;
    EncDecContext *ed=ctx;const BlockGeom *g=ed->blk_geom;BlkStruct *b=ed->blk_ptr;
    const EcBlkStruct *d=dest;
    REQUIRE(d->mds_idx==b->mds_idx && d->qindex==b->qindex && !memcmp(&d->eob,&b->eob,sizeof(b->eob)) &&
            !memcmp(d->tx_type,b->tx_type,sizeof(b->tx_type)));
    REQUIRE(!pthread_mutex_lock(&pc_lock));
    REQUIRE(sb<510 && pc_seen[sb] && !pc_accepted && !ed->md_ctx->bypass_encdec);
    unsigned off=pc_commit_offset[sb],w=g->tx_width[b->tx_depth],h=g->tx_height[b->tx_depth];
    EbPictureBufferDesc *qb=pcs->ppcs->enc_dec_ptr->quantized_coeff[sb];
    for(unsigned t=0;t<g->txb_count[b->tx_depth];++t) {
        REQUIRE(off<4096 && !(off%16) && off+w*h<=4096);
        unsigned id=pc_owner_map[sb][off/16];
        if(id) {
            PcOwner *o=&pc_owners[id-1];
            REQUIRE(o->block==b && o->tu==t && o->done && !o->committed && o->w==w && o->h==h && o->offset==off);
            REQUIRE(o->eob==(b->skip_mode?0:b->eob.y[t]) && o->typ==b->tx_type[t]);
            if(o->eob) {
                REQUIRE(o->q && b->block_has_coeff && ((b->y_has_coeff>>t)&1) && !b->skip_mode);
                REQUIRE(!memcmp(o->q,(int32_t*)qb->buffer_y+off,4*o->n));
            }
            pc_header(18,0,"{\"token\":%" PRIu64 ",\"sb\":%u,\"committed_ordinal\":%u,\"tu_index\":%u,\"coeff_offset\":%u,\"eob\":%u,\"type\":%u,\"source_block_has_coeff\":%u,\"source_skip_mode\":%u,\"qindex\":%u,\"mds_idx\":%u,\"block_ptr\":%" PRIuPTR "}",
                o->token,sb,ordinal,t,off,o->eob,o->typ,b->block_has_coeff,b->skip_mode,d->qindex,d->mds_idx,(uintptr_t)b);
            o->committed=1;++pc_committed;free(o->q);o->q=NULL;
        }
        off+=w*h;
    }
    pc_commit_offset[sb]=off;
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
static void pc_attempt(int recode) {
    if(!pc_active())return;
    REQUIRE(!pthread_mutex_lock(&pc_lock));
    REQUIRE(!pc_accepted && pc_routes==510 && pc_started==pc_ended && pc_started==pc_committed && pc_started>0);
    for(unsigned i=0;i<510;++i)REQUIRE(pc_seen[i]);
    pc_header(16,0,"{\"recode\":%d,\"routes\":%u,\"started\":%" PRIu64 ",\"ended\":%" PRIu64 "}",recode,pc_routes,pc_started,pc_ended);
    if(recode){
        ++pc_gen;pc_routes=0;pc_started=pc_ended=pc_committed=pc_owner_count=0;
        memset(pc_seen,0,sizeof(pc_seen));memset(pc_owner_map,0,sizeof(pc_owner_map));
        memset(pc_commit_offset,0,sizeof(pc_commit_offset));
    }
    else pc_accepted=1;
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
static void pc_finish(void) {
    if(!pc_active())return;
    REQUIRE(!pthread_mutex_lock(&pc_lock));
    REQUIRE(pc_accepted && pc_gen==generation && pc_started==pc_ended && pc_routes==510);
    pc_header(17,0,"{\"status\":\"complete\",\"accepted_generation\":%u,\"started\":%" PRIu64 ",\"ended\":%" PRIu64 "}",pc_gen,pc_started,pc_ended);
    REQUIRE(!fsync(pc_fd));REQUIRE(!close(pc_fd));pc_fd=-1;
    REQUIRE(!pthread_mutex_unlock(&pc_lock));
}
