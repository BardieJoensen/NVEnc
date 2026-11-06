import os
from prep import *
man = jload(MANIFEST)
os.environ['REUSE'] = '1'
for wid in ('dkr2',):
    man[wid] = prep(wid); jsave(MANIFEST, man); print(wid, man[wid]['lowluma_frac'])
os.environ.pop('REUSE')
for wid in ('bd1', 'bd2', 'ca2', 'dkr1'):
    lf = man[wid]['lowluma_frac']
    man[wid] = prep(wid, shift=60, note=f'+60 s once: {lf:.3f} of frames in the nominal window had active-area mean luma < 32')
    man[wid]['v'] = 2; jsave(MANIFEST, man); print(wid, man[wid]['seek_target'], man[wid]['lowluma_frac'], man[wid]['active'], flush=True)
