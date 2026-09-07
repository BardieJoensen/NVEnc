#!/usr/bin/env python3
"""Read-only full-image SDR/PQ/HLG review of a bounded video window.

The default is two seconds at four sampled frames/second. Use --sample-period 0
to inspect every displayed frame. No scores authorize repair or downloading.
"""
import argparse
import csv
import fcntl
import hashlib
import html
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

CHANNELS = ('luma', 'red', 'green', 'blue')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def signature(path):
    value = Path(path).stat()
    return dict(device=value.st_dev, inode=value.st_ino, size=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def summarize(frames, tiles, metadata):
    with Path(frames).open() as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != metadata['measured_frames'] or not rows:
        raise RuntimeError('native completion and CSV frame counts disagree')
    if any(not math.isfinite(float(value)) for row in rows for value in row.values()):
        raise RuntimeError('non-finite measurement')
    times = [float(row['seconds']) for row in rows]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise RuntimeError('non-increasing sampled timestamps')
    peaks, directional_peaks = {}, {}
    for channel in CHANNELS:
        row = max(rows, key=lambda row: float(row[channel + '_peak_score']))
        peaks[channel] = dict(seconds=float(row['seconds']),
                              score=float(row[channel + '_peak_score']),
                              p95_area_score=float(row[channel + '_p95_tile_score']),
                              p99_area_score=float(row[channel + '_p99_tile_score']),
                              x=int(row[channel + '_peak_x']), y=int(row[channel + '_peak_y']), tiles=[])
        directional = max(rows, key=lambda row: float(row[channel + '_peak_directional_score']))
        directional_peaks[channel] = dict(seconds=float(directional['seconds']),
            score=float(directional[channel + '_peak_directional_score']),
            x=int(directional[channel + '_directional_x']), y=int(directional[channel + '_directional_y']))
    expected = {row['seconds']: int(row['tiles']) * 4 for row in rows}
    actual = dict.fromkeys(expected, 0)
    width, height = metadata['width'], metadata['height']
    def partition(length):
        result = [(at, min(48, length-at)) for at in range(0, length, 48)]
        if len(result) > 1 and result[-1][1] < 8:
            tail = result.pop()[1]
            result[-1] = (result[-1][0], result[-1][1] + tail)
        return result
    grid = {(x, y, w, h, c) for x, w in partition(width) for y, h in partition(height) for c in range(4)}
    if any(int(row['pixels']) != width * height or int(row['tiles']) * 4 != len(grid) for row in rows):
        raise RuntimeError('frame coverage disagrees with image dimensions')
    seen = {seconds: set() for seconds in expected}
    with Path(tiles).open() as stream:
        for row in csv.DictReader(stream):
            if row['seconds'] not in actual:
                raise RuntimeError('tile dump contains an unexpected frame')
            identity = tuple(int(row[k]) for k in ('x', 'y', 'width', 'height', 'channel'))
            if identity not in grid or identity in seen[row['seconds']]:
                raise RuntimeError('duplicate or invalid tile geometry/channel')
            if any(not math.isfinite(float(value)) for value in row.values()):
                raise RuntimeError('non-finite tile measurement')
            seen[row['seconds']].add(identity)
            actual[row['seconds']] += 1
            channel = CHANNELS[int(row['channel'])]
            if abs(float(row['seconds']) - peaks[channel]['seconds']) < 1e-7:
                peaks[channel]['tiles'].append([int(row[k]) for k in ('x', 'y', 'width', 'height')]
                                               + [float(row['score'])])
    if actual != expected:
        raise RuntimeError('tile dump does not cover every measured frame and channel')
    return dict(frames=len(rows), first_seconds=times[0], last_seconds=times[-1], peaks=peaks,
                directional_peaks=directional_peaks,
                scope='Every image pixel in sampled frames; temporal sampling and this window limit coverage.')


def render(report):
    metadata, summary = report['measurement'], report['summary']
    data = json.dumps(dict(width=metadata['width'], height=metadata['height'], peaks=summary['peaks'])).replace('<', '\\u003c')
    mapping = (f"{metadata['transfer']}; HDR peak {metadata['peak_nits']} nits; "
               f"SDR white {metadata['sdr_white_nits']} nits; "
               f"BT.709 assumption requested: {metadata['assume_bt709_requested']}.")
    return '''<!doctype html><meta charset="utf-8"><title>Grain review window</title>
<style>body{font:16px system-ui;max-width:1050px;margin:30px auto;padding:0 16px;background:#16191f;color:#edf1f6}canvas{width:100%;background:#080b10}select{font:inherit;padding:6px}a{color:#98ccff}.small{color:#b9c2cf}#detail{min-height:2em}</style>
<h1>Grain review window</h1><p>''' + html.escape(Path(report['source']).name) + '''</p>
<p>Full image coverage on ''' + str(summary['frames']) + ''' sampled frames, from ''' + str(summary['first_seconds']) + ''' to ''' + str(summary['last_seconds']) + ''' seconds.</p>
<p class="small">''' + html.escape(mapping) + ''' Static reference display; dynamic HDR tone mapping is not applied. Unknown chroma siting uses centered bilinear reconstruction.</p>
<p>The map shows each channel's strongest sampled frame. Colour represents local texture score in PU21 units. Scores support visual review; there is no universal damage cutoff.</p>
<label>Channel <select id="channel"><option>luma</option><option>red</option><option>green</option><option>blue</option></select></label>
<p id="description"></p><canvas id="map"></canvas><p id="detail" class="small">Move over the map for tile coordinates and score.</p>
<p><a href="report.json">Full report and identities</a> · <a href="frames.csv">Frame measurements</a> · <a href="tiles.csv">Tile measurements</a></p>
<script>const data=''' + data + ''';const canvas=document.getElementById('map'),ctx=canvas.getContext('2d'),select=document.getElementById('channel');
canvas.width=data.width;canvas.height=data.height;
function draw(){const p=data.peaks[select.value];ctx.clearRect(0,0,canvas.width,canvas.height);for(const [x,y,w,h,s] of p.tiles){const f=p.score?s/p.score:0;ctx.fillStyle=`rgb(${Math.round(255*f)},${Math.round(150*Math.sqrt(f))},${Math.round(55+80*(1-f))})`;ctx.fillRect(x,y,w,h);}document.getElementById('description').textContent=`Time ${p.seconds.toFixed(3)} s · local peak ${p.score.toFixed(3)} · area p95 ${p.p95_area_score.toFixed(3)} · area p99 ${p.p99_area_score.toFixed(3)}`;}
select.onchange=draw;canvas.onmousemove=e=>{const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)*data.width/r.width,y=(e.clientY-r.top)*data.height/r.height;const t=data.peaks[select.value].tiles.find(t=>x>=t[0]&&x<t[0]+t[2]&&y>=t[1]&&y<t[1]+t[3]);if(t)document.getElementById('detail').textContent=`Tile x=${t[0]}, y=${t[1]}, ${t[2]}×${t[3]} pixels; score ${t[4].toFixed(4)}`;};draw();</script>'''


def inspect(args):
    source, output = args.file.resolve(), args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('another review is using this output directory') from error
        return inspect_locked(args, source, output)


def inspect_locked(args, source, output):
    request = dict(source=str(source), source_signature=signature(source), binary_sha256=sha(args.binary),
                   wrapper_sha256=sha(__file__),
                   start=args.start, duration=args.duration, sample_period=args.sample_period,
                   peak_nits=args.peak_nits, sdr_white_nits=args.sdr_white_nits,
                   assume_bt709=args.assume_bt709, stream_index=args.stream_index)
    existing = output / 'report.json'
    if existing.exists():
        try:
            previous = json.loads(existing.read_text())
        except (ValueError, OSError):
            previous = {}
        if (previous.get('status') == 'complete' and previous.get('request') == request
                and all((output / name).is_file() and sha(output / name) == previous.get('artifacts', {}).get(name)
                        for name in ('frames.csv', 'tiles.csv'))):
            (output / 'report.html').write_text(render(previous))
            write(output / 'status.json', previous)
            return previous
    report = dict(status='running', request=request, source=str(source), started_at=time.time())
    write(output / 'status.json', report)
    (output / 'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Review running</title>'
        '<p>This review is running. Previous measurements are not the current result.</p>'
        '<p><a href="status.json">Current status</a></p>')
    try:
        with tempfile.TemporaryDirectory(prefix='.attempt-', dir=output) as temporary:
            temp = Path(temporary)
            command = [str(args.binary.resolve()), '--extended', '--sample-period', str(args.sample_period),
                       '--peak-nits', str(args.peak_nits), '--sdr-white-nits', str(args.sdr_white_nits),
                       '--tiles-csv', str(temp / 'tiles.csv')]
            if args.assume_bt709:
                command += ['--assume-bt709']
            if args.stream_index is not None:
                command += ['--stream-index', str(args.stream_index)]
            command += [str(source), str(temp / 'frames.csv'), str(args.start), str(args.start + args.duration)]
            with (output / 'native.log').open('w') as log:
                process = subprocess.run(command, stdout=subprocess.PIPE, stderr=log, text=True, timeout=args.timeout)
            if process.returncode:
                raise RuntimeError((output / 'native.log').read_text()[-1800:])
            metadata = json.loads(process.stdout)
            if metadata.get('schema') != 'fgs_reference_full_v1' or not metadata.get('interval_complete'):
                raise RuntimeError('native inspector did not complete the requested interval')
            if signature(source) != request['source_signature'] or sha(args.binary) != request['binary_sha256']:
                raise RuntimeError('source or inspector changed during measurement')
            summary = summarize(temp / 'frames.csv', temp / 'tiles.csv', metadata)
            report.update(status='complete', measurement=metadata, summary=summary, finished_at=time.time(), artifacts={})
            for name in ('frames.csv', 'tiles.csv'):
                report['artifacts'][name] = sha(temp / name)
                os.replace(temp / name, output / name)
            write(existing, report)
            (output / 'report.html').write_text(render(report))
            write(output / 'status.json', report)
            return report
    except Exception as error:
        report.update(status='error', error=str(error), finished_at=time.time())
        write(output / 'status.json', report)
        (output / 'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Review failed</title>'
            '<p>This review failed: '+html.escape(str(error))+'</p>'
            '<p><a href="status.json">Current status</a></p>')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--duration', type=float, default=2)
    parser.add_argument('--sample-period', type=float, default=.25)
    parser.add_argument('--peak-nits', type=float, default=1000)
    parser.add_argument('--sdr-white-nits', type=float, default=100)
    parser.add_argument('--assume-bt709', action='store_true')
    parser.add_argument('--stream-index', type=int)
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if (not all(math.isfinite(x) for x in (args.start, args.duration, args.sample_period, args.timeout,
                                          args.peak_nits, args.sdr_white_nits))
            or args.start < 0 or args.duration <= 0 or args.sample_period < 0 or args.timeout <= 0):
        parser.error('invalid measurement window or timeout')
    report = inspect(args)
    print(json.dumps(dict(status=report['status'], report=str(args.output_dir / 'report.html'),
                          frames=report['summary']['frames'])))


if __name__ == '__main__':
    main()
