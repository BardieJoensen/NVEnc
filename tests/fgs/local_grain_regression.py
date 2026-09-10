#!/usr/bin/env python3
"""Offline source-labelled grain regions sharing the same mean brightness.

An average grain amplitude can hide a small quiet or weak-grain region.
Measure each source-defined region on every decoded plane and frame, including
motion and spatially correlated grain. Same QP 20 for plain/old/new arms.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

import numpy as np

import fidelity_compare as fc
from picture_fidelity_regression import planes_at


CASES = {
    'luma_quiet': dict(plane=0, weak=0),
    'luma_weak': dict(plane=0, weak=1),
    'luma_quiet_motion': dict(plane=0, weak=0, motion=True),
    'luma_quiet_correlated': dict(plane=0, weak=0, correlated=True),
    'chroma_quiet': dict(plane=1, weak=0),
    'chroma_weak': dict(plane=1, weak=.5),
    'chroma_quiet_motion': dict(plane=1, weak=0, motion=True),
    'chroma_quiet_pq': dict(plane=1, weak=0, bits=10, color='pq'),
    'chroma_quiet_hlg': dict(plane=1, weak=0, bits=10, color='hlg'),
    'chroma_quiet_correlated': dict(plane=1, weak=0, correlated=True),
    'cr_quiet': dict(plane=2, weak=0),
    'chroma_quiet_coupled': dict(plane=1, weak=0, coupling=.8),
    'chroma_quiet_anticoupled': dict(plane=1, weak=0, coupling=-.8),
    'chroma_quiet_transition': dict(plane=1, weak=0, transition=True),
    'chroma_coupling_entry': dict(plane=1, weak=3, strong=4, luma_correlated=True,
                                 coupling=.8, quiet_chroma_until=16),
    'luma_medium': dict(plane=0, weak=3),
    'luma_medium_correlated': dict(plane=0, weak=3, correlated=True),
    'luma_boundary_4': dict(plane=0, weak=4, strong=4),
    'luma_boundary_4_correlated': dict(plane=0, weak=4, strong=4, correlated=True),
    'luma_boundary_8': dict(plane=0, weak=8, strong=8),
    'luma_boundary_8_correlated': dict(plane=0, weak=8, strong=8, correlated=True),
    'luma_correlated_uniform': dict(plane=0, weak=6, correlated=True),
    'luma_black_border': dict(plane=0, weak=0, correlated=True, black=True),
    'luma_black_border_pq': dict(plane=0, weak=0, correlated=True, black=True, bits=10, color='pq'),
}


def low_region(spec, frame, width, height):
    x = np.arange(width)
    if spec.get('motion'):
        x = (x - 2 * frame) % width
    band = x * 12 // width
    return np.broadcast_to((band == 5)[None, :], (height, width))


def masks(spec, frame, width, height):
    low = low_region(spec, frame, width, height)
    out = []
    for region in [low, ~low]:
        # Stay away from the changing noise boundary and the image edges.
        interior = region.copy()
        for dx in [-8, 8]:
            interior &= np.roll(region, dx, axis=1)
        interior[:12] = False
        interior[-12:] = False
        interior[:, :12] = False
        interior[:, -12:] = False
        assert interior.sum() > 100
        out.append(interior)
    return out


def generate(root, spec, frames=48, width=768, height=432):
    bits = spec.get('bits', 8)
    ds = 1 << (bits - 8)
    dtype = np.uint8 if bits == 8 else np.uint16
    rng = np.random.default_rng(0x51A4ED)
    paths = [root / n for n in ['source.y4m', 'source.yuv']]
    with paths[0].open('wb') as y4m, paths[1].open('wb') as raw:
        chroma = 'C420mpeg2' if bits == 8 else 'C420p10'
        y4m.write(f'YUV4MPEG2 W{width} H{height} F24:1 Ip A1:1 {chroma}\n'.encode())
        for frame in range(frames):
            y4m.write(b'FRAME\n')
            luma_noise = None
            for plane, strength in enumerate([spec.get('strong', 6), 3, 3]):
                w, h = (width, height) if plane == 0 else (width // 2, height // 2)
                noise = rng.normal(size=(h, w))
                if (spec.get('correlated') and spec['plane'] == plane) or (spec.get('luma_correlated') and plane == 0):
                    for axis in [0, 1]:
                        noise = (np.roll(noise, 1, axis) + 2 * noise + np.roll(noise, -1, axis)) / 4
                    noise /= noise.std()
                if plane == 0:
                    luma_noise = noise.reshape(h // 2, 2, w // 2, 2).mean((1, 3))
                    luma_noise /= luma_noise.std()
                elif plane == spec['plane'] and spec.get('coupling'):
                    rho = spec['coupling']
                    noise = rho * luma_noise + np.sqrt(1 - rho * rho) * noise
                sigma = strength
                if plane == spec['plane']:
                    weak = spec['weak'] if not spec.get('transition') or 16 <= frame < 32 else strength
                    sigma = np.where(low_region(spec, frame, w, h), weak, strength)
                    if frame < spec.get('quiet_chroma_until', 0):
                        sigma = 0
                mean = np.where(low_region(spec, frame, w, h), 16, 128) if spec.get('black') and plane == 0 else 128
                data = np.clip(np.rint((mean + noise * sigma) * ds), 0, (1 << bits) - 1).astype(dtype)
                y4m.write(data.tobytes())
                raw.write(data.tobytes())
    return dict(width=width, height=height, bits=bits, frames=frames,
                hashes={p.name: fc.sha(p) for p in paths})


def measure(root, directory, spec, info):
    width, height, bits, frames = [info[k] for k in ['width', 'height', 'bits', 'frames']]
    ds = 1 << (bits - 8)
    dtype = np.uint8 if bits == 8 else np.uint16
    paths = {'source': root / 'source.yuv'}
    for grain, key in [(0, 'off'), (1, 'on')]:
        path = directory / f'grain-{grain}.yuv'
        fc.command(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                    '-threads', '2', '-filmgrain', str(grain), '-i', str(directory / 'output.mkv'),
                    '-map', '0:v:0', '-an', '-sn', '-pix_fmt', 'yuv420p' if bits == 8 else 'yuv420p10le',
                    '-fps_mode', 'passthrough', '-f', 'rawvideo', str(path)], directory / f'decode-{grain}.log')
        paths[key] = path
    size = frames * width * height * 3 // 2 * np.dtype(dtype).itemsize
    assert all(p.stat().st_size == size for p in paths.values())
    mapped = {k: np.memmap(p, dtype=dtype, mode='r').reshape(frames, -1) for k, p in paths.items()}
    trace = []
    for frame in range(frames):
        pictures = {k: planes_at(a, frame, width, height) for k, a in mapped.items()}
        row = dict(frame=frame, planes=[])
        for plane in range(3):
            w, h = (width, height) if plane == 0 else (width // 2, height // 2)
            regions = masks(spec, frame, w, h)
            values = {}
            for key in ['source', 'off', 'on']:
                highpass = fc.quality_metrics.highpass(pictures[key][plane]) / ds
                values[key] = [dict(mean=float(pictures[key][plane][mask].mean() / ds),
                                    sigma=float(pictures[key][plane][mask].std() / ds),
                                    hf_sigma=float(highpass[mask].std())) for mask in regions]
            delta = (pictures['on'][plane].astype(float) - pictures['off'][plane]) / ds
            values['synthesis_sigma'] = [float(delta[mask].std()) for mask in regions]
            row['planes'].append(values)
        if spec.get('coupling') and frame >= spec.get('quiet_chroma_until', 0):
            row['correlation'] = {}
            for key in ['source', 'off', 'on']:
                y = pictures[key][0].astype(float).reshape(height // 2, 2, width // 2, 2).mean((1, 3))
                c = pictures[key][spec['plane']].astype(float)
                region = masks(spec, frame, width // 2, height // 2)[1]
                row['correlation'][key] = float(np.corrcoef(y[region], c[region])[0, 1])
        trace.append(row)
    return dict(trace=trace, decoded_hashes={k: fc.sha(paths[k]) for k in ['off', 'on']})


def check(case, arm='candidate'):
    errors = []
    for row, plain in zip(case['arms'][arm]['trace'], case['arms']['plain']['trace']):
        if 'correlation' in row:
            corr = row['correlation']
            tolerance = max(.10, abs(plain['correlation']['off'] - corr['source']) + .02)
            if abs(corr['on'] - corr['source']) > tolerance:
                errors.append(f'frame {row["frame"]}: source luma/chroma grain correlation lost')
        for plane, values in enumerate(row['planes']):
            for region in range(2):
                source = values['source'][region]
                output = values['on'][region]
                ordinary = plain['planes'][plane]['off'][region]
                if abs(output['mean'] - source['mean']) > .5:
                    errors.append(f'frame {row["frame"]} plane {plane} region {region}: mean shift')
                upper = max(1.25 * source['sigma'], source['sigma'] + .5, ordinary['sigma'] + .25)
                lower = min(.75 * source['sigma'], .95 * ordinary['sigma'])
                if output['sigma'] > upper or (source['sigma'] >= 2 and output['sigma'] < lower):
                    errors.append(f'frame {row["frame"]} plane {plane} region {region}: grain amplitude {output["sigma"]:.3f}, source {source["sigma"]:.3f}, plain {ordinary["sigma"]:.3f}')
                if ((case['spec'].get('correlated') and plane == case['spec']['plane'])
                        or (case['spec'].get('luma_correlated') and plane == 0)):
                    hf_upper = max(1.15 * source['hf_sigma'], ordinary['hf_sigma'] * 1.05 + .1)
                    if output['hf_sigma'] > hf_upper:
                        errors.append(f'frame {row["frame"]} plane {plane} region {region}: excess fine-grain energy')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline', 'candidate', 'scanner', 'output-dir']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--cases', choices=list(CASES), nargs='+', default=list(CASES))
    args = parser.parse_args()
    if len(set(args.cases)) != len(args.cases):
        parser.error('Duplicate cases')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, passed=False, started_at=time.time(), cases=[],
                  baseline_sha256=fc.sha(args.baseline), candidate_sha256=fc.sha(args.candidate),
                  scanner_sha256=fc.sha(args.scanner), harness_sha256=fc.sha(__file__),
                  helpers_sha256={n: fc.sha(Path(__file__).with_name(n))
                                  for n in ['fidelity_compare.py', 'picture_fidelity_regression.py', 'fgs_kat.py']})

    def save():
        tmp = args.output_dir / 'report.tmp'
        tmp.write_text(json.dumps(report, indent=2) + '\n')
        tmp.replace(args.output_dir / 'report.json')

    save()
    try:
        for name in args.cases:
            spec = CASES[name]
            root = args.output_dir / name
            root.mkdir()
            case = dict(name=name, spec=spec, source=generate(root, spec), arms={})
            report['cases'].append(case)
            for arm, binary in [('plain', args.baseline), ('previous_auto', args.baseline), ('candidate', args.candidate)]:
                directory = root / arm
                row = fc.encode(binary, directory, root / 'source.y4m', spec, 20, arm != 'plain',
                                case['source']['frames'], .1 if arm != 'plain' else None, film_grain=arm != 'plain')
                scan = subprocess.run([str(args.scanner), str(directory / 'output.mkv')],
                                      capture_output=True, text=True, check=True, timeout=120)
                row['scan'] = json.loads(scan.stdout)
                if not (row['scan'].get('complete') and row['scan'].get('verdict') == 'stable'
                        and row['scan'].get('criterion') == 'synthesis_texture_v1'
                        and row['scan'].get('packets') == case['source']['frames']):
                    raise ValueError('Incomplete or unsafe synthesis scan')
                row.update(measure(root, directory, spec, case['source']))
                case['arms'][arm] = row
                save()
            case['errors'] = check(case)
            case['previous_errors'] = check(case, 'previous_auto')
            print(name, 'previous errors', len(case['previous_errors']), 'candidate errors', len(case['errors']),
                  'fallbacks', case['arms']['candidate']['source_fallbacks'], flush=True)
            save()
        report.update(complete=True, passed=not any(c['errors'] for c in report['cases']), finished_at=time.time())
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
