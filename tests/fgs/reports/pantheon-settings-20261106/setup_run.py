from pset import *
man = {}
for w in WINS:
    t=time.time(); m = setup(w); man[w] = m
    print(w, {k: m[k] for k in ('ok','start','shift','shift_note','framemd5_exact','preroll_frames','ref_frames','lowluma_frac','orig_mbps','first_ref_pts')}, m['active']['rect'], round(time.time()-t), flush=True)
m = jload(f'{S}/manifest.json')
for w in WINS:
    if m[w].get('src_stats'): continue
    m[w]['src_stats'] = source_stats(w, m); jsave(f'{S}/manifest.json', m)
    print(w, m[w]['src_stats'], flush=True)
