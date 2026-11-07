from common import *
rows = jload(RESULTS)
wids = [w for w in WINDOWS if rows.get(w, {}).get('_done')]
M = ['err_Y_s3.0', 'amp_Y_s3.0', 'err_Y_s1.5', 'amp_Cb', 'peak_Cb', 'amp_Cr', 'peak_Cr', 'hf_ratio', 'acf1', 'butter_max_p95', 'vmaf_p1']
SH = ['errY3', 'ampY3', 'errY1.5', 'ampCb', 'pkCb', 'ampCr', 'pkCr', 'hf_r', 'acf1', 'but95', 'vmaf1']
CLS = {}
for w in wids: CLS.setdefault(TITLES[WINDOWS[w][0]][2], []).append(w)
def ladder(w, var, off):
    return sorted((r['mbps'], r) for k, r in rows[w].items() if not k.startswith('_') and r['variant'] == var and r['off'] == off)
def interp(w, var, off, S):
    p = ladder(w, var, off)
    if S < p[0][0] * 0.9999 or S > p[-1][0] * 1.0001: return None
    x = np.log([a[0] for a in p])
    return {m: float(np.interp(np.log(S), x, [a[1][m] for a in p])) for m in M}
def delta(w, var, off, q, cvar, coff):
    r = rows[w][f'{var}_o{off}_q{q}']; c = interp(w, cvar, coff, r['mbps'])
    if c is None: return None
    return {m: r[m] - c[m] for m in M}
def verdicts(d):
    return dict(err=d['err_Y_s3.0'] < 0,
                chroma=all(d[m] >= -0.002 for m in ('amp_Cb', 'peak_Cb', 'amp_Cr', 'peak_Cr')),
                butter=d['butter_max_p95'] <= 0.1)
def block(var, off, q, cvar, coff):
    per = {w: delta(w, var, off, q, cvar, coff) for w in wids}
    ok = {w: d for w, d in per.items() if d}
    out = {'n': len(ok), 'outside_range': [w for w, d in per.items() if not d], 'per_window': per}
    out['median'] = {m: float(np.median([d[m] for d in ok.values()])) if ok else None for m in M}
    vs = [verdicts(d) for d in ok.values()]
    out['counts'] = {k: sum(v[k] for v in vs) for k in ('err', 'chroma', 'butter')}
    out['class_median'] = {}
    for c, ws in CLS.items():
        sub = [ok[w] for w in ws if w in ok]
        out['class_median'][c] = {'n': len(sub), **{m: (float(np.median([d[m] for d in sub])) if sub else None) for m in M}}
    return out
T1 = {}; T2 = {}
for off in (0, -2, -4):
    for q in (26, 30, 34):
        T1[f'r050@{off} q{q} vs prod@0'] = block('r050', off, q, 'prod', 0)
        if off: T1[f'r050@{off} q{q} vs prod@{off}'] = block('r050', off, q, 'prod', off)
for off in (-2, -4):
    T2[f'prod@{off} q30 vs prod@0'] = block('prod', off, 30, 'prod', 0)
# also size cost at q30 for reference
size = {f'{v}@{o}': {w: rows[w][f'{v}_o{o}_q30']['mbps'] for w in wids} for v in ('prod', 'r050') for o in (0, -2, -4)}
def f(v, m):
    if v is None: return 'NA'
    return f'{v:+.4f}'
out = ['# FGS retain=0.5 + chroma QP offset (2026-11-07): measurements, no verdict\n', f'Windows scored: {len(wids)}: {", ".join(wids)}\n',
       'Delta = candidate minus comparator ladder interpolated (log Mbps, no extrapolation) at the candidate size. err/butter: negative is better; others: positive is better. Counts: errY3 better / all four chroma amp,peak >= -0.002 / Butteraugli p95 not worse than +0.1.\n']
for title, T in (('Table 1', T1), ('Table 2', T2)):
    out.append(f'\n## {title}: median delta over bracketed windows\n')
    out.append('| row | n | outside | ' + ' | '.join(SH) + ' | errY3 better | chroma ok | butter ok |\n|---|---|---|' + '---|' * (len(M) + 3))
    for k, b in T.items():
        out.append(f"| {k} | {b['n']} | {','.join(b['outside_range']) or '-'} | " + ' | '.join(f(b['median'][m], m) for m in M) + f" | {b['counts']['err']}/{b['n']} | {b['counts']['chroma']}/{b['n']} | {b['counts']['butter']}/{b['n']} |")
    out.append(f'\n### {title}: per-class medians\n')
    for k, b in T.items():
        out.append(f'\n{k}\n\n| class | n | ' + ' | '.join(SH) + ' |\n|---|---|' + '---|' * len(M))
        for c, d in b['class_median'].items():
            out.append(f"| {c} | {d['n']} | " + ' | '.join(f(d[m], m) for m in M) + ' |')
out.append('\n## Repro check (offset-0 arms vs 2026-11-06 results.json)\n\n| win | max size diff % | max abs err_Y3 diff | max butter p95 diff | max vmaf_p1 diff |\n|---|---|---|---|---|')
for w in wids:
    r = rows[w]['_repro']; out.append(f"| {w} | {r['size_pct']:.3f} | {r['err_Y3']:.5f} | {r['all']['butter_max_p95']:.3f} | {r['all']['vmaf_p1']:.3f} |")
out.append('\n## Mbps at q30\n\n| arm | ' + ' | '.join(wids) + ' |\n|---|' + '---|' * len(wids))
for k, v in size.items(): out.append(f'| {k} | ' + ' | '.join(f'{v[w]:.3f}' for w in wids) + ' |')
open(f'{S}/summary.md', 'w').write('\n'.join(out) + '\n')
jsave(f'{S}/results.json', {'rows': rows, 'table1': T1, 'table2': T2, 'size_q30_mbps': size, 'manifest': jload(MANIFEST)})
print('\n'.join(out[:3 + 2 * (len(T1) + len(T2)) + 12]))
