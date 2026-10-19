#!/usr/bin/env python3
"""One optimistic diagnostic ROI allocation: absolute qindex16, whole fixture.
E05 budget runner ALSO imposes a global max-transform32 cap; its measured
budget result is a combined intervention, not an allocation-only ablation.

This deliberately hand-specified ROI is NOT a deployable texture classifier.
It tests budget feasibility on the known target while exposing whole-window cost.
"""
import sys,pathlib
import numpy as np
from study import ROOT,x
from texture import BOXES
if sys.argv[1]=='patch':
 p=ROOT/'svt-source/Source/Lib/Codec/pantheon_alloc.h';s=p.read_text();needle='    const char *path=getenv("PANTHEON_ALLOCATION_MAP");if(!path)return;'
 assert s.count(needle)==1
 block='''    const char *absolute=getenv("PANTHEON_ABSOLUTE_Q_MAP");
    if(absolute){
        if(pcs->ppcs->picture_number>=336 || pcs->scs->sb_size!=64 || pcs->sb_total_count!=510)abort();
        FILE *f=fopen(absolute,"rb");if(!f)abort();
        if(fseek(f,pcs->ppcs->picture_number*510*2,SEEK_SET))abort();
        int16_t map[510];if(fread(map,2,510,f)!=510)abort();fclose(f);
        int changed=0;
        for(int i=0;i<510;i++)if(map[i]>=0){
            if(map[i]<1||map[i]>255)abort();
            changed=1;pcs->sb_ptr_array[i]->qindex=map[i];
        }
        if(changed){pcs->ppcs->frm_hdr.delta_q_params.delta_q_present=1;pcs->ppcs->frm_hdr.delta_q_params.delta_q_res=1;}
        return;
    }
'''
 p.write_text(s.replace(needle,block+needle))
else:
 case=sys.argv[1];d=ROOT/case;xx,yy,w,h=next(iter(BOXES[case].values()));a=np.full((336,17,30),-1,dtype='<i2')
 a[:,yy//64:(yy+h+63)//64,xx//64:(xx+w+63)//64]=16;a.tofile(d/'absolute-map.bin')
 x.dump(d/'absolute-map.json',{'shape':list(a.shape),'dtype':'little-endian int16','keep_value':-1,'absolute_target_qindex':16,'scored_roi_xywh':[xx,yy,w,h],'aligned_roi_xywh':[xx//64*64,yy//64*64,((xx+w+63)//64-xx//64)*64,((yy+h+63)//64-yy//64)*64],'all336_frames':True,'selected_sb_fraction':float((a>=0).mean()),'production_classifier':False,'delta_q_res':1})
