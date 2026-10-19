#!/usr/bin/env python3
"""Apply only the planned map intervention to already-instrumented scratch."""
from pathlib import Path
import sys,shutil
root=Path(sys.argv[1]);d=root/'svt-source/Source/Lib/Codec';here=Path(__file__).parent
shutil.copy2(here/'pantheon_alloc.h',d/'pantheon_alloc.h')
for name in ('rc_process.c','enc_dec_process.c'):
    p=d/name;b=p.read_bytes();s=b.decode('utf-8-sig');assert 'pt_adjust_q(' not in s
    s=s.replace('#include "enc_handle.h"','#include "enc_handle.h"\n#include "pantheon_alloc.h"',1)
    if name=='rc_process.c':
        old='    svt_av1_rc_init_sb_qindex(pcs, scs);';assert old in s;s=s.replace(old,old+'\n    pt_adjust_q(pcs);',1)
    else:
        old='        if (pcs->ppcs->frm_hdr.delta_q_params.delta_q_present && pcs->ppcs->frm_hdr.delta_q_params.delta_q_res != 1) {'
        assert old in s;s=s.replace(old,'        pt_adjust_q(pcs);\n'+old,1)
    p.write_text(s,encoding='utf-8-sig' if b.startswith(b'\xef\xbb\xbf') else 'utf-8')
