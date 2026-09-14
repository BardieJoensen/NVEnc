"""Validate the two additional diagnostic outputs and compare their payloads."""
from pathlib import Path
from fractions import Fraction
import json
import re
import subprocess
from run_encoder_trials import T,L,sha
from validate_outputs import run,repair,S

record=json.loads((L/'beasts-grain-followup.json').read_text());assert record['stage']=='encodes_complete'
reference=Path(record['reference']);assert sha(reference)==record['reference_sha256']
rows=[]
for entry in record['trials']:
    output=Path(entry['output']);directory=output.parent
    assert sha(output)==entry['sha256']
    result=run(['ffprobe','-v','error','-threads','4','-select_streams','v:0','-count_frames',
        '-show_streams','-show_packets','-show_entries',
        'stream=codec_name,width,height,pix_fmt,color_space,color_transfer,color_primaries,color_range,chroma_location,nb_read_frames:packet=pts_time,size',
        '-of','json',str(output)],directory/'output-probe.json')
    probe=json.loads(result.stdout);s=probe['streams'][0];packets=probe['packets']
    assert (s['codec_name'],s['width'],s['height'],s['pix_fmt'])==('av1',3840,2160,'yuv420p10le')
    assert (s['color_space'],s['color_transfer'],s['color_primaries'],s['color_range'],s['chroma_location'])==('bt2020nc','smpte2084','bt2020','tv','left')
    assert int(s['nb_read_frames'])==len(packets)==165
    assert all(abs(Fraction(p['pts_time'])-Fraction(k*1001,24000))<=Fraction(1,1000) for k,p in enumerate(packets))
    result=run([str(S/'bin/fgs-scan-syntax-c7d756f7'),str(output)],directory/'grain-scan.json')
    scan=json.loads(result.stdout)
    if entry['mode']=='fgs_debug':repair.validate_grain_scan(scan)
    else:assert scan['grain_present']==0 and scan['complete'] and scan['errors']==0
    stats=directory/'psnr-pq-frames.log'
    filters=f'[0:v]settb=1/24000,setpts=N*1001[r];[1:v]settb=1/24000,setpts=N*1001[d];[d][r]psnr=stats_file={stats}:stats_version=2:shortest=1:repeatlast=0[q]'
    result=run(['ffmpeg','-hide_banner','-v','info','-nostdin','-xerror','-err_detect','explode',
        '-threads','4','-i',str(reference),'-threads','4','-c:v','libdav1d','-i',str(output),
        '-filter_complex_threads','4','-filter_complex',filters,'-map','[q]','-fps_mode','passthrough','-f','null','-'],directory/'decode-psnr.log')
    assert len([x for x in stats.read_text().splitlines() if x.startswith('n:')])==165
    match=re.search(r'PSNR y:([\d.inf]+) u:([\d.inf]+) v:([\d.inf]+) average:([\d.inf]+)',result.stderr);assert match
    payload=run(['ffmpeg','-v','error','-i',str(output),'-map','0:v:0','-c','copy','-f','streamhash','-hash','sha256','-'],directory/'payload-sha256.txt').stdout.strip()
    rows.append(dict(mode=entry['mode'],passed=True,frames=165,video_packet_bytes=sum(int(p['size']) for p in packets),
        psnr_pq={k:float(v) for k,v in zip(['y','u','v','average'],match.groups())},payload_sha256=payload))
original=T/'outputs/1f373204e9b8d9b771a9-20-default/candidate-pq-av1.mkv'
payload=run(['ffmpeg','-v','error','-i',str(original),'-map','0:v:0','-c','copy','-f','streamhash','-hash','sha256','-'],original.parent/'payload-sha256.txt').stdout.strip()
identical=next(r for r in rows if r['mode']=='fgs_debug')['payload_sha256']==payload
assert identical
(L/'beasts-followup-validation.json').write_text(json.dumps(dict(rows=rows,
    diagnostic_logging_preserved_original_video_payload=identical,
    limit='PQ code-domain PSNR, not HDR perceptual approval.'),indent=2)+'\n')
print(json.dumps(rows,indent=2));print('Debug reproduction matches original AV1 payload')
