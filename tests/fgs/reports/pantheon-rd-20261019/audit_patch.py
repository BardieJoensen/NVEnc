#!/usr/bin/env python3
"""Reconstruct the diagnostic source from immutable inputs and compare build inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
from probe import ROOT, sha

HERE=Path(__file__).resolve().parent
out=ROOT/'parent/audit-source';out.mkdir(exist_ok=False)
archive=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-independent-investigation/svt-source.tar.gz')
commands=[['tar','-xzf',str(archive),'--strip-components=1','-C',str(out)],
          ['patch','-d',str(out),'-p1','-i',str(HERE.parent/'pantheon-causal-20261019/svt-causal.patch')],
          ['patch','-d',str(out),'-p1','-i',str(HERE.parent/'pantheon-quantization-20261019/svt-quantization.patch')],
          ['python3',str(HERE/'instrument.py'),str(out)],
          ['python3',str(HERE/'private_fp.py'),str(out)],
          ['patch','-d',str(out),'-p1','-i',str(HERE.parent/'pantheon-quantization-20261019/svt-absolute.patch')],
          ['python3',str(HERE/'retain_fp.py'),str(out)]]
for cmd in commands:subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
checks={}
for path in (out/'Source').rglob('*'):
    if path.is_file():
        actual=ROOT/'parent-source'/path.relative_to(out)
        a,b=sha(path),sha(actual)
        assert a==b,str(path.relative_to(out))
        checks[str(path.relative_to(out))]=a
record={'pristine_source_sha256':sha(archive),'all_reconstructed_source_files_equal':True,
        'files_checked':len(checks),'source_hashes':checks,'commands':commands,
        'diagnostic_binary_sha256':sha(ROOT/'parent-source/Bin/Release/SvtAv1EncApp')}
(ROOT/'parent/patch-audit.json').write_text(json.dumps(record,indent=2)+'\n')
print('Source reconstruction exact:',len(checks),'files')
