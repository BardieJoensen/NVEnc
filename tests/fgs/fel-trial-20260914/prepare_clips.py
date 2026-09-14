"""Copy bounded dual-layer video clips; never modify source/library media."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

TRIAL = Path('/tmp/downloads/fgs-fel-trial-20260914')
LEDGER = Path('/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-reconstruction-trial-20260914')
DOVI = '/opt/docker-apps/logs/fgs-ripple-repair-20260906/production-readiness-20260909/bin/dovi_tool'


def signature(path):
    st = Path(path).stat()
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size, mtime_ns=st.st_mtime_ns)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def main():
    plan = json.loads((LEDGER / 'work-plan.json').read_text())
    records = []
    for source in plan['sources']:
        probe = json.loads((LEDGER / (source['key'] + '-source-probe.json')).read_text())
        for fraction in [.20, .63]:
            assert signature(source['path']) == source['signature']
            assert shutil.disk_usage(TRIAL).free > 50 * 1024**3
            start = round(float(probe['format']['duration']) * fraction, 3)
            name = source['key'] + '-' + str(round(fraction * 100))
            directory = TRIAL / 'clips' / name
            directory.mkdir()
            record = dict(name=name, source=source['path'], source_signature=source['signature'],
                          requested_start_seconds=start, requested_duration_seconds=6,
                          timing_note='Stream-copy starts at a preceding random-access point; measurements use decoded clip frame indices.',
                          directory=str(directory), commands=[])
            commands = [
                ['ffmpeg', '-hide_banner', '-v', 'warning', '-nostdin', '-ss', str(start),
                 '-i', source['path'], '-t', '6', '-map', '0:v:0', '-c:v', 'copy',
                 '-bsf:v', 'hevc_mp4toannexb', '-f', 'hevc', str(directory / 'combined.hevc')],
                [DOVI, 'demux', '-i', str(directory / 'combined.hevc'),
                 '-b', str(directory / 'BL.hevc'), '-e', str(directory / 'EL.hevc')],
                [DOVI, 'extract-rpu', '-i', str(directory / 'combined.hevc'),
                 '-o', str(directory / 'RPU.bin')],
                [DOVI, 'info', '-i', str(directory / 'RPU.bin'), '-s'],
            ]
            for number, command in enumerate(commands):
                started = time.monotonic()
                result = subprocess.run(command, capture_output=True, text=True, timeout=180)
                (directory / f'command-{number}.log').write_text(result.stdout + result.stderr)
                record['commands'].append(dict(argv=command, returncode=result.returncode,
                                               seconds=time.monotonic()-started))
                if result.returncode:
                    (directory / 'preparation.json').write_text(json.dumps(record, indent=2)+'\n')
                    raise RuntimeError(f'clip preparation failed: {name}, command {number}')
            assert signature(source['path']) == source['signature']
            record['files'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
                               for p in directory.iterdir() if p.suffix in ('.hevc', '.bin')}
            record['prepared_at'] = time.time()
            (directory / 'preparation.json').write_text(json.dumps(record, indent=2)+'\n')
            records.append(record)
            (LEDGER / 'clip-preparation.json').write_text(json.dumps(records, indent=2)+'\n')
            print(name, 'prepared', sum(x['bytes'] for x in record['files'].values()), flush=True)


if __name__ == '__main__':
    main()
