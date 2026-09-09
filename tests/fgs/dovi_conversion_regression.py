#!/usr/bin/env python3
"""Real-media P7 MEL to AV1 regression against independently converted RPUs.

The config pins a complete short source, original/normalized dovi_tool JSON and
RPU artifacts, encoder binaries, scanner, and a historical negative control.
No library replacement, download, or production-tool modification is performed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import time

from hdr_metadata_trace import compare, record
from production_compare import decode_validation, identity, run, sha


def validate_mel_reference(original, normalized, frames):
    if len(original) != frames or len(normalized) != frames or frames <= 0:
        raise ValueError('Independent RPU reference is incomplete')
    for before, after in zip(original, normalized):
        if before.get('dovi_profile') != 7 or before.get('el_type') != 'MEL':
            raise ValueError('This test requires a MEL source on every frame')
        if after.get('dovi_profile') != 8 or after.get('el_type'):
            raise ValueError('Independent conversion did not produce single-layer RPUs')
        header = dict(before['header'], el_spatial_resampling_filter_flag=False, disable_residual_flag=True)
        if after['header'] != header or before['vdr_dm_data'] != after['vdr_dm_data']:
            raise ValueError('Independent conversion changed display metadata or unexpected header fields')
        mapping = {k: v for k, v in before['rpu_data_mapping'].items() if not k.startswith('nlq')}
        if mapping != after['rpu_data_mapping']:
            raise ValueError('Independent MEL conversion changed reshaping curves')


def execute(config, directory):
    directory.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, started_at=time.time(), scope=__doc__, config=config,
                  harness_sha256=sha(__file__), runs=[], comparisons={})
    def save():
        (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        for item in config['pinned_files']:
            if sha(item['path']) != item['sha256']:
                raise ValueError('Changed test artifact: ' + item['path'])
        original = json.loads(Path(config['original_rpu_json']).read_text())
        normalized = json.loads(Path(config['normalized_rpu_json']).read_text())
        validate_mel_reference(original, normalized, config['frames'])
        source = Path(config['source'])
        source_before = identity(source)
        common = config['arguments']
        if any(flag in common for flag in ['-i', '-o', '--dolby-vision-profile', '--dolby-vision-rpu']):
            raise ValueError('Arguments must omit source/output and Dolby Vision selection')
        arms = [
            ('trusted_external_rpu', config['old_encoder'], config['normalized_rpu'], '10.1'),
            ('candidate_explicit', config['candidate_encoder'], 'copy', '10.1'),
            ('candidate_copy', config['candidate_encoder'], 'copy', 'copy'),
        ]
        for name, binary, rpu, profile in arms:
            out = directory / name
            out.mkdir()
            video = out / 'output.mkv'
            command = [binary, *config['prefix'], '-i', str(source), *common,
                       '--dolby-vision-rpu', rpu, '--dolby-vision-profile', profile,
                       '-o', str(video)]
            elapsed = run(command, out / 'encode.log', 1800)
            run([config['scanner'], str(video)], out / 'scan.json', 900)
            scan = json.loads((out / 'scan.json').read_text())
            if not (scan.get('complete') and scan.get('verdict') == 'stable'
                    and scan.get('criterion') == 'synthesis_texture_v1'
                    and scan.get('packets') == config['frames'] and scan.get('errors') == 0):
                raise ValueError('Candidate synthesis scan failed')
            row = dict(name=name, command=command, seconds=elapsed, file=str(video),
                       sha256=sha(video), bytes=video.stat().st_size, scan=scan, decodes={})
            report['runs'].append(row)
            save()
            print(name, 'encoded', elapsed, flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            work = {pool.submit(decode_validation, directory / row['name'], grain,
                                config['frames'], 1800, 2): (row, grain)
                    for row in report['runs'] for grain in [0, 1]}
            for future in as_completed(work):
                row, grain = work[future]
                row['decodes'][str(grain)] = future.result()
                save()
        with ThreadPoolExecutor(max_workers=2) as pool:
            work = {pool.submit(record, row['file'], directory / (row['name'] + '-metadata'),
                                config['frames'], row['sha256'], threads=2): row
                    for row in report['runs']}
            for future in as_completed(work):
                work[future]['metadata'] = future.result()
                save()
        trusted = directory / 'trusted_external_rpu-metadata'
        for name in ['candidate_explicit', 'candidate_copy']:
            result = compare(trusted, directory / (name + '-metadata'))
            report['comparisons'][name] = result
            if not result['passed']:
                raise ValueError('Candidate does not match independently normalized RPU metadata')
            stream = next(r for r in report['runs'] if r['name'] == name)['metadata']['stream']
            conf = next(s for s in stream['side_data_list'] if s['side_data_type'] == 'DOVI configuration record')
            for key, expected in dict(dv_profile=10, dv_bl_signal_compatibility_id=1,
                                      el_present_flag=0, bl_present_flag=1, rpu_present_flag=1).items():
                if conf.get(key) != expected:
                    raise ValueError('Incorrect single-layer output signaling: ' + key)
        # The pre-fix output also decoded and carried both HDR systems. Requiring
        # normalized RPUs must distinguish it from the independently correct arm.
        negative = compare(trusted, config['negative_metadata_trace'])
        report['comparisons']['historical_negative'] = negative
        if negative['passed'] or negative['different_frames'] != config['frames']:
            raise ValueError('The historical P7 RPU conversion failure was not detected')
        if negative['stream_failures'] or any(row['differences'] != ['Dolby Vision Metadata']
                                              for row in negative['first_differences']):
            raise ValueError('Negative control differs beyond the demonstrated RPU failure')
        source_comparison = compare(config['source_metadata_trace'], trusted)
        report['comparisons']['source_to_normalized'] = source_comparison
        expected_signaling_changes = {
            'Unverified Dolby Vision source-profile conversion',
            'Dolby Vision el_present_flag',
            'Dolby Vision dv_bl_signal_compatibility_id',
        }
        if set(source_comparison['stream_failures']) != expected_signaling_changes:
            raise ValueError('Unexpected source-to-AV1 stream property change')
        if any(row['differences'] != ['Dolby Vision Metadata']
               for row in source_comparison['first_differences']):
            raise ValueError('Conversion changed timestamps or other HDR metadata')
        # Check every trace row, not only the report's first diagnostic examples.
        a = Path(config['source_metadata_trace']) / 'frames.jsonl'
        b = trusted / 'frames.jsonl'
        with a.open() as fa, b.open() as fb:
            count = 0
            for sa, sb in zip(fa, fb):
                x, y = json.loads(sa), json.loads(sb)
                x['metadata'].pop('Dolby Vision Metadata', None)
                y['metadata'].pop('Dolby Vision Metadata', None)
                if x != y:
                    raise ValueError('Non-DV metadata or timing changed at frame ' + str(count))
                count += 1
            if count != config['frames']:
                raise ValueError('Incomplete source metadata correspondence')
        if identity(source) != source_before:
            raise ValueError('Source changed during regression test')
        report.update(complete=True, finished_at=time.time())
        print('P7 MEL normalization regression PASS', flush=True)
    except BaseException as error:
        report.update(error=str(error), failed_at=time.time())
        raise
    finally:
        save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    execute(json.loads(args.config.read_text()), args.output_dir)
