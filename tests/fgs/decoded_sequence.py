"""Independent decoded-picture regression against one pinned, reviewed SDR clip.

These bounds detect changes to that fixture. They do not classify arbitrary
movies as damaged, and are not calibrated for HDR or different display mapping.
The measurements contain luma and red/blue display channels, not raw U/V planes.
"""
import csv
from pathlib import Path
import numpy as np

CHANNELS = ('luma', 'red', 'blue')


def load(path, frames=3600, fps=24, correlations=False):
    with Path(path).open() as source:
        rows = list(csv.DictReader(source))
    suffixes = ('rms', 'max_patch_rms', 'correlation', 'score', 'dx', 'dy') + (
                tuple('acf_' + str(i) for i in range(12)) if correlations else ())
    fields = ('seconds', 'grain_present') + tuple(c + '_' + f for c in CHANNELS for f in suffixes)
    if len(rows) != frames or not rows or tuple(rows[0]) != fields:
        raise ValueError('incomplete or unexpected decoded measurement stream')
    data = {field: np.array([float(row[field]) for row in rows]) for field in fields}
    if any(not np.isfinite(values).all() for values in data.values()):
        raise ValueError('non-finite decoded measurement')
    if not np.all(np.abs(data['seconds'] - np.arange(frames) / fps) <= .0011):
        raise ValueError('missing, reordered, or misaligned displayed timestamps')
    if not np.isin(data['grain_present'], (0, 1)).all():
        raise ValueError('invalid grain presence flag')
    for c in CHANNELS:
        if (data[c + '_rms'] < 0).any() or (data[c + '_score'] < 0).any():
            raise ValueError('negative grain amplitude')
        if (data[c + '_rms'][data['grain_present'] == 0] != 0).any():
            raise ValueError('grain-free frame has a measured grain residual')
    return data


def runs(mask, fps=24):
    boundaries = np.diff(np.r_[False, mask, False].astype(int))
    lengths = np.flatnonzero(boundaries == -1) - np.flatnonzero(boundaries == 1)
    return dict(frames=int(np.count_nonzero(mask)), measured_seconds=float(np.count_nonzero(mask) / fps),
                runs=len(lengths), longest_run_seconds=float(lengths.max() / fps) if len(lengths) else 0.)


def describe(data):
    present = data['grain_present'].astype(bool)
    result = dict(frames=len(present), grain=runs(present),
                  grain_on_off_transitions=int(np.count_nonzero(np.diff(present))), channels={})
    for c in CHANNELS:
        score = data[c + '_score']; rms = data[c + '_rms']
        peak = int(np.argmax(score))
        result['channels'][c] = dict(peak_score=float(score[peak]), peak_seconds=float(data['seconds'][peak]),
                                     rms_p95=float(np.quantile(rms, .95)),
                                     max_adjacent_rms_change=float(np.max(abs(np.diff(rms)))))
    return result


def compare(candidate, reference):
    """Fail on texture, amplitude, or temporal changes requiring fresh review.

    The reviewed positive has a maximum channel score of 1.61; the known mesh
    reaches 3.54. Two is a fixture ceiling. Per-frame comparisons additionally
    catch relocation/recurrence, disappearing grain, and new on/off pumping.
    Numerical margins are small because this is the same source and settings;
    intentional quality/model changes require a reviewed baseline update.
    """
    if len(candidate['seconds']) != len(reference['seconds']) or not np.array_equal(candidate['seconds'], reference['seconds']):
        raise ValueError('candidate and reference frames are not aligned')
    failures = []
    switches = candidate['grain_present'] != reference['grain_present']
    if switches.any():
        failures.append(dict(check='grain scheduling changed', **runs(switches)))
    for c in CHANNELS:
        score, previous = candidate[c + '_score'], reference[c + '_score']
        texture = (score > 2.) | (score > previous * 1.10 + .10)
        # Compare all signed offsets. The strongest offset can switch at a
        # near-tie without a meaningful texture change, even on unchanged code.
        correlation = np.any([abs(candidate[c + '_acf_' + str(i)] - reference[c + '_acf_' + str(i)]) > .10
                              for i in range(12)], axis=0)
        amplitude = abs(candidate[c + '_rms'] - reference[c + '_rms']) > reference[c + '_rms'] * .10 + .15
        temporal = abs(np.diff(candidate[c + '_rms']) - np.diff(reference[c + '_rms'])) > .25
        for check, mask in [('texture changed', texture), ('amplitude changed', amplitude),
                            ('signed correlation vector changed', correlation),
                            ('adjacent-frame grain change', temporal)]:
            if mask.any():
                failures.append(dict(check=check, channel=c, **runs(mask)))
    return dict(passed=not failures, failures=failures, candidate=describe(candidate), reference=describe(reference),
                scope='All displayed frames, nine native spatial patches, SDR luma/red/blue. Pinned-fixture change detector; no universal perceptual verdict.')
