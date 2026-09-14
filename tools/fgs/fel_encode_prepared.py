#!/usr/bin/env python3
"""Encode one prepared FEL source into scratch, with no library installation.

The caller owns admission and playback policy. A successful encode still needs
whole-file validation, final track-preserving muxing and playback qualification.
Raw pictures travel through a FIFO and are never stored or sent to Docker logs.
"""
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import fel_metadata as fm
from fel_prepare import signature
from fel_process import supervise


def image_id(value):
    if not value.startswith('sha256:') or len(value) != 71:
        raise ValueError('An immutable image ID is required')
    actual = json.loads(subprocess.check_output(['docker', 'image', 'inspect', value]))[0]['Id']
    if actual != value: raise ValueError('Container image identity changed')
    return value


def mastering_metadata(source, destination):
    command = ['ffprobe', '-v', 'error', '-threads', '2', '-select_streams', 'v:0',
        '-read_intervals', '%+#60', '-show_frames', '-show_entries', 'frame=side_data_list',
        '-of', 'json', str(source)]
    text = subprocess.check_output(command, text=True, timeout=120)
    Path(destination).write_text(text)
    values = [side for frame in json.loads(text)['frames']
              for side in frame.get('side_data_list', [])
              if side['side_data_type'] == 'Mastering display metadata']
    if not values or any(v != values[0] for v in values):
        raise ValueError('Missing or changing source mastering display metadata')
    return values[0], command


def commands(config, job, runtime_image, encoder_image, encoder, mastering, metadata_report):
    job = Path(job).resolve()
    components, metadata = Path(config['components']), Path(config['metadata'])
    fifo = job / 'input.y4m.fifo'
    graph = dict(config, runtime='/opt/fel/runtime', cache=str(job / 'index'))
    manifest = job / 'reconstruct.json'
    manifest.write_text(json.dumps(graph, indent=2) + '\n')
    names = ['fgs-fel-producer-' + str(os.getpid()), 'fgs-fel-encoder-' + str(os.getpid())]
    common = ['docker', 'run', '--rm', '--init', '--read-only', '--network', 'none',
        '--log-driver', 'none', '--tmpfs', '/tmp:rw,size=128m', '--user', '1000:1000']
    mounts = ['-v', str(job) + ':' + str(job), '-v', str(metadata) + ':' + str(metadata) + ':ro']
    producer = [*common, '--name', names[0], '--cpus', '4', '--memory', '6g', '--memory-swap', '6g',
        *mounts, '-v', str(components) + ':' + str(components) + ':ro', runtime_image,
        '--requests', '2', '--container', 'y4m', '--arg', 'manifest=' + str(manifest),
        '/opt/fel/tools/fel_input.vpy', str(fifo)]
    hdr = fm.static_hdr_arguments(mastering, metadata_report['authoring_level6'])
    encoder_args = ['--y4m', '-i', str(fifo), '--codec', 'av1', '--output-depth', '10',
        '--qvbr', '29', '--max-bitrate', '50000', '--av1-film-grain',
        'denoise=auto,chroma=auto,denoiser=bilateral', '--film-grain-scene-cuts',
        str(metadata / 'scene-cuts.txt'), '--preset', 'quality', '--tune', 'hq',
        '--lookahead', '32', '--lookahead-level', '3', '--aq', '--aq-temporal',
        '--colormatrix', 'bt2020nc', '--colorprim', 'bt2020', '--transfer', 'smpte2084',
        '--colorrange', 'limited', '--chromaloc', '0', *hdr, '--dolby-vision-profile', '10.1',
        '--dolby-vision-rpu', str(metadata / 'pq-rpu.bin'), '--log-level', 'vpp=debug',
        '-o', str(job / 'encoded.mkv')]
    consumer = [*common, '--name', names[1], '--gpus', 'all', '--cpus', '2', '--memory', '4g',
        '--memory-swap', '4g', *mounts, '-v', str(encoder) + ':/candidate/nvencc:ro',
        '--entrypoint', '/candidate/nvencc', encoder_image, *encoder_args]
    return [producer, consumer], names, hdr


