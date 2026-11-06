from common import *
man = jload(MANIFEST); rows = jload(RESULTS); ctl = jload(f'{S}/controls.json', {})
LAD = ['prod', 'plain', 'r050', 'r075', 'r090']
NAME = {'prod': 'prod(retain=0)', 'plain': 'plain', 'r050': 'retain=0.5', 'r075': 'retain=0.75', 'r090': 'retain=0.9', 'auto': 'retain=auto'}
M = ['amp_Y_s3.0', 'err_Y_s3.0', 'amp_Y_s1.5', 'err_Y_s1.5', 'amp_Cb', 'peak_Cb', 'err_Cb', 'amp_Cr', 'peak_Cr', 'err_Cr', 'hf_ratio', 'acf1', 'butter_max_p95', 'vmaf_p1']
SHORT = {'amp_Y_s3.0': 'ampY3', 'err_Y_s3.0': 'errY3', 'amp_Y_s1.5': 'ampY1.5', 'err_Y_s1.5': 'errY1.5', 'amp_Cb': 'ampCb', 'peak_Cb': 'pkCb', 'err_Cb': 'errCb', 'amp_Cr': 'ampCr', 'peak_Cr': 'pkCr', 'err_Cr': 'errCr', 'hf_ratio': 'hf_r', 'acf1': 'acf1', 'butter_max_p95': 'but_p95', 'vmaf_p1': 'vmaf_p1'}
wids = [w for w in WINDOWS if rows.get(w, {}).get('_done')]
CLASSES = {}
for w in wids: CLASSES.setdefault(TITLES[WINDOWS[w][0]][2], []).append(w)
def pts(w, var):
    return sorted((r['mbps'], r['q'], r) for k, r in rows[w].items() if not k.startswith('_') and r['variant'] == var and not r.get('negative'))
def interp(w, var, S):
    p = pts(w, var)
    if S < p[0][0] * 0.9999 or S > p[-1][0] * 1.0001: return None
    x = np.log([a[0] for a in p]); res = {}
    for m in M:
        res[m] = float(np.interp(np.log(S), x, [a[2][m] for a in p]))
    for i in range(len(p) - 1):
        if p[i][0] - 1e-9 <= S <= p[i + 1][0] + 1e-9:
            res['between_q'] = [p[i + 1][1], p[i][1]]; break
    return res
eq = {}
for w in wids:
    S1 = rows[w]['prod_q30']['mbps']; S2 = rows[w]['r050_q30']['mbps']
    eq[w] = {'S1': S1, 'S2': S2}
    for sn, SV in (('S1', S1), ('S2', S2)):
        eq[w][sn + '_vals'] = {v: interp(w, v, SV) for v in LAD}
def f(v, m=None):
    if v is None: return 'NA'
    return f'{v:.4g}' if m is None else (f'{v:.3f}' if m.startswith(('amp', 'peak', 'hf')) else f'{v:.4f}' if m.startswith('err') else f'{v:.2f}')
out = []
P = out.append
P('# FGS retention reopen: measurements (no verdict)\n')
P('Windows, actual start PTS, frames, active area, replacement notes')
P('| win | class | nominal start | seek used | actual start PTS | frames | fps | active rect x,y,w,h | lowluma frac (nominal) | note |\n|---|---|---|---|---|---|---|---|---|---|')
for w in wids:
    m = man[w]; P(f"| {w} | {m['cls']} | {m['nominal_start']} | {m['seek_target']} | {m['actual_start_pts']} | {m['frames']} | {m['fps']} | {m['active']['rect']} (raw {m['active']['raw']}) | {m['lowluma_frac']} (after shift) | {m.get('shift_note') or ''} {('decode errors: ' + m['decode_errors']) if m['decode_errors'] else ''} |")
P('\n## Instrument controls\n')
P('Source vs itself: ' + '; '.join(f"{w}: " + ', '.join(f'{k}={v}' for k, v in c.get('self', {}).items()) for w, c in ctl.items()))
P('\nGrain-confound (prod q30 base + iid gaussian, sigma = source HF sigma / 4 in 8-bit units, added before lowpass)')
P('| win | noise sigma | metric | base | base+noise |\n|---|---|---|---|---|')
for w, c in ctl.items():
    cf = c.get('confound')
    if not cf: continue
    for k in cf['base']: P(f"| {w} | {cf['noise_sigma_8bit']} | {k} | {cf['base'][k]} | {cf['noisy'][k]} |")
P('\nFFVship film-grain handling (Butteraugli on prod q30: encode read directly vs lossless grain-on decode vs lossless grain-off decode)')
P('| win | input | butter_max_p95 | butter_2norm |\n|---|---|---|---|')
for w, c in ctl.items():
    for nm, v in c.get('ffvship', {}).items(): P(f"| {w} | {nm} | {v['butter_max_p95']} | {v['butter_2norm']} |")
P('\nNegative control: prod q40 vs prod q30 (expect lower ampY3 and higher errY3)')
P('| win | ampY3 q30 | ampY3 q40 | errY3 q30 | errY3 q40 | pass |\n|---|---|---|---|---|---|')
for w in wids:
    a, b = rows[w]['prod_q30'], rows[w]['prod_q40']
    ok = b['amp_Y_s3.0'] < a['amp_Y_s3.0'] and b['err_Y_s3.0'] > a['err_Y_s3.0']
    P(f"| {w} | {a['amp_Y_s3.0']} | {b['amp_Y_s3.0']} | {a['err_Y_s3.0']} | {b['err_Y_s3.0']} | {'yes' if ok else 'NO'} |")
