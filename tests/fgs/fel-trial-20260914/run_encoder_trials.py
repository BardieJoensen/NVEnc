"""Finite GPU comparisons, admitted only after Tdarr drains and playback is idle."""
from pathlib import Path
from fractions import Fraction
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time

T = Path('/tmp/downloads/fgs-fel-trial-20260914')
L = Path('/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-reconstruction-trial-20260914')
IMAGE = 'nvenc-fidelity/tdarr-node:2.87.01-ef5c61fe-20260912'
IMAGE_ID = 'sha256:218540effe6149030631445914c8f35c6e81090326a8e4bbca55d0b57c3f50e4'
ENCODER_SHA = 'd8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b'
sys.path.insert(0, '/opt/docker-apps/scripts')
spec = importlib.util.spec_from_file_location('co', '/opt/docker-apps/scripts/fgs-ripple-coordinator.py')
co = importlib.util.module_from_spec(spec); spec.loader.exec_module(co)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(record):
    (L/'encoder-trials.json').write_text(json.dumps(record, indent=2)+'\n')


def hdr_arguments(directory):
    data = json.loads((directory/'hdr-static-probe.json').read_text())['frames'][0]['side_data_list']
    md = next(x for x in data if x['side_data_type']=='Mastering display metadata')
    def chroma(key): return int(Fraction(md[key])*50000)
    text = ''.join(f'{label}({chroma(x)},{chroma(y)})' for label,x,y in [
        ('G','green_x','green_y'),('B','blue_x','blue_y'),('R','red_x','red_y'),
        ('WP','white_point_x','white_point_y')])
    text += f"L({int(Fraction(md['max_luminance'])*10000)},{int(Fraction(md['min_luminance'])*10000)})"
    # Retain mastering display information. Whole-source MaxCLL/FALL are not
    # reasserted as measurements of these reconstructed excerpts.
    return ['--master-display', text]


def main():
    assert subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',IMAGE], text=True).strip()==IMAGE_ID
    binary_hash = subprocess.check_output(['docker','run','--rm','--entrypoint','sha256sum',IMAGE,'/usr/bin/nvencc'], text=True).split()[0]
    assert binary_hash == ENCODER_SHA
    record = dict(stage='waiting_for_tdarr_and_cpu_measurements', started_at=time.time(), image=IMAGE,
                  image_id=IMAGE_ID, encoder_sha256=binary_hash, trials=[], production_changes=False)
    write(record)
    deadline = time.monotonic()+1200
    while True:
        node = co.tdarr_node()
        path = T/'results/reconstruction-summary.json'
        summaries = json.loads(path.read_text()) if path.exists() else []
        if not node.get('workers') and len(summaries)==8 and not co.watchdog.emby_gpu_transcodes():
            break
        if time.monotonic()>deadline:
            raise RuntimeError('trial admission deadline reached; restore owned pause and inspect')
        time.sleep(5)
    record['stage']='encoding';write(record)
    for directory in sorted((T/'clips').glob('*-20')):
        for mode in ['default','noresidual']:
            assert not co.tdarr_node().get('workers')
            if co.watchdog.emby_gpu_transcodes():
                raise RuntimeError('playback became active before trial admission')
            assert shutil.disk_usage(T).free > 50*1024**3
            output_dir = T/'outputs'/(directory.name+'-'+mode)
            output_dir.mkdir(parents=True)
            relative = str(output_dir.relative_to(T))
            output = output_dir/'candidate-pq-av1.mkv'
            reference = output_dir/'reference-pq10.y4m'
            producer_cmd = ['docker','exec','fgs-fel-trial-20260914','bash','/trial/scripts/env.sh',
                'vspipe','--requests','2','--container','y4m','--arg','clip_name='+directory.name,
                '--arg','mode='+mode,'--timecodes','/trial/'+relative+'/reference-timecodes.txt',
                '/trial/scripts/encode_input.vpy','-']
            container = 'fgs-fel-encode-20260914'
            encoder_args = ['--y4m','-i','-','--codec','av1','--output-depth','10','--qvbr','29',
                '--max-bitrate','50000','--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral',
                '--preset','quality','--tune','hq','--lookahead','32','--lookahead-level','3',
                '--aq','--aq-temporal','--colormatrix','bt2020nc','--colorprim','bt2020',
                '--transfer','smpte2084','--colorrange','limited','--chromaloc','0',
                *hdr_arguments(directory),'-o','/trial/'+relative+'/candidate-pq-av1.mkv']
            encoder_cmd = ['docker','run','--rm','-i','--name',container,'--gpus','all','--network','none',
                '--cpus','4','--memory','4g','--memory-swap','4g','--user',str(__import__('os').getuid()),
                '-v',str(T)+':/trial','--entrypoint','/usr/bin/nvencc',IMAGE,*encoder_args]
            trial = dict(name=directory.name,mode=mode,output=str(output),reference=str(reference),
                         producer_command=producer_cmd,encoder_command=encoder_cmd,started_at=time.time(),
                         status='running',dolby_vision_metadata=False)
            record['trials'].append(trial);write(record)
            start = time.monotonic(); processes=[]
            try:
                with (output_dir/'producer.log').open('w') as plog, (output_dir/'encoder.log').open('w') as elog:
                    producer = subprocess.Popen(producer_cmd,stdout=subprocess.PIPE,stderr=plog);processes.append(producer)
                    tee = subprocess.Popen(['tee',str(reference)],stdin=producer.stdout,stdout=subprocess.PIPE,stderr=plog)
                    processes.append(tee);producer.stdout.close()
                    encoder = subprocess.Popen(encoder_cmd,stdin=tee.stdout,stdout=elog,stderr=subprocess.STDOUT)
                    processes.append(encoder);tee.stdout.close()
                    while encoder.poll() is None:
                        if time.monotonic()-start>600 or co.watchdog.emby_gpu_transcodes():
                            raise RuntimeError('trial stopped for playback or elapsed-time limit')
                        time.sleep(3)
                    codes=[p.wait(timeout=20) for p in processes]
                trial.update(returncodes=codes,wall_seconds=time.monotonic()-start)
                if any(codes) or not output.is_file():
                    raise RuntimeError('trial pipeline did not complete')
                trial.update(status='encoded',bytes=output.stat().st_size,reference_bytes=reference.stat().st_size,
                             sha256=sha(output),reference_sha256=sha(reference))
                write(record);print(directory.name,mode,trial['bytes'],trial['wall_seconds'],flush=True)
            finally:
                for process in processes:
                    if process.poll() is None: process.terminate()
                if subprocess.run(['docker','inspect',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
                    subprocess.run(['docker','stop','-t','2',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    record.update(stage='encoded_all_eight',finished_at=time.time());write(record)


if __name__ == '__main__':
    main()
