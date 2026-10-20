/* R12 scratch-only wrappers around the pinned R11 native C kernels. */
#include "aom_dsp_rtcd.h"
#include "inv_transforms.h"
#include "pcs.h"
#include "transforms.h"
#include <stdint.h>
#include <string.h>
#define PUBLIC __attribute__((visibility("default")))
void svt_av1_highbd_quantize_fp_facade(const TranLow *, intptr_t, const MacroblockPlane *,
                                      TranLow *, TranLow *, uint16_t *, const ScanOrder *, const QuantParam *);
void svt_av1_highbd_quantize_b_facade(const TranLow *, intptr_t, const MacroblockPlane *,
                                     TranLow *, TranLow *, uint16_t *, const ScanOrder *, const QuantParam *);
static int initialized;
PUBLIC uint64_t rp_init(void) {
    EbCpuFlags flags=svt_aom_get_cpu_flags_to_use();
    svt_aom_setup_common_rtcd_internal(flags);
    svt_aom_setup_rtcd_internal(flags);
    initialized=1;
    return (uint64_t)flags;
}

/* These are exactly the three FP rows initialized at md_config_process.c:134-143.
   B-only sharpness/zbin/round/shift inputs remain the captured native rows. */
PUBLIC int rp_fp_tables(int qindex, int y_dc_delta, int16_t *out) {
    if (!out || qindex < 1 || qindex > 255 || y_dc_delta < -255 || y_dc_delta > 255)
        return -1;
    for (int i = 0; i < 8; ++i) {
        int d = i == 0 ? svt_aom_dc_quant_qtx(qindex, y_dc_delta, EB_TEN_BIT)
                       : svt_aom_ac_quant_qtx(qindex, 0, EB_TEN_BIT);
        if (d <= 0) return -2;
        out[i] = (int16_t)((1 << 16) / d);
        out[8+i] = (int16_t)((64 * d) >> 7);
        out[16+i] = (int16_t)d;
    }
    return 0;
}

/* tables order: quant_fp, round_fp, quant, quant_shift, zbin, round, dequant.
   Native FP ignores zbin/quant_shift/iscan; native B uses its captured rows. */
PUBLIC int rp_quant(int mode, int tx, const int32_t *raw, int n, const int16_t *tables,
                    const int16_t *scan, const int16_t *iscan,
                    const uint8_t *qm, const uint8_t *iqm, int log_scale,
                    int32_t *q, int32_t *dq, uint16_t *eob) {
    if (!initialized || mode < 0 || mode > 3 || !raw || !tables || !scan || !iscan || !q || !dq || !eob ||
        tx < 0 || tx >= TX_SIZES_ALL || n != av1_get_max_eob(tx) ||
        n <= 0 || n > 1024 || log_scale < 0 || log_scale > 2 || (!!qm != !!iqm))
        return -1;
    for (int i = 0; i < n; ++i)
        if (scan[i] < 0 || scan[i] >= n || iscan[scan[i]] != i) return -2;
    DECLARE_ALIGNED(32,int32_t,raw_copy[1024]);
    DECLARE_ALIGNED(32,int32_t,q_copy[1024]);
    DECLARE_ALIGNED(32,int32_t,dq_copy[1024]);
    DECLARE_ALIGNED(32,int16_t,table_copy[56]);
    DECLARE_ALIGNED(32,int16_t,scan_copy[1024]);
    DECLARE_ALIGNED(32,int16_t,iscan_copy[1024]);
    DECLARE_ALIGNED(32,uint8_t,qm_copy[1024]);
    DECLARE_ALIGNED(32,uint8_t,iqm_copy[1024]);
    memcpy(raw_copy,raw,4*n);memcpy(table_copy,tables,112);
    memcpy(scan_copy,scan,2*n);memcpy(iscan_copy,iscan,2*n);
    if(qm){memcpy(qm_copy,qm,n);memcpy(iqm_copy,iqm,n);}
    const QmVal *m=qm?qm_copy:NULL,*im=iqm?iqm_copy:NULL;
    const int16_t *tb=table_copy;
    if (mode >= 2) {
        MacroblockPlane plane={.quant_fp_qtx=tb,.round_fp_qtx=tb+8,.quant_qtx=tb+16,
            .quant_shift_qtx=tb+24,.zbin_qtx=tb+32,.round_qtx=tb+40,.dequant_qtx=tb+48};
        ScanOrder order={.scan=scan_copy,.iscan=iscan_copy};
        QuantParam param={.log_scale=log_scale,.tx_size=tx,.qmatrix=m,.iqmatrix=im};
        if(mode==2)svt_av1_highbd_quantize_fp_facade(raw_copy,n,&plane,q_copy,dq_copy,eob,&order,&param);
        else svt_av1_highbd_quantize_b_facade(raw_copy,n,&plane,q_copy,dq_copy,eob,&order,&param);
    } else if (mode == 0) {
        svt_av1_highbd_quantize_fp_qm_c(raw_copy,n,tb+32,tb+8,tb,tb+24,
                                       q_copy,dq_copy,tb+48,eob,scan_copy,iscan_copy,m,im,log_scale);
    } else {
        svt_aom_highbd_quantize_b_c(raw_copy,n,tb+32,tb+40,tb+16,tb+24,
                                   q_copy,dq_copy,tb+48,eob,scan_copy,iscan_copy,m,im,log_scale);
    }
    if(memcmp(raw_copy,raw,4*n)||memcmp(table_copy,tables,112)||
       memcmp(scan_copy,scan,2*n)||memcmp(iscan_copy,iscan,2*n)||
       (qm&&(memcmp(qm_copy,qm,n)||memcmp(iqm_copy,iqm,n))))return -4;
    memcpy(q,q_copy,4*n);memcpy(dq,dq_copy,4*n);
    return *eob <= n ? 0 : -3;
}

