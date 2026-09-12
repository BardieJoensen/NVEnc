#!/usr/bin/env python3
"""Finite consumer of a manually started version-bound header audit.

Measure every pixel/frame of selected windows and compare retained sources.
No library writes, downloads, transcodes, timers, or automatic repair decisions.
"""
import argparse
import bisect
import collections
import csv
import fcntl
import gzip
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
import library_audit as audit
import source_plane_review as source_review


class AuditResourceUnavailable(RuntimeError):
    """The run must pause without consuming pending media as failed checks."""


def require_storage(directory):
    if shutil.disk_usage(directory).free < 6*1024**3:
        raise AuditResourceUnavailable('audit evidence filesystem below 6 GiB reserve')


def summarize(path, metadata, expected):
    with Path(path).open() as stream: rows=list(csv.DictReader(stream))
    if (metadata.get('schema')!='fgs_reference_full_v1' or not metadata.get('interval_complete')
            or len(rows)!=metadata.get('measured_frames') or len(rows)!=len(expected) or not rows):
        raise RuntimeError('decoded/header frame coverage mismatch')
    if any(not math.isfinite(float(v)) for row in rows for v in row.values()):
        raise RuntimeError('non-finite decoded measurement')
    times=[float(r['seconds']) for r in rows]
    if any(abs(a-b)>.00001 for a,b in zip(times,expected)):
        raise RuntimeError('decoded timestamps do not match displayed headers')
    pixels=metadata['width']*metadata['height']
    if any(int(r['pixels'])!=pixels for r in rows) or metadata['measured_pixels']!=pixels*len(rows):
        raise RuntimeError('incomplete decoded spatial coverage')
    channels={}
    for channel in ('luma','red','green','blue'):
        peak=max(rows,key=lambda r:float(r[channel+'_max_tile_rms']))
        values=[float(r[channel+'_rms']) for r in rows]
        channels[channel]=dict(whole_frame_rms=values,whole_frame_rms_change=max(values)-min(values),
            max_tile_rms=float(peak[channel+'_max_tile_rms']),peak_seconds=float(peak['seconds']),
            peak_texture_score=max(float(r[channel+'_peak_score']) for r in rows),
            peak_directional_score=max(float(r[channel+'_peak_directional_score']) for r in rows))
    flags=[int(r['grain_present']) for r in rows]
    if any(f not in (0,1) for f in flags):raise RuntimeError('invalid decoded grain flag')
    return dict(frames=len(rows),seconds=times,channels=channels,grain_present_frames=sum(flags),
        clipped_base_fraction=metadata['clipped_base_pixels']/metadata['measured_pixels'],
        clipped_grain_fraction=metadata['clipped_grain_pixels']/metadata['measured_pixels'],
        units=metadata['units'],scope='All pixels and displayed frames in these selected windows; no whole-file visual verdict.')


def source_candidate(item, directory):
    available=[s for s in item.get('sources',[]) if s.get('current_signature')]
    available.sort(key=lambda s:not s.get('identity_matches_expected'))
    if not available:return dict(status='source_unavailable')
    candidate=available[0]
    if audit.signature(candidate['path'])!=candidate['current_signature']:
        return dict(status='source_changed',path=candidate['path'])
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-of','json',candidate['path']],text=True,timeout=90))['streams'][0]
    if (probe['width'],probe['height'])!=(item['video']['width'],item['video']['height']):
        return dict(status='source_geometry_review_required',probe=probe)
    if probe['codec_name'] not in ('h264','hevc','vc1','mpeg2video','mpeg4','vp9','av1'):
        return dict(status='source_codec_review_required',probe=probe)
    source=source_review.first_picture(candidate['path'],directory/'source-first-picture.log')
    output=source_review.first_picture(item['path'],directory/'output-first-picture.log',grain=True)
    return dict(status='candidate_calibrated',path=candidate['path'],signature=candidate['current_signature'],
        probe=probe,source_first=source,output_first=output,offset=source['seconds']-output['seconds'],
        scope='First displayed-picture offset is a hypothesis; each sampled window must independently match source content.')


