#!/usr/bin/env python3
"""Compare source fidelity at fixed QP and at no greater candidate file size.

Known clean pictures and independent grain expose detail loss separately from
noise. This is an offline experiment, not a production validation threshold.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np

import fgs_kat as kat
import quality_metrics

CASES = {
    'detail_fine': dict(sigma=6, detail=True),
    'detail_weak': dict(sigma=2, detail=True),
    'detail_coarse': dict(sigma=6, detail=True, coarse=True),
    'woven_detail': dict(sigma=6, woven=True),
    'flat_fine': dict(sigma=6),
    'flat_coarse': dict(sigma=6, coarse=True),
    'asymmetric_chroma': dict(sigma=6, chroma=(3, 0)),
    'changing_strength': dict(sigma=6, later_sigma=10),
    'strength_steps': dict(sigma=6, steps=True),
    'pq_detail': dict(sigma=3, detail=True, bits=10, color='pq'),
}


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def command(argv, log):
    start = time.monotonic()
    with log.open('w') as handle:
        subprocess.run(argv, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=300)
    return time.monotonic() - start


def generate(directory, spec, frames):
    width, height, bits = 768, 432, spec.get('bits', 8)
    ds = 1 << (bits - 8)
    dtype = np.uint8 if bits == 8 else np.uint16
    rng = np.random.default_rng(0xF1DE117)
    kat.apply_spec(dict(width=width, height=height, bits=bits))
    base = kat.base_luma(detail=spec.get('detail', False))
    if spec.get('detail') and ds != 1:
        flat = kat.base_luma()
        base = flat + ds * (base - flat)
    if spec.get('woven'):
        yy, xx = np.mgrid[:height//2, 64:width-64]
        base[:height//2, 64:width-64] += ds * (5*np.sin(2*np.pi*xx/9) + 5*np.sin(2*np.pi*yy/9))
    clean_planes = [np.rint(base).astype(dtype)] + [np.full((height//2, width//2), 128*ds, dtype=dtype)] * 2
    inputs = [directory / name for name in ['source.y4m', 'source.yuv', 'ideal.yuv']]
    with inputs[0].open('wb') as y4m, inputs[1].open('wb') as raw, inputs[2].open('wb') as ideal:
        y4m.write(f'YUV4MPEG2 W{width} H{height} F24:1 Ip A1:1 {"C420mpeg2" if bits == 8 else "C420p10"}\n'.encode())
        for n in range(frames):
            sigma = spec.get('later_sigma', spec['sigma']) if n >= frames//2 else spec['sigma']
            sigma_map = np.full((height, width), sigma * ds, dtype=np.float64)
            if spec.get('steps'):
                for band in range(kat.BANDS):
                    sigma_map[:, band*kat.BAND_W:(band+1)*kat.BAND_W] = (2 if band % 2 else 10) * ds
            unit = kat.correlated_unit_noise(rng, (height, width)) if spec.get('coarse') else rng.normal(size=(height, width))
            planes = [np.clip(np.rint(base + unit*sigma_map), 0, (1 << bits)-1).astype(dtype)]
            for sigma_c in spec.get('chroma', (0, 0)):
                planes.append(np.clip(np.rint(128*ds + rng.normal(0, sigma_c*ds, (height//2,width//2))),
                                      0, (1 << bits)-1).astype(dtype))
            y4m.write(b'FRAME\n')
            for plane in planes:
                raw.write(plane.tobytes()); y4m.write(plane.tobytes())
            for plane in clean_planes:
                ideal.write(plane.tobytes())
    return dict(width=width, height=height, bits=bits, frames=frames,
                hashes={p.name:sha(p) for p in inputs})


def encode(binary, directory, source, spec, qp, retain, expected_frames):
    directory.mkdir()
    output = directory / 'output.mkv'
    opts = 'denoise=auto,chroma=auto,denoiser=bilateral' + (',retain=auto' if retain else '')
    argv = [str(binary), '--codec', 'av1', '--preset', 'quality', '--tune', 'hq', '--cqp', str(qp),
            '--av1-film-grain', opts, '--log-level', 'debug', '-i', str(source), '-o', str(output)]
    if spec.get('bits') == 10:
        argv += ['--output-depth', '10']
    argv += kat.COLOR_ARGS.get(spec.get('color'), [])
    elapsed = command(argv, directory / 'encode.log')
    log = (directory / 'encode.log').read_text()
    finish = re.search(r'encoded (\d+) frames, ([\d.]+) fps', log)
    if not finish or int(finish[1]) != expected_frames:
        raise RuntimeError('incomplete experimental encode')
    models = kat.parse_log(log)
    return dict(qp=qp, retain_auto=retain, bytes=output.stat().st_size, file_sha256=sha(output),
                seconds=elapsed, encoder_fps=float(finish[2]), command=argv,
                model_frames=models, source_fallbacks=log.count('sourceFallback=1'),
                source_fallback_frames=[int(v) for v in re.findall(r'fgs-model frame=(\d+)[^\n]*sourceFallback=1', log)],
                fit_errors=[[float(v) for v in m] for m in re.findall(r'fitError=([\d.]+)/([\d.]+)/([\d.]+)', log)])


def measure(directory, root, info):
    pix = 'yuv420p' if info['bits'] == 8 else 'yuv420p10le'
    for grain in [0, 1]:
        command(['ffmpeg','-v','error','-nostdin','-c:v','libdav1d','-threads','2','-filmgrain',str(grain),
                 '-i',str(directory/'output.mkv'),'-map','0:v:0','-an','-sn','-pix_fmt',pix,
                 '-fps_mode','passthrough','-f','rawvideo',str(directory/f'grain-{grain}.yuv')],
                directory/f'decode-{grain}.log')
    expected_bytes = info['frames']*info['width']*info['height']*3//2*(1 if info['bits'] == 8 else 2)
    for name in ['grain-0.yuv','grain-1.yuv']:
        if (directory/name).stat().st_size != expected_bytes:
            raise RuntimeError('decoded frame count changed')
    separation = quality_metrics.separation_metrics(root/'source.yuv', root/'ideal.yuv', directory/'grain-0.yuv',
                                                    info['width'],info['height'],info['bits'],first_frame=8)
    readers = {name:quality_metrics.LumaReader(path,info['width'],info['height'],info['bits']) for name,path in
               [('source',root/'source.yuv'),('ideal',root/'ideal.yuv'),('off',directory/'grain-0.yuv'),('on',directory/'grain-1.yuv')]}
    paths = dict(source=root/'source.yuv', off=directory/'grain-0.yuv', on=directory/'grain-1.yuv')
    dtype = np.uint8 if info['bits'] == 8 else np.uint16
    planes = {name:np.memmap(path,dtype=dtype,mode='r').reshape(info['frames'],-1) for name,path in paths.items()}
    luma_count = info['width'] * info['height']
    ds = 1 << (info['bits']-8)
    # Lower-half interiors of known flat bands exclude all synthetic detail and edges.
    mask = np.zeros((info['height'],info['width']),dtype=bool)
    for band in range(12):
        mask[info['height']//2+24:-24, band*64+16:(band+1)*64-16] = True
    trace = []
    for frame in range(info['frames']):
        values = {name:r.luma(frame).astype(np.float64) for name,r in readers.items()}
        residuals = {name:(values[name]-values['ideal'])[mask] for name in ['source','off','on']}
        row = dict(frame=frame, source_sigma=float(residuals['source'].std()/ds),
                   base_sigma=float(residuals['off'].std()/ds), output_sigma=float(residuals['on'].std()/ds),
                   synth_sigma=float((values['on']-values['off'])[mask].std()/ds))
        for index, component in enumerate(['u','v']):
            sl = slice(luma_count + index*luma_count//4, luma_count + (index+1)*luma_count//4)
            samples = {name:mm[frame,sl].astype(np.float64) for name,mm in planes.items()}
            row[component] = {name:float(value.std()/ds) for name,value in samples.items()}
            row[component]['synth'] = float((samples['on']-samples['off']).std()/ds)
        trace.append(row)
    return dict(separation=separation, flat_trace=trace,
                decoded_hashes={f'grain-{g}.yuv':sha(directory/f'grain-{g}.yuv') for g in [0,1]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--cases',default=','.join(CASES))
    parser.add_argument('--frames',type=int,default=48)
    args = parser.parse_args()
    if args.frames < 24:
        parser.error('at least 24 frames are required')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    report = dict(started_at=time.time(), baseline_sha256=sha(args.baseline), candidate_sha256=sha(args.candidate),
                  harness_sha256=sha(__file__), cases=[], complete=False,
                  scope='Controlled sources, fixed QP plus a candidate encoding no larger than baseline auto. '
                        'Small-frame timings are not throughput benchmarks. No universal quality threshold.')
    def save():
        tmp = args.output_dir/'report.tmp'
        tmp.write_text(json.dumps(report,indent=2)+'\n');os.replace(tmp,args.output_dir/'report.json')
    save()
    for name in args.cases.split(','):
        spec = CASES[name];root=args.output_dir/name;root.mkdir()
        info=generate(root,spec,args.frames)
        case=dict(name=name,spec=spec,source=info,arms={})
        report['cases'].append(case)
        for arm,binary,retain in [('old-default',args.baseline,False),('old-auto',args.baseline,True),
                                 ('new-auto',args.candidate,True)]:
            directory=root/arm
            result=encode(binary,directory,root/'source.y4m',spec,20,retain,args.frames)
            result.update(measure(directory,root,info));case['arms'][arm]=result;save()
            print(json.dumps(dict(case=name,arm=arm,bytes=result['bytes'],detail=result['separation']['detail_transfer_gain'],
                                  fallback=result['source_fallbacks'])),flush=True)
        target=case['arms']['old-auto']['bytes']
        candidate=case['arms']['new-auto']
        for qp in range(21,33):
            if candidate['bytes'] <= target:break
            arm=f'new-auto-qp{qp}';directory=root/arm
            candidate=encode(args.candidate,directory,root/'source.y4m',spec,qp,True,args.frames)
            case.setdefault('size_search',{})[arm]=candidate;save()
        if candidate is case['arms']['new-auto']:
            case['no_larger_arm']='new-auto'
        elif candidate['bytes'] <= target:
            candidate.update(measure(directory,root,info));case['arms'][arm]=candidate;case['no_larger_arm']=arm
        else:
            case['no_larger_arm']=None
        for filename,expected in info['hashes'].items():
            if sha(root/filename) != expected:raise RuntimeError('controlled source changed')
        case['complete']=True;save()
        print(json.dumps(dict(case=name,no_larger_arm=case['no_larger_arm'])),flush=True)
    report.update(complete=True,finished_at=time.time());save()


if __name__ == '__main__':
    main()
