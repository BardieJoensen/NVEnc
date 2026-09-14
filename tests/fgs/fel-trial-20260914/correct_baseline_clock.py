"""Finite correction of four diagnostic controls, without pausing Tdarr again.

Encodes run serially alongside ordinary workers, so elapsed times are explicitly
excluded from performance comparisons. The earlier invalid controls are retained.
"""
from pathlib import Path
from fractions import Fraction
import json
import shutil
import subprocess
import time
from run_encoder_trials import T, L, co, IMAGE, IMAGE_ID, ENCODER_SHA, sha


def main():
    prior=L/'baseline-trials-invalid-clock.json'
    assert not prior.exists()
    shutil.copy2(L/'baseline-trials.json', prior)
    old=json.loads(prior.read_text())
    record=dict(stage='correcting_raw_hevc_input_clock', image_id=IMAGE_ID,
                encoder_sha256=ENCODER_SHA, invalid_prior_record=str(prior),
                timing_excluded_reason='Serial short controls alongside ordinary Tdarr workers; not an isolated throughput benchmark.',
                trials=[])
    def save(): (L/'baseline-trials.json').write_text(json.dumps(record,indent=2)+'\n')
    save()
    assert subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',IMAGE],text=True).strip()==IMAGE_ID
    for original in old['trials']:
        if original['mode']!='hdr10base':
            record['trials'].append(original);save();continue
        assert not co.watchdog.emby_gpu_transcodes()
        assert shutil.disk_usage(T).free>50*1024**3
        free_mib=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
        assert free_mib>6000
        clock=json.loads((T/'clips'/original['name']/'reconstruction-summary.json').read_text())
        fps=Fraction(*clock['fps'])
        directory=T/'outputs'/(original['name']+'-hdr10base-fps-corrected');directory.mkdir()
        output=directory/'candidate-pq-av1.mkv'
        cmd=list(original['command']);cmd.extend(['--fps',str(fps)])
        cmd[cmd.index('-o')+1]='/trial/'+str(output.relative_to(T))
        workers=co.tdarr_node().get('workers',{})
        began=time.monotonic()
        with (directory/'encoder.log').open('w') as log:
            process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            try:
                while process.poll() is None:
                    if time.monotonic()-began>120 or co.watchdog.emby_gpu_transcodes():
                        subprocess.run(['docker','stop','-t','2','fgs-fel-baseline-20260914'],capture_output=True)
                        raise RuntimeError('stopped for playback/time limit')
                    time.sleep(.5)
                if process.returncode:raise RuntimeError('corrected baseline failed')
            finally:
                if process.poll() is None:process.terminate()
        elapsed=time.monotonic()-began
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_packets','-show_entries','packet=pts_time','-of','json',str(output)],text=True))
        assert len(probe['packets'])==clock['frames']
        assert all(abs(Fraction(p['pts_time'])-Fraction(k,1)/fps)<=Fraction(1,1000)
                   for k,p in enumerate(probe['packets']))
        row=dict(original,name=original['name'],command=cmd,output=str(output),bytes=output.stat().st_size,
                 sha256=sha(output),wall_seconds=elapsed,source_fps=str(fps),clock_check_passed=True,
                 ordinary_workers_during_trial=len(workers),performance_comparison_valid=False)
        record['trials'].append(row);save();print(row['name'],row['bytes'],'CLOCK PASS',flush=True)
    record.update(stage='complete',finished_at=time.time());save()


if __name__=='__main__':main()
