import json, math, sys, os, numpy as np
S = '/tmp/downloads/codex-work/pantheon-settings-20261106'
rows = json.load(open(f'{S}/rows.json')); man = json.load(open(f'{S}/manifest.json'))
WINS = ['p04a', 'p04b', 'p01', 'p05']
def src(w): return man[w]['src_stats']
def metrics_of(r, w):
    s = src(w); m = {}
    m['hf_frame'] = r['frame_grain_on']['hf'] / s['hf']['hf']
    m['acf1'] = r['frame_grain_on']['acf1']
    m['hf_roi'] = r['tex']['roi']['hf'] / s['tex']['roi']['hf']
    m['acf1_roi'] = r['tex']['roi']['acf1']
    m['amp_Y3'] = r['amp_Y_s3.0']; m['err_Y3'] = r['err_Y_s3.0']; m['amp_Y15'] = r['amp_Y_s1.5']; m['err_Y15'] = r['err_Y_s1.5']
    m['amp_C'] = (r['amp_Cb'] + r['amp_Cr']) / 2
    m['butter_p95'] = r['butter_max_p95']; m['vmaf_p1'] = r['vmaf_p1']; m['cambi'] = r['cambi_enc']
    m['vmaf'] = r['vmaf']; m['ssimu2'] = r['ssimu2']
    return m
KEYS = ['hf_frame', 'hf_roi', 'acf1', 'amp_Y3', 'err_Y3', 'amp_Y15', 'err_Y15', 'amp_C', 'butter_p95', 'vmaf_p1', 'cambi']
def good(w, tag):
    r = rows.get(f'{w}/{tag}'); return r if r and 'error' not in r and r.get('_final') else None
def ladder(w):
    pts = []
    for q in (38, 34, 30, 26, 22):
        r = good(w, f'prod_q{q}')
        if r: pts.append((r['mbps'], q, metrics_of(r, w)))
    return sorted(pts)
def interp(pts, mb, key):
    if not pts or mb < pts[0][0] - 1e-9 or mb > pts[-1][0] + 1e-9: return None
    for (a, _, ma), (b, _, mb2) in zip(pts, pts[1:]):
        if a - 1e-9 <= mb <= b + 1e-9:
            t = (math.log(mb) - math.log(a)) / (math.log(b) - math.log(a))
            return ma[key] + t * (mb2[key] - ma[key])
def cross(pts, key, target):
    for (a, _, ma), (b, _, mb) in zip(pts, pts[1:]):
        if (ma[key] - target) * (mb[key] - target) <= 0 and ma[key] != mb[key]:
            t = (target - ma[key]) / (mb[key] - ma[key])
            return math.exp(math.log(a) + t * (math.log(b) - math.log(a)))
    if pts and pts[0][2][key] >= target: return 'at/below lowest rung'
    return None
out = {'windows': {}, 'deviations': []}
for w in WINS:
    L = ladder(w); wo = {'orig_mbps': man[w]['orig_mbps'], 'start': man[w]['start'], 'src_hf': src(w)['hf']['hf'], 'ladder': [], 'variants': {}, 'cost_to_texture': {}}
    for mb, q, m in L: wo['ladder'].append({'q': q, 'mbps': mb, **{k: m[k] for k in KEYS}})
    for key in ('hf_frame', 'hf_roi'):
        wo['cost_to_texture'][key] = {}
        for t in (0.6, 0.8):
            c = cross(L, key, t)
            wo['cost_to_texture'][key][str(t)] = round(c, 3) if isinstance(c, float) else ('not reached by q22' if c is None else c)
    for k, r in rows.items():
        if not k.startswith(w + '/'): continue
        tag = k.split('/')[1]
        if 'error' in r: wo['variants'][tag] = {'error': r['error'][-300:]}; continue
        if not r.get('_final'): continue
        m = metrics_of(r, w); v = {'mbps': r['mbps'], 'aligned': r['aligned'], 'metrics': {kk: round(m[kk], 4) for kk in KEYS}, 'delta_vs_prod_same_size': {}, 'note': r.get('note')}
        for kk in KEYS:
            p = interp(L, r['mbps'], kk)
            v['delta_vs_prod_same_size'][kk] = None if p is None else round(m[kk] - p, 4)
        wo['variants'][tag] = v
    out['windows'][w] = wo
json.dump(out, open(f'{S}/results.json', 'w'), indent=1)
# table
L = []
def f(x, d=3): return '-' if x is None else f'{x:+.{d}f}'
tags = sorted({t for w in WINS for t in out['windows'][w]['variants']})
for w in WINS:
    wo = out['windows'][w]
    L.append(f"\n## {w} (orig {wo['orig_mbps']} Mbps, src HF {wo['src_hf']})\n")
    L.append('Prod ladder: ' + '; '.join(f"q{x['q']} {x['mbps']}Mbps HF {x['hf_frame']:.2f}/ROI {x['hf_roi']:.2f}" for x in wo['ladder']))
    L.append(f"Cost to HF ratio (frame) 0.6/0.8: {wo['cost_to_texture']['hf_frame']}; ROI: {wo['cost_to_texture']['hf_roi']}\n")
    L.append('| variant | Mbps | dHF fr | dHF roi | dacf1 | dampY3 | derrY3 | dampY1.5 | derrY1.5 | dampC | dButter | dVMAFp1 | dCAMBI |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for t, v in sorted(wo['variants'].items()):
        if t.startswith('prod_'): continue
        if 'error' in v: L.append(f'| {t} | ERROR {v["error"][:80]} |'); continue
        d = v['delta_vs_prod_same_size']
        L.append(f"| {t} | {v['mbps']} | {f(d['hf_frame'],3)} | {f(d['hf_roi'],3)} | {f(d['acf1'],3)} | {f(d['amp_Y3'],4)} | {f(d['err_Y3'],4)} | {f(d['amp_Y15'],4)} | {f(d['err_Y15'],4)} | {f(d['amp_C'],4)} | {f(d['butter_p95'],2)} | {f(d['vmaf_p1'],2)} | {f(d['cambi'],3)} |")
open(f'{S}/summary.md', 'w').write('\n'.join(L))
print('\n'.join(L))