bad = [(w, k) for w in wids for k, r in rows[w].items() if not k.startswith('_') and (r['enc_frames'] != r['src_frames'] or r.get('frames_decoded', r['src_frames']) != r['src_frames'] or not r.get('aligned'))]
P(f'\nFrame-count/alignment check over all {sum(1 for w in wids for k in rows[w] if not k.startswith("_"))} encodes: ' + ('all encodes match source frame count and best offset is 0' if not bad else f'EXCEPTIONS: {bad}'))
P('\n## Raw QVBR 30 table (per window)')
for w in wids:
    P(f'\n### {w} ({man[w]["cls"]}); source hf={rows[w]["_src"]["hf"]} acf1..3={rows[w]["_src"]["acf1"]},{rows[w]["_src"]["acf2"]},{rows[w]["_src"]["acf3"]}')
    P('| variant | Mbps | ' + ' | '.join(SHORT[m] for m in M) + ' | acf2 | acf3 | vmaf | ssimu2 |\n|' + '---|' * (len(M) + 6))
    for v in LAD + ['auto']:
        r = rows[w][f'{v}_q30']
        P(f"| {NAME[v]} | {r['mbps']} | " + ' | '.join(f(r[m], m) for m in M) + f" | {r['acf2']} | {r['acf3']} | {r['vmaf']} | {r['ssimu2']} |")
P('\n## Auto (retain=auto QVBR 30)')
P('| win | mean risk | retain mean | retain min | retain max | Mbps | vs prod q30 size % |\n|---|---|---|---|---|---|---|')
for w in wids:
    a = rows[w]['auto_q30']; au = a.get('auto', {})
    P(f"| {w} | {au.get('risk_mean')} | {au.get('retain_mean')} | {au.get('retain_min')} | {au.get('retain_max')} | {a['mbps']} | {(a['mbps'] / rows[w]['prod_q30']['mbps'] - 1) * 100:+.1f} |")
P('\n## Size cost vs prod at QVBR 30 (percent, mean over windows in class; per-window in json)')
sc = {}
hdr = ['plain', 'r050', 'r075', 'r090', 'auto']
P('| class | ' + ' | '.join(NAME[v] for v in hdr) + ' |\n|---|' + '---|' * len(hdr))
for c, ws in CLASSES.items():
    vals = {v: [(rows[w][f'{v}_q30']['mbps'] / rows[w]['prod_q30']['mbps'] - 1) * 100 for w in ws] for v in hdr}
    sc[c] = {v: round(float(np.mean(vals[v])), 2) for v in hdr}
    P(f'| {c} | ' + ' | '.join(f'{sc[c][v]:+.1f}' for v in hdr) + ' |')
sc['per_window'] = {w: {v: round((rows[w][f'{v}_q30']['mbps'] / rows[w]['prod_q30']['mbps'] - 1) * 100, 2) for v in hdr} for w in wids}
cm = {}
for sn in ('S1', 'S2'):
    P(f'\n## Equal-size comparison at {sn} ({"prod QVBR 30 size" if sn == "S1" else "retain=0.5 QVBR 30 size"}): class means of interpolated metrics')
    P('| class | variant | ' + ' | '.join(SHORT[m] for m in M) + ' | n bracketed |\n|---|---|' + '---|' * (len(M) + 1))
    for c, ws in CLASSES.items():
        for v in LAD:
            vs = [eq[w][sn + '_vals'][v] for w in ws if eq[w][sn + '_vals'][v]]
            cm.setdefault(sn, {}).setdefault(c, {})[v] = {m: (float(np.mean([x[m] for x in vs])) if vs else None) for m in M}
            P(f'| {c} | {NAME[v]} | ' + ' | '.join(f(cm[sn][c][v][m], m) for m in M) + f' | {len(vs)}/{len(ws)} |')
P('\n## Equal-size comparison per window')
for w in wids:
    for sn in ('S1', 'S2'):
        P(f'\n### {w} {sn} = {eq[w][sn]:.4f} Mbps')
        P('| variant | between QVBR | ' + ' | '.join(SHORT[m] for m in M) + ' |\n|---|---|' + '---|' * len(M))
        for v in LAD:
            r = eq[w][sn + '_vals'][v]
            if r is None: P(f'| {NAME[v]} | NOT BRACKETED | ' + ' | '.join('NA' for _ in M) + ' |'); continue
            P(f"| {NAME[v]} | {r.get('between_q')} | " + ' | '.join(f(r[m], m) for m in M) + ' |')
open(f'{S}/summary.md', 'w').write('\n'.join(out) + '\n')
jsave(f'{S}/results.json', {'manifest': man, 'rows': rows, 'controls': ctl, 'equal_size': eq, 'class_means_equal_size': cm, 'size_cost_pct': sc,
      'notes': {'butteraugli_field': 'butter_max_p95 = p95 over frames of per-frame Butteraugli max-norm (all frames); also butter_2norm mean', 'frames': 'GPU metrics on all frames, base/grain metrics every 2nd frame (hf on 12 frames)'}})
print('written', len(wids), 'windows')
