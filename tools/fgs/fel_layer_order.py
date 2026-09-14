#!/usr/bin/env python3
"""Compare BL/EL picture order using FFmpeg's independent HEVC header parser."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import threading

from fel_metadata import sha

FIELD = re.compile(r'\]\s+\d+\s+(nal_unit_type|nuh_temporal_id_plus1|'
    r'first_slice_segment_in_pic_flag|slice_pic_order_cnt_lsb|'
    r'log2_max_pic_order_cnt_lsb_minus4)\s+\S+\s+=\s+(\d+)')


def pictures(lines):
    nal = {}
    rows = []
    poc_bits = set()
    def flush():
        if nal.get('first_slice_segment_in_pic_flag') != 1:
            return
        kind = nal.get('nal_unit_type', -1)
        if not 0 <= kind <= 31:
            raise ValueError('Unexpected non-picture first slice')
        if ('nuh_temporal_id_plus1' not in nal
            or (kind not in (19, 20) and 'slice_pic_order_cnt_lsb' not in nal)):
            raise ValueError('Incomplete picture-order header')
        poc = 0 if kind in (19, 20) else nal['slice_pic_order_cnt_lsb']
        rows.append([kind, poc, nal['nuh_temporal_id_plus1']])
    for line in lines:
        match = FIELD.search(line)
        if not match:
            continue
        key, value = match[1], int(match[2])
        if key == 'nal_unit_type':
            flush()
            nal = {}
        if key == 'log2_max_pic_order_cnt_lsb_minus4':
            poc_bits.add(value + 4)
        nal[key] = value
    flush()
    if not rows or rows[0][0] not in (19, 20) or len(poc_bits) != 1:
        raise ValueError('Layer needs an initial IDR and a constant POC width')
    return dict(pictures=rows, poc_bits=sorted(poc_bits), frames=len(rows))


def trace(path, ffmpeg='ffmpeg', timeout=3600):
    original = sha(path)
    command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'info', '-xerror',
               '-i', str(path), '-map', '0:v:0', '-c', 'copy', '-bsf:v', 'trace_headers', '-f', 'null', '-']
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    timer = threading.Timer(timeout, process.kill)
    timer.start()
    try:
        result = pictures(process.stderr)
        if process.wait() != 0:
            raise ValueError('HEVC header trace failed or timed out')
    finally:
        timer.cancel()
        if process.poll() is None: process.kill()
        process.wait()
        process.stderr.close()
    if sha(path) != original:
        raise ValueError('Layer changed during header check')
    result.update(path=str(path), sha256=original, command=command)
    return result


def compare(bl, el, frames):
    if frames <= 0 or bl['frames'] != frames or el['frames'] != frames:
        raise ValueError('BL/EL/expected picture count mismatch')
    if bl['poc_bits'] != el['poc_bits'] or bl['pictures'] != el['pictures']:
        raise ValueError('BL/EL picture order, random-access type or temporal layer mismatch')
    return dict(complete=True, frames=frames, method='ffmpeg_hevc_trace_headers_picture_order_v1',
        limitation='Checks demultiplexed pair correspondence; source provenance and decoded RPU/picture checks are also required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bl', type=Path, required=True)
    parser.add_argument('--el', type=Path, required=True)
    parser.add_argument('--frames', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    # Exclusive output creation prevents silently replacing an earlier receipt.
    with args.output.open('x') as receipt:
        bl, el = trace(args.bl, args.ffmpeg), trace(args.el, args.ffmpeg)
        result = compare(bl, el, args.frames)
        result.update(bl=bl, el=el)
        json.dump(result, receipt, indent=2)
        receipt.write('\n')
