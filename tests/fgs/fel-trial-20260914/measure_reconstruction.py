"""Temporal coverage of all clip frames; explicit spatial sampling for differences."""
from pathlib import Path
import hashlib
import json
import resource
import time
import numpy as np
from PIL import Image, ImageDraw
from fel_clip import inputs, reconstructed, base_rgb, rgb_to_pq10, core

ROOT = Path('/trial')
STEP = 4


def sampled(frame):
    return np.stack([np.asarray(frame[p])[::STEP, ::STEP] for p in range(3)]).astype(np.int32)


def difference(a, b):
    d = np.abs(a - b)
    return dict(mean_abs_code16=float(d.mean()), p99_abs_code16=float(np.percentile(d, 99)),
                max_abs_code16=int(d.max()), changed_fraction=float(np.count_nonzero(d)/d.size))


def rgb_pixels(clip, n):
    with clip.get_frame(n) as frame:
        return np.stack([np.asarray(frame[p]) for p in range(3)], axis=-1)


def preview(rgb):
    # Fixed BT.2020 PQ -> 100-nit Reinhard/sRGB inspection preview. This is not
    # Dolby display management and cannot qualify actual HDR/DV playback.
    x = rgb[::4, ::4].astype(np.float32) / 65535
    m1, m2 = 2610/16384, 2523/32
    c1, c2, c3 = 3424/4096, 2413/128, 2392/128
    z = x ** (1/m2)
    linear = 10000 * (np.maximum(z-c1, 0) / np.maximum(c2-c3*z, 1e-9)) ** (1/m1)
    lum = linear @ np.array([.2627, .6780, .0593], dtype=np.float32)
    linear = linear / (100+lum[..., None])
    mat = np.array([[1.660491, -.587641, -.072850],[-.124550, 1.132900, -.008349],[-.018151, -.100579, 1.118730]], dtype=np.float32)
    y = np.clip(linear @ mat.T, 0, 1)
    srgb = np.where(y <= .0031308, y*12.92, 1.055*y**(1/2.4)-.055)
    return Image.fromarray(np.rint(srgb*255).astype(np.uint8))


def main():
    summaries = []
    for directory in sorted((ROOT/'clips').iterdir()):
        started = time.monotonic()
        bl, el = inputs(directory)
        full = reconstructed(bl, el)
        omitted = reconstructed(bl, el, mode='noresidual')
        base = base_rgb(bl)
        rows = []
        rgb_hash = hashlib.sha256()
        rpu_hash = hashlib.sha256()
        refresh_frames = []
        for n in range(bl.num_frames):
            with full.get_frame(n) as f, omitted.get_frame(n) as o, base.get_frame(n) as b, el.get_frame(n) as e:
                a = sampled(f)
                row = dict(frame=n, residual=difference(a, sampled(o)),
                           versus_hdr10_base=difference(a, sampled(b)))
                for plane in range(3):
                    rgb_hash.update(np.asarray(f[plane]).tobytes(order='C'))
                rpu = e.props.get('DolbyVisionRPU', b'')
                if not rpu:
                    raise RuntimeError(f'missing decoded RPU: {directory.name}, frame {n}')
                rpu_hash.update(len(rpu).to_bytes(4, 'big')); rpu_hash.update(rpu)
                if f.props.get('_SceneChangePrev', 0):
                    refresh_frames.append(n)
                rows.append(row)
            if n % 20 == 0:
                print(directory.name, n, '/', bl.num_frames, 'rss_kib', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, flush=True)
        strongest = max(rows, key=lambda r:r['residual']['mean_abs_code16'])['frame']
        review_frames = sorted(set([0, bl.num_frames//2, strongest]))
        pq10 = rgb_to_pq10(full)
        roundtrip = core.resize.Spline36(pq10, format=full.format.id, matrix_in_s='2020ncl',
                                       range_in_s='limited', range_s='full')
        internal = reconstructed(bl, el, external=False)
        compat = reconstructed(bl, el, mode='compat', external=False)
        controls = []
        for n in review_frames:
            with full.get_frame(n) as f, roundtrip.get_frame(n) as q, internal.get_frame(n) as i, compat.get_frame(n) as c:
                a = sampled(f)
                controls.append(dict(frame=n, pq10_roundtrip=difference(a, sampled(q)),
                                     external_vs_internal=difference(a, sampled(i)),
                                     internal_vs_compat=difference(sampled(i), sampled(c))))
        visuals = []
        for label, clip in [('hdr10_base', base), ('mapping_without_residual', omitted), ('fel_reconstructed', full)]:
            pixels = rgb_pixels(clip, strongest)
            np.save(directory/(label+'-strongest.npy'), pixels)
            pic = preview(pixels)
            canvas = Image.new('RGB', (pic.width, pic.height+34), 'black')
            canvas.paste(pic, (0,34));ImageDraw.Draw(canvas).text((8,8), f'{label} | clip frame {strongest}', fill='white')
            canvas.save(directory/(label+'-preview.png'));visuals.append(canvas)
        sheet = Image.new('RGB', (visuals[0].width*3, visuals[0].height))
        for x,pic in enumerate(visuals):sheet.paste(pic, (x*pic.width,0))
        sheet.save(directory/'comparison.png')
        summary = dict(name=directory.name, frames=bl.num_frames, fps=[bl.fps_num,bl.fps_den],
            complete=True, spatial_sample_step=STEP, metrics_domain='untrimmed BT.2020 PQ RGB, 0..65535; not VMAF or a perceptual approval score',
            temporal_coverage='every decoded clip frame', reconstructed_rgb_planar_sha256=rgb_hash.hexdigest(),
            decoded_rpu_order_sha256=rpu_hash.hexdigest(), scene_refresh_frames=refresh_frames,
            strongest_residual_frame=strongest,
            mean_residual_code16=float(np.mean([r['residual']['mean_abs_code16'] for r in rows])),
            mean_residual_changed_fraction=float(np.mean([r['residual']['changed_fraction'] for r in rows])),
            mean_vs_hdr10_base_code16=float(np.mean([r['versus_hdr10_base']['mean_abs_code16'] for r in rows])),
            review_controls=controls, measurement_seconds=time.monotonic()-started,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            preview_mapping='Fixed 100-nit Reinhard followed by BT.709/sRGB; diagnostic only; no Dolby trims applied.')
        (directory/'reconstruction-frames.json').write_text(json.dumps(rows,indent=2)+'\n')
        (directory/'reconstruction-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        summaries.append(summary)
        (ROOT/'results/reconstruction-summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
        print(directory.name, 'COMPLETE', summary['mean_residual_code16'], 'code16', flush=True)
        del bl, el, full, omitted, base, pq10, roundtrip, internal, compat


if __name__ == '__main__':
    main()
