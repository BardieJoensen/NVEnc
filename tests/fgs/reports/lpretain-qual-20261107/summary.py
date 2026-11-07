from common import *
rows = jload(RESULTS)
wids = [w for w in WINDOWS if rows.get(w, {}).get('_done')]
ARMS = ['r090lp3']
for w in wids:
    for k, r in rows[w].items():
        if not k.startswith('_'): r['acf1_abs'] = abs(r['acf1'] - rows[w]['_src']['acf1'])
M = ['err_Y_s3.0', 'amp_Y_s3.0', 'err_Y_s1.5', 'amp_Cb', 'peak_Cb', 'amp_Cr', 'peak_Cr', 'err_Cb', 'err_Cr', 'hf_ratio', 'acf1', 'acf1_abs', 'butter_max_p95', 'vmaf_p1', 'err_Y_s6.0', 'amp_Y_s6.0', 'ssimu2']
SH = ['errY3', 'ampY3', 'errY1.5', 'ampCb', 'pkCb', 'ampCr', 'pkCr', 'errCb', 'errCr', 'hf_r', 'acf1', '|acf1-src|', 'but95', 'vmaf1', 'errY6', 'ampY6', 'ssimu2']
CLS = {}
for w in wids: CLS.setdefault(WINDOWS[w][0], []).append(w)
def ladder(w): return sorted((r['mbps'], r) for k, r in rows[w].items() if not k.startswith('_') and r['variant'] == 'prod')
def interp(w, S):
    p = ladder(w)
    if S < p[0][0] * 0.9999 or S > p[-1][0] * 1.0001: return None
    x = np.log([a[0] for a in p])
    return {m: float(np.interp(np.log(S), x, [a[1][m] for a in p])) for m in M}
def delta(w, var, q):
    r = rows[w][f'{var}_o0_q{q}']; c = interp(w, r['mbps'])
    return None if c is None else {m: r[m] - c[m] for m in M}
CH = ('amp_Cb', 'peak_Cb', 'amp_Cr', 'peak_Cr')
def block(var, q):
    per = {w: delta(w, var, q) for w in wids}; ok = {w: d for w, d in per.items() if d}
    o = {'n': len(ok), 'outside_range': [w for w, d in per.items() if not d], 'per_window': per}
    o['median'] = {m: float(np.median([d[m] for d in ok.values()])) if ok else None for m in M}
    o['errY3_better'] = sum(d['err_Y_s3.0'] < 0 for d in ok.values())
    o['title_chroma_fail_all'] = [c for c, ws in CLS.items() if all(w in ok and not all(ok[w][m] >= -0.002 for m in CH) for w in ws)]
    o['chroma_ok'] = sum(all(d[m] >= -0.002 for m in CH) for d in ok.values())
    o['class_median'] = {c: {'n': len([w for w in ws if w in ok]), **{m: (float(np.median([ok[w][m] for w in ws if w in ok])) if any(w in ok for w in ws) else None) for m in M}} for c, ws in CLS.items()}
    return o
T = {f'{v} q{q}': block(v, q) for q in (30, 34) for v in ARMS}
size = {}
for v in ARMS:
    pc = [rows[w][f'{v}_o0_q30']['mbps'] / rows[w]['prod_o0_q30']['mbps'] - 1 for w in wids]
    size[v] = {'median_pct': 100 * float(np.median(pc)), 'min_pct': 100 * min(pc), 'max_pct': 100 * max(pc), 'per_window_pct': {w: 100 * p for w, p in zip(wids, pc)}}
act = {}
for v in ARMS:
    act[v] = {w: rows[w][f'{v}_o0_q30'].get('auto', {}).get('retain_active_frac') for w in wids}
ctrl = {}
def f(v): return 'NA' if v is None else f'{v:+.4f}'
out = [f'# retain-lp qualification corpus vs production FGS at equal size (2026-11-07)\n', f'Windows: {len(wids)}: {", ".join(wids)}. Delta = arm minus prod ladder interpolated (log Mbps, no extrapolation) at the arm size. err/butter: negative better; others positive better.\n',
       '| row | n | outside | ' + ' | '.join(SH) + ' | errY3 better | chroma ok |\n|---|---|---|' + '---|' * (len(M) + 2)]
for k, b in T.items():
    out.append(f"| {k} | {b['n']} | {','.join(b['outside_range']) or '-'} | " + ' | '.join(f(b['median'][m]) for m in M) + f" | {b['errY3_better']}/{b['n']} | {b['chroma_ok']}/{b['n']} |")
out.append('\n## Per-class medians\n')
for k, b in T.items():
    out.append(f'\n{k}\n\n| class | n | ' + ' | '.join(SH) + ' |\n|---|---|' + '---|' * len(M))
    for c, d in b['class_median'].items(): out.append(f"| {c} | {d['n']} | " + ' | '.join(f(d[m]) for m in M) + ' |')
out.append('\n## Size at fixed QVBR 30 vs prod\n\n| arm | median % | min % | max % |\n|---|---|---|---|')
for v, s in size.items(): out.append(f"| {v} | {s['median_pct']:+.1f} | {s['min_pct']:+.1f} | {s['max_pct']:+.1f} |")
out.append('\n## Retain-active frame fraction (q30 debug logs)\n\n| arm | ' + ' | '.join(wids) + ' |\n|---|' + '---|' * len(wids))
for v, d in act.items(): out.append(f'| {v} | ' + ' | '.join(str(d[w]) for w in wids) + ' |')
# pass rule at q30
P = {}
for v in ARMS:
    b = T[f'{v} q30']; m = b['median']; ok = [d for d in b['per_window'].values() if d]
    P[v] = {'1 errY3>=7/9': (b['errY3_better'], b['errY3_better'] >= 7), '2 chroma>=8/9': (b['chroma_ok'], b['chroma_ok'] >= 8),
            '3 HF>=-0.03': (m['hf_ratio'], m['hf_ratio'] >= -0.03), '4 |acf1-src|<=+0.02': (m['acf1_abs'], m['acf1_abs'] <= 0.02),
            '5 butter<=+0.2': (m['butter_max_p95'], m['butter_max_p95'] <= 0.2), '6 vmaf_p1>=-0.5': (m['vmaf_p1'], m['vmaf_p1'] >= -0.5),
            '7 size q30<=+10%': (size[v]['median_pct'], size[v]['median_pct'] <= 10)}
out.append('\n## Pass-rule grid (q30)\n\n| rule | ' + ' | '.join(ARMS) + ' |\n|---|' + '---|' * len(ARMS))
for k in P['r090lp3']: out.append(f'| {k} | ' + ' | '.join(f"{'PASS' if P[v][k][1] else 'FAIL'} ({P[v][k][0]:.3f})" for v in ARMS) + ' |')
out.append('\nTitles failing rule 2 on all their windows (q30): ' + str(T['r090lp3 q30']['title_chroma_fail_all']))
out.append('\n## Per-window q30 deltas\n\n| win | ' + ' | '.join(SH) + ' |\n|---|' + '---|' * len(M))
for w, d in T['r090lp3 q30']['per_window'].items(): out.append(f'| {w} | ' + ' | '.join(f(d[m]) for m in M) + ' |')
open(f'{S}/summary.md', 'w').write('\n'.join(out) + '\n')
jsave(f'{S}/results.json', {'rows': rows, 'tables': T, 'size_q30': size, 'retain_active': act, 'pass_grid': P, 'manifest': jload(MANIFEST)})
print('\n'.join(out))