def inspect_file(item, header, binary, destination, pins, source_enabled=True):
    directory=destination/item['key']/item['version'];directory.mkdir(parents=True,exist_ok=True)
    request=dict(library_signature=item['signature'],header_sha256=audit.sha(header),
        binary_sha256=pins['binary_sha256'],wrapper_sha256=pins['wrapper_sha256'],source_wrapper_sha256=pins['source_wrapper_sha256'],
        source_enabled=source_enabled,source_candidates=item.get('sources',[]),review_anchors=item.get('review_anchors',[]))
    final=directory/'report.json'
    if final.exists():
        old=json.loads(final.read_text())
        if old.get('status')=='measured' and old.get('complete') and old.get('request')==request and audit.signature(item['path'])==item['signature']:
            valid=True
            for window in old['windows']:
                if window.get('csv') and audit.sha(window['csv'])!=window.get('csv_sha256'):valid=False
                if window.get('source_review',{}).get('status')=='source_review_error':valid=False
            source=old.get('source',{})
            if source.get('status') in ('source_calibration_error','source_changed'):valid=False
            if source.get('signature') and audit.signature(source['path'])!=source['signature']:valid=False
            if valid:return old
    report=dict(key=item['key'],version=item['version'],path=item['path'],request=request,
        started_at=time.time(),complete=False,windows=[],source={},quality_verdict='unreviewed')
    try:
        audit.check_identity(item)
        if audit.signature(binary)!=pins['binary_signature']:raise RuntimeError('inspector changed')
        h=json.loads(header.read_text())
        if h['status']!='complete' or h['request']['signature']!=item['signature']:
            raise RuntimeError('header report does not match current inventory')
        opener=gzip.open if h['headers'].endswith('.gz') else open
        with opener(h['headers'],'rt') as stream:
            reader=csv.reader(stream);next(reader);times=[float(r[2]) for r in reader]
        if len(times)!=h['profile']['displayed_frames'] or audit.sha(h['headers'])!=h['headers_sha256']:
            raise RuntimeError('header artifact changed')
        if source_enabled:
            try:report['source']=source_candidate(item,directory)
            except Exception as error:report['source']=dict(status='source_calibration_error',error=str(error))
        else:report['source']=dict(status='not_requested')
        source=report['source']
        windows=list(h['profile']['windows'])
        for anchor in item.get('review_anchors',[]):
            t=anchor['seconds']
            if not isinstance(t,(int,float)) or not math.isfinite(t) or not 0<=t<=times[-1]:
                raise RuntimeError('invalid additional reviewed-scene anchor')
            if any(w['start']<=t<w['stop'] for w in windows):continue
            windows.append(dict(kind='prior_review_anchor',seconds=t,start=max(0,t-.18),stop=min(times[-1]+.001,t+.40),
                prior_evidence=anchor.get('evidence'),prior_role=anchor.get('role')))
        for index,window in enumerate(windows):
            audit.check_identity(item)
            require_storage(destination)
            d=directory/f'window-{index:02d}';d.mkdir(exist_ok=True)
            row=dict(window,index=index,status='running')
            try:
                csv_path=d/'frames.csv'
                if csv_path.exists():
                    # A changed request never overwrites previous evidence.
                    d=d/('attempt-'+str(time.time_ns()));d.mkdir();csv_path=d/'frames.csv'
                command=[str(binary),'--extended','--sample-period','0','--stream-index',str(item['video']['index'])]
                v=item['video']
                if v.get('color_transfer') not in ('smpte2084','arib-std-b67') and v.get('color_primaries')!='bt2020':
                    command+=['--assume-bt709']
                command+=[item['path'],str(csv_path),str(window['start']),str(window['stop'])]
                with (d/'native.log').open('w') as log:
                    native=subprocess.run(command,stdout=subprocess.PIPE,stderr=log,text=True,timeout=360)
                (d/'command.json').write_text(json.dumps(command,indent=2)+'\n')
                if native.returncode:raise RuntimeError('reference-display measurement failed; see native.log')
                metadata=json.loads(native.stdout)
                expected=times[bisect.bisect_left(times,window['start']-1e-7):bisect.bisect_left(times,window['stop'])]
                row.update(status='decoded',metadata=metadata,decoded=summarize(csv_path,metadata,expected),
                    csv=str(csv_path),csv_sha256=audit.sha(csv_path))
                if row['decoded']['grain_present_frames']==0:
                    row['source_review']=dict(status='grain_absent_in_window',source_measurement_eligible=False,
                        scope='All sampled displayed frames disable AV1 grain. No synthesized overlay to source-compare here; this does not grade base-codec quality.')
                elif source.get('status')=='candidate_calibrated':
                    if audit.signature(source['path'])!=source['signature']:raise RuntimeError('source changed')
                    try:
                        result=source_review.review(source['path'],item['path'],window['start'],v['width'],v['height'],source['offset'],d/'source-review')
                        if audit.signature(source['path'])!=source['signature']:raise RuntimeError('source changed during comparison')
                        row['source_review']=result
                    except Exception as error:row['source_review']=dict(status='source_review_error',error=str(error))
                audit.check_identity(item)
            except Exception as error:row.update(status='error',error=str(error))
            audit.write(d/'report.json',row);report['windows'].append(row)
            audit.write(directory/'progress.json',report)
        audit.check_identity(item)
        if audit.signature(binary)!=pins['binary_signature']:raise RuntimeError('inspector changed')
        report.update(complete=True,status='measured' if all(w['status']=='decoded' for w in report['windows']) else 'measurement_errors')
    except AuditResourceUnavailable as error:
        report.update(status='resource_paused',error=str(error),paused_at=time.time())
        audit.write(directory/'resource-paused.json',report)
        raise
    except Exception as error:report.update(status='superseded' if 'snapshot superseded' in str(error) else 'error',error=str(error))
    report.update(finished_at=time.time(),scope='Full selected-window pixel coverage, calibrated source comparisons where available. Completion is measurement completion, not a whole-file watchability verdict.')
    audit.write(final,report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path);parser.add_argument('--headers',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--binary-sha256',required=True)
    parser.add_argument('--skip-sources',action='store_true');parser.add_argument('--limit',type=int)
    args=parser.parse_args();manifest=json.loads(args.manifest.read_text())
    if manifest.get('schema')!='fgs_library_audit_v1':raise ValueError('invalid manifest')
    pins=dict(binary_sha256=audit.sha(args.binary),binary_signature=audit.signature(args.binary),
              wrapper_sha256=audit.sha(__file__),source_wrapper_sha256=audit.sha(source_review.__file__))
    if pins['binary_sha256']!=args.binary_sha256:raise ValueError('inspector pin mismatch')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with (args.output_dir/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        items=[i for i in manifest['files'] if i.get('codec')=='av1']
        items.sort(key=lambda i:(not bool(i.get('repair_receipt')),-i.get('installed_at',0),i['path']))
        if args.limit:items=items[:args.limit]
        pending=list(items);results=[];began=time.time()
        manifest_sha=audit.sha(args.manifest)
        def publish(waiting=False,paused=None):
            audit.write(args.output_dir/'status.json',dict(updated_at=time.time(),started_at=began,total=len(items),processed=len(results),
                counts=dict(collections.Counter(r['status'] for r in results)),waiting_for_headers=waiting,
                phase_complete=not pending,audit_complete=False,manifest_sha256=manifest_sha,
                paused_reason=paused,pending_files=len(pending),
                scope='Selected windows cover every image pixel/frame; retained source comparisons are separate. Flags require visual and recurrence review.',
                results=[{k:r[k] for k in ('key','version','status') if k in r} for r in results]))
        publish()
        while pending:
            progressed=False
            for item in list(pending):
                header=args.headers/item['key']/item['version']/'report.json'
                if not header.exists():continue
                h=json.loads(header.read_text())
                try:
                    require_storage(args.output_dir)
                    if h.get('status')!='complete':r=dict(key=item['key'],version=item['version'],status='header_'+h['status'])
                    else:r=inspect_file(item,header,args.binary,args.output_dir,pins,not args.skip_sources)
                except AuditResourceUnavailable as error:
                    # Leave this file and the rest of the manifest pending.
                    # A restart after storage recovery can reuse valid results.
                    publish(paused=str(error))
                    print(json.dumps(dict(status='resource_paused',reason=str(error),pending=len(pending))),flush=True)
                    return 75
                pending.remove(item);results.append(r);publish();progressed=True
                print(json.dumps(dict(processed=len(results),total=len(items),key=item['key'],status=r['status'])),flush=True)
            if not progressed:
                status=json.loads((args.headers/'status.json').read_text())
                if status.get('phase_complete'):
                    for i in pending:results.append(dict(key=i['key'],version=i['version'],status='header_missing'))
                    pending.clear();break
                if time.time()-status['updated_at']>15000:
                    raise RuntimeError('header producer has not published within its maximum per-file budget; resume manually after resolving it')
                publish(waiting=True);time.sleep(10)
        publish()
    return 0


if __name__=='__main__':raise SystemExit(main())
