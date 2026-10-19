#!/usr/bin/env python3
"""Read-only Pantheon sample audit using the installed campaign GPU metrics."""
import importlib.util, json, os, pathlib, re, statistics, subprocess, sys
import numpy as np

ROOT = pathlib.Path(os.environ.get('PANTHEON_AUDIT_DIR', '/tmp/downloads/codex-work/pantheon-s02e05-grain-20261019'))
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

inv = json.loads(pathlib.Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-20261019/inventory.json').read_text())
item = next(i for i in inv if i['episode']=='S02E05')
save('inputs.json', {k:item[k] for k in ('episode','original','library')})
results = json.loads((ROOT/'results.json').read_text()) if (ROOT/'results.json').exists() else {}
for ts in (1420,1440,1460):
    key = str(ts)
    if key in results: continue
    d = ROOT/key; d.mkdir(exist_ok=True)
    ref,on,off = [str(d/n) for n in ('ref.mkv','on.mkv','off.mkv')]
    print(key, 'decode', flush=True)
    audit.decode(item['original'],ts,ref)
    audit.decode(item['library'],ts,on,dav1d=True,grain=1)
    audit.decode(item['library'],ts,off,dav1d=True,grain=0)
    row={'timestamp_seconds':ts,'frames':N,'alignment':alignment(ref,off)}
    assert row['alignment']['zero_is_best'], row
    for arm,path in [('source',ref),('on',on),('off',off)]:
        subprocess.run(['ffmpeg','-v','error','-y','-i',path,'-vf','select=eq(n\\,120)','-frames:v','1',str(d/(arm+'-120.png'))],check=True)
    print(key,'score',flush=True)
    for arm,path in [('on',on),('off',off)]:
        scores=campaign.score(ref,path,arm,str(d),1080,N)
        doc=json.loads((d/f'metrics-cuda-{arm}.json').read_text())
        perfect=normalize_ciede(doc,ref,path)
        scores.update(audit.pooled(doc))
        scores['ciede_finite_mean']=scores.pop('ciede'); scores.pop('ciede2000')
        scores['ciede_perfect_frames']=perfect
        for prefix in ('ssimu2','butter'):
            assert len(json.loads((d/f'{prefix}-{arm}.json').read_text()))==N
        row[arm]=scores
    results[key]=row; save('results.json',results)
    print(key,json.dumps(row),flush=True)
