#!/usr/bin/env python3
"""Scalar, arbitrary-precision cross-check of sampled FEL reconstruction codes.

Uses the published FelBaker/DoViBaker fixed-point method, expressed separately
in Python. It checks polynomial/MMR mapping, residual reconstruction, clipping
and the YCC matrix. The HEVC decoder and resampler are shared with the pipeline;
this is not a Dolby-certified independent end-to-end reference decoder.
"""
from bisect import bisect_right
import hashlib
from itertools import accumulate
import json
from pathlib import Path
import sys
import time


def clamp(value, low, high): return max(low, min(high, value))


class Reference:
    def __init__(self, row):
        self.mapping = row['rpu_data_mapping']
        self.curves = self.mapping['curves']
        self.pivots = [list(accumulate(c['pivots'])) for c in self.curves]
        self.denom = row['header']['coefficient_log2_denom']
        self.dm = row['vdr_dm_data']

    def fixed(self, integer, fraction): return (integer << self.denom) + fraction

    def map(self, channel, sample, residual, yuv):
        curve = self.curves[channel]
        bounds = self.pivots[channel]
        segment = bisect_right(bounds[1:-1], sample)
        if curve['mapping_idc'] == 'Polynomial':
            x = clamp(sample, bounds[0], bounds[-1])
            coef = [self.fixed(i, f) << 20 for i, f in
                    zip(curve['poly_coef_int'][segment], curve['poly_coef'][segment])]
            value = coef[-1]
            for c in reversed(coef[:-1]): value = ((value * x) >> 10) + c
        else:
            x, y, z = [clamp(int(v), p[0], p[-1]) << 10 for v, p in zip(yuv, self.pivots)]
            first = [x, y, z, x*y >> 20, x*z >> 20, y*z >> 20, ((x*y >> 20)*z) >> 20]
            second = [v*v >> 20 for v in first]
            third = [a*b >> 20 for a, b in zip(first, second)]
            value = self.fixed(curve['mmr_constant_int'][segment], curve['mmr_constant'][segment]) << 20
            orders = curve['mmr_order_minus1'][segment] + 1
            for power, samples in enumerate([first, second, third][:orders]):
                for i, v in enumerate(samples):
                    value += self.fixed(curve['mmr_coef_int'][segment][power][i],
                                        curve['mmr_coef'][segment][power][i]) * v
        mapped = clamp(max(0, value) >> (self.denom + 4), 0, 65535)
        nlq = self.mapping['nlq']
        offset = nlq['nlq_offset'][channel]
        delta = residual - offset
        dequantized = 0
        if delta:
            slope = self.fixed(nlq['linear_deadzone_slope_int'][channel], nlq['linear_deadzone_slope'][channel])
            threshold = self.fixed(nlq['linear_deadzone_threshold_int'][channel], nlq['linear_deadzone_threshold'][channel]) * 2
            limit = self.fixed(nlq['vdr_in_max_int'][channel], nlq['vdr_in_max'][channel]) * 2
            dequantized = ((2*delta - 1)*slope + threshold if delta > 0
                           else (2*delta + 1)*slope - threshold)
            dequantized = clamp(dequantized, -limit, limit) >> (self.denom - 15)
        return clamp((mapped + dequantized + 8) >> 4, 0, 4095)

    def rgb(self, yuv):
        yuv = [int(v)*16 - (self.dm[f'ycc_to_rgb_offset{i}'] >> 12) for i, v in enumerate(yuv)]
        return [clamp(sum(self.dm[f'ycc_to_rgb_coef{c*3+i}'] * v for i, v in enumerate(yuv)) >> 13,
                      0, 65535) for c in range(3)]


def execute(manifest, destination):
    import numpy as np
    import vapoursynth as vs
    config = json.loads(Path(manifest).read_text())
    runtime, components = Path(config['runtime']), Path(config['components'])
    core = vs.core; core.num_threads = 4; core.max_cache_size = 256
    core.std.LoadPlugin(str(runtime/'prefix/lib/libffms2.so'))
    core.std.LoadPlugin(str(runtime/'build/felbaker/libfelbaker.so'))
    def bounded(clip):
        core.std.SetVideoCache(clip, mode=1, fixedsize=1, maxsize=2)
        return clip
    bl = bounded(core.ffms2.Source(str(components/'BL.hevc'), threads=2, cachefile=str(destination/'bl.ffindex')))
    el = bounded(core.ffms2.Source(str(components/'EL.hevc'), threads=2, cachefile=str(destination/'el.ffindex')))
    el = bounded(core.resize.Spline16(el, width=3840, height=2160))
    baked = bounded(core.fel.Bake(bl, el, no_resample=1))
    chroma = bounded(core.resize.Spline16(baked, format=vs.YUV444P12))
    rgb = bounded(core.fel.ToRGB(chroma))
    rows = json.loads((Path(config['metadata'])/'source.json').read_text())
    xs = [0, 1, 63, 255, 511, 959, 1439, 1807, 1918, 1919]
    ys = [0, 1, 83, 239, 539, 799, 1007, 1078, 1079]
    points = [(x, y) for y in ys for x in xs]
    result = dict(complete=False, frames=0, yuv_samples=0, rgb_samples=0, mismatches=0,
        residual_negative_differences=0, reference_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        manifest=manifest, started_at=time.time(), limit=__doc__)
    for n, row in enumerate(rows):
        oracle = Reference(row)
        fb, fe, fy, fc, fr = [clip.get_frame(n) for clip in [bl, el, baked, chroma, rgb]]
        b, e, cooked, full, colour = [[np.asarray(f[c]) for c in range(3)] for f in [fb, fe, fy, fc, fr]]
        for x, y in points:
            xx, yy = 2*x, 2*y
            yy0 = (2 + 2*int(b[0][yy,xx]) + int(b[0][yy,xx+1]) + int(b[0][yy,max(0,xx-1)])) >> 2
            yy1 = (2 + 2*int(b[0][yy+1,xx]) + int(b[0][yy+1,xx+1]) + int(b[0][yy+1,max(0,xx-1)])) >> 2
            mmr = [(yy0+yy1+1) >> 1, int(b[1][y,x]), int(b[2][y,x])]
            for channel in range(3):
                px, py = (xx, yy) if channel == 0 else (x, y)
                value = oracle.map(channel, int(b[channel][py,px]), int(e[channel][py,px]), mmr)
                if value != int(cooked[channel][py,px]):
                    raise ValueError(f'FEL arithmetic mismatch at frame={n}, plane={channel}, x={px}, y={py}: {value} != {cooked[channel][py,px]}')
                nores = oracle.map(channel, int(b[channel][py,px]), oracle.mapping['nlq']['nlq_offset'][channel], mmr)
                result['residual_negative_differences'] += value != nores
                result['yuv_samples'] += 1
            # Both edges and image interior are sampled on every displayed frame.
            for px in [xx, xx+1]:
                expected = oracle.rgb([plane[yy,px] for plane in full])
                if expected != [int(plane[yy,px]) for plane in colour]:
                    raise ValueError(f'RGB matrix mismatch at frame={n}, x={px}, y={yy}')
                result['rgb_samples'] += 3
        result['frames'] += 1
        if n % 24 == 0:
            (destination/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    if not result['residual_negative_differences']:
        raise ValueError('The negative control did not distinguish dropping FEL')
    result.update(complete=True, finished_at=time.time())
    (destination/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    destination = Path(sys.argv[2]); destination.mkdir(parents=True, exist_ok=False)
    print(json.dumps(execute(sys.argv[1], destination), indent=2))
