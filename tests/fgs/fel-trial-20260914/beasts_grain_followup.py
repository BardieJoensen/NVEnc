"""Manually invoked two-encode diagnosis with owned admission pause/restoration."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
from run_encoder_trials import T,L,co,sha


def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n')


def main():
    directory=T/'beasts-grain-followup';directory.mkdir()
    prior=next(r for r in json.loads((L/'encoder-trials.json').read_text())['trials']
               if r['name']=='1f373204e9b8d9b771a9-20' and r['mode']=='default')
    record=dict(stage='regenerating_reference',trials=[],started_at=time.time());save(L/'beasts-grain-followup.json',record)
    node=co.tdarr_node();pause_path=L/'tdarr-grain-followup-pause.json'
    pause=dict(previous_node_paused=node.get('nodePaused'),owns_pause=False,created_at=time.time())
    save(pause_path,pause)
    if node.get('nodePaused') is False:
        co.set_paused(node,True);pause['owns_pause']=True;save(pause_path,pause)
    container='fgs-fel-beasts-followup-20260914'
    try:
        env=dict(os.environ,FEL_TRIAL_ROOT=str(T),PYTHONPATH=str(T/'prefix/lib/python3.12/site-packages')+':'+str(T/'scripts'),
                 LD_LIBRARY_PATH=str(T/'prefix/lib')+':/usr/local/lib',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        command=['systemd-run','--user','--pipe','--wait','--collect','--unit=fgs-fel-beasts-producer-20260914',
                 '-p','CPUQuota=400%','-p','MemoryMax=6G','-p','MemorySwapMax=0']
        for key in ['FEL_TRIAL_ROOT','PYTHONPATH','LD_LIBRARY_PATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']:
            command.extend(['--setenv',key+'='+env[key]])
        reference=directory/'reference-pq10.y4m'
        command.extend([str(T/'prefix/bin/vspipe'),'--requests','2','--container','y4m','--arg','clip_name='+prior['name'],
                        str(T/'scripts/encode_input.vpy'),str(reference)])
        with (directory/'regeneration.log').open('w') as log:
            subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        assert sha(reference)==prior['reference_sha256']
        record.update(stage='waiting_for_tdarr',reference=str(reference),reference_sha256=sha(reference),
                      exact_original_reference_reproduced=True,regeneration_command=command);save(L/'beasts-grain-followup.json',record)
        deadline=time.monotonic()+600
        while co.tdarr_node().get('workers'):
            if time.monotonic()>deadline:raise RuntimeError('Tdarr drain deadline reached')
            time.sleep(3)
        for mode in ['fgs_debug','no_fgs']:
            if co.watchdog.emby_gpu_transcodes():raise RuntimeError('playback active; no trial admitted')
            output_dir=directory/mode;output_dir.mkdir();output=output_dir/'candidate.mkv'
            cmd=list(prior['encoder_command']);cmd.remove('-i')
            cmd[cmd.index('--name')+1]=container
            cmd[cmd.index('-i')+1]='/trial/'+str(reference.relative_to(T))
            cmd[cmd.index('-o')+1]='/trial/'+str(output.relative_to(T))
            cmd.extend(['--log-level','vpp=debug'])
            if mode=='no_fgs':
                k=cmd.index('--av1-film-grain');del cmd[k:k+2]
            began=time.monotonic()
            with (output_dir/'encoder.log').open('w') as log:
                process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
                while process.poll() is None:
                    if co.watchdog.emby_gpu_transcodes() or time.monotonic()-began>120:
                        subprocess.run(['docker','stop','-t','2',container],capture_output=True)
                        raise RuntimeError('trial stopped for playback/time limit')
                    time.sleep(.5)
                if process.returncode:raise RuntimeError('diagnostic encode failed')
            record['trials'].append(dict(mode=mode,command=cmd,output=str(output),bytes=output.stat().st_size,
                sha256=sha(output),wall_seconds=time.monotonic()-began))
            save(L/'beasts-grain-followup.json',record);print(mode,'complete',flush=True)
        record.update(stage='encodes_complete',finished_at=time.time());save(L/'beasts-grain-followup.json',record)
    finally:
        if subprocess.run(['docker','inspect',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
            subprocess.run(['docker','stop','-t','2',container],capture_output=True)
        if pause['owns_pause']:
            co.set_paused(co.tdarr_node(),False);pause.update(owns_pause=False,restored_at=time.time(),node_paused_after=co.tdarr_node().get('nodePaused'));save(pause_path,pause)


if __name__=='__main__':main()
