#!/usr/bin/env python3
"""Run a finite audit concurrently using separately pinned measurement tools."""
import argparse
import collections
import concurrent.futures
import fcntl
import importlib.util
import json
from pathlib import Path
import signal
import sys
import threading
import time


def ordered_items(items, priorities, completed):
    identities = [(item['key'], item['version']) for item in items]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate file/version in audit manifest')
    # Each library key owns one report directory; simultaneous versions would
    # also compete for the current file and cannot both describe it.
    if len({item['key'] for item in items}) != len(items):
        raise ValueError('multiple versions of one library file in audit queue')
    return sorted(items, key=lambda item: (
        (item['key'], item['version']) not in completed,
        priorities.get(item['key'], float('inf')),
        not bool(item.get('repair_receipt')),
        -item.get('installed_at', 0), item['path']))


def header_phase_complete(path, consumer_started, now=None):
    now = time.time() if now is None else now
    try:
        state = json.loads(Path(path).read_text())
    except FileNotFoundError:
        # The producer can still be loading its manifest when the consumer
        # starts. Allow bounded startup, without silently waiting forever.
        if now-consumer_started < 60:
            return False
        raise RuntimeError('header producer did not publish its initial status')
    if not state.get('phase_complete') and now-state['updated_at'] > 15000:
        raise RuntimeError('header producer stopped publishing; manual resume required')
    return state.get('phase_complete', False)


def run_queue(items, workers, header_for, measure, publish, resource_error,
              headers_finished, stop, sleep=time.sleep):
    """Only the coordinator publishes; failed admission keeps a file pending."""
    if not 1 <= workers <= 4:
        raise ValueError('workers must be between one and four')
    pending = list(items)
    results = []
    active = {}
    paused = None
    publish(results, pending, active, paused)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        while pending or active:
            if not stop.is_set() and paused is None:
                for item in list(pending):
                    if len(active) >= workers:
                        break
                    header = header_for(item)
                    if header is None:
                        continue
                    pending.remove(item)
                    active[pool.submit(measure, item, header)] = item
            if active:
                done, _ = concurrent.futures.wait(active, timeout=1,
                    return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    item = active.pop(future)
                    try:
                        result = future.result()
                    except resource_error as error:
                        pending.insert(0, item)
                        paused = str(error)
                    except Exception as error:
                        # Unexpected orchestration failures must not consume
                        # unmeasured media or label it damaged.
                        pending.insert(0, item)
                        paused = 'audit worker failed: ' + str(error)
                    else:
                        if (result.get('key'), result.get('version')) != (item['key'], item['version']):
                            pending.insert(0, item)
                            paused = 'audit worker returned another file/version'
                        else:
                            results.append(result)
                publish(results, pending, active, paused)
                continue
            if paused is not None or stop.is_set():
                break
            if pending:
                try:
                    finished = headers_finished()
                except Exception as error:
                    paused = 'header producer status unavailable: ' + str(error)
                    break
                if finished:
                    results.extend(dict(key=item['key'], version=item['version'],
                                        status='header_missing') for item in pending)
                    pending.clear()
                    break
            if pending:
                publish(results, pending, active, paused)
                sleep(10)
    if stop.is_set() and pending and paused is None:
        paused = 'operator requested a stop after active files finished'
    publish(results, pending, active, paused)
    return 75 if paused else 0


def load_measurements(directory, qualification):
    # The frozen module remains the identity of the measurement method.
    # Changing this scheduler does not invalidate unchanged decoded evidence.
    directory = directory.resolve()
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location('qualified_decoded_audit', directory/'decoded_library_audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, expected in qualification['tools'].items():
        if module.audit.sha(directory/name) != expected:
            raise ValueError('measurement tool pin mismatch: ' + name)
    if Path(module.source_review.__file__).resolve() != directory/'source_plane_review.py':
        raise ValueError('source measurement imported outside pinned directory')
    if Path(module.audit.__file__).resolve() != directory/'library_audit.py':
        raise ValueError('header helper imported outside pinned directory')
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--headers', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--measurement-tools', type=Path, required=True)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--priorities', type=Path)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3, 4), default=2)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    qualification = json.loads(args.qualification.read_text())
    if manifest.get('schema') != 'fgs_library_audit_v1':
        raise ValueError('invalid manifest')
    method = load_measurements(args.measurement_tools, qualification)
    binary = Path(qualification['binary'])
    pins = dict(binary_sha256=method.audit.sha(binary), binary_signature=method.audit.signature(binary),
                wrapper_sha256=method.audit.sha(method.__file__),
                source_wrapper_sha256=method.audit.sha(method.source_review.__file__))
    if pins['binary_sha256'] != qualification['binary_sha256']:
        raise ValueError('inspector pin mismatch')
    priorities = json.loads(args.priorities.read_text())['priorities'] if args.priorities else {}
    if any(not isinstance(v, (int, float)) or not (-1e20 < v < 1e20) for v in priorities.values()):
        raise ValueError('priorities must be finite numbers')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: stop.set())
    with (args.output_dir/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status_path = args.output_dir/'status.json'
        previous = json.loads(status_path.read_text()) if status_path.exists() else {}
        completed = {(r['key'], r['version']) for r in previous.get('results', [])
                     if r.get('status') == 'measured'}
        items = ordered_items([i for i in manifest['files'] if i.get('codec') == 'av1'], priorities, completed)
        manifest_sha = method.audit.sha(args.manifest)
        began = time.time()
        last_publish = [0.0, -1]

        def publish(results, pending, active, paused):
            now = time.time()
            if pending or active:
                if not paused and now-last_publish[0] < 5 and len(results) == last_publish[1]:
                    return
            last_publish[:] = [now, len(results)]
            method.audit.write(status_path, dict(updated_at=now, started_at=began,
                total=len(items), processed=len(results),
                counts=dict(collections.Counter(row['status'] for row in results)),
                waiting_for_headers=bool(pending) and not active and not paused,
                phase_complete=not pending and not active and not paused, audit_complete=False,
                manifest_sha256=manifest_sha, paused_reason=paused,
                pending_files=len(pending)+len(active), workers=args.workers,
                scheduler_sha256=method.audit.sha(__file__),
                measurement_tools=str(args.measurement_tools), measurement_pins=pins,
                priority_file=str(args.priorities) if args.priorities else None,
                priority_sha256=method.audit.sha(args.priorities) if args.priorities else None,
                active=[dict(key=i['key'], version=i['version'], path=i['path']) for i in active.values()],
                scope='Unchanged qualified full-image/frame measurements in selected windows; flags require visual and recurrence review.',
                results=[{k:row[k] for k in ('key','version','status')} for row in results]))

        def header_for(item):
            path = args.headers/item['key']/item['version']/'report.json'
            return path if path.exists() else None

        def measure(item, path):
            method.require_storage(args.output_dir)
            header = json.loads(path.read_text())
            if header.get('status') != 'complete':
                return dict(key=item['key'], version=item['version'], status='header_'+header['status'])
            result = method.inspect_file(item, path, binary, args.output_dir, pins)
            print(json.dumps(dict(key=item['key'], version=item['version'], status=result['status'])), flush=True)
            return result

        def headers_finished():
            return header_phase_complete(args.headers/'status.json', began)

        return run_queue(items, args.workers, header_for, measure, publish,
                         method.AuditResourceUnavailable, headers_finished, stop)


if __name__ == '__main__':
    raise SystemExit(main())
