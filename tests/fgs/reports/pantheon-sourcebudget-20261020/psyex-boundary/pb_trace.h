#ifndef PANTHEON_BOUNDARY_TRACE_H
#define PANTHEON_BOUNDARY_TRACE_H
#include "pcs.h"
#include "EbSvtAv1Enc.h"
void pb_source(PictureControlSet *pcs, EbPictureBufferDesc *src, unsigned x, unsigned y, int is16);
void pb_attempt(PictureControlSet *pcs, EbPictureBufferDesc *recon, int recode);
void pb_post(PictureControlSet *pcs, EbPictureBufferDesc *recon);
void pb_finish(const EbSvtAv1EncConfiguration *cfg, unsigned instances);
#endif
