#!/usr/bin/env python3
"""Validate and summarize the completed Pantheon sample audit."""
import json, os, pathlib, statistics

ROOT = pathlib.Path(os.environ.get('PANTHEON_AUDIT_DIR', '/tmp/downloads/codex-work/pantheon-quality-20261019'))
results = json.loads((ROOT / 'results.json').read_text())
inventory = json.loads((ROOT / 'inventory.json').read_text())
assert len(results) == 48
assert sum(r['status'] == 'scored' for r in results.values()) == 24

def percentile(a, p):
    a = sorted(a)
    return a[min(len(a)-1, int(len(a)*p/100))]

def aggregate(keys, arm='on'):
    frames, ss, butter = [], [], []
    for key in keys:
        row = results[key]
        assert row['alignment']['zero_is_best']
        use = 'on' if arm == 'off' and row.get('off_reused_identical_pixels') else arm
        d = ROOT / key
        doc = json.loads((d / f'metrics-cuda-{use}.json').read_text())
        f = doc['frames']
        assert len(f) == 240
        assert all(x['metrics'].get(k) is not None for x in f for k in ('vmaf','vmaf_neg','integer_vif_scale0'))
        frames += f
        s = json.loads((d / f'ssimu2-{use}.json').read_text())
        b = json.loads((d / f'butter-{use}.json').read_text())
        assert len(s) == len(b) == 240
        ss += [x[0] for x in s]
        butter += [x[2] for x in b]
    avg = lambda k: statistics.mean(f['metrics'][k] for f in frames)
    ciede = [f['metrics']['ciede2000'] for f in frames if f['metrics']['ciede2000'] is not None]
    return dict(frames=len(frames), vmaf=round(avg('vmaf'),2),
                vmaf_neg=round(avg('vmaf_neg'),2),
                vmaf_p1=round(percentile([f['metrics']['vmaf'] for f in frames if f['frameNum'] != 0],1),2),
                ssimu2=round(statistics.mean(ss),2), ssimu2_p5=round(percentile(ss,5),2),
                butter_max_p95=round(percentile(butter,95),2),
                psnr_y=round(avg('psnr_y'),2), ssim=round(avg('float_ssim'),4),
                ciede_finite_mean=round(statistics.mean(ciede),2),
                ciede_perfect_frames=len(frames)-len(ciede),
                cambi_source=round(avg('cambi_source'),3), cambi=round(avg('cambi'),3))

episodes = {}
keys = [k for k,r in results.items() if r['status'] == 'scored']
for ep in sorted({results[k]['episode'] for k in keys}):
    ek = [k for k in keys if results[k]['episode'] == ep]
    episodes[ep] = aggregate(ek)
summary = {'episodes': episodes, 'season2_on': aggregate(keys), 'season2_off': aggregate(keys,'off'),
           'windows_scored':24, 'windows_decode_only':24,
           'worst_window':min(keys,key=lambda k:results[k]['on']['vmaf']),
           'grain_changes_pixels_windows':sum(results[k]['grain_changes_pixels'] for k in keys)}
(ROOT / 'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
