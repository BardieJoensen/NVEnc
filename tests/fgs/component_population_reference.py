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


def _selected_registration(source, depth, side, radius, x, y, proposal):
    """Choose stationary or translation using only the two training pairs.

    A best displacement always exists, including on independent noise. Require
    affirmative training evidence before using it to align the history. Later
    validation can reject the choice, but cannot replace it with another model.
    """
    height, width = source.shape[1:]
    xs = np.arange(max(x, radius+1), min(x+side, width-radius-1))
    ys = np.arange(max(y, radius+1), min(y+side, height-radius-1))
    count = int(xs.size*ys.size)
    result = dict(dx=0, dy=0, samples=count, training_mse=0.,
                  zero_mse=[0., 0.], shifted_mse=[0., 0.], improvement=[0., 0.],
                  motion_supported=False, anchor_supported=False, correlation=0.,
                  validation_searches=0, source_model='stationary',
                  training_pairs=[[0, 1], [2, 3]], proposal_dx=0, proposal_dy=0,
                  training_zero_mse=[0., 0.], training_shifted_mse=[0., 0.],
                  training_improvement=[0., 0.], training_correlation=[0., 0.])
    if proposal['fit_samples'] < 16 or count < 16:
        return result

    def pixels(frame, dy=0, dx=0):
        return source[frame, (ys+dy)[:, None], xs+dx].astype(np.float64)

    def correlation(a, b):
        a, b = a-a.mean(), b-b.mean()
        energy = float(np.sum(a*a)*np.sum(b*b))
        return float(np.sum(a*b)/np.sqrt(energy)) if energy > 0 else 0.

    offsets = [(dy, dx)
               for dy in range(max(-radius, proposal['dy']-1), min(radius, proposal['dy']+1)+1)
               for dx in range(max(-radius, proposal['dx']-1), min(radius, proposal['dx']+1)+1)]
    offsets.sort(key=lambda p: (p != (0, 0), abs(p[0])+abs(p[1]), p))
    costs = [sum(float(np.sum((pixels(after)-pixels(before, dy, dx))**2))
                 for before, after in result['training_pairs']) for dy, dx in offsets]
    dy, dx = offsets[int(np.argmin(costs))]
    result.update(proposal_dx=dx, proposal_dy=dy)
    scale = 1 << (depth-8)
    for i, (before, after) in enumerate(result['training_pairs']):
        current, shifted = pixels(after), pixels(before, dy, dx)
        zero = float(np.mean((current-pixels(before))**2)/(scale*scale))
        moved = float(np.mean((current-shifted)**2)/(scale*scale))
        result['training_zero_mse'][i] = zero
        result['training_shifted_mse'][i] = moved
        result['training_improvement'][i] = (zero-moved)/zero if zero > 0 else 0.
        result['training_correlation'][i] = correlation(current, shifted)
    translation = bool((dx or dy) and all(
        zero > .04 and improvement > .2 and corr >= .5
        for zero, improvement, corr in zip(result['training_zero_mse'],
            result['training_improvement'], result['training_correlation'])))
    if translation:
        result.update(dx=dx, dy=dy, source_model='translation')
    else:
        dx = dy = 0
    result['training_mse'] = float(np.mean(result[
        'training_shifted_mse' if translation else 'training_zero_mse']))

    # Neither the independent pairs nor the candidate can alter this choice.
    for i, (before, after) in enumerate(((4, 5), (6, 7))):
        current = pixels(after)
        zero = float(np.mean((current-pixels(before))**2)/(scale*scale))
        moved = float(np.mean((current-pixels(before, dy, dx))**2)/(scale*scale))
        result['zero_mse'][i], result['shifted_mse'][i] = zero, moved
        result['improvement'][i] = (zero-moved)/zero if zero > 0 else 0.
    result['correlation'] = correlation(pixels(7), pixels(6, dy, dx))
    result['anchor_supported'] = result['correlation'] >= .5
    result['motion_supported'] = bool(translation and all(
        z > .04 and improvement > .2
        for z, improvement in zip(result['zero_mse'], result['improvement'])))
    return result


def _stationary_consistency(aligned, depth, evidence):
    """Veto source evolution hidden by the short constant-history model.

    Two disjoint least-squares line predictions use original even 0/2/4/6 and
    odd 1/3/5 frames to predict time 7. Neither prediction contains frame 7.
    Agreement does not prove stationarity; disagreement forbids treating the
    constant-history estimate as trustworthy. Never choose the nicer estimate.
    """
    source = aligned.astype(np.float64)/(1 << (depth-8))
    first = (-7*source[0]+source[2]+9*source[4]+17*source[6])/20
    second = (-2*source[1]+source[3]+4*source[5])/3
    a, b = source[7]-first, source[7]-second
    linear = float(np.sum((a-a.mean())*(b-b.mean()))/(a.size-1))
    constant = evidence['source_residual_variance']
    within = bool(linear > 0 and constant > 0
                  and abs(linear-constant) <= .08*min(linear, constant))
    return dict(linear_residual_variance=linear, constant_residual_variance=constant,
                absolute_disagreement=abs(linear-constant), within_limits=within,
                prediction_frame_groups=[[0, 2, 4, 6], [1, 3, 5]],
                relative_disagreement_limit=.08, source_admission=False)


def _diagnose_component(prepared, component, x, y, select_stationary):
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
    if select_stationary:
        result['registration_policy'] = 'source_selected_stationary_or_translation_v2'
    if not select_stationary and (x+side > width or y+side > height):
        result['reason'] = 'partial_current_border'
        return result
    tw, th = result['width'], result['height']
    if select_stationary and tw*th < 16:
        result['reason'] = 'insufficient_visible_support'
        return result
    original = source[:, y:y+th, x:x+tw]
    candidate = base[y:y+th, x:x+tw]
    result['unaligned'] = _evidence(original, candidate, depth)
    motion = tile(source, base, depth, side, radius, 4, x, y, native_match=True)
    registration = (_selected_registration if select_stationary else _registration)(
        source, depth, side, radius, x, y, motion)
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
        if xx < 0 or yy < 0 or xx+tw > width or yy+th > height:
            result['reason'] = 'insufficient_full_history_overlap'
            return result
        aligned.append(source[frame, yy:yy+th, xx:xx+tw])
        locations.append([xx, yy, tw, th])
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
    if select_stationary and registration['source_model'] == 'stationary':
        consistency = _stationary_consistency(aligned, depth, result['evidence'])
        result['stationary_consistency'] = consistency
        if not consistency['within_limits']:
            result['evidence']['conflicts'].append('stationary_and_linear_predictions_disagree')
    return result


def diagnose_component(prepared, component, x, y):
    """Original D74 diagnostic; its results and admission scope are unchanged."""
    return _diagnose_component(prepared, component, x, y, False)


def diagnose_selected_component(prepared, component, x, y):
    """Explicit source-only model selection, including actual border pixels.

    This is a necessary diagnostic, not a new grain/detail admission rule.
    No retry follows independent validation failure. Missing anchors, search
    support or complete shifted history remain unknown. All older consistency
    and persistent-detail vetoes still apply to the selected source history.
    """
    return _diagnose_component(prepared, component, x, y, True)
