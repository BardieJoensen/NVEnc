#!/usr/bin/env python3
"""Run the isolated entropy probe against immutable-binary CQP8 control decisions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(os.environ.get('PANTHEON_RD_ROOT', '/tmp/downloads/codex-work/pantheon-rd-20261019'))

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while raw := f.read(4*1024*1024): h.update(raw)
    return h.hexdigest()

def main():
    case = sys.argv[1]
    control = ROOT/'worker'/(case+'-q32-control')
    out = ROOT/'parent'/(case+'-entropy')
    out.mkdir(exist_ok=False)
    saved = json.loads((control/'command.json').read_text())
    cmd = saved['argv']
    cmd[6] = str(ROOT/'parent-source/Bin/Release/SvtAv1EncApp')
    cmd[cmd.index('-b')+1] = str(out/'out.ivf')
    cmd[cmd.index('-o')+1] = str(out/'recon.yuv')
    env = {k: v for k, v in os.environ.items() if not k.startswith('PANTHEON_')}
    extra = {'PANTHEON_RD_DETAIL_INPUT': str(control/'detail'),
             'PANTHEON_RD_POC': saved['env']['PANTHEON_DETAIL_POC'],
             'PANTHEON_RD_LOG': str(out/'entropy.jsonl')}
    env.update(extra)
    start = time.monotonic()
    with (out/'encode.log').open('wb') as log:
        r = subprocess.run(cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
    receipt = {'argv': cmd, 'cwd': str(out), 'env': extra, 'seconds': time.monotonic()-start,
               'returncode': r.returncode, 'binary_sha256': sha(Path(cmd[6]))}
    (out/'command.json').write_text(json.dumps(receipt, indent=2)+'\n')
    assert r.returncode == 0, (out/'encode.log').read_text()[-3000:]
    receipt['control_ivf_sha256'] = sha(control/'out.ivf')
    receipt['probe_ivf_sha256'] = sha(out/'out.ivf')
    receipt['control_recon_sha256'] = sha(control/'recon.yuv')
    receipt['probe_recon_sha256'] = sha(out/'recon.yuv')
    assert receipt['control_ivf_sha256'] == receipt['probe_ivf_sha256']
    assert receipt['control_recon_sha256'] == receipt['probe_recon_sha256']
    rows = [json.loads(line) for line in (out/'entropy.jsonl').read_text().splitlines()]
    assert rows and all(row['clone_state_equal'] and row['clone_bytes_equal'] and row['clone_cdf_equal'] for row in rows)
    assert len({(r['poc'],r['x'],r['y']) for r in rows}) == len(rows)
    receipt['entropy_records'] = len(rows)
    receipt['all_clones_match_real_coder'] = True
    (out/'validation.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(case, len(rows), 'validated coder records; exact control IVF/reconstruction', flush=True)

if __name__ == '__main__': main()
