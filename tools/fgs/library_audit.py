#!/usr/bin/env python3
"""Version-bound, read-only displayed-grain inventory audit.

Every header is read. Selected decoded windows are a separate coverage stage;
neither header flags nor stage completion are picture-quality verdicts.
"""
import argparse
import collections
import concurrent.futures
import csv
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

FIELDS = ('frame', 'pts_ms', 'seconds', 'show_existing', 'apply_grain',
          'effective_grain', 'max_y_scaling', 'max_cb_scaling', 'max_cr_scaling', 'scaling_shift')


def signature(path):
    st = Path(path).stat()
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size, mtime_ns=st.st_mtime_ns)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def select_windows(runs, jumps, first, last, limit=12):
    pools = collections.defaultdict(list)
    for i, run in enumerate(runs):
        strength = run['strength']
        if run['on']:
            kind = 'short_on' if run['frames'] <= 2 else 'longer_on' if run['end'] - run['start'] <= 2 else 'sustained_grain'
            pools[kind].append(dict(kind=kind, seconds=run['start'], strength=strength,
                                    run_frames=run['frames'], run_end=run['end']))
            if kind == 'longer_on':
                pools['longer_on_end'].append(dict(kind='longer_on_end', seconds=run['end'],
                    strength=strength, run_frames=run['frames'], run_start=run['start']))
        elif i and i + 1 < len(runs) and run['end'] - run['start'] <= 1:
            pools['short_off'].append(dict(kind='short_off', seconds=run['start'],
                strength=max(runs[i-1]['strength'], runs[i+1]['strength']), run_frames=run['frames']))
    pools['amplitude_change'] = jumps
    selected = []
    # Separate categories prevent high-scaling one-frame flags from exhausting
    # every slot. Spacing is within a category, so a pulse's start/end survive.
    for kind in ('short_on', 'longer_on', 'longer_on_end', 'short_off', 'amplitude_change', 'sustained_grain'):
        accepted = []
        for item in sorted(pools[kind], key=lambda x: (-x['strength'], x['seconds'])):
            if all(abs(item['seconds'] - old['seconds']) >= 30 for old in accepted):
                accepted.append(item)
            if len(accepted) == 2:
                break
        selected.extend(accepted)
    if len(selected) < limit:
        # A file with no on/off transitions still receives temporal coverage.
        for fraction in (.1, .5, .9):
            seconds = first + (last - first) * fraction
            if all(abs(seconds - old['seconds']) >= 1 for old in selected):
                selected.append(dict(kind='timeline_control', seconds=seconds, strength=0))
    windows = []
    for item in selected[:limit]:
        start, stop = max(0, item['seconds'] - .18), min(last + .001, item['seconds'] + .40)
        if stop > start:
            windows.append(dict(item, start=start, stop=stop))
    return windows


