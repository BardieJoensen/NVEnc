"""Native single-component alignment evidence, never source/model admission.

Copied colour need not share luma's motion proposal. This diagnostic measures
only the named component; it makes no claim about inter-component covariance.
The existing joint registration/covariance path remains separate and unchanged.
"""
import hashlib
import numpy as np
from aligned_population_reference import _Prepared, _registration, LIMITS
from motion_detail_reference import tile
from persistent_detail_reference import moments, reference


def _evidence(aligned, candidate, depth):
    source = aligned.astype(np.float64)/(1 << (depth-8))
    base = candidate.astype(np.float64)/(1 << (depth-8))
    current = source[-1]
    first, second = source[:3].mean(axis=0), source[3:7].mean(axis=0)

    def cross(a, b):
        return float(np.sum((a-a.mean())*(b-b.mean()))/(a.size-1))

    residual = cross(current-first, current-second)
    lags = [sum(cross(d, d) for d in source[lag:]-source[:-lag])/(2*(8-lag))
            for lag in (1, 2, 3)]
    history = cross(first-second, first-second)
    history_mean = float(first.mean()-second.mean())
    current_mean = float(current.mean()-.5*(first.mean()+second.mean()))
    conflicts = []
    if residual < .04 or residual > 256:
        conflicts.append('conditional_variance_outside_study_range')
    if residual <= 0 or any(abs(lag-residual) > .2*residual for lag in lags):
        conflicts.append('lag_energy_inconsistent')
    if residual <= 0 or abs(history-(1/3+1/4)*residual) > .3*(1/3+1/4)*residual:
        conflicts.append('disjoint_histories_inconsistent')
    if abs(history_mean) > 1 or abs(current_mean) > 1:
        conflicts.append('mean_changed')
    return dict(samples=current.size, history_split=[3, 4],
                source_variance=cross(current, current),
                persistent_variance=cross(first, second),
                source_residual_variance=residual,
                base_residual_variance=cross(base-first, base-second),
                source_base_residual_covariance=.5*(cross(current-first, base-second)
                                                    + cross(current-second, base-first)),
                removed_structure_covariance=.5*(cross(current-base, first)+cross(current-base, second)),
                lag_difference_variance=lags, history_difference_variance=history,
                history_mean_difference=history_mean, current_mean_difference=current_mean,
                conflicts=conflicts)


def diagnose_component(prepared, component, x, y):
    """Measure a canonical native Y64/C32 region of an immutable source pair.

    Registration never reads another component, the candidate cannot select
    motion, and native Y is never averaged before its detail/noise measurements.
    Missing support and failed consistency remain explicit unknowns/conflicts.
    """
    if not isinstance(prepared, _Prepared):
        raise ValueError('prepare native source history first')
    if type(component) is not int or component not in (0, 1, 2):
        raise ValueError('one native component required')
    source, base = prepared.history[component], prepared.base[component]
    depth, ids, pts = prepared.depth, prepared.ids, prepared.pts
    side = 32 if component else 64
    radius = 16 if component else 32
    height, width = base.shape
    if (type(x) is not int or type(y) is not int or x < 0 or y < 0
            or x % side or y % side or x >= width or y >= height):
        raise ValueError('canonical native component coordinates required')
    result = dict(hypothesis_only=True, source_admission=False, detail_admission=False,
                  joint_admission=False, component=component, x=x, y=y,
                  width=min(side, width-x), height=min(side, height-y),
                  frame_id=int(ids[-1]), epoch=int(prepared.epochs[0]),
                  registration_supported=False, reason=None, evidence=None)
    if x+side > width or y+side > height:
        result['reason'] = 'partial_current_border'
        return result
    original = source[:, y:y+side, x:x+side]
    candidate = base[y:y+side, x:x+side]
    result['unaligned'] = _evidence(original, candidate, depth)
    motion = tile(source, base, depth, side, radius, 4, x, y, native_match=True)
    registration = _registration(source, depth, side, radius, x, y, motion)
    result.update(native_motion=motion, registration=registration)
    if motion['fit_samples'] < 16 or registration['samples'] < 16:
        result['reason'] = 'insufficient_search_support'
        return result
    dx, dy = registration['dx'], registration['dy']
    if (dx or dy) and not (registration['motion_supported'] and registration['anchor_supported']):
        result['reason'] = 'motion_not_independently_supported'
        return result
    aligned, locations = [], []
    for frame in range(8):
        xx, yy = x+(7-frame)*dx, y+(7-frame)*dy
        if xx < 0 or yy < 0 or xx+side > width or yy+side > height:
            result['reason'] = 'insufficient_full_history_overlap'
            return result
        aligned.append(source[frame, yy:yy+side, xx:xx+side])
        locations.append([xx, yy, side, side])
    aligned = np.array(aligned)
    persistent = reference(moments(aligned, candidate, depth, ids, pts), LIMITS)
    result['persistent'] = persistent
    if not (dx or dy) and not persistent['anchors_supported']:
        result['reason'] = 'stationary_source_anchors_missing'
        return result
    result.update(registration_supported=True, history_coordinates=locations,
                  aligned_native_sha256=[hashlib.sha256(np.ascontiguousarray(p,dtype='<u2').tobytes()).hexdigest()
                                         for p in aligned],
                  candidate_native_sha256=hashlib.sha256(np.ascontiguousarray(candidate,dtype='<u2').tobytes()).hexdigest(),
                  evidence=_evidence(aligned, candidate, depth),
                  persistent_detail_conflict=bool(abs(persistent['mean_error']) > .125
                    or (persistent['anchors_supported'] and not persistent['within_limits'])))
    return result