def control(names, paused=None):
    for name in reversed(names):
        if paused is None:
            subprocess.run(['docker', 'unpause', name], capture_output=True, timeout=15)
            subprocess.run(['docker', 'stop', '-t', '3', name], capture_output=True, timeout=30)
        else:
            state = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=15)
            if state.returncode: continue  # Already completed and removed.
            state = json.loads(state.stdout)[0]['State']
            if state['Running'] and state['Paused'] != paused:
                subprocess.run(['docker', 'pause' if paused else 'unpause', name],
                               capture_output=True, check=True, timeout=15)


def encode(prepared, job, runtime_image, encoder_image, encoder, encoder_sha256,
           should_pause=lambda: False, timeout=12 * 3600):
    prepared, job = Path(prepared).resolve(strict=True), Path(job).resolve()
    proof = json.loads((prepared / 'preparation.json').read_text())
    if proof.get('complete') is not True or proof.get('stage') != 'prepared':
        raise ValueError('Complete source preparation is required')
    source = Path(proof['source'])
    if signature(source) != proof['source_signature']:
        raise ValueError('Retained source changed')
    # Offset sources need separately qualified mux synchronization; never
    # silently reset their video clock while retaining the original audio.
    if Fraction(proof['clock']['first_pts']) != 0:
        raise ValueError('Nonzero source video start is not yet qualified')
    runtime_image, encoder_image = image_id(runtime_image), image_id(encoder_image)
    encoder = Path(encoder).resolve(strict=True)
    if fm.sha(encoder) != encoder_sha256:
        raise ValueError('Encoder binary identity changed')
    config = json.loads((prepared / 'reconstruct.json').read_text())
    metadata = Path(config['metadata'])
    mr = json.loads((metadata / 'metadata-report.json').read_text())
    if (mr.get('complete') is not True or mr.get('reconstruction_contract') != 'p7-fel-pq-bt2020-v2'
            or mr['frames'] != proof['clock']['frames']):
        raise ValueError('Qualified complete metadata preparation is required')
    seconds = float(Fraction(proof['clock']['duration']))
    reserve = 32 * 1024**3
    # Two video containers, retained non-video streams and 16 GiB mux overhead.
    remaining = int(seconds * 50000000 / 8) * 2 + 16 * 1024**3 + reserve
    if shutil.disk_usage(prepared).free < remaining:
        raise ValueError('Insufficient space for encoding and the final mux')
    job.mkdir(parents=True, exist_ok=False)
    mastering, probe_command = mastering_metadata(source, job / 'source-mastering.json')
    pair, names, hdr = commands(config, job, runtime_image, encoder_image, encoder, mastering, mr)
    record = dict(stage='encoding', source=str(source), source_signature=proof['source_signature'],
        prepared=str(prepared), runtime_image=runtime_image, encoder_image=encoder_image,
        encoder=str(encoder), encoder_sha256=encoder_sha256, expected_frames=mr['frames'],
        clock=proof['clock'], static_hdr_arguments=hdr, mastering_probe_command=probe_command,
        containers=names, reserve_bytes=reserve, started_at=time.time(), installed=False,
        tools_sha256={p.name: fm.sha(p) for p in Path(__file__).parent.glob('fel_*.py')})
    def save():
        (job / 'encode.json').write_text(json.dumps(record, indent=2) + '\n')
    save()
    fifo = job / 'input.y4m.fifo'; os.mkfifo(fifo, 0o600)
    def resources():
        if shutil.disk_usage(job).free < reserve:
            raise RuntimeError('Scratch reserve reached')
    try:
        supervise(pair, job, timeout, stop_external=lambda: control(names),
                  should_pause=should_pause, set_paused=lambda value: control(names, value),
                  check_resources=resources, interval=2)
        if signature(source) != proof['source_signature'] or fm.sha(encoder) != encoder_sha256:
            raise ValueError('Source or encoder changed during the job')
        result = job / 'encoded.mkv'
        if not result.is_file() or result.stat().st_size < 100000:
            raise ValueError('Missing or empty encoded video')
        record.update(stage='encoded_unvalidated', encoded_sha256=fm.sha(result),
                      encoded_bytes=result.stat().st_size, finished_at=time.time())
    except BaseException as error:
        record.update(stage='failed', error=repr(error), failed_at=time.time())
        raise
    finally:
        fifo.unlink(missing_ok=True)
        save()
    return record
