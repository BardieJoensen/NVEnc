#!/usr/bin/env python3
"""Exercise the actual C record reader against complete and corrupted TU exports."""
import json
from pathlib import Path
import resource
import struct
import subprocess
from analyze import ROOT, read_tu

here=Path(__file__).resolve().parent;out=ROOT/'parent/parser-checks-v2';out.mkdir(exist_ok=False)
path=next(p for p in sorted((ROOT/'worker/e05-1440-q32-control/detail').glob('0216-*.tu'))
          if 'initial_qcoeff' in read_tu(p))
r=read_tu(path);n=len(r['initial_qcoeff']);raw=path.read_bytes()
prefix=(here/'entropy_probe.c').read_text().split('typedef struct RdClone')[0]
code='#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'+prefix+'\nint main(int argc,char **argv){RdRecord r;rd_read(argv[1],atoi(argv[2]),&r);return 0;}\n'
(out/'reader.c').write_text(code)
subprocess.run(['cc','-O2',str(out/'reader.c'),'-o',str(out/'reader')],check=True)
(out/'complete.tu').write_bytes(raw)
records=[];offset=0
while offset<len(raw):
    header=raw[offset:offset+40];nn,ss=struct.unpack('<II',header[32:]);end=offset+40+nn*ss
    records.append((header[:32].split(b'\0')[0].decode(),raw[offset:end]));offset=end
(out/'missing-eob.tu').write_bytes(b''.join(blob for name,blob in records if name!='final_eob'))
(out/'partial-header.tu').write_bytes(raw+b'bad')
(out/'unknown-truncated.tu').write_bytes(raw+b'unknown'.ljust(32,b'\0')+struct.pack('<II',20,4)+b'abcd')
resource.setrlimit(resource.RLIMIT_CORE,(0,0));results={}
for name,good in [('complete',True),('missing-eob',False),('partial-header',False),('unknown-truncated',False)]:
    q=subprocess.run([str(out/'reader'),str(out/(name+'.tu')),str(n)],capture_output=True)
    assert (q.returncode==0)==good
    results[name]={'returncode':q.returncode,'stderr':q.stderr.decode()}
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
