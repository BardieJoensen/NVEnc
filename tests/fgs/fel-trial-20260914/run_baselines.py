"""Ordinary base-layer comparison and one staged-input speed/determinism control."""
from pathlib import Path
import json
import subprocess
import time
from run_encoder_trials import T, L, co, IMAGE, IMAGE_ID, ENCODER_SHA, sha


def main():
    while True:
        data=json.loads((L/'encoder-trials.json').read_text())
        if data['stage']=='encoded_all_eight':break
        time.sleep(3)
    record=dict(stage='running',image_id=IMAGE_ID,encoder_sha256=ENCODER_SHA,trials=[])
    def save(): (L/'baseline-trials.json').write_text(json.dumps(record,indent=2)+'\n')
    save()
    full=[x for x in data['trials'] if x['mode']=='default']
    cases=[(x,'hdr10base') for x in full]+[(full[0],'staged_reconstructed')]
    for original,mode in cases:
        assert not co.tdarr_node().get('workers') and not co.watchdog.emby_gpu_transcodes()
        directory=T/'outputs'/(original['name']+'-'+mode);directory.mkdir()
        cmd=list(original['encoder_command'])
        cmd[cmd.index('--name')+1]='fgs-fel-baseline-20260914'
        # Remove docker's stdin switch; the encoder now reads the mounted file.
        cmd.remove('-i')
        if mode=='hdr10base':
            cmd[cmd.index('--y4m')]='--avhw'
            input_name='/trial/clips/'+original['name']+'/BL.hevc'
            cmd[cmd.index('--chromaloc')+1]='2'  # Original BL: top-left, verified by probe.
            # Elementary HEVC lacks container timestamps; its demuxer defaults
            # to 25 fps. Use the independently checked original/BL/EL clock.
            clock=json.loads((T/'clips'/original['name']/'reconstruction-summary.json').read_text())
            cmd.extend(['--fps', '/'.join(map(str, clock['fps']))])
        else:
            input_name='/trial/'+str(Path(original['reference']).relative_to(T))
        cmd[cmd.index('-i')+1]=input_name
        cmd[cmd.index('-o')+1]='/trial/'+str(directory.relative_to(T))+'/candidate-pq-av1.mkv'
        start=time.monotonic()
        with (directory/'encoder.log').open('w') as log:
            process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            try:
                while process.poll() is None:
                    if time.monotonic()-start>180 or co.watchdog.emby_gpu_transcodes():
                        subprocess.run(['docker','stop','-t','2','fgs-fel-baseline-20260914'],capture_output=True)
                        raise RuntimeError('baseline stopped for playback/time limit')
                    time.sleep(.5)
                if process.returncode:raise RuntimeError('baseline encode failed')
            finally:
                if process.poll() is None:process.terminate()
        output=directory/'candidate-pq-av1.mkv'
        row=dict(name=original['name'],mode=mode,command=cmd,returncode=process.returncode,
                 wall_seconds=time.monotonic()-start,output=str(output),bytes=output.stat().st_size,sha256=sha(output))
        record['trials'].append(row);save();print(row['name'],mode,row['bytes'],row['wall_seconds'],flush=True)
    record.update(stage='complete',finished_at=time.time());save()


if __name__=='__main__':main()
