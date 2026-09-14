"""Observe grain over every frame of four diagnostic outputs; no damage threshold."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from run_encoder_trials import T,L

BINARY=Path('/opt/docker-apps/logs/fgs-ripple-repair-20260906/bin/fgs-grain-inspect-reference-0d4cfdce')
EXPECTED='0d4cfdcea0766f85b4300425cca2e35b3a7e3ecbf234d2c355f0bfc2c1d5cf24'


def main():
    with BINARY.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==EXPECTED
    record=dict(binary=str(BINARY),binary_sha256=EXPECTED,
        interpretation='Every displayed frame measured with fixed HDR display mapping. Grain on/off runs are observations, not automatic damage verdicts; scene and source context matter.',rows=[])
    for entry in json.loads((L/'encoder-trials.json').read_text())['trials']:
        if entry['mode']!='default':continue
        output=Path(entry['output']);directory=output.parent;csv_path=directory/'decoded-grain.csv'
        command=[str(BINARY),'--extended',str(output),str(csv_path)]
        with (directory/'decoded-grain.log').open('w') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        rows=list(csv.DictReader(csv_path.open()))
        clock=json.loads((T/'clips'/entry['name']/'reconstruction-summary.json').read_text())
        assert len(rows)==clock['frames']
        runs=[]
        for n,r in enumerate(rows):
            on=bool(int(r['grain_present']))
            if not runs or runs[-1]['grain_present']!=on:runs.append(dict(first_frame=n,last_frame=n,grain_present=on))
            else:runs[-1]['last_frame']=n
        result=dict(name=entry['name'],frames=len(rows),command=command,runs=runs,
            scene_refresh_frames=clock['scene_refresh_frames'],
            peak_luma_rms=max(float(x['luma_rms']) for x in rows))
        record['rows'].append(result);(L/'decoded-grain-observation.json').write_text(json.dumps(record,indent=2)+'\n')
        print(entry['name'],runs,flush=True)


if __name__=='__main__':main()
