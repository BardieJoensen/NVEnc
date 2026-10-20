#!/usr/bin/env python3
"""Independent R16 midpoint-refinement packet/native-stage derivation.

Every mutable R16 input is supplied with its expected SHA.  This script must
not be run until the parent identifies the selected matched-rate attempt and
its admitted native evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import numpy as np

HELP = Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/analyze_psyex_boundary.py')
HELP_SHA = '1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'
EXPECTED_ADMIT_SHA = 'fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb'
EXPECTED_ENCODER_SHA = '5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4'
EXPECTED_CONTRACT_SHA = '9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82'
W, H = 1920, 1080
BOXES = {'shirt': (1200, 650, 200, 100), 'background': (950, 50, 250, 180), 'face': (160, 600, 500, 480)}


def ident(path: Path) -> dict:
    path = path.resolve()
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest, 'size': path.stat().st_size}


def exact(path: Path, expected: str) -> dict:
    row = ident(path)
    assert row['sha256'] == expected, (row, expected)
    return row


def exact_record(row: dict) -> Path:
    path = Path(row['path'])
    assert ident(path) == row
    return path


def y(path: Path) -> np.ndarray:
    values = np.fromfile(path, dtype='<u2')
    assert values.size in (W * H, W * H * 3 // 2)
    values = values[: W * H].reshape(H, W).astype(np.float64) / 4
    assert np.isfinite(values).all() and values.min() >= 0 and values.max() <= 255.75
    return values


def intersection(begin: dict, box: tuple[int, int, int, int]) -> int:
    x, y0, w, h = (int(begin[k]) for k in ('x', 'y', 'w', 'h'))
    rx, ry, rw, rh = box
    return max(0, min(x + w, rx + rw) - max(x, rx)) * max(0, min(y0 + h, ry + rh) - max(y0, ry))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--admission', type=Path, required=True)
    ap.add_argument('--admission-sha', required=True)
    ap.add_argument('--command', type=Path, required=True)
    ap.add_argument('--command-sha', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    assert not args.output.exists()
    script_before = ident(Path(__file__))
    inputs = {
        'admission': exact(args.admission, args.admission_sha),
        'command': exact(args.command, args.command_sha),
        'helper': exact(HELP, HELP_SHA),
    }
    admission = json.loads(args.admission.read_text())
    command = json.loads(args.command.read_text())
    assert admission['status'] == 'admitted' and command['status'] == 'encoded'
    assert admission['case'] == command['case'] == 'e05-1440'
    assert admission['tag'] == command['tag']
    assert admission['script']['sha256'] == EXPECTED_ADMIT_SHA
    exact_record(admission['script'])
    assert admission['original_receipt'] == admission['artifacts']['original_receipt'] == inputs['command']
    assert command['executed_script']['sha256'] == EXPECTED_ENCODER_SHA
    assert command['contract']['sha256'] == EXPECTED_CONTRACT_SHA
    exact_record(command['contract'])
    assert command['calibration']['phase'] == 'midpoint-refinement'
    assert 1 <= int(command['calibration']['attempt']) <= 3
    assert command.get('calibration_response_within_bracket') is True
    assert 'synthetic_control_only' not in command
    assert command['within_source_ceiling'] and command['matched_rate_comparable']
    assert admission['all336_exact'] and admission['actual_committed_owner']
    assert admission['all_traced_roi_owners_source_predictor_preloop_exact']
    assert admission['all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact']

    packet_path = exact_record(command['packet_window'])
    packet = json.loads(packet_path.read_text())
    assert packet['mkv']['selected_indices'] == [96, 336]
    mkv_packets = packet['mkv']['packets']
    assert len(mkv_packets) == 336
    selected_bytes = sum(int(row['size']) for row in mkv_packets[96:336])
    actual_mbps = selected_bytes * 8 / 10 / 1_000_000
    assert actual_mbps == packet['mkv']['actual_mbps'] == packet['actual_mbps'] == command['actual_mbps']
    pass_seconds = sum(float(command['passes'][name]['seconds']) for name in ('pass1', 'pass2'))
    assert pass_seconds == command['wall_seconds']
    for name in ('pass1', 'pass2'):
        assert command['passes'][name]['returncode'] == 0
        exact_record(command['passes'][name]['log'])

    surfaces = {name: y(exact_record(row)) for name, row in admission['source_boundaries'].items()}
    assert set(surfaces) == {'original', 'coding_input', 'preloop', 'postloop'}
    decoder = json.loads(exact_record(admission['decoder_admission']).read_text())
    assert decoder['status'] == 'admitted' and decoder['all336_allplanes_exact']
    assert decoder['complete_visible_luma_ownership'] and decoder['all_events_independently_bound']
    assert decoder['r9_stages'] == admission['source_boundaries']

    tokens = json.loads(exact_record(admission['token_manifest']).read_text())
    assert len(tokens) == admission['tokens'] and len({int(t['token']) for t in tokens}) == len(tokens)
    category_state = Counter()
    rois = {}
    for name, box in BOXES.items():
        invoked = uninvoked = 0
        q_pixels = Counter()
        categories = Counter()
        positive_eob_pixels = zero_eob_pixels = 0
        for token in tokens:
            count = intersection(token['begin'], box)
            if not count:
                continue
            stages = token['stages']
            info = token['info']
            eob = int(token['end']['eob'])
            category = int(token['category'])
            category_state[(bool(stages), info is None, eob > 0, category)] += count
            categories[str(category)] += count
            if stages:
                q = int(info['actual_qindex'])
                assert q == int(token['commit']['qindex'])
                q_pixels[str(q)] += count
                invoked += count
            else:
                assert info is None and eob == 0
                uninvoked += count
            if eob > 0:
                assert category == 4
                positive_eob_pixels += count
            else:
                zero_eob_pixels += count
        assert invoked + uninvoked == box[2] * box[3]
        assert positive_eob_pixels + zero_eob_pixels == box[2] * box[3]
        assert admission['quantization'][name]['invoked_pixels'] == invoked
        assert admission['quantization'][name]['uninvoked_pixels'] == uninvoked
        assert admission['quantization'][name]['qindex_invoked_pixels'] == dict(q_pixels)
        rois[name] = {
            'pixels': box[2] * box[3], 'invoked_pixels': invoked,
            'uninvoked_pixels': uninvoked, 'positive_eob_pixels': positive_eob_pixels,
            'zero_eob_pixels': zero_eob_pixels, 'qindex_invoked_pixels': dict(q_pixels),
            'category_pixels': dict(categories), 'stages': {},
        }

    assert ident(Path(__file__)) == script_before
    spec = importlib.util.spec_from_file_location('boundary_helper', HELP)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    for name, box in BOXES.items():
        x0, y0, width, height = box
        source = surfaces['original'][y0:y0 + height, x0:x0 + width]
        for stage, frame in surfaces.items():
            crop = frame[y0:y0 + height, x0:x0 + width]
            descriptor = helper.luma_pair(source, crop)
            rois[name]['stages'][stage] = {
                'mse': float(np.mean(np.square(crop - source))),
                'hf_sigma': float(descriptor['hf_sigma']),
                'acf1': None if descriptor['acf1'] is None else float(descriptor['acf1']),
                'hf_corr_source': None if descriptor.get('hf_corr_source') is None else float(descriptor['hf_corr_source']),
            }

    result = {
        'status': 'complete', 'script': script_before, 'inputs': inputs,
        'packet_cost': {
            'selected_packets': 240, 'selected_mkv_bytes': selected_bytes,
            'actual_mbps_recomputed': actual_mbps, 'source_mbps': command['source_mbps'],
            'rate_ratio': actual_mbps / command['source_mbps'],
            'within_source_ceiling': command['within_source_ceiling'],
            'matched_rate_comparable': command['matched_rate_comparable'],
            'packet_receipt': ident(packet_path),
        },
        'runtime': {
            'pass1_seconds': command['passes']['pass1']['seconds'],
            'pass2_seconds': command['passes']['pass2']['seconds'],
            'two_pass_seconds_recomputed': pass_seconds,
        },
        'native_join': {
            'all336_exact': True, 'complete_visible_luma_ownership': True,
            'all_events_independently_bound': True, 'tokens': len(tokens),
            'positive_units': admission['positive_units'],
            'source_change_count': admission['source_change_count'],
            'category_state_pixels': {'|'.join(map(str, key)): value for key, value in sorted(category_state.items())},
        },
        'whole_luma': {
            'original_equals_coding_input': bool(np.array_equal(surfaces['original'], surfaces['coding_input'])),
            'preloop_equals_postloop': bool(np.array_equal(surfaces['preloop'], surfaces['postloop'])),
        },
        'rois': rois,
        'scope': 'One admitted target frame from a selected real midpoint-refinement encode for native stages; packet rate/runtime cover that selected full encode. No playback or full-window stage attribution.',
    }
    assert ident(Path(__file__)) == script_before
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('optimized Python prohibited')
    main()
