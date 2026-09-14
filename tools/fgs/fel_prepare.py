#!/usr/bin/env python3
"""Prepare one complete retained FEL source for an isolated encoding job.

Never modifies the source or a media library. A failed/partial directory is not
reusable as a successful preparation. Run under the documented CPU/memory cap.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time

import fel_layer_order
import fel_metadata


def signature(path):
    value = Path(path).stat()
    return dict(device=value.st_dev, inode=value.st_ino, size=value.st_size, mtime_ns=value.st_mtime_ns)


def clock(packets, fps):
    if fps <= 0 or not packets:
        raise ValueError('Missing source picture clock')
    pts = sorted(Fraction(p['pts_time']) for p in packets)
    if len(set(pts)) != len(pts):
        raise ValueError('Duplicate source picture timestamps')
    first = pts[0]
    if any(abs(t - first - Fraction(n, 1) / fps) > Fraction(1, 1000) for n, t in enumerate(pts)):
        raise ValueError('Source is not frame-preserving CFR within Matroska rounding')
    return dict(frames=len(pts), fps=str(fps), first_pts=str(first), last_pts=str(pts[-1]),
                duration=str(Fraction(len(pts), 1) / fps), method='every source video packet PTS')


def prepare(source, directory, runtime, dovi_tool, reserve_bytes=32 * 1024**3):
    source = Path(source).resolve(strict=True)
    directory = Path(directory).resolve()
    runtime = Path(runtime).resolve(strict=True)
    before = signature(source)
    # Demultiplexed video + up to two 50-Mbit/s output containers + reserve.
    probe_command = ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_chapters',
                     '-of', 'json', str(source)]
    probe = json.loads(subprocess.check_output(probe_command, text=True, timeout=120))
    videos = [v for v in probe['streams'] if v['codec_type'] == 'video' and not v.get('disposition', {}).get('attached_pic')]
    if len(videos) != 1:
        raise ValueError('Exactly one ordinary video track is required')
    video = videos[0]
    fel_metadata.require_fields(video, dict(codec_name='hevc', width=3840, height=2160,
        pix_fmt='yuv420p10le', color_space='bt2020nc', color_transfer='smpte2084',
        color_primaries='bt2020', color_range='tv', chroma_location='topleft'), 'source video')
    dv = next(d for d in video.get('side_data_list', []) if d['side_data_type'] == 'DOVI configuration record')
    fel_metadata.require_fields(dv, dict(dv_profile=7, rpu_present_flag=1, el_present_flag=1,
                                       bl_present_flag=1), 'source Dolby configuration')
    duration = float(probe['format']['duration'])
    required = before['size'] + int(duration * 50000000 / 8) * 2 + reserve_bytes
    directory.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory.parent).free < required:
        raise ValueError(f'Insufficient scratch space: reserve at least {required} bytes')
    directory.mkdir(exist_ok=False)
    report = dict(complete=False, stage='source_clock', started_at=time.time(), source=str(source),
        source_signature=before, required_free_bytes=required, reserve_bytes=reserve_bytes,
        dovi_tool=str(dovi_tool), dovi_tool_sha256=fel_metadata.sha(dovi_tool), commands=[probe_command])
    def save():
        (directory / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    def command(args, name, timeout=14400):
        report['commands'].append(args); save()
        with (directory / (name + '.log')).open('w') as log:
            subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)
    save()
    (directory / 'source-probe.json').write_text(json.dumps(probe, indent=2) + '\n')
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets',
               '-show_entries', 'packet=pts_time,duration_time', '-of', 'json', str(source)]
        report['commands'].append(cmd); save()
        with (directory / 'source-packets.json').open('w') as output, (directory / 'source-packets.log').open('w') as log:
            subprocess.run(cmd, stdout=output, stderr=log, check=True, timeout=14400)
        packets = json.loads((directory / 'source-packets.json').read_text())['packets']
        report['clock'] = clock(packets, Fraction(video['avg_frame_rate']))
        del packets
        report['stage'] = 'demultiplexing'; save()
        producer = ['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(source),
            '-map', '0:v:0', '-c:v', 'copy', '-bsf:v', 'hevc_mp4toannexb', '-f', 'hevc', '-']
        consumer = [str(dovi_tool), 'demux', '-i', '-', '-b', str(directory / 'BL.hevc'),
                    '-e', str(directory / 'EL.hevc')]
        report['commands'] += [producer, consumer]; save()
        reason = []
        stop = threading.Event()
        with (directory / 'extract.log').open('w') as one, (directory / 'demux.log').open('w') as two:
            first = subprocess.Popen(producer, stdout=subprocess.PIPE, stderr=one)
            second = subprocess.Popen(consumer, stdin=first.stdout, stdout=two, stderr=subprocess.STDOUT)
            first.stdout.close()
            def watch():
                deadline = time.monotonic() + 14400
                while not stop.wait(2):
                    if shutil.disk_usage(directory).free < reserve_bytes or time.monotonic() > deadline:
                        reason.append('scratch reserve or time limit reached')
                        for process in [first, second]:
                            if process.poll() is None: process.kill()
                        return
            watcher = threading.Thread(target=watch, daemon=True); watcher.start()
            try:
                rc2 = second.wait(); rc1 = first.wait()
                if rc1 or rc2 or reason: raise ValueError('Source demultiplexing failed: ' + str(reason or [rc1, rc2]))
            finally:
                stop.set(); watcher.join()
                for process in [first, second]:
                    if process.poll() is None: process.kill()
                    process.wait()
        report['stage'] = 'metadata_and_layer_order'; save()
        command([str(dovi_tool), 'extract-rpu', '-i', str(directory / 'EL.hevc'),
                 '-o', str(directory / 'RPU.bin')], 'extract-rpu')
        count = report['clock']['frames']
        metadata = directory / 'metadata'
        fel_metadata.prepare(directory / 'RPU.bin', metadata, dovi_tool, count)
        bl, el = fel_layer_order.trace(directory / 'BL.hevc', timeout=14400), fel_layer_order.trace(directory / 'EL.hevc', timeout=14400)
        layers = fel_layer_order.compare(bl, el, count)
        layers.update(bl=bl, el=el)
        (metadata / 'layer-order.json').write_text(json.dumps(layers, indent=2) + '\n')
        config = dict(runtime=str(runtime), components=str(directory), cache=str(directory / 'cache'),
            metadata=str(metadata), fps=report['clock']['fps'],
            component_sha256={name: fel_metadata.sha(directory / name) for name in ['BL.hevc', 'EL.hevc', 'RPU.bin']},
            runtime_sha256={name: fel_metadata.sha(runtime / name)
                for name in ['prefix/lib/libffms2.so', 'build/felbaker/libfelbaker.so']})
        if signature(source) != before:
            raise ValueError('Retained original changed during preparation')
        (directory / 'reconstruct.json').write_text(json.dumps(config, indent=2) + '\n')
        report.update(complete=True, stage='prepared', finished_at=time.time())
    except BaseException as error:
        report.update(stage='failed', error=str(error), failed_at=time.time())
        raise
    finally:
        save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--dovi-tool', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.output_dir, args.runtime, args.dovi_tool)