def profile_csv(path, completion, expected_frames=None):
    if (completion.get('complete') is not True or completion.get('errors') != 0
            or completion.get('displayed_frames', 0) <= 0):
        raise ValueError('incomplete native header extraction')
    runs, jumps = [], []
    counts = collections.Counter()
    first = previous = None
    last_strength = [0, 0, 0]
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', newline='') as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError('unexpected header CSV schema')
        for index, row in enumerate(reader):
            if None in row or any(v is None for v in row.values()):
                raise ValueError('incomplete CSV row')
            values = {k: float(v) if k == 'seconds' else int(v) for k, v in row.items()}
            seconds = values['seconds']
            if (not math.isfinite(seconds) or values['frame'] != index
                    or (previous is not None and seconds <= previous)):
                raise ValueError('missing frame or non-increasing displayed time')
            for k in ('show_existing', 'apply_grain', 'effective_grain'):
                if values[k] not in (0, 1):
                    raise ValueError('invalid header flag')
            maxima = [values[k] for k in FIELDS[6:9]]
            shift = values['scaling_shift']
            if any(not 0 <= x <= 255 for x in maxima) or shift not in (0, 8, 9, 10, 11):
                raise ValueError('invalid scaling value')
            on = values['effective_grain']
            if on != int(bool(values['apply_grain'] and max(maxima) > 0)) or (on and not shift):
                raise ValueError('inconsistent effective grain state')
            strengths = [x * 2.0 ** (8 - shift) if shift else 0 for x in maxima]
            strength = max(strengths)
            if first is None:
                first = seconds
            if not runs or runs[-1]['on'] != on:
                runs.append(dict(on=on, start=seconds, end=seconds, frames=0, strength=0))
            runs[-1].update(end=seconds, frames=runs[-1]['frames'] + 1,
                            strength=max(runs[-1]['strength'], strength))
            delta = max(abs(a-b) for a, b in zip(strengths, last_strength))
            if previous is not None and on and counts['previous_on'] and delta >= 4:
                jumps.append(dict(kind='amplitude_change', seconds=seconds, strength=delta))
            counts['previous_on'] = on
            counts['frames'] += 1
            counts['grain_on_frames'] += on
            for plane, value in zip(('y', 'cb', 'cr'), strengths):
                counts[plane + '_explicit_scaling_frames'] += int(value > 0)
            previous, last_strength = seconds, strengths
    frames = counts.pop('frames', 0)
    counts.pop('previous_on', None)
    if (frames != completion['displayed_frames'] or frames != completion.get('packets')
            or (expected_frames is not None and frames != expected_frames)):
        raise ValueError('header/frame coverage mismatch')
    return dict(displayed_frames=frames, first_seconds=first, last_seconds=previous,
        on_off_transitions=max(0, len(runs)-1), run_counts=dict(collections.Counter(
            ('on_' if r['on'] else 'off_') + ('1_2' if r['frames'] <= 2 else '3_48' if r['frames'] <= 48 else '49_plus') for r in runs)),
        amplitude_changes=len(jumps), **counts,
        windows=select_windows(runs, jumps, first, previous),
        scope='All displayed headers; selected windows require independent decoded/source review. Scaling is a syntax proxy, not measured grain amplitude. Chroma-from-luma is not separately represented in the legacy CSV.')


def check_identity(item):
    if signature(item['path']) != item['signature']:
        raise RuntimeError('snapshot superseded: library file identity changed')


