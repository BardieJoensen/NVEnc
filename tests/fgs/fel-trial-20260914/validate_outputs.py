"""Complete decode/syntax/timing checks and explicitly PQ-domain error measurements."""
from pathlib import Path
from fractions import Fraction
import importlib.util
import hashlib
import json
import re
import subprocess
import sys
import time

T=Path('/tmp/downloads/fgs-fel-trial-20260914')
S=Path('/opt/docker-apps/logs/fgs-ripple-repair-20260906')
L=S/'fel-reconstruction-trial-20260914'
sys.path.insert(0,'/opt/docker-apps/scripts')
spec=importlib.util.spec_from_file_location('repair','/opt/docker-apps/scripts/fgs-ripple-repair.py')
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)


def run(command, log):
    result=subprocess.run(command,capture_output=True,text=True,timeout=300)
    Path(log).write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('command failed; see '+str(log))
    return result


def main():
    encoded=json.loads((L/'encoder-trials.json').read_text())
    baseline=json.loads((L/'baseline-trials.json').read_text())
    assert encoded['stage']=='encoded_all_eight' and baseline['stage']=='complete'
    specs=encoded['trials']+baseline['trials']
    receipt=L/'output-validation.json'
    rows=json.loads(receipt.read_text()) if receipt.exists() else []
    for entry in specs:
        output=Path(entry['output']);directory=output.parent
        existing=[r for r in rows if (r['name'],r['mode'],r['output'])==(entry['name'],entry['mode'],entry['output'])]
        if existing:
            with output.open('rb') as media:
                digest=hashlib.file_digest(media,'sha256').hexdigest()
            assert digest==entry['sha256'] and existing[0]['passed']
            existing[0]['output_sha256']=digest
            print(entry['name'],entry['mode'],'REUSE VERIFIED UNCHANGED OUTPUT',flush=True)
            continue
        clock=json.loads((T/'clips'/entry['name']/'reconstruction-summary.json').read_text())
        n=clock['frames'];fps=Fraction(*clock['fps'])
        command=['ffprobe','-v','error','-threads','4','-select_streams','v:0','-count_frames',
                 '-show_streams','-show_packets','-show_entries',
                 'stream=codec_name,width,height,pix_fmt,color_space,color_transfer,color_primaries,color_range,chroma_location,r_frame_rate,nb_read_frames:stream_side_data:packet=pts_time,size',
                 '-of','json',str(output)]
        result=run(command,directory/'output-probe.log');probe=json.loads(result.stdout)
        (directory/'output-probe.json').write_text(json.dumps(probe,indent=2)+'\n')
        stream=probe['streams'][0]
        assert stream['codec_name']=='av1' and (stream['width'],stream['height'])==(3840,2160)
        assert stream['pix_fmt']=='yuv420p10le' and stream['color_space']=='bt2020nc'
        assert stream['color_transfer']=='smpte2084' and stream['color_primaries']=='bt2020'
        assert stream['color_range']=='tv'
        assert stream['chroma_location']==('topleft' if entry['mode']=='hdr10base' else 'left')
        assert not any('DOVI' in x.get('side_data_type','') for x in stream.get('side_data_list',[]))
        assert int(stream['nb_read_frames'])==n and len(probe['packets'])==n
        for k,packet in enumerate(probe['packets']):
            assert abs(Fraction(packet['pts_time'])-Fraction(k,1)/fps)<=Fraction(1,1000)
        scanner=run([str(S/'bin/fgs-scan-syntax-c7d756f7'),str(output)],directory/'grain-scan.log')
        grain=json.loads(scanner.stdout);repair.validate_grain_scan(grain)
        (directory/'grain-scan.json').write_text(json.dumps(grain,indent=2)+'\n')
        if entry['mode']=='hdr10base':
            reference=T/'clips'/entry['name']/'BL.hevc'
        elif entry['mode']=='staged_reconstructed':
            reference=T/'outputs'/(entry['name']+'-default')/'reference-pq10.y4m'
        else:
            reference=Path(entry['reference'])
        stats=directory/'psnr-pq-frames.log';progress=directory/'decode-progress.txt'
        filters=(f'[0:v]settb=1/{fps.numerator},setpts=N*{fps.denominator}[r];'
                 f'[1:v]settb=1/{fps.numerator},setpts=N*{fps.denominator}[d];'
                 f'[d][r]psnr=stats_file={stats}:stats_version=2:shortest=1:repeatlast=0[q]')
        command=['ffmpeg','-hide_banner','-v','info','-nostdin','-xerror','-err_detect','explode',
                 '-threads','4','-i',str(reference),'-threads','4','-c:v','libdav1d','-i',str(output),
                 '-filter_complex_threads','4','-filter_complex',filters,'-map','[q]',
                 '-fps_mode','passthrough','-progress',str(progress),'-stats_period','10','-f','null','-']
        result=run(command,directory/'decode-psnr.log')
        measurements=[x for x in stats.read_text().splitlines() if x.startswith('n:')]
        assert len(measurements)==n and 'progress=end' in progress.read_text()
        match=re.search(r'PSNR y:([\d.inf]+) u:([\d.inf]+) v:([\d.inf]+) average:([\d.inf]+)',result.stderr)
        assert match
        with output.open('rb') as media:
            digest=hashlib.file_digest(media,'sha256').hexdigest()
        assert digest==entry['sha256']
        row=dict(name=entry['name'],mode=entry['mode'],passed=True,frames=n,output_sha256=digest,
                 video_packet_bytes=sum(int(x['size']) for x in probe['packets']),
                 grain_scan=grain,psnr_pq={k:float(v) for k,v in zip(['y','u','v','average'],match.groups())},
                 psnr_reference=str(reference),psnr_limit='PQ code-domain error with decoded grain; not HDR perceptual quality or Dolby playback qualification',
                 output=str(output),verified_at=time.time())
        rows.append(row);(L/'output-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(row['name'],row['mode'],'PASS',row['psnr_pq']['average'],flush=True)
    assert len(rows)==len(specs)
    # The staged repeat excludes reconstruction time and tests video determinism.
    selected=next(x for x in baseline['trials'] if x['mode']=='staged_reconstructed')
    originals=[x for x in encoded['trials'] if x['name']==selected['name'] and x['mode']=='default']
    hashes=[]
    for entry in [originals[0],selected]:
        result=run(['ffmpeg','-v','error','-i',entry['output'],'-map','0:v:0','-c','copy','-f','streamhash','-hash','sha256','-'],Path(entry['output']).parent/'video-payload-sha256.txt')
        hashes.append(result.stdout.strip())
    (L/'staged-input-comparison.json').write_text(json.dumps(dict(video_payload_hashes=hashes,
        identical_video_payload=hashes[0]==hashes[1],streamed_wall_seconds=originals[0]['wall_seconds'],
        staged_wall_seconds=selected['wall_seconds'],limit='One short repeated trial; container startup and pipeline fill included.'),indent=2)+'\n')


if __name__=='__main__':main()
