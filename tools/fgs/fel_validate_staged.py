"""Validate and remux a complete FEL canary without installing it."""
from decimal import Decimal
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

import fel_metadata as fm
from fel_prepare import clock, signature


def native_frame_times(path):
    """Read Matroska frame starts; mkvextract appends an inferred end, not a frame.

    Verified against MKVToolNix 82.0 src/extract/tracks.cpp::close_timestamp_files.
    TrueHD decoding determines the final audio duration from unchanged samples.
    """
    with Path(path).open() as source:
        if source.readline().strip() != '# timestamp format v2':
            raise ValueError('Unsupported native timestamp export')
        previous, count = None, 0
        for line in source:
            value = Decimal(line.strip()) / 1000
            if not value.is_finite() or (previous is not None and value < previous):
                raise ValueError('Invalid native audio timestamp order')
            if previous is not None: yield previous
            previous, count = value, count + 1
        if count < 2: raise ValueError('Missing native audio frames or end marker')


def truehd_timestamps(path, info, directory, run, label):
    """Export the existing TrueHD clock before its packetizer recalculates it."""
    audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if not any(s['codec_name'] == 'truehd' for s in audio): return []
    run(['mkvmerge', '-J', str(path)], label + '-track-ids.json', timeout=120)
    tracks = json.loads((directory / (label + '-track-ids.json')).read_text())['tracks']
    tracks = [t for t in tracks if t['type'] == 'audio']
    if len(tracks) != len(audio): raise ValueError('Retained audio track identification differs')
    selected = []
    for stream, track in zip(audio, tracks):
        if (stream['codec_name'] == 'truehd') != (track['properties']['codec_id'] == 'A_TRUEHD'):
            raise ValueError('TrueHD track identity differs between readers')
        if stream['codec_name'] != 'truehd': continue
        output = directory / f'{label}-truehd-{track["id"]}-timestamps.txt'
        selected.append(dict(stream_index=stream['index'], track_id=track['id'], path=str(output)))
    run(['mkvextract', str(path), 'timestamps_v2'] +
        [f'{v["track_id"]}:{v["path"]}' for v in selected], label + '-native-timestamps.log')
    return selected


def packet_times(path, stream_indexes, log, native_timestamps=None):
    """Hash every retained stream's packet timing without a huge JSON array."""
    hashes = {index: hashlib.sha256() for index in stream_indexes}
    counts = {index: 0 for index in stream_indexes}
    native = {index: native_frame_times(value) for index, value in (native_timestamps or {}).items()}
    command = ['ffprobe', '-v', 'error', '-show_packets', '-show_entries',
               'packet=stream_index,pts_time,duration_time', '-of', 'compact=p=0', str(path)]
    with Path(log).open('w') as stderr:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr, text=True)
        try:
            for line in process.stdout:
                row = dict(part.split('=', 1) for part in line.strip().split('|') if '=' in part)
                index = int(row.get('stream_index', -1))
                if index not in hashes: continue
                if index in native:
                    try: stored = next(native[index])
                    except StopIteration: raise ValueError('More TrueHD packets than stored timestamps')
                    pts = row.get('pts_time', 'N/A')
                    if pts != 'N/A' and Decimal(pts) != stored:
                        raise ValueError('Demuxed TrueHD PTS differs from its native Matroska clock')
                    # FFprobe can omit the PTS of a second access unit in one
                    # block. Only the exact stored clock may fill that omission.
                    row['pts_time'] = str(stored)
                times = []
                for key in ['pts_time', 'duration_time']:
                    value = row.get(key, 'N/A')
                    times.append(value if value == 'N/A' else str(Decimal(value).normalize()))
                hashes[index].update(('|'.join(times) + '\n').encode())
                # Preserve codec trimming as well as packet starts/durations.
                trim = [row.get(key, 'N/A') for key in ('skip_samples', 'discard_padding',
                                                       'skip_reason', 'discard_reason')]
                hashes[index].update(('|'.join(trim) + '\n').encode())
                counts[index] += 1
            if process.wait() != 0: raise RuntimeError('Retained packet timing scan failed')
            for values in native.values():
                if next(values, None) is not None: raise ValueError('Fewer TrueHD packets than stored timestamps')
        finally:
            if process.poll() is None: process.kill()
            process.wait(); process.stdout.close()
            for values in native.values(): values.close()
    return [dict(packets=counts[index], sha256=hashes[index].hexdigest()) for index in stream_indexes]


def retained_clock(packets, fps, expected):
    """Require the library timeline to match the pictures being reconstructed."""
    observed = clock(packets, Fraction(fps))
    if (observed['frames'] != expected['frames']
            or Fraction(observed['fps']) != Fraction(expected['fps'])
            or Fraction(observed['first_pts']) != Fraction(expected['first_pts'])):
        raise ValueError('Retained library picture clock differs from the original')
    return observed