def audit_one(item, binary, output, scratch, pins):
    directory = output / item['key'] / item['version']
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / 'report.json'
    request = dict(path=item['path'], signature=item['signature'],
                   binary_sha256=pins['binary_sha256'], wrapper_sha256=pins['wrapper_sha256'],
                   expected_frames=item.get('expected_frames'))
    began = time.time()
    result = dict(key=item['key'], version=item['version'], request=request, started_at=began)
    try:
        check_identity(item)
        if signature(binary) != pins['binary_signature']:
            raise RuntimeError('header binary changed')
        if destination.exists():
            old = json.loads(destination.read_text())
            if old.get('status') == 'complete' and old.get('request') == request:
                if sha(old['headers']) == old['headers_sha256']:
                    return old
        if item.get('codec') != 'av1':
            return dict(result, status='outside_av1_scope', codec=item.get('codec'))
        inherited = item.get('header_evidence')
        if inherited:
            prior = json.loads(Path(inherited['summary']).read_text())
            reader_matches = prior.get('header_reader_sha256') == request['binary_sha256']
            if inherited.get('reader_kind') == 'historical_python_tracker':
                proof = json.loads(Path(inherited['reader_equivalence']).read_text())
                reader_matches = (sha(inherited['reader_equivalence']) == inherited['reader_equivalence_sha256']
                    and proof.get('complete') is True and proof.get('binary_sha256') == request['binary_sha256']
                    and bool(proof.get('cases')) and all(c.get('mismatches') == 0 and c.get('returncode') == 0 for c in proof['cases']))
            if (sha(inherited['summary']) != inherited['summary_sha256']
                    or prior.get('installed_signature') != item['signature'] or not reader_matches):
                raise RuntimeError('inherited header evidence does not match snapshot/tool')
            completion = dict(complete=prior['complete'], errors=0, packets=prior['packets'],
                              displayed_frames=prior['displayed_frames'])
            headers = Path(inherited['csv'])
            result['inherited_evidence'] = inherited
        else:
            with tempfile.TemporaryDirectory(prefix=item['key']+'-', dir=scratch) as work:
                work = Path(work)
                with (work/'headers.csv').open('w') as stdout, (directory/'native.log').open('w') as stderr:
                    process = subprocess.run([str(binary), item['path']], stdout=stdout, stderr=stderr,
                        timeout=max(600, min(14400, 180 + item['signature']['size']/(2*1024**2))))
                completion = json.loads((directory/'native.log').read_text().splitlines()[-1])
                if process.returncode:
                    raise RuntimeError('native header scan failed; see native.log')
                # Validate before promoting compressed bytes to durable evidence.
                profile_csv(work/'headers.csv', completion, item.get('expected_frames'))
                headers = directory/'headers.csv.gz'
                with (work/'headers.csv').open('rb') as source, gzip.open(str(headers)+'.tmp', 'wb', compresslevel=1) as target:
                    for block in iter(lambda: source.read(1024*1024), b''):
                        target.write(block)
                os.replace(str(headers)+'.tmp', headers)
        header_sha = sha(headers)
        profile = profile_csv(headers, completion, item.get('expected_frames'))
        check_identity(item)
        if sha(headers) != header_sha or signature(binary) != pins['binary_signature']:
            raise RuntimeError('audit artifact/tool changed during review')
        result.update(status='complete', headers=str(headers), headers_sha256=header_sha,
            completion=completion, profile=profile,
            external_frame_count_kind=item.get('expected_frame_count_kind', 'not_available'),
            picture_quality_verdict='unreviewed')
    except Exception as error:
        result.update(status='superseded' if 'snapshot superseded' in str(error) else 'error', error=str(error))
    result.update(finished_at=time.time(), elapsed_seconds=time.time()-began)
    write(destination, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2, choices=(1, 2, 3, 4))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get('schema') != 'fgs_library_audit_v1':
        raise ValueError('unsupported manifest')
    binary = Path(manifest['header_binary'])
    pins = dict(binary_sha256=sha(binary), binary_signature=signature(binary), wrapper_sha256=sha(__file__))
    if pins['binary_sha256'] != manifest['header_binary_sha256']:
        raise ValueError('header binary pin mismatch')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.scratch.mkdir(parents=True, exist_ok=True)
    with (args.output_dir/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        items = [i for i in manifest['files'] if i.get('codec') == 'av1']
        identities = [(i['key'], i['version']) for i in items]
        if len(set(identities)) != len(identities):
            raise ValueError('duplicate file/version')
        results = []
        manifest_sha = sha(args.manifest)
        def publish():
            counts = dict(collections.Counter(r['status'] for r in results))
            write(args.output_dir/'status.json', dict(updated_at=time.time(), started_at=began,
                total=len(items), processed=len(results), counts=counts,
                phase_complete=len(items)==len(results), audit_complete=False,
                manifest=str(args.manifest), manifest_sha256=manifest_sha,
                scope='Displayed-header coverage only; full library picture review remains a separate stage.',
                results=[{k:r[k] for k in ('key','version','status','elapsed_seconds') if k in r} for r in results]))
        began = time.time()
        publish()
        # Reused headers first, then newly repaired versions, then old media.
        items.sort(key=lambda i: (not bool(i.get('header_evidence')), not bool(i.get('repair_receipt')), i['signature']['size']))
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(audit_one, i, binary, args.output_dir, args.scratch, pins):i for i in items}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                publish()
                if len(results)%25==0 or result['status']!='complete':
                    print(json.dumps(dict(processed=len(results), total=len(items), key=result['key'], status=result['status'])), flush=True)
        if any(r['status']!='complete' for r in results):
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
