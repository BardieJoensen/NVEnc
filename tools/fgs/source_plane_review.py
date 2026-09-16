#!/usr/bin/env python3
"""Native-plane source/on/off measurements for a version-bound short window.

Flat-region measurements are review aids, never automatic repair verdicts.
Source timing is calibrated at the first decoded picture, then independently
checked against picture content in each window. HDR code levels are not display
visibility units; review such candidates with the reference-display inspector.
"""
import json
import math
from bisect import bisect_left
from pathlib import Path
import re
import subprocess
import numpy as np

PTS = re.compile(rb' n:\s*\d+ pts:\s*-?\d+ pts_time:([-+0-9.eE]+)')


def first_picture(path, log_path, grain=False):
    command = ['ffmpeg','-hide_banner','-nostdin','-copyts','-threads','2']
    if grain: command += ['-c:v','libdav1d','-filmgrain','0']
    command += ['-i',str(path),'-map','0:v:0','-an','-sn','-frames:v','1',
                '-vf','showinfo','-filter_threads','1','-f','null','-']
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=90)
    Path(log_path).write_bytes(result.stderr)
    times = [float(p) for p in PTS.findall(result.stderr)]
    if result.returncode or not times:
        raise RuntimeError('first-picture timing calibration failed')
    return dict(seconds=times[0], command=command)


