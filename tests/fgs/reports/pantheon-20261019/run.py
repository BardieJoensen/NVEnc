#!/usr/bin/env python3
"""Read-only Pantheon sample audit using the installed campaign GPU metrics."""
import importlib.util, json, os, pathlib, re, statistics, subprocess, sys
import numpy as np

ROOT = pathlib.Path(os.environ.get('PANTHEON_AUDIT_DIR', '/tmp/downloads/codex-work/pantheon-quality-20261019'))
ROOT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, '/home/bardie/git-repos/NVEnc/tests/fgs')
import campaign
spec = importlib.util.spec_from_file_location('audit', '/opt/docker-apps/scripts/library-fidelity/libvsorig.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
N = 240

def save(name, obj):
    temp = ROOT / (name + '.tmp')
    temp.write_text(json.dumps(obj, indent=2))
    temp.replace(ROOT / name)

def probe(p):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(p)]))

def video(p):
    return next(s for s in p['streams'] if s['codec_type'] == 'video')

def thumb(p):
    b = subprocess.check_output(['ffmpeg', '-v', 'error', '-threads', '4', '-i', str(p), '-frames:v', '24', '-vf', 'scale=480:270', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
    return np.frombuffer(b, dtype=np.uint8).reshape(-1, 270, 480).astype(np.float32)

def alignment(ref, enc):
    r, e = thumb(ref), thumb(enc)
    costs = {k: float(np.abs(r[4+k:20+k] - e[4:20]).mean()) for k in range(-3, 4)}
    best = min(costs, key=costs.get)
    # Repeated animation frames can tie; zero must be one of the minima.
    return {'costs': costs, 'best_offset': best, 'zero_is_best': costs[0] <= costs[best] + 1e-6}

def framehash(p):
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-threads', '4', '-i', str(p), '-map', '0:v:0', '-f', 'hash', '-hash', 'sha256', '-']).decode().strip()

def normalize_ciede(doc, ref, enc):
    """Exact matches have infinite CIEDE log score, serialized as null."""
    nulls = [f['frameNum'] for f in doc['frames'] if f['metrics']['ciede2000'] is None]
    if nulls:
        def hashes(p):
            text = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(p), '-map', '0:v:0', '-f', 'framemd5', '-']).decode()
            return [line.rsplit(',', 1)[1].strip() for line in text.splitlines() if not line.startswith('#')]
        r, e = hashes(ref), hashes(enc)
        assert all(r[n] == e[n] for n in nulls), 'Nonidentical CIEDE null frame'
        vals = [f['metrics']['ciede2000'] for f in doc['frames'] if f['metrics']['ciede2000'] is not None]
        assert vals, 'Entire window identical; needs separate exact-match reporting'
        doc['pooled_metrics']['ciede2000']['mean'] = statistics.mean(vals)
    return len(nulls)

def vmaf_adapter(ref, enc, models, out, tag, frames):
    doc = audit.vmaf(ref, enc, out, False)
    assert len(doc['frames']) == N, (out, len(doc['frames']))
    normalize_ciede(doc, ref, enc)
    return doc['pooled_metrics']

campaign.vmaf_run = vmaf_adapter
libs = sorted(pathlib.Path('/media/merged-storage/media/cartoon-anime/Pantheon (2022)').rglob('*.mkv'))
origs = {re.search(r'S\d+E\d+', p.name)[0]: p for p in pathlib.Path('/media/merged-storage/media/downloads/long-term-seeding/tv-shows').glob('Pantheon*/*.mkv')}
inventory = []
for p in libs:
    ep = re.search(r'S\d+E\d+', p.name)[0]
    row = {'episode': ep, 'library': str(p), 'library_probe': probe(p)}
    if ep in origs:
        row.update(original=str(origs[ep]), original_probe=probe(origs[ep]))
        a, b = video(row['library_probe']), video(row['original_probe'])
        assert (a['width'], a['height'], a['r_frame_rate']) == (b['width'], b['height'], b['r_frame_rate'])
        assert abs(float(row['library_probe']['format']['duration']) - float(row['original_probe']['format']['duration'])) < .05
    inventory.append(row)
save('inventory.json', inventory)
results = json.loads((ROOT / 'results.json').read_text()) if (ROOT / 'results.json').exists() else {}
for item in inventory:
    ep = item['episode']
    duration = float(item.get('original_probe', item['library_probe'])['format']['duration'])
    for frac in (.2, .5, .8):
        key = f'{ep}-{int(frac*100)}'
        if key in results:
            continue
        d = ROOT / key
        d.mkdir(exist_ok=True)
        ts = round(duration * frac, 3)
        ref, on, off = [str(d / name) for name in ('ref.mkv', 'on.mkv', 'off.mkv')]
        print(key, 'decode', ts, flush=True)
        row = {'episode': ep, 'fraction': frac, 'timestamp_seconds': ts, 'frames': N}
        audit.decode(item['library'], ts, on, dav1d=True)
        if 'original' not in item:
            count = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'json', on]))
            assert int(count['streams'][0]['nb_read_frames']) == N
            row['status'] = 'sample_decode_ok_no_original'
        else:
            audit.decode(item['original'], ts, ref)
            audit.decode(item['library'], ts, off, dav1d=True, grain=0)
            row['alignment'] = alignment(ref, off)
            assert row['alignment']['zero_is_best'], (key, row['alignment'])
            row['grain_changes_pixels'] = framehash(on) != framehash(off)
            print(key, 'score', 'grain differs:', row['grain_changes_pixels'], flush=True)
            for arm, enc in [('on', on)] + ([('off', off)] if row['grain_changes_pixels'] else []):
                scores = campaign.score(ref, enc, arm, str(d), 1080, N)
                doc = json.loads((d / f'metrics-cuda-{arm}.json').read_text())
                perfect = normalize_ciede(doc, ref, enc)
                scores.update(audit.pooled(doc))
                scores['ciede_finite_mean'] = scores.pop('ciede')
                scores.pop('ciede2000')
                scores['ciede_perfect_frames'] = perfect
                for prefix in ('ssimu2', 'butter'):
                    assert len(json.loads((d / f'{prefix}-{arm}.json').read_text())) == N
                row[arm] = scores
            if not row['grain_changes_pixels']:
                row['off'] = dict(row['on'])
                row['off_reused_identical_pixels'] = True
            row['status'] = 'scored'
        results[key] = row
        save('results.json', results)
        print(key, json.dumps(row), flush=True)
        for p in d.iterdir():
            if p.suffix == '.mkv' or p.name.endswith('.ffindex'):
                p.unlink()
save('complete.json', {'windows': len(results), 'scored': sum(r['status'] == 'scored' for r in results.values())})
