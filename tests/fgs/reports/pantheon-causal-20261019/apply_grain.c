/* Offline native AV1 synthesis on an unchanged decoded picture.
 * Usage: apply_grain input.ivf output.yuv mode[0=base,1=existing,2=model]
 *                   skip count [model.txt]
 * model lines: seed shift lag ar_shift grain_shift nY x scale... 24 AR ints
 *              nU x scale... 25 AR ints nV x scale... 25 AR ints
 * UV multipliers are fixed at chroma-only lookup (64,0,0), overlap=1,
 * restricted-range clipping=1. Raw output is planar yuv420p10le.
 * Does not rewrite the bitstream or mutate decoder-owned frame headers.
 */
#include <dav1d/dav1d.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int mode, skip, count, frame_no, bases_verified;
static FILE *out, *models;
static uint32_t le32(const unsigned char *p) {
    return p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static int value(void) { int v; if (fscanf(models,"%d",&v)!=1) {fprintf(stderr,"short model at frame %d\n",frame_no);exit(3);} return v; }
static void model(Dav1dFilmGrainData *g) {
    memset(g,0,sizeof(*g));g->seed=value();g->scaling_shift=value();g->ar_coeff_lag=value();g->ar_coeff_shift=value();g->grain_scale_shift=value();
    g->num_y_points=value();if(g->num_y_points>14)exit(4);
    for(int k=0;k<g->num_y_points;k++){g->y_points[k][0]=value();g->y_points[k][1]=value();}
    for(int k=0;k<24;k++)g->ar_coeffs_y[k]=value();
    for(int c=0;c<2;c++){
        g->num_uv_points[c]=value();if(g->num_uv_points[c]>10)exit(4);
        for(int k=0;k<g->num_uv_points[c];k++){g->uv_points[c][k][0]=value();g->uv_points[c][k][1]=value();}
        for(int k=0;k<25;k++)g->ar_coeffs_uv[c][k]=value();
        g->uv_mult[c]=64;g->uv_luma_mult[c]=0;g->uv_offset[c]=0;
    }
    g->overlap_flag=1;g->clip_to_restricted_range=1;
}
static void picture(Dav1dContext *ctx,Dav1dPicture *p) {
    if(frame_no>=skip && frame_no<skip+count){
        if(p->p.bpc!=10 || p->p.layout!=DAV1D_PIXEL_LAYOUT_I420)exit(5);
        Dav1dPicture grain={0}, borrowed=*p;Dav1dFrameHeader header=*p->frame_hdr;
        uint8_t *before=malloc(p->p.w*p->p.h*3);size_t off=0;
        if(!before)exit(11);
        for(int c=0;c<3;c++)for(int y=0;y<(p->p.h>>(c!=0));y++){
            size_t bytes=(p->p.w>>(c!=0))*2;
            memcpy(before+off,(uint8_t*)p->data[c]+y*p->stride[c!=0],bytes);off+=bytes;
        }
        if(mode==2){model(&header.film_grain.data);header.film_grain.present=1;header.film_grain.update=1;borrowed.frame_hdr=&header;}
        Dav1dPicture *chosen=p;
        if(mode){int err=dav1d_apply_grain(ctx,&grain,&borrowed);if(err){fprintf(stderr,"apply %d\n",err);exit(6);}chosen=&grain;}
        off=0;
        for(int c=0;c<3;c++)for(int y=0;y<(p->p.h>>(c!=0));y++){
            size_t bytes=(p->p.w>>(c!=0))*2;
            if(memcmp(before+off,(uint8_t*)p->data[c]+y*p->stride[c!=0],bytes))exit(12);off+=bytes;
        }
        free(before);bases_verified++;
        for(int c=0;c<3;c++){
            int w=p->p.w>>(c!=0),h=p->p.h>>(c!=0);
            for(int y=0;y<h;y++)if(fwrite((uint8_t*)chosen->data[c]+y*chosen->stride[c!=0],2,w,out)!=(size_t)w)exit(7);
        }
        if(mode)dav1d_picture_unref(&grain);
    }
    frame_no++;dav1d_picture_unref(p);
}
int main(int argc,char **argv){
    if(argc<6)return 2;
    mode=atoi(argv[3]);skip=atoi(argv[4]);count=atoi(argv[5]);
    if(mode==2 && argc<7)return 2;
    FILE *in=fopen(argv[1],"rb");out=fopen(argv[2],"wb");if(mode==2)models=fopen(argv[6],"r");
    if(!in||!out||(mode==2&&!models))return 2;
    uint8_t hdr[32];if(fread(hdr,1,32,in)!=32||memcmp(hdr,"DKIF",4))return 2;
    Dav1dSettings settings;dav1d_default_settings(&settings);settings.n_threads=4;settings.max_frame_delay=1;settings.apply_grain=0;
    Dav1dContext *ctx=NULL;if(dav1d_open(&ctx,&settings))return 2;
    uint8_t fh[12];
    while(fread(fh,1,12,in)==12){
        uint32_t size=le32(fh);Dav1dData data={0};uint8_t *buf=dav1d_data_create(&data,size);
        if(!buf||fread(buf,1,size,in)!=size)return 2;
        while(data.sz){
            int err=dav1d_send_data(ctx,&data);if(err && err!=DAV1D_ERR(EAGAIN))return 8;
            Dav1dPicture p={0};while(!(err=dav1d_get_picture(ctx,&p)))picture(ctx,&p);
            if(err!=DAV1D_ERR(EAGAIN))return 9;
        }
        dav1d_data_unref(&data);
    }
    Dav1dPicture p={0};while(!dav1d_get_picture(ctx,&p))picture(ctx,&p);
    dav1d_close(&ctx);fclose(in);fclose(out);if(models)fclose(models);
    fprintf(stderr,"decoded=%d wrote=%d base_before_after_exact=%d native_dav1d=%s\n",frame_no,count,bases_verified,dav1d_version());
    return frame_no<skip+count?10:0;
}
