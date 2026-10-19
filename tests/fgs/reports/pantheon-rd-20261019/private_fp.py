#!/usr/bin/env python3
"""Add private, same-algorithm FP probes at q, q-8 and q-16; never replace coding data."""
from pathlib import Path
import sys
p=Path(sys.argv[1])/'Source/Lib/Codec/full_loop.c'
s=p.read_text()
start=s.index('void pq_counter(')
end=s.index('\nuint8_t svt_aom_quantize_inv_quantize',start)
part=s[start:end]
old=''' }
}
'''
assert part.endswith(old)
loop=part[part.index(' int qs[3]'):part.rindex('\n}')]
loop=loop.replace('int qs[3]={effective,MAX(1,effective-32),1}', 'int mid=getenv("PANTHEON_FP_MIDDLE_DELTA")?atoi(getenv("PANTHEON_FP_MIDDLE_DELTA")):8; if(mid!=8&&mid!=12)abort(); int qs[3]={effective,MAX(1,effective-mid),MAX(1,effective-16)}')
loop=loop.replace('svt_av1_highbd_quantize_b_facade', 'svt_av1_highbd_quantize_fp_facade').replace('"scalar%d_', '"fp%d_')
part=part[:-2]+ '\n {\n'+loop+'\n }\n}\n'
s=s[:start]+part+s[end:]
p.write_text(s)
