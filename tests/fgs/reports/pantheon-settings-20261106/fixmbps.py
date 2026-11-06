from pset import *
m = jload(f'{S}/manifest.json')
for w in WINS:
    T = m[w]['start']; pk = packets(m[w]['src'], T, 16)
    i0 = next(i for i,(t,_) in enumerate(pk) if t >= T); sel = pk[i0:i0+N]
    m[w]['orig_mbps'] = round(sum(s for _,s in sel)*8/(N/FPS)/1e6, 4); m[w]['first_ref_pts']=sel[0][0]
    print(w, m[w]['orig_mbps'], sel[0][0])
jsave(f'{S}/manifest.json', m)
