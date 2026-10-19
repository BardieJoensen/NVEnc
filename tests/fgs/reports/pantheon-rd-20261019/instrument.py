#!/usr/bin/env python3
"""Apply the isolated entropy wrapper after the existing causal+quantization patches."""
from pathlib import Path
import sys
here = Path(__file__).resolve().parent
codec = Path(sys.argv[1])/'Source/Lib/Codec'
p = codec/'entropy_coding.c'
s = p.read_text()
old = 'static int32_t av1_write_coeffs_txb_1d('
assert s.count(old) == 1
s = s.replace(old, 'static int32_t av1_write_coeffs_txb_1d_impl(', 1)
marker = 'static EbErrorType av1_encode_tx_coef_y('
assert s.count(marker) == 1
s = s.replace(marker, '#include "pantheon_entropy_probe.h"\n\n'+marker)
(codec/'pantheon_entropy_probe.h').write_text((here/'entropy_probe.c').read_text())
p.write_text(s)
