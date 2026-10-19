#!/usr/bin/env python3
"""Audit the complete eligible population and summarize local coder deltas."""
import json
import os
from pathlib import Path
import sys
from analyze import read_tu, BOXES
ROOT = Path(os.environ.get('PANTHEON_RD_ROOT', '/tmp/downloads/codex-work/pantheon-rd-20261019'))

def summarize(case):
    control = ROOT/'worker'/(case+'-q32-control')
    out = ROOT/'parent'/(case+'-entropy')
    rows = [json.loads(line) for line in (out/'entropy.jsonl').read_text().splitlines()]
    actual = {(r['poc'], r['x'], r['y']): r for r in rows}
    assert len(actual) == len(rows)
    pocs = sorted({r['poc'] for r in rows})
    assert pocs == ([184, 230] if case == 'e04' else [120, 216])
    expected, excluded, bypass = set(), [], []
    for poc in pocs:
        trace = {}
        for line in (control/'trace'/f'luma_txs-{poc:04d}-a0-o0.csv').read_text().splitlines():
            v = list(map(int, line.split(',')))
            assert (v[0],v[1]) not in trace
            trace[(v[0],v[1])] = v
        blocks = {}
        for line in (control/'trace'/f'blocks-{poc:04d}-a0-o0.csv').read_text().splitlines():
            v = list(map(int, line.split(','))); blocks[(v[3],v[4])] = v
        for path in sorted((control/'detail').glob(f'{poc:04d}-*.tu')):
            r = read_tu(path); m = r['meta']; key = (poc,m['x'],m['y'])
            if 'initial_qcoeff' not in r:
                bypass.append(key); continue
            assert all(k in r for k in ['initial_eob','final_qcoeff','final_eob']), path
            block = blocks[(m['block_x'],m['block_y'])]
            if (m['x'],m['y']) not in trace:
                assert block[9] == 1 or block[10] == 1, 'Missing entropy hook without whole-block skip'
                assert int(r['final_eob'][0]) == 0
                excluded.append({'key':key, 'initial_eob':int(r['initial_eob'][0]), 'whole_block_skip':block[9], 'skip_mode':block[10], 'w':m['w'],'h':m['h']})
            else:
                assert block[9] == 0 and block[10] == 0
                expected.add(key)
                t = trace[(m['x'],m['y'])]; a = actual[key]
                assert [a[k] for k in ['w','h','effective_qindex','final_eob']] == t[2:6]
    assert expected == set(actual), (len(expected),len(actual),len(expected-set(actual)),len(set(actual)-expected))
    groups = {}
    for poc in pocs:
        for name,box in {'whole_frame':[0,0,1920,1080], **BOXES[case]}.items():
            xx,yy,w,h = box
            pool = [r for r in rows if r['poc']==poc and xx<=r['x'] and yy<=r['y'] and r['x']+r['w']<=xx+w and r['y']+r['h']<=yy+h]
            groups[f'{poc-96}/{name}'] = {'fully_contained_tus':len(pool),
                'pixels':sum(r['w']*r['h'] for r in pool), 'changed_tus':sum(r['changed'] for r in pool),
                'zero_eob_revived_tus':sum(r['final_eob']==0 and r['initial_eob']>0 for r in pool),
                **{k:sum(r[k] for r in pool) for k in ['baseline_bits','retained_bits','delta_bits']}}
    result = {'case':case,'rows':len(rows),'expected_population_exact':True,
        'quantizer_bypass_tus':len(bypass),'whole_block_skipped_quantizer_run_tus':excluded,
        'groups':groups,'scope':'Sum of independent fixed-prestate arithmetic-coder tell_frac deltas, in eighth-bits. Not a sequential alternate stream or packet bitrate. Whole-block skip revival excluded.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='whole_block_skipped_quantizer_run_tus'},indent=2))

if __name__=='__main__': summarize(sys.argv[1])
