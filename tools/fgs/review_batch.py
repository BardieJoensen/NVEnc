#!/usr/bin/env python3
"""Run a finite, resumable list of bounded grain reviews; no quality verdicts."""
import argparse
import fcntl
import html
import json
import math
from pathlib import Path
import re
import time
import review_window as review


def requests(manifest, binary, output):
    document = json.loads(manifest.read_text())
    if document.get('schema') != 'fgs_review_batch_v1' or not document.get('cases'):
        raise ValueError('expected a nonempty fgs_review_batch_v1 manifest')
    names, result = set(), []
    for case in document['cases']:
        if set(case) - {'name', 'file', 'role', 'sha256', 'start', 'duration', 'sample_period',
                        'peak_nits', 'sdr_white_nits', 'assume_bt709', 'stream_index', 'timeout'}:
            raise ValueError('unknown case option; refusing a silent default')
        name = case['name']
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}', name) or name in names:
            raise ValueError('case names must be unique safe directory names')
        names.add(name)
        args = argparse.Namespace(file=(manifest.parent / case['file']).resolve(), binary=binary,
            output_dir=output/name, start=case.get('start', 0), duration=case.get('duration', 2),
            sample_period=case.get('sample_period', .25), peak_nits=case.get('peak_nits', 1000),
            sdr_white_nits=case.get('sdr_white_nits', 100), assume_bt709=case.get('assume_bt709', False),
            stream_index=case.get('stream_index'), timeout=case.get('timeout', 300))
        numeric = (args.start, args.duration, args.sample_period, args.peak_nits, args.sdr_white_nits, args.timeout)
        if (not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in numeric)
                or args.start < 0 or args.duration <= 0 or args.sample_period < 0 or args.timeout <= 0
                or not 100 <= args.peak_nits <= 10000 or not 20 <= args.sdr_white_nits <= 1000
                or not isinstance(args.assume_bt709, bool)
                or (args.stream_index is not None and (type(args.stream_index) is not int or args.stream_index < 0))):
            raise ValueError('invalid display/window options for '+name)
        expected = case.get('sha256')
        if expected is not None and not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('invalid source SHA-256 for '+name)
        result.append((case, args))
    return result


def publish(output, state):
    review.write(output/'status.json', state)
    rows = []
    for case in state['cases']:
        link = '<a href="'+case['name']+'/report.html">'+html.escape(case['name'])+'</a>' if case['status'] == 'complete' else html.escape(case['name'])
        rows.append('<tr><td>'+link+'</td><td>'+html.escape(case.get('role', ''))+'</td><td>'
            +str(case.get('frames', ''))+'</td><td>'+html.escape(case['status'])+'</td><td>'
            +html.escape(case.get('error', ''))+'</td></tr>')
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Grain review batch</title>'
        '<style>body{font:16px system-ui;margin:30px;max-width:1200px}td,th{padding:9px;text-align:left;border-bottom:1px solid #ccc}</style>'
        '<h1>Grain review batch</h1><p>Full spatial coverage of explicitly sampled windows. Completion means the measurements finished; it is not a clean/damaged verdict. Scores require scene and display context.</p>'
        '<p>'+str(state['completed'])+' of '+str(state['total'])+' windows completed; '+str(state['errors'])+' errors.</p>'
        '<table><tr><th>Window</th><th>Context</th><th>Frames measured</th><th>Status</th><th>Issue</th></tr>'
        +''.join(rows)+'</table>')


def batch(manifest, binary, output):
    jobs = requests(manifest, binary, output)
    output.mkdir(parents=True, exist_ok=True)
    with (output/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = dict(started_at=time.time(), total=len(jobs), completed=0, errors=0, finished=False,
            manifest_sha256=review.sha(manifest), batch_sha256=review.sha(__file__),
            binary_sha256=review.sha(binary), wrapper_sha256=review.sha(review.__file__), cases=[])
        pinned = {}
        for case, args in jobs:
            state.update(current=case['name'], updated_at=time.time())
            publish(output, state)
            entry = dict(name=case['name'], role=case.get('role', ''), status='error')
            try:
                if review.sha(binary) != state['binary_sha256'] or review.sha(review.__file__) != state['wrapper_sha256']:
                    raise ValueError('inspector or wrapper changed during batch')
                pinned_signature = None
                if case.get('sha256'):
                    pinned_signature = review.signature(args.file)
                    identity = (str(args.file), tuple(pinned_signature.values()))
                    if identity not in pinned:
                        pinned[identity] = review.sha(args.file)
                    if pinned[identity] != case['sha256']:
                        raise ValueError('source SHA-256 does not match the pinned fixture')
                result = review.inspect(args)
                if pinned_signature is not None and result['request']['source_signature'] != pinned_signature:
                    raise ValueError('source changed between fixture verification and measurement')
                entry.update(status='complete', frames=result['summary']['frames'])
                state['completed'] += 1
            except Exception as error:
                entry['error'] = str(error)[-1800:]
                state['errors'] += 1
            state['cases'].append(entry)
        state.update(current=None, finished=True, updated_at=time.time())
        publish(output, state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    state = batch(args.manifest.resolve(), args.binary.resolve(), args.output_dir.resolve())
    print(json.dumps({key:state[key] for key in ('total', 'completed', 'errors', 'finished')}))
    raise SystemExit(2 if state['errors'] else 0)


if __name__ == '__main__':
    main()
