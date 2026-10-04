#!/usr/bin/env python3
"""Regenerate private full-history amplitude witnesses; never deploy or overwrite inputs.

Prepared 2026-10-04. Execution requires a completed, exact Play Dirty original.
The output manifest is preparation evidence, not a passing amplitude/local gate.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

TASK = Path('/tmp/downloads/codex-work/fgs-improvement-20261004')
SOURCE_BYTES = 8667928469
SOURCE_SHA = 'd4a348ec7afc3dd22a66a492f2c804a49392ba8de1afc5aa244c548f4e15934d'
NEGATIVE = Path('/opt/docker-apps/logs/fgs-ripple-repair-20260906/bin/nvencc-ef5c61fe')
NEGATIVE_SHA = 'd8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b'
CANDIDATE = TASK / 'bin/nvencc-kernels'
CANDIDATE_SHA = 'be7a50a1681fc5aa9a7133533f081d4e3253b2c74bc639605358f69d591ababe'
CANDIDATE_CORE = '6e8fa1fb1a2b06e64b8c4a19af392bc5adfe5c5e'
FRAMES = 183661
BUDGET = 40 * 1024**3
HEADROOM = 1024**3
TIMEOUT = 6 * 60 * 60
CHUNK = 8 * 1024**2
FGS_ARGS = [
    '--avhw', '--timestamp-passthrough', '--allow-other-negative-pts',
    '--video-track', '1', '-i', '<source>', '--codec', 'av1', '--output-depth', '10',
    '--qvbr', '30', '--max-bitrate', '50000', '--av1-film-grain',
    'denoise=auto,chroma=auto,denoiser=bilateral', '--preset', 'quality',
    '--tune', 'hq', '--lookahead', '32', '--lookahead-level', '3', '--aq',
    '--aq-temporal', '--colormatrix', 'auto', '--colorprim', 'auto',
    '--transfer', 'auto', '--colorrange', 'auto', '--chromaloc', 'auto',
    '--master-display', 'copy', '--max-cll', 'copy', '--video-metadata', 'copy',
    '-o', '<output>',
]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def signature(value):
    s = value if isinstance(value, os.stat_result) else Path(value).stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def write_json(path, value):
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)  # Only files in this newly owned run directory.


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def stable_hash(path, expected=None):
    before = signature(path)
    digest = sha256(path)
    require(signature(path) == before, f'File changed during hash: {path}')
    if expected:
        require(digest == expected, f'SHA mismatch: {path}: {digest} != {expected}')
    return dict(path=str(path), sha256=digest, stat=before)


def check_budget(root):
    # Own run only: never scan source/download/library trees.
    used = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    free = shutil.disk_usage(root).free
    require(used <= BUDGET, f'40 GiB run budget exceeded: {used} bytes')
    require(free >= HEADROOM, f'Insufficient scratch headroom: {free} bytes free')
    return dict(used_bytes=used, free_bytes=free, budget_bytes=BUDGET)


def checked_command(command, root, prefix, timeout=60, env=None):
    write_json(root / (prefix + '-command.json'), command)
    started = now()
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    (root / (prefix + '.stdout')).write_text(result.stdout)
    (root / (prefix + '.stderr')).write_text(result.stderr)
    write_json(root / (prefix + '-runtime.json'), dict(started_at=started,
               finished_at=now(), returncode=result.returncode, argv=command))
    require(result.returncode == 0, f'{prefix} failed: exit {result.returncode}')
    return result


def copy_source(source, root):
    destination = root / 'source.mkv'
    before = signature(source)
    require(before['bytes'] == SOURCE_BYTES, f'Wrong/incomplete source size: {before["bytes"]}')
    digest = hashlib.sha256()
    written = 0
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        require(signature(os.fstat(incoming.fileno())) == before, 'Source changed before copy')
        require(stat.S_ISREG(os.fstat(incoming.fileno()).st_mode), 'Source must be a regular file')
        for block in iter(lambda: incoming.read(CHUNK), b''):
            written += len(block)
            require(written <= SOURCE_BYTES, 'Source grew while copying')
            digest.update(block)
            outgoing.write(block)
            if written % (128 * 1024**2) == 0:
                check_budget(root)
        outgoing.flush()
        os.fsync(outgoing.fileno())
        require(signature(os.fstat(incoming.fileno())) == before, 'Open source changed during copy')
    after = signature(source)
    require(after == before, 'Source path changed during copy')
    require(written == SOURCE_BYTES and digest.hexdigest() == SOURCE_SHA,
            f'Incomplete/wrong original: bytes={written}, SHA={digest.hexdigest()}')
    require(destination.stat().st_nlink == 1, 'Copy unexpectedly has other hard links')
    require((destination.stat().st_dev, destination.stat().st_ino) !=
            (before['device'], before['inode']), 'Copy aliases the original')
    copied = stable_hash(destination, SOURCE_SHA)
    destination.chmod(0o400)  # Our independent copy only; never chmod the original.
    copied['stat'] = signature(destination)
    require(signature(source) == before, 'Original changed during destination verification')
    receipt = dict(original=str(source), original_before=before, original_after=after,
                   streamed_bytes=written, streamed_sha256=digest.hexdigest(),
                   copy=copied, independent_copy=True, original_modified=False)
    write_json(root / 'source-copy.json', receipt)
    return destination, copied


def encoder_arguments(source, target, plain):
    args = FGS_ARGS.copy()
    args[args.index('-i') + 1] = str(source)
    args[args.index('-o') + 1] = str(target)
    if plain:
        i = args.index('--av1-film-grain')
        del args[i:i+2]
    require(not any(x in args for x in ('--seek', '--frames', '--trim')), 'History truncated')
    return args


def encode(binary, expected_sha, source, source_stat, root, label, plain, env):
    arm = root / label
    arm.mkdir()
    target = arm / 'video.mkv'
    require(not target.exists(), 'Refusing existing output')
    identity = stable_hash(binary, expected_sha)
    require(signature(source) == source_stat, 'Private source changed before encode')
    command = [str(binary), *encoder_arguments(source, target, plain)]
    write_json(arm / 'command.json', command)
    runtime = dict(started_at=now(), command=command, runtime='native host',
                   encoder_sha256=identity['sha256'], source_stat_before=source_stat,
                   scope='Full history from first input picture; video-only, no seek/frame limit',
                   temporary_environment={'TMPDIR':env['TMPDIR'], 'CUDA_CACHE_PATH':env['CUDA_CACHE_PATH']})
    write_json(arm / 'runtime.json', runtime)
    started = time.monotonic()
    process = None
    try:
        check_budget(root)
        with (arm / 'encode.log').open('xb') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, env=env)
            runtime['pid'] = process.pid
            write_json(arm / 'runtime.json', runtime)
            while process.poll() is None:
                require(time.monotonic() - started <= TIMEOUT, f'{label} timed out')
                check_budget(root)
                time.sleep(2)
            runtime['returncode'] = process.returncode
        require(process.returncode == 0, f'{label} encode failed: {process.returncode}')
    finally:
        # This exact child is owned by this invocation; no process-name pattern is used.
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
        runtime.update(finished_at=now(), elapsed_seconds=time.monotonic() - started,
                       returncode=process.returncode if process else None)
        write_json(arm / 'runtime.json', runtime)
    require(signature(source) == source_stat, 'Private source changed during encode')
    require(signature(binary) == identity['stat'], 'Encoder changed during encode')
    text = (arm / 'encode.log').read_text(errors='replace')
    counts = re.findall(r'\bencoded\s+(\d+)\s+frames\b', text)
    require(counts and counts[-1] == str(FRAMES), f'{label}: encoded frame count is {counts}')
    require(target.is_file() and target.stat().st_size > 0, f'{label}: output absent/empty')
    before_probe = signature(target)
    probe_cmd = ['ffprobe', '-v', 'error', '-err_detect', 'explode', '-threads', '2',
                 '-select_streams', 'v:0', '-count_frames', '-show_entries',
                 'stream=codec_name,width,height,pix_fmt,avg_frame_rate,r_frame_rate,nb_read_frames,start_time,color_range,color_space,color_transfer,color_primaries:format=duration,size',
                 '-of', 'json', str(target)]
    probe = checked_command(probe_cmd, arm, 'ffprobe', timeout=TIMEOUT, env=env)
    require(not probe.stderr.strip(), f'{label}: ffprobe reported decode errors')
    require(signature(target) == before_probe, f'{label}: output changed during frame counting')
    metadata = json.loads(probe.stdout)
    streams = metadata.get('streams', [])
    require(len(streams) == 1, f'{label}: missing video stream')
    video = streams[0]
    require(video.get('codec_name') == 'av1' and video.get('width') == 1920 and
            video.get('height') == 800 and video.get('pix_fmt') == 'yuv420p10le',
            f'{label}: unexpected video metadata: {video}')
    require(video.get('nb_read_frames') == str(FRAMES), f'{label}: decoded frame count differs')
    output_identity = stable_hash(target)
    require(output_identity['stat'] == before_probe, f'{label}: output changed after frame counting')
    result = dict(label=label, complete=True, command=command, runtime=runtime,
                  source_sha256=SOURCE_SHA, encoder_sha256=identity['sha256'],
                  encoded_frames=int(counts[-1]), ffprobe=metadata, **output_identity)
    write_json(arm / 'report.json', result)
    check_budget(root)
    return result


def interrupted(signum, frame):
    raise KeyboardInterrupt(f'Interrupted by signal {signum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path,
                        help='Completed exact original under /tmp/downloads; never a partial file')
    parser.add_argument('--output', type=Path,
                        help='New directory directly below task scratch; must not exist')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    require(source.is_relative_to(Path('/tmp/downloads').resolve()),
            'Only the user-reacquired /tmp/downloads source is admitted')
    require(source.is_file() and source.stat().st_size == SOURCE_BYTES,
            'Source missing or incomplete; expected exact original byte size')
    output = (args.output or TASK / ('amplitude-regenerated-' +
              dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).absolute()
    require(output.parent.resolve() == TASK.resolve(), 'Output must be directly below task scratch')
    require(not output.exists() and not output.is_symlink(), 'Output already exists; use a fresh path')
    require(shutil.disk_usage(TASK).free >= BUDGET, 'Need at least 40 GiB free scratch')
    for binary in (NEGATIVE, CANDIDATE):
        require(binary.is_file() and os.access(binary, os.X_OK), f'Encoder unavailable: {binary}')
    require(shutil.which('ffprobe'), 'ffprobe is required')
    output.mkdir(mode=0o700)
    signal.signal(signal.SIGTERM, interrupted)
    status = dict(started_at=now(), complete=False, stage='preflight',
                  candidate_core=CANDIDATE_CORE, candidate_sha256=CANDIDATE_SHA,
                  original=str(source), output=str(output), budget_bytes=BUDGET,
                  generation_only=True, amplitude_gate_passed=False, local_full_gate_passed=False)
    try:
        write_json(output / 'status.json', status)
        (output / 'README.md').write_text(
            'Owned Codex FGS amplitude regeneration, 2026-10-04. Exact source copied independently; '
            'three full-history AV1 witnesses, hashes and commands. Never installed or exposed to Emby. '
            'Regenerate with regenerate_amplitude.py and the exact pinned original/binaries. '
            'Retain until qualification review; scratch is not a backup. Failure leaves partial evidence '
            'and no amplitude manifest. Generation alone is not a release gate pass.\n')
        (output / 'regenerate_amplitude.py').write_bytes(Path(__file__).read_bytes())
        tmp = output / 'tmp'
        tmp.mkdir()
        env = os.environ.copy()
        env.update(TMPDIR=str(tmp), CUDA_CACHE_PATH=str(output / 'cuda-cache'), PYTHONDONTWRITEBYTECODE='1')
        identities = {}
        for label, binary, expected in [('negative', NEGATIVE, NEGATIVE_SHA),
                                        ('candidate', CANDIDATE, CANDIDATE_SHA)]:
            identities[label] = stable_hash(binary, expected)
            checked_command([str(binary), '--version'], output, label + '-version', env=env)
            loader = checked_command(['ldd', str(binary)], output, label + '-ldd', env=env)
            require('not found' not in loader.stdout, f'{label}: missing native library')
        checked_command(['ffprobe', '-version'], output, 'ffprobe-version', env=env)
        write_json(output / 'encoder-identities.json', identities)
        status.update(stage='copying_and_verifying_source');write_json(output / 'status.json', status)
        copied_source, copied = copy_source(source, output)
        results = {}
        for label, binary, expected, plain in [('negative', NEGATIVE, NEGATIVE_SHA, False),
                                               ('reference', NEGATIVE, NEGATIVE_SHA, True),
                                               ('candidate', CANDIDATE, CANDIDATE_SHA, False)]:
            status.update(stage='encoding_' + label);write_json(output / 'status.json', status)
            results[label] = encode(binary, expected, copied_source, copied['stat'], output, label, plain, env)
        require(signature(copied_source) == copied['stat'], 'Private source changed before publication')
        for label, result in results.items():
            require(signature(Path(result['path'])) == result['stat'], f'{label}: finalized file changed')
        manifest = {'source':dict(path=str(copied_source), sha256=SOURCE_SHA)}
        for label, result in results.items():
            manifest[label] = dict(path=result['path'], sha256=result['sha256'],
                                   encoder_sha256=result['encoder_sha256'])
        manifest['reference']['mode'] = 'Same full source/settings and historical encoder; only --av1-film-grain removed'
        manifest['provenance'] = dict(candidate_core=CANDIDATE_CORE, expected_frames=FRAMES,
              complete_history=True, source_copy_receipt=str(output / 'source-copy.json'),
              witness_windows={'city':{'seconds':856.333,'frames':12},
                               'dialogue':{'seconds':5727.583,'frames':12}},
              preparation_only=True, amplitude_gate_passed=False, local_full_gate_passed=False)
        status.update(stage='complete', complete=True, finished_at=now(),
                      results=results, storage=check_budget(output))
        write_json(output / 'status.json', status)
        # Publish last, only after every arm and all independent checks finish.
        write_json(output / 'amplitude-manifest.json', manifest)
        print(str(output / 'amplitude-manifest.json'), flush=True)
        return 0
    except BaseException as error:
        status.update(stage='failed', complete=False, finished_at=now(), error=repr(error))
        write_json(output / 'status.json', status)
        raise


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f'amplitude regeneration failed: {error}', file=sys.stderr)
        sys.exit(2)
