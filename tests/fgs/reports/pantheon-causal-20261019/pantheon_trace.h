/* Scratch-only SVT 4.2 diagnostic hooks. No codec decisions are changed.
 * Files contain 1920x1080 planar 10-bit little-endian values, keyed by
 * display picture_number and alt-ref/overlay flags. SB writes do not overlap.
 */
#ifndef PANTHEON_TRACE_H
#define PANTHEON_TRACE_H
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include "pcs.h"
#include "pic_buffer_desc.h"
static const char *pt_dir(uint64_t n) {
    const char *d=getenv("PANTHEON_TRACE_DIR");
    return d && n>=96 && n<336 ? d : NULL;
}
static void pt_image(const char *stage, PictureParentControlSet *ppcs,
                     EbPictureBufferDesc *p,int packed,int x,int y,int w,int h) {
    const char *dir=pt_dir(ppcs->picture_number);if(!dir)return;
    if(getenv("PANTHEON_TRACE_IMAGES_OFF"))return;
    char path[1024];snprintf(path,sizeof(path),"%s/%s-%04llu-a%d-o%d.yuv",dir,stage,
        (unsigned long long)ppcs->picture_number,ppcs->is_alt_ref,ppcs->is_overlay);
    int fd=open(path,O_CREAT|O_WRONLY,0664);if(fd<0)abort();
    if(ftruncate(fd,1920LL*1080*3))abort();
    uint16_t row[1920];off_t offset=0;
    for(int c=0;c<3;c++){
        int W=1920>>(c!=0),H=1080>>(c!=0),X=x>>(c!=0),Y=y>>(c!=0);
        int WW=w>>(c!=0),HH=h>>(c!=0);
        if(X+WW>W)WW=W-X;if(Y+HH>H)HH=H-Y;
        for(int yy=Y;yy<Y+HH;yy++){
            for(int xx=X;xx<X+WW;xx++){
                if(packed)row[xx-X]=((uint16_t*)p->buffer[c])[yy*p->stride[c]+xx];
                else {
                    int lo=p->buffer_bit_inc[c] ? (p->buffer_bit_inc[c][yy*(p->stride_bit_inc[c]/4)+xx/4]>>(6-2*(xx%4)))&3 : 0;
                    row[xx-X]=(p->buffer[c][yy*p->stride[c]+xx]<<2)|lo;
                }
            }
            if(pwrite(fd,row,WW*2,offset+((off_t)yy*W+X)*2)!=WW*2)abort();
        }
        offset+=(off_t)W*H*2;
    }
    close(fd);
}
static void pt_line(PictureParentControlSet *ppcs,const char *stage,const char *line){
    const char *dir=pt_dir(ppcs->picture_number);if(!dir)return;
    char path[1024];snprintf(path,sizeof(path),"%s/%s-%04llu-a%d-o%d.csv",dir,stage,
        (unsigned long long)ppcs->picture_number,ppcs->is_alt_ref,ppcs->is_overlay);
    int fd=open(path,O_CREAT|O_WRONLY|O_APPEND,0664);if(fd<0)abort();
    size_t n=strlen(line);if(write(fd,line,n)!=(ssize_t)n)abort();close(fd);
}
#endif
