#!/usr/bin/env python3
"""Structured colour detail in the coded base, with the release as the floor.

The base checks elsewhere in the gate are luma-only, so a change that keeps
luma but flattens real colour (lips, small saturated features) passed them.
This encodes the pinned Gentlemen clip with the candidate, decodes it with
film grain OFF, and compares it with the lossless source on the most
colour-structured tenth of 16x16 chroma patches per frame (chosen from the
source alone, exactly flat patches excluded):

  amp  = sqrt(sum base patch variance / sum source patch variance)
  peak = sum of patch p95 |C - neutral| (base) / same for the source

per plane (Cb, Cr). The floor is the reviewed release output already pinned
for the periodic stage; the candidate may not fall more than MARGIN below it
on any of the four numbers. A retained codec-flat chroma encode, which
visibly dulled red lips in blind review, is the labelled negative.
MARGIN is 20x the measured same-binary repeat variation (about 0.0001).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import fixtures

RECT = (0, 160, 1920, 768)  # Gentlemen active picture (2.39:1 inside 1080)
STEP = 2                    # score every second frame
MARGIN = 0.002


def stream(path, grain):
    command = ['ffmpeg', '-v', 'error', '-threads', '4']
    if grain is not None:
        command += ['-c:v', 'libdav1d', '-filmgrain', str(grain)]
    command += ['-i', str(path), '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'yuv420p10le', '-']
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    size = 1920 * 1080 * 3
    try:
        while True:
            data = process.stdout.read(size)
            if len(data) < size:
                break
            planes = np.frombuffer(data, np.uint16).astype(np.float32) / 4
            yield (planes[1920 * 1080:1920 * 1080 * 5 // 4].reshape(540, 960),
                   planes[1920 * 1080 * 5 // 4:].reshape(540, 960))
    finally:
        process.kill(); process.wait()


def tiles(plane):
    x, y, w, h = (v // 2 for v in RECT)
    rows, cols = h // 16, w // 16
    return plane[y:y + rows * 16, x:x + cols * 16].reshape(rows, 16, cols, 16).swapaxes(1, 2).reshape(rows, cols, 256)


def measure(source, encodes):
    """Retained structured colour of each encode (grain off) against the source."""
    sums = {name: np.zeros((2, 2)) for name in ['source', *encodes]}
    streams = [stream(source, None)] + [stream(path, 0) for path in encodes.values()]
    frames = 0
    for index, pictures in enumerate(zip(*streams)):
        if index % STEP:
            continue
        frames += 1
        for plane in range(2):
            source_tiles = tiles(pictures[0][plane])
            spread = source_tiles.std(-1)
            usable = spread > 0
            selected = usable & (spread >= np.quantile(spread[usable], 0.9))
            for name, picture in zip(sums, pictures):
                chosen = tiles(picture[plane])[selected]
                sums[name][plane] += (chosen.var(-1).sum(), np.percentile(np.abs(chosen - 128), 95, axis=-1).sum())
    if frames * STEP < 3600 - STEP:
        raise RuntimeError('incomplete decoded measurement')
    result = {}
    for name in encodes:
        result[name] = {plane: dict(amp=float(np.sqrt(sums[name][i][0] / sums['source'][i][0])),
                                    peak=float(sums[name][i][1] / sums['source'][i][1]))
                        for i, plane in enumerate(('Cb', 'Cr'))}
    return result, frames


def passes(candidate, floor):
    return all(candidate[plane][key] >= floor[plane][key] - MARGIN for plane in floor for key in ('amp', 'peak'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nvencc', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=fixtures.DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    pinned = fixtures.verify(args.root, json.loads(fixtures.MANIFEST.read_text()),
                             ['gentlemen_clip', 'gentlemen_clean_source_positive', 'gentlemen_chroma_detail_negative'])
    source = Path(pinned['gentlemen_clip']['path'])
    output = args.output / 'candidate.mkv'
    command = [str(args.nvencc), '--avsw', '-i', str(source), '--codec', 'av1', '--output-depth', '10',
               '--qvbr', '30', '--max-bitrate', '50000', '--preset', 'quality', '--tune', 'hq',
               '--lookahead', '32', '--lookahead-level', '3', '--aq', '--aq-temporal',
               '--av1-film-grain', 'denoise=auto,chroma=auto,denoiser=bilateral', '-o', str(output)]
    with (args.output / 'encode.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    encodes = {'floor': Path(pinned['gentlemen_clean_source_positive']['path']),
               'negative': Path(pinned['gentlemen_chroma_detail_negative']['path']),
               'candidate': output}
    result, frames = measure(source, encodes)
    report = dict(candidate_sha256=hashlib.sha256(args.nvencc.read_bytes()).hexdigest(),
                  fixtures=pinned, encode_command=command, frames_scored=frames, rect=RECT, margin=MARGIN,
                  retained=result, negative_rejected=not passes(result['negative'], result['floor']),
                  candidate_passed=passes(result['candidate'], result['floor']),
                  scope='Pinned live-action clip; structured colour in the coded base against the reviewed release. '
                        'Not a general colour-fidelity certificate.')
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('retained', 'negative_rejected', 'candidate_passed')}, indent=2))
    if not report['negative_rejected']:
        raise RuntimeError('Known colour-detail loss was not rejected')
    if not report['candidate_passed']:
        raise RuntimeError('Candidate lost structured colour detail against the release floor; see report.json')


if __name__ == '__main__':
    main()
