#!/usr/bin/env python3
"""Frame-position packet accounting, independent of container start timestamps."""
import json
import sys
from analyze import ROOT, x

def measure(path,fps):
    pk=sorted(x.packets(path),key=lambda r:float(r['pts_time']))
    assert len(pk)==336
    pts=[float(r['pts_time']) for r in pk]
    assert all(0<pts[i+1]-pts[i] and abs((pts[i]-pts[0])*fps-i)<0.03 for i in range(335))
    assert abs((pts[-1]-pts[0])*fps-335)<0.03
    selected=pk[96:336]
    rate=sum(int(r['size']) for r in selected)*8/(240/fps)/1e6
    return rate,selected,pts[0]

def audit(case,tag):
    d=ROOT/'parent/crosscodec'/case/tag
    source=json.loads((ROOT/'fixtures'/case/'validity.json').read_text())
    multiple=json.loads((d/'command.json').read_text()).get('target_multiple',2)
    assert multiple in (2,3)
    rate,selected,first=measure(d/'out.mkv',x.CASES[case][2]);target=multiple*source['source_mbps']
    result={'actual_mbps':rate,'source_mbps':source['source_mbps'],'target_mbps':target,'target_multiple':multiple,
            'relative_target_error':rate/target-1,'within_1pct':abs(rate/target-1)<=.01,
            'first_pts':first,'selected_sorted_packet_positions':[96,336],
            'selected_packets':selected,'output':x.fingerprint(d/'out.mkv')}
    x.dump(d/'packet-window-audit.json',result)
    print(case,tag,rate,'target',target,'within1%',result['within_1pct'])
    return result

if __name__=='__main__':audit(*sys.argv[1:])
