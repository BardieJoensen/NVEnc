#!/usr/bin/env python3
"""Compact committed evidence; raw arrays/commands live in evidence archive."""
import json, pathlib, statistics
import investigate as x

out={'archive':'/media/merged-storage/cold-storage/docker-apps/pantheon-independent-investigation','cases':{}}
for case in x.CASES:
    d=x.ROOT/case;v=json.loads((d/'validity.json').read_text())
    row={'reference':{k:v[k] for k in ('source','source_stat','requested_start','fps','source_mbps','first_pts','last_pts','all_240_equal')},'arms':{}}
    for p in sorted(d.glob('*-result.json')):
        tag=p.name[:-len('-result.json')];r=json.loads(p.read_text());r.pop('alignment_all_blocks',None)
        if tag=='clean':r.pop('actual_mbps',None)
        if tag.startswith('library'):r['actual_mbps']=json.loads((d/'library-packets.json').read_text())['mbps']
        tpath=d/(tag+'-texture.json')
        if tpath.exists():
            t=json.loads(tpath.read_text());r['midpoint_texture']=t['midpoint_summary']
            edge=[f['strong_horizontal_edge'] for f in t['frames'] if 'strong_horizontal_edge' in f]
            r['source_selected_edges']={k:statistics.mean(f[k] for f in edge if f[k] is not None) for k in ('gradient_ratio','gradient_mae')}
            shifts=[f['plane_mean_shift'] for f in t['frames'] if 'plane_mean_shift' in f]
            r['mean_plane_shift_8bit']=[statistics.mean(f[i] for f in shifts) for i in range(3)]
            r['brightness_color_hf_ratios']={}
            for b in sorted({k for f in t['brightness_color_samples'] for k in f['bins']}):
                entries=[f['bins'][b] for f in t['brightness_color_samples'] if b in f['bins'] and f['bins'][b]['source']>1e-6]
                r['brightness_color_hf_ratios'][b]=statistics.mean(f['target']/f['source'] for f in entries)
        sel=d/(tag+'-selection.json')
        if sel.exists():r['rate_match']=json.loads(sel.read_text())
        cmd=pathlib.Path(r['encode']).with_name(pathlib.Path(r['encode']).stem+'-command.json')
        if cmd.exists():
            doc=json.loads(cmd.read_text())
            if isinstance(doc,dict):r['encode_wall_seconds']=doc['seconds'];r['encode_fps_336_including_startup']=336/doc['seconds']
        row['arms'][tag]=r
    out['cases'][case]=row
x.dump(x.HERE/'results.json',out)
lines=['| Case / arm | Actual Mbps | VMAF / NEG | SSIMU2 | Butter p95 max | PSNR Y | SSIM | CAMBI | ROI HF / source | ACF1 | wall s |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for case,c in out['cases'].items():
    for tag,r in c['arms'].items():
        t=next(iter(r.get('midpoint_texture',{}).values()),None)
        hf=f"{100*t['target']['hf_sigma']/t['source']['hf_sigma']:.1f}%" if t else '—';acf=f"{t['target']['acf1']:.3f}" if t else '—'
        rate=f"{r['actual_mbps']:.3f}" if 'actual_mbps' in r else 'raw'
        lines.append(f"| {case} / {tag} | {rate} | {r['vmaf']:.2f} / {r['vmaf_neg']:.2f} | {r['ssimu2']:.2f} | {r['butter_max_p95']:.2f} | {r['psnr_y']:.2f} | {r['ssim']:.4f} | {r['pooled']['cambi']['mean']:.3f} | {hf} | {acf} | {r.get('encode_wall_seconds',0):.2f} |")
(x.HERE/'metric-table.md').write_text('\n'.join(lines)+'\n\nROI = purple background for E04, shirt for E05; other regions, all ACF lags, color/brightness bins, CIEDE and source CAMBI in results.json. Raw is uncompressed stage output, not an encode. Wall time is a single sample under shared load, not a throughput benchmark. Zero means timing unavailable or a decoder-only arm.\n')
print('\n'.join(lines))
