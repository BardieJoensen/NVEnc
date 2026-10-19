#!/usr/bin/env python3
"""Compare all frame hashes across software reference and NVIDIA decode."""
import json
import investigate as x

out={'ffmpeg':x.run(['/usr/bin/ffmpeg','-version']),'cases':{}}
for case,(cfg,ts,fps) in x.CASES.items():
    d=x.ROOT/case
    h=x.hashes(['/usr/bin/ffmpeg','-v','error','-c:v','h264_cuvid','-threads','4','-ss',str(ts),'-i',cfg['original'],'-frames:v','240','-pix_fmt','yuv420p10le'])
    ref=json.loads((d/'validity.json').read_text())['hashes_ref']
    row={'original_nvdec_hashes':h,'original_software_nvdec_exact':h==ref};assert h==ref
    if case.startswith('e05'):
        on=x.hashes(['/usr/bin/ffmpeg','-v','error','-c:v','av1_cuvid','-threads','4','-ss',str(ts),'-i',cfg['library'],'-frames:v','240','-pix_fmt','yuv420p10le'])
        sw=x.hashes(['ffmpeg','-v','error','-threads','4','-i',str(d/'library-on.mkv'),'-frames:v','240','-pix_fmt','yuv420p10le'])
        row.update({'library_nvdec_hashes':on,'library_dav1d_hashes':sw,'library_dav1d_nvdec_exact':on==sw});assert on==sw
    out['cases'][case]=row;x.dump(x.ROOT/'decoder-check.json',out);print(case,'exact',flush=True)