def validate(job, helpers, scanner, scanner_sha256, rpu_checker, rpu_checker_sha256,
             expected_static, *, retained_library=None, library_signature=None):
    job, helpers = Path(job), Path(helpers)
    if fm.sha(scanner) != scanner_sha256 or fm.sha(rpu_checker) != rpu_checker_sha256:
        raise ValueError('Validation tool identity changed')
    sys.path.insert(0, str(helpers))
    spec = importlib.util.spec_from_file_location('fel_repair_checks', helpers / 'fgs-ripple-repair.py')
    repair = importlib.util.module_from_spec(spec); spec.loader.exec_module(repair)
    encoded = job / 'encoded.mkv'
    encoding = json.loads((job / 'encode.json').read_text())
    if encoding['stage'] != 'encoded_unvalidated' or fm.sha(encoded) != encoding['encoded_sha256']:
        raise ValueError('A completed, unchanged canary encode is required')
    source = Path(encoding['source'])
    if signature(source) != encoding['source_signature']: raise ValueError('Retained source changed')
    if (retained_library is None) != (library_signature is None):
        raise ValueError('Library path and expected identity must be supplied together')
    retained = source if retained_library is None else Path(retained_library)
    retained_signature = encoding['source_signature'] if library_signature is None else library_signature
    if signature(retained) != retained_signature: raise ValueError('Retained track source changed')
    directory = job / 'validation'; directory.mkdir(exist_ok=False)
    record = dict(passed=False, installed=False, stage='checking_video', started_at=time.time(),
        scope='complete automated mux/decode/metadata qualification; physical playback remains separate',
        source=str(source), source_signature=encoding['source_signature'],
        retained_track_source=str(retained), retained_track_signature=retained_signature,
        commands=[], helpers_sha256={p.name: fm.sha(p) for p in helpers.glob('*.py')})
    def save():
        path = directory / 'validation.new.json'
        path.write_text(json.dumps(record, indent=2) + '\n'); path.replace(directory / 'validation.json')
    def run(command, name, timeout=12 * 3600):
        record['commands'].append(command); save()
        repair.run(command, directory / name, timeout=timeout)
    save()
    try:
        before, video_info = repair.probe(retained), repair.probe(encoded)
        (directory / 'retained-probe.json').write_text(json.dumps(before, indent=2) + '\n')
        if retained_library is not None:
            record['stage'] = 'checking_library_alignment'; save()
            run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets',
                 '-show_entries', 'packet=pts_time', '-of', 'json', str(retained)],
                'library-clock.json')
            packets = json.loads((directory / 'library-clock.json').read_text())['packets']
            record['library_clock'] = retained_clock(packets,
                repair.video(before)['avg_frame_rate'], encoding['clock'])
            del packets
            original_info = repair.probe(source)
            (directory / 'source-probe.json').write_text(json.dumps(original_info, indent=2) + '\n')
            record['library_content_alignment'] = repair.content_check(source, retained, original_info, before)
            record['stage'] = 'checking_video'; save()
        fm.require_fields(repair.video(video_info), dict(codec_name='av1', width=3840, height=2160,
            pix_fmt='yuv420p10le', color_range='tv', color_space='bt2020nc', color_transfer='smpte2084',
            color_primaries='bt2020', chroma_location='left'), 'encoded video')
        dv = next(d for d in repair.video(video_info)['side_data_list'] if d['side_data_type'] == 'DOVI configuration record')
        fm.require_fields(dv, dict(dv_profile=10, dv_bl_signal_compatibility_id=1,
            bl_present_flag=1, el_present_flag=0, rpu_present_flag=1), 'encoded Dolby configuration')
        run([str(scanner), str(encoded)], 'encoded-grain-scan.json')
        repair.validate_grain_scan(json.loads((directory / 'encoded-grain-scan.json').read_text()))
        a = ['ffmpeg', '-v', 'error', '-nostdin', '-i', str(encoded), '-map', '0:v:0', '-c', 'copy', '-f', 'obu', '-']
        b = [str(rpu_checker)]; record['commands'] += [a, b]; save()
        with (directory / 'roundtrip-rpu.bin').open('wb') as out, (directory / 'roundtrip.json').open('w') as log, (directory / 'obu-extract.log').open('w') as errors:
            first = subprocess.Popen(a, stdout=subprocess.PIPE, stderr=errors)
            second = subprocess.Popen(b, stdin=first.stdout, stdout=out, stderr=log); first.stdout.close()
            try:
                rc2 = second.wait(timeout=3600); rc1 = first.wait(timeout=60)
                if rc1 or rc2: raise RuntimeError('Complete Dolby/static HDR extraction failed')
            finally:
                for process in [first, second]:
                    if process.poll() is None: process.kill()
                    process.wait()
        hdr = json.loads((directory / 'roundtrip.json').read_text())
        prepared = Path(encoding['prepared'])
        graph = json.loads((prepared / 'reconstruct.json').read_text())
        expected_rpu = Path(graph['metadata']) / 'pq-rpu.bin'
        if (hdr.get('complete') is not True or hdr['rpus'] != encoding['expected_frames']
                or fm.sha(directory / 'roundtrip-rpu.bin') != fm.sha(expected_rpu)):
            raise ValueError('Complete Dolby metadata or frame correspondence changed')
        if ({(v['type'], v['payload_hex']) for v in hdr['static_hdr']} !=
            {(v['type'], v['payload_hex']) for v in expected_static}):
            raise ValueError('Static HDR differs from the decoded qualified reference')
        record['metadata'] = hdr
        record['stage'] = 'muxing'; save()
        original_timing = truehd_timestamps(retained, before, directory, run, 'retained')
        timestamp_options = [item for value in original_timing
                             for item in ['--timestamps', f'{value["track_id"]}:{value["path"]}']]
        completed = job / 'complete.mkv'
        if completed.exists(): raise ValueError('Final canary output already exists')
        order = repair.replacement_track_order(encoded, retained)
        run(['mkvmerge', '--engage', 'keep_whitespaces_in_text_subtitles', '--track-order', order,
            '-o', str(completed), '--no-audio', '--no-subtitles', '--no-buttons', '--no-attachments',
            '--no-global-tags', '--no-chapters', str(encoded), '--no-video'] +
            timestamp_options + [str(retained)], 'mux.log')
        after = repair.probe(completed)
        (directory / 'final-probe.json').write_text(json.dumps(after, indent=2) + '\n')
        if repair.video_signal_summary(repair.video(after)) != repair.video_signal_summary(repair.video(video_info)):
            raise ValueError('Final mux changed video signalling')
        if repair.nonvideo_summary(before) != repair.nonvideo_summary(after):
            raise ValueError('Retained track metadata or attachments changed')
        record['chapters'] = dict(passed=True, method='ffprobe_exact')
        if repair.chapter_summary(before) != repair.chapter_summary(after):
            record['chapters'] = repair.compare_stored_chapters(retained, completed, directory)
        record['stage'] = 'checking_retained_tracks'; save()
        old_hashes = repair.stream_hashes(retained, directory / 'retained-stream-hashes.txt', before)
        new_hashes = repair.stream_hashes(completed, directory / 'final-stream-hashes.txt', after)
        record['retained_payloads'] = dict(passed=True, method='exact_stream_hashes')
        if old_hashes != new_hashes:
            record['retained_payloads'] = repair.compare_nonvideo_payloads(
                retained, completed, before, after, old_hashes, new_hashes, directory)
        final_timing = truehd_timestamps(completed, after, directory, run, 'final')
        record['native_truehd_timestamps'] = dict(source=original_timing, final=final_timing,
            method='explicit original Matroska frame starts; inferred trailing end is not a frame')
        timings = []
        for path, info, label in [(retained, before, 'retained'), (completed, after, 'final')]:
            indexes = [v['index'] for v in info['streams'] if v['codec_type'] in ['audio', 'subtitle']]
            native = original_timing if label == 'retained' else final_timing
            timings.append(packet_times(path, indexes, directory / (label + '-packet-times.log'),
                                        {v['stream_index']: v['path'] for v in native}))
        if timings[0] != timings[1]: raise ValueError('Retained audio/subtitle packet timing changed')
        record['retained_packet_timing'] = timings[0]
        for path, label in [(encoded, 'encoded'), (completed, 'final')]:
            run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-map', '0:v:0',
                 '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'], label + '-video-hash.txt')
        if (directory / 'encoded-video-hash.txt').read_text() != (directory / 'final-video-hash.txt').read_text():
            raise ValueError('Mux changed the encoded video payload')
        run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_packets',
            '-show_entries', 'packet=pts_time', '-of', 'csv=p=0', str(completed)], 'final-clock.csv')
        fps, count = Fraction(encoding['clock']['fps']), 0
        with (directory / 'final-clock.csv').open() as times:
            for count, line in enumerate(times, 1):
                if abs(Fraction(line.strip()) - Fraction(count - 1) / fps) > Fraction(1, 1000):
                    raise ValueError('Final video clock differs from the source')
        if count != encoding['expected_frames']: raise ValueError('Final video frame count differs')
        record['stage'] = 'strict_full_decode'; save()
        progress = directory / 'decode-progress.txt'
        run(['ffmpeg', '-v', 'error', '-nostdin', '-xerror', '-err_detect', 'explode', '-threads', '2',
            '-c:v', 'libdav1d', '-i', str(completed), '-map', '0:v:0', '-an', '-sn', '-dn',
            '-fps_mode', 'passthrough', '-progress', str(progress), '-stats_period', '30',
            '-f', 'null', '-'], 'strict-decode.log')
        decoded = [int(line.split('=', 1)[1]) for line in progress.read_text().splitlines() if line.startswith('frame=')]
        if not decoded or decoded[-1] != count: raise ValueError('Incomplete strict decoded output')
        if signature(source) != encoding['source_signature']: raise ValueError('Retained source changed')
        if signature(retained) != retained_signature: raise ValueError('Retained track source changed')
        record.update(passed=True, stage='automated_checks_passed', frames=count,
            output=str(completed), output_sha256=fm.sha(completed), output_bytes=completed.stat().st_size,
            source_bytes=source.stat().st_size, finished_at=time.time(),
            retained_track_source_bytes=retained.stat().st_size,
            physical_playback_qualified=False, source_decode_validation_required=True)
    except BaseException as error:
        record.update(stage='failed', error=repr(error), failed_at=time.time())
        raise
    finally:
        save()
    return record
