/* Scratch-only two-pass qindex map intervention. Disabled unless env is set.
 * Map is 336 frames x 510 raster 64x64 superblocks, signed 8-bit qindex deltas.
 * It is derived from full-window source/reconstruction evidence, not ROI labels.
 */
#ifndef PANTHEON_ALLOC_H
#define PANTHEON_ALLOC_H
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "pcs.h"
#include "sequence_control_set.h"
static void pt_adjust_q(PictureControlSet *pcs) {
    const char *path=getenv("PANTHEON_ALLOCATION_MAP");if(!path)return;
    if(pcs->ppcs->picture_number>=336 || pcs->scs->sb_size!=64 || pcs->sb_total_count!=510)abort();
    FILE *f=fopen(path,"rb");if(!f)abort();
    if(fseek(f,pcs->ppcs->picture_number*510,SEEK_SET))abort();
    int8_t map[510];if(fread(map,1,510,f)!=510)abort();fclose(f);
    int changed=0;
    for(int i=0;i<510;i++){
        SuperBlock *sb=pcs->sb_ptr_array[i];int q=sb->qindex+map[i];
        if(q<1)q=1;if(q>255)q=255;
        changed|=q!=sb->qindex;sb->qindex=q;
    }
    if(changed)pcs->ppcs->frm_hdr.delta_q_params.delta_q_present=1;
}
#endif
