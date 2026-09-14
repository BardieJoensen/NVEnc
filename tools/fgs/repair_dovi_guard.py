"""Dolby Vision admission for the separate retained-source repair worker.

P7 uses the same initial 120-picture MEL/FEL classification as Tdarr. FEL or
uncertain classification retains the library file and original. Successful P7
conversion additionally requires the independently qualified encoder build.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

P7_ENCODER = 'bb7e75cbcb9097f1f1c7ac3347e7193c74caa6c7d57db1c3c77348cc27daf144'


def comparable_tags(tags):
    """Matroska can omit an empty TrackName while preserving its meaning."""
    return {k: v for k, v in tags.items()
            if k.lower() in ['language', 'title', 'filename', 'mimetype']
            and not (k.lower() == 'title' and v == '')}


def file_hash(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def classify(summary):
    kinds = set(re.findall(r'Profile:\s*7\s*\((FEL|MEL)\)', summary, re.I))
    kinds = {v.upper() for v in kinds}
    if len(kinds) != 1:
        raise ValueError('Dolby Vision P7 layer type is missing or ambiguous')
    return kinds.pop()


def admit_p7(kind, encoder_sha256, arguments):
    if kind != 'MEL':
        raise ValueError('Dolby Vision FEL repair held: this repair path does not reconstruct its enhancement layer')
    if encoder_sha256 != P7_ENCODER:
        raise ValueError('P7 MEL repair requires the qualified RPU-normalizing encoder')
    for flag, expected in [('--dolby-vision-rpu', 'copy'), ('--dolby-vision-profile', '10.1')]:
        if arguments.count(flag) != 1 or arguments.index(flag) + 1 == len(arguments) or arguments[arguments.index(flag)+1] != expected:
            raise ValueError('P7 replay requires reviewed in-stream RPU copy and profile 10.1; transient RPU paths are not reusable')


def prepare_source(info, source, config, directory, arguments):
    primary = [s for s in info['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if len(primary) != 1:
        raise ValueError('Expected one primary source video')
    video = primary[0]
    conf = [d for d in video.get('side_data_list', []) if d.get('side_data_type') == 'DOVI configuration record']
    if not conf:
        return {'has_dovi': False}
    if len(conf) != 1:
        raise ValueError('Ambiguous Dolby Vision configuration')
    result = {'has_dovi': True, 'source_configuration': conf[0]}
    if conf[0].get('dv_profile') != 7:
        return result
    if video['codec_name'] != 'hevc':
        raise ValueError('P7 repair source must be HEVC')
    tool = config['dovi_tool']
    if file_hash(tool) != config['dovi_tool_sha256']:
        raise ValueError('Repair dovi_tool changed')
    with tempfile.TemporaryDirectory(prefix='fgs-repair-dovi-') as temporary:
        hevc, rpu = Path(temporary)/'sample.hevc', Path(temporary)/'sample.bin'
        commands = [
            ['/usr/local/bin/ffmpeg', '-v', 'error', '-nostdin', '-i', str(source), '-map', f"0:{video['index']}",
             '-frames:v', '120', '-an', '-sn', '-dn', '-c:v', 'copy', '-bsf:v', 'hevc_mp4toannexb', '-f', 'hevc', str(hevc)],
            [tool, 'extract-rpu', '-l', '120', str(hevc), '-o', str(rpu)],
            [tool, 'info', '-s', str(rpu)],
        ]
        transcripts = []
        for command in commands:
            p = subprocess.run(command, capture_output=True, text=True, timeout=300, check=True)
            transcripts.append(p.stdout + '\n' + p.stderr)
        summary = transcripts[-1]
        Path(directory, 'dovi-source-classification.log').write_text('\n'.join(transcripts))
    kind = classify(summary)
    result.update(layer_type=kind, sampled_pictures=120,
                  classification_scope='Initial 120 pictures, matching Tdarr; not a whole-file layer-type audit')
    Path(directory, 'dovi-source-classification.json').write_text(json.dumps(result, indent=2)+'\n')
    admit_p7(kind, config['encoder_sha256'], arguments)
    return result


def validate_output(output, config):
    guard = config['dovi_output_guard']
    if file_hash(guard) != config['dovi_output_guard_sha256']:
        raise ValueError('Repair Dolby Vision output guard changed')
    code = "const g=require(process.argv[1]);g.plugin({inputFileObj:{_id:process.argv[2]},variables:{user:{}},jobLog:()=>{}}).then(r=>process.stdout.write(JSON.stringify(r.variables.user.fidelityDoviCheck))).catch(e=>{process.stderr.write(e.message);process.exitCode=1})"
    p = subprocess.run(['/usr/bin/node', '-e', code, guard, str(output)], capture_output=True,
                       text=True, timeout=300, check=True)
    result = json.loads(p.stdout)
    if result.get('passed') is not True or result.get('has_dovi') is not True:
        raise ValueError('Repaired output lost Dolby Vision metadata')
    return result
