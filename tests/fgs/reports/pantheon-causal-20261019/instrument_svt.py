#!/usr/bin/env python3
"""Apply diagnostic hooks to a pristine SVT4.2 archive in task scratch."""
from pathlib import Path
import re,shutil,sys
root=Path(sys.argv[1]);src=root/'svt-source/Source/Lib/Codec';here=Path(__file__).parent
names=['resource_coordination_process.c','temporal_filtering.c','enc_dec_process.c','dlf_process.c','rest_process.c','entropy_coding.c']
for name in names:
    shutil.copy2(root/'svt-pristine'/name,src/name)
shutil.copy2(here/'pantheon_trace.h',src/'pantheon_trace.h')
def edit(name,old,new):
    p=src/name;b=p.read_bytes();bom=b.startswith(b'\xef\xbb\xbf');t=b.decode('utf-8-sig')
    assert old in t,(name,old)
    p.write_text(t.replace(old,new,1),encoding='utf-8-sig' if bom else 'utf-8')
for name in names:
    t=(src/name).read_text(encoding='utf-8-sig');anchor=re.findall(r'^#include .+$',t,re.M)[-1]
    edit(name,anchor,anchor+'\n#include "pantheon_trace.h"')
edit('resource_coordination_process.c','        if (scs->passes == 2 && !context_ptr->end_of_sequence_flag','        pt_image("original",pcs,pcs->enhanced_pic,0,0,0,1920,1080);\n        if (scs->passes == 2 && !context_ptr->end_of_sequence_flag')
edit('temporal_filtering.c','        // signal that temp filt is done','        pt_image("tf",centre_pcs,central_picture_ptr,0,0,0,1920,1080);\n        // signal that temp filt is done')
edit('enc_dec_process.c','                    // free MD palette info buffer','''                    if(pt_dir(pcs->ppcs->picture_number)) {
                        EbPictureBufferDesc *pr;svt_aom_get_recon_pic(pcs,&pr,ed_ctx->is_16bit);
                        pt_image("pre_sb_dlf",pcs->ppcs,pr,ed_ctx->is_16bit,sb_origin_x,sb_origin_y,scs->sb_size,scs->sb_size);
                        char line[200];snprintf(line,sizeof(line),"%u,%u,%u,%u,%u,%u,%u\\n",sb_ptr->index,sb_ptr->org_x,sb_ptr->org_y,scs->sb_size,sb_ptr->qindex,pcs->ppcs->frm_hdr.quantization_params.base_q_idx,sb_ptr->final_blk_cnt);
                        pt_line(pcs->ppcs,"sb",line);
                    }
                    // free MD palette info buffer''')
edit('dlf_process.c','    //pre-cdef prep','    pt_image("coding_input",ppcs,ppcs->enhanced_pic,0,0,0,1920,1080);\n    //pre-cdef prep')
edit('dlf_process.c','        Av1Common* cm = pcs->ppcs->av1_cm;','        pt_image("post_dlf",ppcs,recon_pic,is_16bit,0,0,1920,1080);\n        Av1Common* cm = pcs->ppcs->av1_cm;')
edit('rest_process.c','        // delete scaled_input_pic after lr finished','''        if(pt_dir(ppcs->picture_number)) {
            EbPictureBufferDesc *pr;svt_aom_get_recon_pic(pcs,&pr,scs->is_16bit_pipeline);
            pt_image("final",ppcs,pr,scs->is_16bit_pipeline,0,0,1920,1080);
        }
        // delete scaled_input_pic after lr finished''')
edit('entropy_coding.c','    const uint8_t skip_mode = mbmi->block_mi.skip_mode;','''    const uint8_t skip_mode = mbmi->block_mi.skip_mode;
    if(pt_dir(pcs->ppcs->picture_number)) {
        char line[200];snprintf(line,sizeof(line),"%u,%u,%u,%u,%u,%u,%u,%u,%u,%d,%d\\n",sb_ptr->index,sb_ptr->org_x,sb_ptr->org_y,blk_org_x,blk_org_y,bwidth,bheight,blk_ptr->qindex,sb_ptr->qindex,skip_coeff,skip_mode);
        pt_line(pcs->ppcs,"blocks",line);
    }
''')
edit('entropy_coding.c','static int32_t av1_write_coeffs_txb_1d(','''static __thread unsigned pt_blk_x,pt_blk_y,pt_sb_index;
static int32_t av1_write_coeffs_txb_1d(''')
edit('entropy_coding.c','    const uint8_t skip_mode = mbmi->block_mi.skip_mode;','''    const uint8_t skip_mode = mbmi->block_mi.skip_mode;
    pt_blk_x=blk_org_x;pt_blk_y=blk_org_y;pt_sb_index=sb_ptr->index;''')
edit('entropy_coding.c','    assert(txs_ctx < TX_SIZES);','''    if(pt_dir(ppcs->picture_number) && component_type==COMPONENT_LUMA) {
        const int16_t *scan=get_scan_order(tx_size,tx_type)->scan;
        unsigned nz=0;long long mag=0;
        for(int k=0;k<eob;k++){int v=coeff_buffer_ptr[scan[k]];nz+=(v!=0);mag+=llabs(v);}
        int inter=is_inter_mode(mbmi->block_mi.mode)||mbmi->block_mi.use_intrabc;
        Position org=tx_org[mbmi->bsize][inter][mbmi->block_mi.tx_depth][txb_index];
        char line[240];snprintf(line,sizeof(line),"%u,%u,%d,%d,%u,%d,%u,%lld,%u\\n",pt_blk_x+org.x,pt_blk_y+org.y,tx_size_wide[tx_size],tx_size_high[tx_size],blk_ptr->qindex,eob,nz,mag,pt_sb_index);
        pt_line(ppcs,"luma_txs",line);
    }
    assert(txs_ctx < TX_SIZES);''')