PUBLIC int rp_inverse(int dispatch, int tx, int typ, int w, int h, int n, int eob,
                      const int32_t *dq, const uint16_t *pred, uint16_t *out) {
    if (!initialized || (dispatch!=0 && dispatch!=1) || !dq || !pred || !out || tx < 0 || tx >= TX_SIZES_ALL ||
        typ < 0 || typ >= TX_TYPES || w != tx_size_wide[tx] || h != tx_size_high[tx] ||
        n != av1_get_max_eob(tx) || n > 1024 || eob < 0 || eob > n || w*h > 4096)
        return -1;
    for (int i = 0; i < w*h; ++i) if (pred[i] > 1023) return -2;
    /* Lossless is deliberately unsupported. All admitted R11 units are nonlossless. */
    if (tx >= TX_32X32 && tx <= TX_64X64 && typ != DCT_DCT) return -3;
    memcpy(out, pred, 2*w*h);
    if (!eob) return 0;
    DECLARE_ALIGNED(32,uint16_t,private_pred[4096]);
    DECLARE_ALIGNED(32,uint16_t,private_out[4096]);
    DECLARE_ALIGNED(32,int32_t,private_dq[4096]);
    memcpy(private_pred, pred, 2*w*h);
    memcpy(private_out, pred, 2*w*h);
    memset(private_dq,0,sizeof(private_dq));memcpy(private_dq,dq,4*n);
    if(dispatch){
        if(svt_aom_inv_transform_recon(private_dq,CONVERT_TO_BYTEPTR(private_pred),w,
            CONVERT_TO_BYTEPTR(private_out),w,tx,10,typ,PLANE_TYPE_Y,eob,0)!=EB_ErrorNone)return -7;
    } else {
#define SQUARE(N) case TX_##N##X##N: \
    svt_av1_inv_txfm2d_add_##N##x##N##_c(private_dq,private_pred,w,private_out,w,typ,10); break
#define RECT(W,H) case TX_##W##X##H: \
    svt_av1_inv_txfm2d_add_##W##x##H##_c(private_dq,private_pred,w,private_out,w,typ,tx,eob,10); break
    switch (tx) {
        SQUARE(8); SQUARE(16); SQUARE(32); SQUARE(64);
        RECT(8,16); RECT(16,8); RECT(16,32); RECT(32,16);
        default: return -4;
    }
#undef SQUARE
#undef RECT
    }
    if (memcmp(private_pred,pred,2*w*h)||memcmp(private_dq,dq,4*n)) return -5;
    memcpy(out,private_out,2*w*h);
    for (int i = 0; i < w*h; ++i) if (out[i] > 1023) return -6;
    return 0;
}
