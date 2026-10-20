from pathlib import Path
import shutil
p=Path(__file__).resolve().parent;s=p/'source'
def edit(f,old,new):
 q=s/f;t=q.read_text();assert t.count(old)==1,(f,t.count(old),old[:80]);q.write_text(t.replace(old,new))
shutil.copyfile(p/'pantheon_decoder.h',s/'av1/decoder/pantheon_decoder.h')
edit('av1/decoder/decoder.c','#include "av1/decoder/obu.h"','#include "av1/decoder/obu.h"\n#define PANTHEON_DECODER_IMPLEMENTATION\n#include "av1/decoder/pantheon_decoder.h"')
edit('av1/decoder/decoder.c','  int frame_decoded =\n      aom_decode_frame_from_obus','  p10_begin(pbi);\n  int frame_decoded =\n      aom_decode_frame_from_obus')
edit('av1/decoder/decoder.c','  update_frame_buffers(pbi, frame_decoded);','  p10_end(pbi, source, *psource, source + size, frame_decoded);\n  update_frame_buffers(pbi, frame_decoded);')
edit('av1/decoder/decodeframe.c','#include "av1/decoder/decoder.h"','#include "av1/decoder/decoder.h"\n#include "av1/decoder/pantheon_decoder.h"')
edit('av1/decoder/decodeframe.c','  av1_predict_intra_block_facade(cm, xd, plane, col, row, tx_size);','  av1_predict_intra_block_facade(cm, xd, plane, col, row, tx_size);\n  const int p10_id = p10_tu(cm, dcb, plane, row, col, tx_size);')
edit('av1/decoder/decodeframe.c','  if (plane == AOM_PLANE_Y && store_cfl_required(cm, xd)) {','  p10_after(cm, dcb, plane, row, col, tx_size, p10_id);\n  if (plane == AOM_PLANE_Y && store_cfl_required(cm, xd)) {')
edit('av1/decoder/decodeframe.c','  inverse_transform_block(dcb, plane, tx_type, tx_size, dst, pd->dst.stride,\n                          reduced_tx_set_used);','  const int p10_id = p10_tu(cm, dcb, plane, blk_row, blk_col, tx_size);\n  inverse_transform_block(dcb, plane, tx_type, tx_size, dst, pd->dst.stride,\n                          reduced_tx_set_used);\n  p10_after(cm, dcb, plane, blk_row, blk_col, tx_size, p10_id);')
edit('av1/decoder/decodeframe.c','  MB_MODE_INFO *mbmi = xd->mi[0];\n\n  if (!is_inter_block(mbmi)) {','  MB_MODE_INFO *mbmi = xd->mi[0];\n  p10_leaf(cm, dcb);\n\n  if (!is_inter_block(mbmi)) {')
edit('av1/decoder/decodeframe.c','    td->predict_inter_block_visit(cm, dcb, bsize);\n    // Reconstruction','    td->predict_inter_block_visit(cm, dcb, bsize);\n    p10_inter_skip(cm, dcb);\n    // Reconstruction')
print('instrumentation_applied')
