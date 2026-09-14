"""Supervise the two sides of a bounded reconstruction/encoding job."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def supervise(commands, directory, timeout, stop_external=lambda: None,
              should_pause=lambda: False, set_paused=lambda paused: None,
              check_resources=lambda: None, interval=1):
    """Both processes must succeed; any failure stops the entire owned job.

    commands communicate through a caller-owned FIFO, not Docker's stdout log.
    stop_external must reap any containers because killing a Docker client does
    not stop its container. A caller cancelling the service should also provide
    an ExecStopPost cleanup for interruption outside Python's control.
    """
    directory = Path(directory)
    processes, handles = [], []
    began = time.monotonic()
    report = dict(passed=False, stage='starting', commands=commands,
                  started_at=time.time(), paused=False, pause_events=[])
    def save():
        temporary = directory / 'pipeline.new.json'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(directory / 'pipeline.json')
    save()
    try:
        if len(commands) != 2 or timeout <= 0:
            raise ValueError('Two commands and a positive deadline are required')
        check_resources()
        for index, command in enumerate(commands):
            log = (directory / ('producer.log' if index == 0 else 'encoder.log')).open('wb')
            handles.append(log)
            processes.append(subprocess.Popen(command, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        report['stage'] = 'running'; save()
        while True:
            codes = [p.poll() for p in processes]
            if any(c not in (None, 0) for c in codes):
                raise RuntimeError('Reconstruction/encoder process failed: ' + str(codes))
            if all(c == 0 for c in codes):
                break
            if time.monotonic() - began >= timeout:
                raise TimeoutError('Reconstruction/encoder job deadline reached')
            check_resources()
            paused = bool(should_pause())
            if paused != report['paused']:
                set_paused(paused)
                report['pause_events'].append(dict(paused=paused, at=time.time()))
                report['paused'] = paused; save()
            time.sleep(interval)
        report.update(passed=True, stage='encoded', returncodes=codes)
    except BaseException as error:
        report.update(stage='failed', error=repr(error))
        raise
    finally:
        try:
            stop_external()
        finally:
            for p in processes:
                if p.poll() is None:
                    try: os.killpg(p.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
            for p in processes:
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL); p.wait()
            for handle in handles: handle.close()
            report.update(finished_at=time.time(), seconds=time.monotonic() - began,
                          final_returncodes=[p.returncode for p in processes])
            save()
    return report
