#!/usr/bin/env python3
"""Prepare original video + existing non-video tracks outside the live library."""
import json, os, pathlib, subprocess
root=pathlib.Path(os.environ.get('PANTHEON_FIX_DIR','/tmp/downloads/codex-work/pantheon-fix-20261019'))
cfg=json.loads((root/'inputs.json').read_text())
out=root/'S02E04-original-video-restored.mkv'
cmd=['mkvmerge','--disable-lacing','-o',str(out),'--no-audio','--no-subtitles','--no-attachments','--no-chapters','--no-global-tags',cfg['original'],'--no-video',cfg['library']]
if not out.exists():
    r=subprocess.run(cmd,capture_output=True,text=True)
    (root/'restore-mux.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise RuntimeError(r.stdout[-1500:]+r.stderr[-1500:])

def hashes(path,maps):
    c=['ffmpeg','-v','error','-i',str(path)]
    for m in maps:c+=['-map',m]
    c+=['-c','copy','-f','streamhash','-hash','sha256','-']
    return subprocess.check_output(c,text=True).strip().splitlines()

original_hash=hashes(cfg['original'],['0:v:0'])
candidate_hash=hashes(out,['0:v:0'])
assert original_hash==candidate_hash,(original_hash,candidate_hash)
library_tracks=hashes(cfg['library'],['0:a','0:s'])
candidate_tracks=hashes(out,['0:a','0:s'])
assert library_tracks==candidate_tracks,(library_tracks,candidate_tracks)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-show_chapters','-of','json',str(out)]))
assert [s['codec_name'] for s in probe['streams']]==['h264','opus','eac3','subrip']
assert [s['disposition']['default'] for s in probe['streams']]==[1,1,0,0]
assert abs(float(probe['format']['duration'])-float(cfg['original_probe']['format']['duration']))<.05
receipt={'candidate':str(out),'mux_command':cmd,'video_packet_hashes':candidate_hash,'nonvideo_packet_hashes':candidate_tracks,
         'video_matches_original':True,'nonvideo_matches_library':True,'probe':probe,
         'library_signature':{k:getattr(pathlib.Path(cfg['library']).stat(),k) for k in ('st_ino','st_size','st_mtime_ns')},
         'status':'Prepared and verified outside live library; installation not authorized.'}
(root/'restore-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:v for k,v in receipt.items() if k not in ('probe','mux_command')},indent=2))
