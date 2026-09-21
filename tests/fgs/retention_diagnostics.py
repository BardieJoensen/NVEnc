#!/usr/bin/env python3
"""Summarize existing encoder debug logs without decoding or encoding video.

Legacy logs cannot distinguish the colour subconditions or recovery-model
failure from rejection of freshly fitted colour. Unknown means unknown.
Diagnostic events are overlapping model decisions, not visible-damage labels.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

CHROMA_REASONS = {
    0: 'eligible', 1: 'invalid_plane', 2: 'scaling_from_luma',
    3: 'unsupported_lag', 4: 'invalid_shift', 5: 'signalled_coupling',
    6: 'insufficient_observations', 7: 'invalid_variance', 8: 'missing_energy',
    9: 'missing_predictor', 10: 'spatial_correlation', 11: 'invalid_correlation',
    12: 'measured_coupling', 254: 'inactive', 255: 'not_evaluated',
}
SOURCE_REASONS = {
    1: 'no_model', 2: 'feedback_rejected', 4: 'missing_adjacent_picture',
    8: 'strength_mismatch', 16: 'local_mismatch', 32: 'colour_restore_rejected',
    64: 'covariance_recovery_rejected', 128: 'dc_limit', 256: 'recovery_hold',
    512: 'insufficient_flat_blocks',
    1024: 'source_support_rejected', 2048: 'synthesis_recovery_hold',
}
EVENT = re.compile(r'\b(fgs-model|fgs-local-covariance|fgs-local-chroma|fgs-local-strength) frame=(\d+)\b')
FIELD = re.compile(r'\b([A-Za-z][A-Za-z0-9]*)=(-?\d+(?:\.\d+)?)\b')


def identity(path):
    s = Path(path).stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def flag(fields, name):
    value = fields.get(name)
    if value not in ('0', '1'):
        raise ValueError(f'missing/invalid {name}: {value}')
    return value == '1'


def first_covariance_blocker(fields):
    independent = flag(fields, 'colourIndependent')
    recovered = flag(fields, 'recovered')
    ready = flag(fields, 'covariance')
    if recovered and (not independent or not ready):
        raise ValueError('inconsistent covariance recovery')
    if 'trace' not in fields:
        if not independent:
            return 'held_colour_unknown'
        if not ready:
            return 'covariance_evidence_rejected'
        return 'recovered' if recovered else 'model_or_fresh_colour_unknown'
    if fields['trace'] != '1':
        raise ValueError('unsupported diagnostic trace version')
    attempt = flag(fields, 'covarianceAttempted')
    minimum = flag(fields, 'minFramesEligible')
    fit_attempt = flag(fields, 'fitAttempted')
    fit_success = flag(fields, 'fitSucceeded')
    if attempt != (independent and minimum) or (ready and not attempt):
        raise ValueError('inconsistent covariance attempt')
    if fit_attempt != ready or (fit_success and not fit_attempt):
        raise ValueError('inconsistent model-fit attempt')
    reasons = {key: int(fields[key]) for key in ('heldCb', 'heldCr', 'freshCb', 'freshCr')}
    if any(code not in CHROMA_REASONS for code in reasons.values()):
        raise ValueError('unknown colour reason')
    if any(reasons[k] == 255 for k in ('heldCb', 'heldCr')):
        raise ValueError('held colour check was not recorded')
    held_pass = all(reasons[k] in (0, 254) for k in ('heldCb', 'heldCr'))
    fresh_pass = all(reasons[k] in (0, 254) for k in ('freshCb', 'freshCr'))
    if independent != held_pass or recovered != (fit_success and fresh_pass):
        raise ValueError('inconsistent colour decision')
    if not fit_success and any(reasons[k] != 255 for k in ('freshCb', 'freshCr')):
        raise ValueError('fresh colour recorded without a completed fit')
    if fit_success and any(reasons[k] == 255 for k in ('freshCb', 'freshCr')):
        raise ValueError('completed fit is missing its fresh colour check')
    if not independent:
        return 'held_colour_rejected'
    if not minimum:
        return 'minimum_model_frames'
    if not ready:
        return 'covariance_evidence_rejected'
    if not fit_success:
        return 'model_fit_rejected'
    return 'recovered' if recovered else 'fresh_colour_rejected'


class DecisionProfiles:
    """Join checks on the same frame without retaining a per-frame log in RAM."""

    def __init__(self):
        self.rows = {}
        self.active = None

    def finish_run(self):
        if self.active is None:
            return
        key, first, last = self.active
        row = self.rows[key]
        run = dict(first_frame=first, last_frame=last, frames=last - first + 1)
        if row['longest_run'] is None or run['frames'] > row['longest_run']['frames']:
            row['longest_run'] = run
        self.active = None

    def add(self, frame_id, reliable, mask, blocker, colour_reasons,
            local_mismatch, restore_checks):
        key = reliable, mask, blocker, colour_reasons, local_mismatch, restore_checks
        if key not in self.rows:
            self.rows[key] = dict(
                outcome='reliable_model' if reliable else 'source_preserved',
                source_reason_mask=mask,
                source_reasons=None if mask is None else
                    [label for bit, label in SOURCE_REASONS.items() if mask & bit],
                covariance_first_blocker=blocker,
                covariance_colour_reasons=None if colour_reasons is None else
                    dict(zip(('heldCb', 'heldCr', 'freshCb', 'freshCr'), colour_reasons)),
                local_mismatch_logged=local_mismatch,
                rejected_restore_planes=[plane for plane, independent, reason in restore_checks if not independent],
                component_restore_checks={str(plane): dict(independent=independent, reason=reason)
                                          for plane, independent, reason in restore_checks},
                frames=0, first_frame=frame_id, last_frame=frame_id, longest_run=None)
        row = self.rows[key]
        row['frames'] += 1
        row['last_frame'] = frame_id
        if self.active is not None and (key != self.active[0] or frame_id != self.active[2] + 1):
            self.finish_run()
        self.active = (key, self.active[1], frame_id) if self.active else (key, frame_id, frame_id)

    def result(self):
        self.finish_run()
        return sorted(self.rows.values(), key=lambda row: (-row['frames'], row['first_frame']))


def analyze_log(path, expected_frames=None, fps=None):
    path = Path(path)
    before = identity(path)
    digest = hashlib.sha256()
    counts, blockers, colours, source_reasons = Counter(), Counter(), Counter(), Counter()
    current_id, events = None, {}
    first_id, last_id, frame_count = None, None, 0
    longest, active_run = [], None
    missing = 0
    profiles = DecisionProfiles()

    def finish_frame(frame_id, frame_events):
        nonlocal first_id, last_id, frame_count, missing, active_run
        model = frame_events.get(('fgs-model', None))
        if model is None:
            raise ValueError(f'frame {frame_id} has events but no final model decision')
        if first_id is None:
            first_id = frame_id
        if last_id is not None:
            missing += frame_id - last_id - 1
        last_id = frame_id
        frame_count += 1
        reliable = flag(model, 'reliable')
        if 'sourceFallback' in model:
            fallback = flag(model, 'sourceFallback')
        elif 'trace' not in model and not reliable and model.get('window') == '0':
            # Qualified older builds log the early flat-block rejection in a
            # shorter format, before any fidelity checks have been attempted.
            fallback = False
            counts['legacy_early_flat_rejection'] += 1
        else:
            raise ValueError('model decision has no sourceFallback field')
        if fallback and reliable:
            raise ValueError('source fallback cannot also be a reliable synthesis model')
        counts['model_reliable' if reliable else 'source_preserved'] += 1
        counts['fidelity_source_fallback'] += fallback
        if reliable or (active_run is not None and frame_id != active_run[1] + 1):
            if active_run is not None:
                longest.append(active_run)
                longest.sort(key=lambda x: x[1] - x[0], reverse=True)
                del longest[20:]
                active_run = None
        if not reliable:
            active_run = [frame_id, frame_id] if active_run is None else [active_run[0], frame_id]
        mask = None
        if 'trace' in model:
            if model['trace'] != '1':
                raise ValueError('unsupported model trace version')
            mask = int(model['sourceReasons'])
            if mask < 0 or mask & ~sum(SOURCE_REASONS):
                raise ValueError('unknown source-reason bits')
            if bool(mask) == reliable:
                raise ValueError('source-reason mask disagrees with final model decision')
            counts['frames_with_precise_source_reasons'] += 1
            for bit, label in SOURCE_REASONS.items():
                source_reasons[label] += bool(mask & bit)
        elif not reliable:
            source_reasons['legacy_unattributed'] += 1

        blocker, colour_reasons = None, None
        covariance = frame_events.get(('fgs-local-covariance', None))
        if covariance:
            counts['covariance_events'] += 1
            blocker = first_covariance_blocker(covariance)
            blockers[blocker] += 1
            counts['covariance_recovered_but_final_source'] += blocker == 'recovered' and not reliable
            if 'trace' in covariance:
                counts['covariance_calls'] += flag(covariance, 'covarianceAttempted')
                counts['covariance_calls_skipped'] += not flag(covariance, 'covarianceAttempted')
                for key in ('heldCb', 'heldCr', 'freshCb', 'freshCr'):
                    colours[f'{key}:{CHROMA_REASONS[int(covariance[key])]}'] += 1
                colour_reasons = tuple(CHROMA_REASONS[int(covariance[key])]
                                       for key in ('heldCb', 'heldCr', 'freshCb', 'freshCr'))
            else:
                counts['legacy_covariance_calls'] += 1
                counts['legacy_calls_avoidable_from_held_colour'] += not flag(covariance, 'colourIndependent')
        restore_checks = []
        for (event, plane), fields in frame_events.items():
            if event != 'fgs-local-chroma':
                continue
            independent = flag(fields, 'independent')
            if plane not in ('1', '2'):
                raise ValueError('invalid component-restoration plane')
            counts['component_restore_eligible' if independent else 'component_restore_rejected'] += 1
            reason = None
            if fields.get('trace') == '1':
                code = int(fields['reason'])
                if code not in CHROMA_REASONS or code >= 254 or independent != (code == 0):
                    raise ValueError('inconsistent component-restoration reason')
                colours[f'component{plane}:{CHROMA_REASONS[code]}'] += 1
                reason = CHROMA_REASONS[code]
            elif 'trace' in fields:
                raise ValueError('unsupported component trace version')
            restore_checks.append((int(plane), independent, reason))
        profiles.add(frame_id, reliable, mask, blocker, colour_reasons,
                     ('fgs-local-strength', 'mismatch') in frame_events,
                     tuple(sorted(restore_checks)))

    with path.open('rb') as handle:
        for raw in handle:
            digest.update(raw)
            # Progress messages may share a physical line with a debug record.
            line = raw.decode('utf-8', errors='replace')
            match = EVENT.search(line)
            if not match:
                continue
            event, value = match.groups()
            frame_id = int(value)
            if current_id is not None and frame_id < current_id:
                raise ValueError('frame order restarted; split the encode logs first')
            if current_id is not None and frame_id != current_id:
                finish_frame(current_id, events)
                events = {}
            current_id = frame_id
            fields = dict(FIELD.findall(line[match.start():]))
            plane = fields.get('plane') if event == 'fgs-local-chroma' else None
            # Local refit and a later mismatch may both be logged for one frame.
            if event == 'fgs-local-strength':
                if 'mismatch' in fields and flag(fields, 'mismatch'):
                    events[(event, 'mismatch')] = fields
                continue
            key = event, plane
            if key in events:
                raise ValueError(f'duplicate {event} at frame {frame_id}')
            events[key] = fields
    if current_id is not None:
        finish_frame(current_id, events)
    if active_run is not None:
        longest.append(active_run)
    if identity(path) != before:
        raise ValueError('log changed during analysis')
    rate = Fraction(fps) if fps else None
    if rate is not None and rate <= 0:
        raise ValueError('frame rate must be positive')
    longest.sort(key=lambda x: x[1] - x[0], reverse=True)
    runs = [dict(first_frame=a, last_frame=b, frames=b - a + 1,
                 nominal_duration_seconds=float(Fraction(b - a + 1) / rate) if rate else None)
            for a, b in longest[:20]]
    decisions = profiles.result()
    combinations = Counter()
    for row in decisions:
        if row['outcome'] == 'source_preserved':
            combinations[row['source_reason_mask']] += row['frames']
    reason_sets = [dict(mask=mask, reasons=None if mask is None else
                       [label for bit, label in SOURCE_REASONS.items() if mask & bit], frames=count)
                   for mask, count in sorted(combinations.items(),
                                             key=lambda item: (-item[1], -1 if item[0] is None else item[0]))]
    overlap = dict(unknown_source_frames=combinations.get(None, 0),
                   single_recorded_reason_frames=sum(count for mask, count in combinations.items()
                       if mask is not None and mask & (mask - 1) == 0),
                   multiple_recorded_reason_frames=sum(count for mask, count in combinations.items()
                       if mask is not None and mask & (mask - 1) != 0),
                   combinations=reason_sets)
    return dict(schema=2, complete=frame_count > 0 and missing == 0
                and (expected_frames is None or frame_count == expected_frames),
                log=str(path.resolve()), log_sha256=digest.hexdigest(), identity=before,
                expected_frames=expected_frames, frames=frame_count, first_frame=first_id,
                last_frame=last_id, missing_frame_decisions=missing,
                counters=dict(counts), covariance_first_blocker=dict(blockers),
                colour_checks=dict(colours), source_reasons=dict(source_reasons),
                source_reason_overlap=overlap, decision_profiles=decisions,
                longest_source_runs=runs,
                limits=['Model decisions do not classify visibly damaged frames.',
                        'Legacy logs do not expose colour subconditions or recovery hold.',
                        'Source reasons overlap; covariance blockers are exclusive per event.',
                        'Profiles record co-occurring checks, not counterfactual recovery or byte savings.',
                        'Absent events do not establish that a check ran and passed.',
                        'Profile runs locate historical decisions; short excerpts may have different temporal state.',
                        'Durations use nominal frame rate, not measured presentation timestamps.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--frames', type=int)
    p.add_argument('--fps')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = analyze_log(args.log, args.frames, args.fps)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