def decode(path, start, width, height, frames, directory, name, grain=None, *, preroll_seconds=0):
    if not math.isfinite(preroll_seconds) or not 0 <= preroll_seconds <= 10:
        raise ValueError('source decode preroll must be between zero and ten seconds')
    filters = 'format=yuv420p16le,showinfo'
    if preroll_seconds:
        # Decode references before the window without returning extra pictures
        # or changing the timestamps that strict source pairing will check.
        filters = f"select='gte(t,{max(0,start)-1e-7:.9f})'," + filters
    command = ['ffmpeg','-hide_banner','-nostdin','-copyts','-threads','2']
    if grain is not None: command += ['-c:v','libdav1d','-filmgrain',str(grain)]
    command += ['-ss',str(max(0,start-preroll_seconds)),'-i',str(path),'-map','0:v:0','-an','-sn',
        '-frames:v',str(frames),'-fps_mode','passthrough','-vf',filters,
        '-filter_threads','1','-f','rawvideo','-']
    with (directory/(name+'.log')).open('wb') as log:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=log, timeout=240)
    (directory/(name+'-command.json')).write_text(json.dumps(command,indent=2)+'\n')
    if result.returncode: raise RuntimeError(name+' decode failed')
    frame_samples = width*height + 2*((width+1)//2)*((height+1)//2)
    raw = np.frombuffer(result.stdout,dtype='<u2')
    if len(raw)%frame_samples: raise RuntimeError('partial native frame')
    count = len(raw)//frame_samples
    times = [float(p) for p in PTS.findall((directory/(name+'.log')).read_bytes())][:count]
    if count < 3 or len(times)!=count or any(b<=a for a,b in zip(times,times[1:])):
        raise RuntimeError('incomplete or ambiguous decoded timing')
    samples=raw.reshape(count,frame_samples)
    y=width*height;c=((width+1)//2)*((height+1)//2)
    planes=[samples[:,:y].reshape(count,height,width),samples[:,y:y+c].reshape(count,(height+1)//2,(width+1)//2),samples[:,y+c:].reshape(count,(height+1)//2,(width+1)//2)]
    return planes,times


def align_indices(source_times, output_times, offset, tolerance=.0021):
    if len(source_times)<3 or len(output_times)<3:
        raise ValueError('too few source/output pictures')
    if not math.isfinite(offset) or not all(math.isfinite(t) for t in source_times+output_times):
        raise ValueError('non-finite alignment time')
    if any(b<=a for times in (source_times,output_times) for a,b in zip(times,times[1:])):
        raise ValueError('non-increasing alignment time')
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('invalid alignment tolerance')
    matches=[]
    for j,t in enumerate(output_times):
        target=t+offset
        # Sorted timestamps need only the two neighbours of the insertion
        # point. Scanning every source frame for every output frame makes
        # whole-film recurrence checks quadratic. Prefer the earlier picture
        # on an exact tie, as numpy.argmin did in the original implementation.
        right=bisect_left(source_times,target)
        if right == 0:
            i=0
        elif right == len(source_times):
            i=right-1
        else:
            i=right-1 if target-source_times[right-1] <= source_times[right]-target else right
        if abs(source_times[i]-target)<=tolerance:matches.append((i,j))
    if len(matches)!=len(output_times) or len({i for i,j in matches})!=len(matches):
        raise ValueError('source alignment does not cover every output picture')
    return matches


def coarse_picture(frame):
    # Block means suppress grain/compression texture without hiding wrong cuts
    # or motion. A quality verdict is never inferred from this alignment score.
    h,w=frame.shape;th,tw=h//54,w//96
    return frame[:54*th,:96*tw].reshape(54,th,96,tw).mean(axis=(1,3))/256.0


def measure_planes(source, on, off, seconds):
    result=[]
    for plane,(s,a,b) in enumerate(zip(source,on,off)):
        n,h,w=s.shape;block=16 if plane==0 else 8;hh,ww=h//block,w//block
        stats=[]
        for array in (s,a,b):
            tiles=array[:,:hh*block,:ww*block].reshape(n,hh,block,ww,block).transpose(0,1,3,2,4).astype(np.float32)/256.0
            stats.append((tiles.mean(axis=(-2,-1)),tiles.std(axis=(-2,-1))))
        mean,sd=stats[0]
        quiet=(sd.max(axis=0)<=.3)&(np.ptp(mean,axis=0)<=.5)&(mean.min(axis=0)>5)&(mean.max(axis=0)<250)
        active=quiet&(mean.min(axis=0)>20)&(mean.max(axis=0)<232)
        delta=(a[:,:hh*block,:ww*block].astype(np.float32)-b[:,:hh*block,:ww*block].astype(np.float32))/256.0
        tiles=delta.reshape(n,hh,block,ww,block).transpose(0,1,3,2,4)
        # Grain texture and a uniform code-level shift are different evidence.
        # In particular AV1 restricted-range clipping can turn superwhite
        # values into legal white without any visible texture at all.
        dc=tiles.mean(axis=(-2,-1),dtype=np.float64)
        second=np.einsum('...ij,...ij->...',tiles,tiles,dtype=np.float64)/(block*block)
        rms=np.sqrt(np.maximum(0,second-dc*dc))
        peak=rms.max(axis=0);change=np.ptp(rms,axis=0)
        record=dict(plane='YUV'[plane],units='native code levels normalized to eight bits',
            analyzed_width=ww*block,analyzed_height=hh*block,full_width=w,full_height=h,
            quiet_static_pixels=int(quiet.sum())*block*block,
            active_quiet_static_pixels=int(active.sum())*block*block,
            active_quiet_added_grain_over_1_pixels=int((active&(peak>1)).sum())*block*block,
            active_quiet_added_grain_over_3_pixels=int((active&(peak>3)).sum())*block*block,
            endpoint_quiet_added_grain_over_1_pixels=int((quiet&~active&(peak>1)).sum())*block*block,
            active_quiet_code_shift_over_3_pixels=int((active&(np.abs(dc).max(axis=0)>3)).sum())*block*block,
            endpoint_quiet_code_shift_over_3_pixels=int((quiet&~active&(np.abs(dc).max(axis=0)>3)).sum())*block*block,
            quiet_added_grain_over_1_pixels=int((quiet&(peak>1)).sum())*block*block,
            quiet_added_grain_over_3_pixels=int((quiet&(peak>3)).sum())*block*block,
            quiet_grain_change_over_1_pixels=int((quiet&(change>1)).sum())*block*block,
            whole_plane_total_difference_rms=np.sqrt(np.mean(delta*delta,axis=(1,2))).tolist(),
            whole_plane_added_noise_rms=np.sqrt(np.mean(rms*rms,axis=(1,2))).tolist())
        if quiet.any():
            y,x=np.unravel_index(np.where(quiet,peak,-1).argmax(),quiet.shape)
            record.update(peak_quiet_patch=dict(x=int(x)*block,y=int(y)*block,width=block,height=block),
                peak_quiet_grain_rms=rms[:,y,x].tolist(),peak_quiet_grain_change=float(change[y,x]),
                source_sd=sd[:,y,x].tolist(),on_sd=stats[1][1][:,y,x].tolist(),off_sd=stats[2][1][:,y,x].tolist())
            record['source_mean']=mean[:,y,x].tolist()
            record['peak_quiet_patch_dc']=dc[:,y,x].tolist()
            dy,dx=np.unravel_index(np.where(quiet,np.abs(dc).max(axis=0),-1).argmax(),quiet.shape)
            record['peak_quiet_code_shift']=dict(x=int(dx)*block,y=int(dy)*block,width=block,height=block,
                source_mean=mean[:,dy,dx].tolist(),mean_difference=dc[:,dy,dx].tolist())
        result.append(record)
    return dict(planes=result,seconds=seconds,frames=len(seconds),
        scope='Whole-frame complete 16x16 luma / 8x8 chroma blocks in aligned sampled windows. Partial edge strips are reported as uncovered. Quiet native-plane statistics require scene/display review; no repair verdict.')


def review(source_path, output_path, start, width, height, source_offset, directory):
    directory.mkdir(parents=True,exist_ok=True)
    source,source_times=decode(source_path,start+source_offset,width,height,16,directory,'source')
    on,on_times=decode(output_path,start,width,height,12,directory,'on',1)
    off,off_times=decode(output_path,start,width,height,12,directory,'off',0)
    if on_times!=off_times:raise RuntimeError('grain-on/off picture timing differs')
    source_recovery=None
    try:
        matches=align_indices(source_times,on_times,source_offset)
    except ValueError as error:
        if str(error) != 'source alignment does not cover every output picture':
            raise
        # A source seek may omit reference-dependent leading pictures or use
        # a different container start offset. Reuse the qualified bounded
        # preroll, then require every original output timestamp and the same
        # source-content match. Keep the failed first decode logs intact.
        source_recovery=dict(initial_error=str(error),preroll_seconds=10)
        del source
        source,source_times=decode(source_path,start+source_offset,width,height,16,
            directory,'source-preroll',preroll_seconds=10)
        matches=align_indices(source_times,on_times,source_offset)
    si,oi=zip(*matches);source=[p[list(si)] for p in source];on=[p[list(oi)] for p in on];off=[p[list(oi)] for p in off]
    rms=[float(np.sqrt(np.mean((coarse_picture(a)-coarse_picture(b))**2))) for a,b in zip(source[0],off[0])]
    alignment=dict(source_offset_seconds=source_offset,coarse_picture_rms=rms,source_pts=[source_times[i] for i in si],output_pts=[on_times[i] for i in oi],
        passed=max(rms)<=4.0,criterion='all aligned sampled coarse luma pictures within 4 native eight-bit RMS; diagnostic threshold, not a fidelity grade')
    if not alignment['passed']:
        result=dict(status='alignment_review_required',alignment=alignment,source_measurement_eligible=False)
    else:
        result=dict(status='source_compared',source_measurement_eligible=True,alignment=alignment,
                    measurements=measure_planes(source,on,off,alignment['output_pts']))
    if source_recovery:result['source_recovery']=source_recovery
    return result
