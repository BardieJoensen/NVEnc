import json, numpy as np, sys
d=json.load(open('/tmp/downloads/codex-work/fgs-retention-reopen/results.json'))
rows=d['rows']; eq=d['equal_size']
M=['amp_Y_s3.0','err_Y_s3.0','amp_Y_s1.5','err_Y_s1.5','amp_Cb','peak_Cb','amp_Cr','peak_Cr','hf_ratio','acf1','butter_max_p95','vmaf_p1']
S=['aY3','eY3','aY15','eY15','aCb','pCb','aCr','pCr','hf','acf1','bp95','v1']
def pts(w,v): return sorted((r['mbps'],r) for k,r in rows[w].items() if not k.startswith('_') and r['variant']==v and not r.get('negative'))
def interp(w,v,s,m):
    p=pts(w,v); x=np.log([a[0] for a in p]); 
    if s<p[0][0]*0.9999 or s>p[-1][0]*1.0001: return None
    return float(np.interp(np.log(s),x,[a[1][m] for a in p]))
for sn in ('S1','S2'):
  for v in ('r050','r075','r090'):
    print(f'== {sn} {v} minus prod | minus plain')
    print('win    '+' '.join(f'{s:>7}' for s in S))
    for w in eq:
        a=eq[w][sn+'_vals'][v]; b=eq[w][sn+'_vals']['prod']; c=eq[w][sn+'_vals']['plain']
        if not a or not b or not c: print(w,'NA'); continue
        print(f'{w:5}P '+' '.join(f'{a[m]-b[m]:+7.4f}' if m not in('butter_max_p95','vmaf_p1') else f'{a[m]-b[m]:+7.2f}' for m in M))
        print(f'{w:5}L '+' '.join(f'{a[m]-c[m]:+7.4f}' if m not in('butter_max_p95','vmaf_p1') else f'{a[m]-c[m]:+7.2f}' for m in M))
# prod ladder bit equivalent for r050 at S1 / S2 luma
print('== prod-ladder bit equivalent of r050 luma at S1 (ampY3, errY3, ampY1.5, errY1.5): prod mbps needed / S1 -1 (%)')
def inv(w,m,val,inc):
    p=pts(w,'prod'); x=[np.log(a[0]) for a in p]; y=[a[1][m] for a in p]
    # monotone? fit
    yy=np.array(y); xx=np.array(x)
    o=np.argsort(yy if inc else -yy)
    ys=yy[o]; xs=xx[o]
    if (inc and val>ys[-1]) or ((not inc) and val<ys[0]*1 and False): pass
    # linear extrap using last two by mbps
    if inc:
        if val<=ys[-1]: return float(np.exp(np.interp(val,ys,xs)))
    else:
        if val>=yy.min(): return float(np.exp(np.interp(-val,-yy[o],xs)))
    # extrapolate from top 2 mbps points
    i=np.argsort(xx)[-2:]; s=(yy[i[1]]-yy[i[0]])/(xx[i[1]]-xx[i[0]])
    if s==0 or (inc and s<=0) or ((not inc) and s>=0): return float('inf')
    return float(np.exp(xx[i[1]]+(val-yy[i[1]])/s))*1.0  # flagged extrap
for sn in ('S1',):
  for w in eq:
    S1=eq[w][sn]; a=eq[w][sn+'_vals']['r050']
    if not a: continue
    out=[]
    for m,inc in (('amp_Y_s3.0',1),('err_Y_s3.0',0),('amp_Y_s1.5',1),('err_Y_s1.5',0)):
        r=inv(w,m,a[m],inc); p=pts(w,'prod'); ext= r>p[-1][0]
        out.append(f'{(r/S1-1)*100:+7.1f}%'+('*' if ext else ' '))
    print(w,' '.join(out), ' prod ladder mbps', [round(x[0],3) for x in pts(w,'prod')])
# auto vs prod/r050 at auto size
print('== auto_q30 minus prod/r050 interpolated at auto size')
for w in rows:
    if w.startswith('_') or 'auto_q30' not in rows[w]: continue
    au=rows[w]['auto_q30']; s=au['mbps']
    for v in ('prod','r050'):
        vals=[interp(w,v,s,m) for m in M]
        print(f'{w:5}{v[:4]} '+' '.join('     NA' if x is None else f'{au[m]-x:+7.4f}' for m,x in zip(M,vals)))
