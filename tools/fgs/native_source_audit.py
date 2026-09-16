#!/usr/bin/env python3
"""Audit native samples when missing colour tags prevent display mapping.

This preserves a display-coverage gap instead of guessing a transfer function.
It uses separately pinned source helpers and requires every displayed picture
in each selected window. Native code levels are not perceptual visibility units.
"""
import argparse
import collections
import csv
import fcntl
import gzip
import json
from pathlib import Path
import sys
import time

import numpy as np
import parallel_library_audit as scheduler


def validate_window(planes, times, expected, width, height):
    if len(times) != len(expected) or not expected:
        raise ValueError('native/header frame coverage mismatch')
    if not np.isfinite(times).all() or any(abs(a-b) > .00001 for a,b in zip(times,expected)):
        raise ValueError('native timestamps differ from displayed headers')
    shapes = [(len(times),height,width)] + [(len(times),(height+1)//2,(width+1)//2)]*2
    if len(planes) != 3 or any(p.shape != shape for p,shape in zip(planes,shapes)):
        raise ValueError('incomplete native spatial coverage')
    if any(p.dtype != np.dtype('<u2') for p in planes):
        raise ValueError('unexpected native component format')


def select_interval(planes, times, start, stop):
    indices = [i for i,t in enumerate(times) if start-1e-7 <= t < stop-1e-7]
    return [p[indices] for p in planes], [times[i] for i in indices]


def native_noise(on, off, flags):
    if len(on) != 3 or len(off) != 3:
        raise ValueError('missing native plane')
    result = {}
    for name,a,b in zip('YUV',on,off):
        if a.shape != b.shape or len(a) != len(flags) or a.ndim != 3:
            raise ValueError('grain-on/off native coverage differs')
        if any(flag not in (0,1) for flag in flags):
            raise ValueError('invalid displayed grain flag')
        delta = (a.astype(np.float64)-b.astype(np.float64))/256.0
        if any(not flag and np.any(delta[i]) for i,flag in enumerate(flags)):
            raise ValueError('grain-free displayed picture changed under synthesis')
        result[name] = dict(noise_rms=delta.std(axis=(1,2)).tolist(),
            mean_shift=delta.mean(axis=(1,2)).tolist(),pixels_per_frame=a.shape[1]*a.shape[2])
    return result


def inspect(item, header_path, destination, method, pins):
    audit = method.audit; source_review = method.source_review
    directory = destination/item['key']/item['version'];directory.mkdir(parents=True,exist_ok=True)
    request = dict(library_signature=item['signature'],header_sha256=audit.sha(header_path),
        wrapper_sha256=audit.sha(__file__),measurement_pins=pins,source_candidates=item.get('sources',[]))
    final = directory/'report.json'
    if final.exists():
        old=json.loads(final.read_text())
        if old.get('status')=='native_measured_display_unavailable' and old.get('request')==request:
            audit.check_identity(item)
            source=old.get('source',{})
            if source.get('signature') and audit.signature(source['path'])==source['signature']:
                return old
    report=dict(key=item['key'],version=item['version'],path=item['path'],request=request,
        started_at=time.time(),complete=False,windows=[],quality_verdict='unreviewed',
        display_coverage=dict(status='unavailable_missing_or_unsupported_colour_metadata',
            signalled_video=item['video'],colour_override_applied=False))
    try:
        audit.check_identity(item)
        header=json.loads(header_path.read_text())
        if header['status']!='complete' or header['request']['signature']!=item['signature']:
            raise ValueError('header evidence does not match installed version')
        if audit.sha(header['headers'])!=header['headers_sha256']:
            raise ValueError('header artifact changed')
        opener=gzip.open if header['headers'].endswith('.gz') else open
        with opener(header['headers'],'rt') as f: rows=list(csv.DictReader(f))
        times=[float(r['seconds']) for r in rows]; flags=[int(r['apply_grain']) for r in rows]
        if len(times)!=header['profile']['displayed_frames']:
            raise ValueError('incomplete displayed header coverage')
        source=method.source_candidate(item,directory);report['source']=source
        if source['status']!='candidate_calibrated':
            report.update(status='source_unavailable_for_native_comparison',complete=False)
        else:
            v=item['video'];width,height=v['width'],v['height']
            for index,window in enumerate(header['profile']['windows']):
                method.require_storage(destination);audit.check_identity(item)
                if audit.signature(source['path'])!=source['signature']:raise ValueError('source changed')
                d=directory/('window-%02d'%index)
                if d.exists():d=d/('attempt-'+str(time.time_ns()))
                d.mkdir(parents=True)
                row=dict(window,index=index,status='running')
                try:
                    expected_indices=[i for i,t in enumerate(times) if window['start']-1e-7<=t<window['stop']-1e-7]
                    expected=[times[i] for i in expected_indices];wf=[flags[i] for i in expected_indices]
                    if len(expected)<3:raise ValueError('too few displayed pictures for source pairing')
                    on,ot=source_review.decode(item['path'],window['start'],width,height,len(expected)+4,d,'on',1)
                    off,bt=source_review.decode(item['path'],window['start'],width,height,len(expected)+4,d,'off',0)
                    on,ot=select_interval(on,ot,window['start'],window['stop'])
                    off,bt=select_interval(off,bt,window['start'],window['stop'])
                    validate_window(on,ot,expected,width,height);validate_window(off,bt,expected,width,height)
                    if ot!=bt:raise ValueError('grain-on/off picture timing differs')
                    src,st=source_review.decode(source['path'],window['start']+source['offset'],width,height,len(expected)+8,d,'source')
                    pairs=source_review.align_indices(st,ot,source['offset'])
                    si,oi=zip(*pairs)
                    if list(oi)!=list(range(len(expected))):raise ValueError('source pairing omits a displayed frame')
                    src=[p[list(si)] for p in src]
                    rms=[float(np.sqrt(np.mean((source_review.coarse_picture(a)-source_review.coarse_picture(b))**2)))
                         for a,b in zip(src[0],off[0])]
                    alignment=dict(source_offset_seconds=source['offset'],coarse_picture_rms=rms,
                        source_pts=[st[i] for i in si],output_pts=ot,passed=max(rms)<=4.0,
                        criterion='Every paired coarse luma picture within 4 native eight-bit RMS; alignment only.')
                    row.update(status='native_decoded',decoded=dict(frames=len(expected),seconds=ot,
                        grain_present_frames=sum(wf),planes=native_noise(on,off,wf),
                        units='native code levels normalized to eight bits',spatial_coverage_fraction=1.0,
                        scope='All native Y/U/V samples of every displayed picture in this selected interval; no reference-display grade.'))
                    row['source_review']=(dict(status='source_compared',source_measurement_eligible=True,alignment=alignment,
                        measurements=source_review.measure_planes(src,on,off,ot)) if alignment['passed'] else
                        dict(status='alignment_review_required',source_measurement_eligible=False,alignment=alignment))
                    del src,on,off
                except Exception as error:row.update(status='error',error=str(error))
                audit.check_identity(item)
                if audit.signature(source['path'])!=source['signature']:raise ValueError('source changed during native window')
                audit.write(d/'report.json',row);report['windows'].append(row);audit.write(directory/'progress.json',report)
            report.update(complete=True,status='native_measured_display_unavailable' if all(w['status']=='native_decoded' for w in report['windows']) else 'measurement_errors')
        audit.check_identity(item)
    except method.AuditResourceUnavailable:
        raise
    except Exception as error:
        report.update(status='superseded' if 'snapshot superseded' in str(error) else 'error',error=str(error))
    report.update(finished_at=time.time(),scope='Native full-window coverage and paired-source diagnostics; missing display mapping remains a separate limitation. Not a whole-file quality verdict.')
    audit.write(final,report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path);parser.add_argument('--headers',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--measurement-tools',type=Path,required=True)
    parser.add_argument('--qualification',type=Path,required=True);parser.add_argument('--limit',type=int)
    args=parser.parse_args();q=json.loads(args.qualification.read_text())
    method=scheduler.load_measurements(args.measurement_tools,q)
    items=json.loads(args.manifest.read_text())['files'][:args.limit]
    pins={name:method.audit.sha(args.measurement_tools/name) for name in q['tools']}
    args.output_dir.mkdir(parents=True,exist_ok=True);results=[];started=time.time()
    with (args.output_dir/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def publish(active=None,paused=None):
            method.audit.write(args.output_dir/'status.json',dict(started_at=started,updated_at=time.time(),total=len(items),
                processed=len(results),counts=dict(collections.Counter(r['status'] for r in results)),active=active,
                paused_reason=paused,phase_complete=len(results)==len(items),audit_complete=False,
                manifest_sha256=method.audit.sha(args.manifest),wrapper_sha256=method.audit.sha(__file__),
                reference_display_coverage=False,results=[{k:r[k] for k in ('key','version','status')} for r in results]))
        publish()
        for item in items:
            header=args.headers/item['key']/item['version']/'report.json'
            while not header.exists():
                producer=json.loads((args.headers/'status.json').read_text())
                if producer.get('phase_complete') or time.time()-producer['updated_at']>15000:
                    publish(paused='header producer ended without this version');return 75
                publish(active=dict(key=item['key'],waiting_for_headers=True));time.sleep(10)
            publish(active=dict(key=item['key'],path=item['path']))
            try:
                method.require_storage(args.output_dir)
                result=inspect(item,header,args.output_dir,method,pins)
            except method.AuditResourceUnavailable as error:
                publish(paused=str(error));return 75
            results.append(result);publish()
            print(json.dumps(dict(key=item['key'],status=result['status'])),flush=True)
        publish()
    return 0


if __name__=='__main__':raise SystemExit(main())
