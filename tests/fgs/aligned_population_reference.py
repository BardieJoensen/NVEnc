"""Conditional structured-source grain estimates after validated alignment.

Finite development hypothesis only. Registration is source-only; detail vetoes,
temporal dependence and population admission remain separate requirements.
Native luma is used for motion/detail. Chroma covariance uses the matching
2x2-averaged luma, as in the existing joint-model measurement contract.
"""
import hashlib
from dataclasses import dataclass
import numpy as np
from motion_detail_reference import validate, tile
from persistent_detail_reference import moments, reference
from temporal_population_reference import measure
from temporal_stationarity_reference import consistency

LIMITS = dict(relative_projected_contrast_change=.02, absolute_projected_rms_8bit=.125,
              absolute_mean_error_8bit=.125, minimum_source_history_correlation=.5,
              minimum_history_history_correlation=.8)


def _co_located(pictures):
    y = pictures[0]
    if y.ndim == 3:
        y = y.astype(np.float64).reshape(8, 32, 2, 32, 2).mean(axis=(2, 4))
        return np.stack([y, *pictures[1:]], axis=1)
    y = y.astype(np.float64).reshape(32, 2, 32, 2).mean(axis=(1, 3))
    return np.array([y, *pictures[1:]], dtype=np.float64)


def _registration(source, depth, side, radius, x, y, proposal):
    """Refine spatially sampled motion using training pixels only.

    A sampled grid can miss the phase within replicated 2x2 luma blocks. The
    fixed full-native neighborhood resolves that ambiguity without searching
    validation frames, interpolating source grain or consulting the candidate.
    """
    h,w=source.shape[1:]
    xs=np.arange(max(x,radius+1),min(x+side,w-radius-1))
    ys=np.arange(max(y,radius+1),min(y+side,h-radius-1))
    result=dict(dx=proposal['dx'],dy=proposal['dy'],samples=int(xs.size*ys.size),
                training_mse=0.,zero_mse=[0.,0.],shifted_mse=[0.,0.],improvement=[0.,0.],
                motion_supported=False,anchor_supported=False,correlation=0.,validation_searches=0)
    if proposal['fit_samples']<16 or result['samples']<16:return result
    offsets=[(dy,dx) for dy in range(max(-radius,proposal['dy']-1),min(radius,proposal['dy']+1)+1)
             for dx in range(max(-radius,proposal['dx']-1),min(radius,proposal['dx']+1)+1)]
    offsets.sort(key=lambda p:(p!=(0,0),abs(p[0])+abs(p[1]),p))
    def samples(frame,dy=0,dx=0):
        return source[frame,(ys+dy)[:,None],xs+dx].astype(np.int32)
    def cost(before,after,dy,dx):
        delta=samples(after)-samples(before,dy,dx)
        return int(np.sum(delta.astype(np.int64)**2))
    costs=[cost(0,1,dy,dx)+cost(2,3,dy,dx) for dy,dx in offsets]
    index=int(np.argmin(costs));dy,dx=offsets[index];scale=1<<(depth-8)
    denominator=result['samples']*scale*scale
    result.update(dx=dx,dy=dy,training_mse=costs[index]/(2*denominator))
    for i,(before,after) in enumerate(((4,5),(6,7))):
        zero=cost(before,after,0,0)/denominator;shifted=cost(before,after,dy,dx)/denominator
        result['zero_mse'][i]=zero;result['shifted_mse'][i]=shifted
        if zero>0:result['improvement'][i]=(zero-shifted)/zero
    s=samples(7).astype(float);a=samples(6,dy,dx).astype(float);s-=s.mean();a-=a.mean()
    energy=float(np.sum(s*s)*np.sum(a*a))
    if energy>0:result['correlation']=float(np.sum(s*a)/np.sqrt(energy))
    result['anchor_supported']=result['correlation']>=.5
    result['motion_supported']=bool((dx or dy) and all(z>.04 and q>.2
        for z,q in zip(result['zero_mse'],result['improvement'])))
    return result


@dataclass(frozen=True)
class _Prepared:
    history: tuple
    base: tuple
    depth: int
    ids: tuple
    pts: tuple
    epochs: tuple


def prepare(history, base, depth, ids, pts, epochs):
    """Validate once and own immutable snapshots for a finite regional census.

    Revalidating all UHD history pixels for every 32x32 region is unnecessary.
    Bytes-backed snapshots also prevent later caller edits from invalidating the
    source/base association or bypassing the one-time native-code checks.
    This is an offline CPU representation, not a streaming encoder allocation.
    """
    if len(history) != 3 or len(base) != 3:
        raise ValueError('all three native components required')
    history = [np.asarray(p) for p in history]; base = [np.asarray(p) for p in base]
    if history[0].ndim != 3: raise ValueError('native history shape')
    height,width = history[0].shape[1:]
    if height & 1 or width & 1: raise ValueError('native 4:2:0 geometry required')
    for c in range(3):
        expected=(8,height//(2 if c else 1),width//(2 if c else 1))
        if history[c].shape != expected: raise ValueError('native component geometry differs')
        validate(history[c],base[c],depth,32 if c else 64,16 if c else 32,4,ids,pts)
    epochs=np.asarray(epochs)
    if (epochs.shape!=(8,) or epochs.dtype.kind not in 'iu' or np.any(epochs<0)
            or np.any(epochs!=epochs[0])):
        raise ValueError('one continuous source epoch required')
    def snapshot(a):
        return np.frombuffer(np.ascontiguousarray(a,dtype='<u2').tobytes(),dtype='<u2').reshape(a.shape)
    return _Prepared(tuple(snapshot(p) for p in history),tuple(snapshot(p) for p in base),
                     depth,tuple(map(int,ids)),tuple(map(int,pts)),tuple(map(int,epochs)))


def diagnose_prepared(prepared, x, y):
    """One canonical region from a validated immutable source/candidate pair.

    Integer indexing never wraps, pads or interpolates unavailable history.
    Supported registration never establishes grain or detail admission.
    """
    if not isinstance(prepared,_Prepared):raise ValueError('prepare native source history first')
    history,base,depth,ids,pts,epochs=(prepared.history,prepared.base,prepared.depth,
                                    prepared.ids,prepared.pts,prepared.epochs)
    height,width=history[0].shape[1:]
    if (type(x) is not int or type(y) is not int or x<0 or y<0 or x%32 or y%32
            or x>=width//2 or y>=height//2):
        raise ValueError('canonical chroma tile coordinates required')
    result=dict(hypothesis_only=True,source_admission=False,detail_admission=False,
                registration_supported=False,reason=None,frame_id=int(ids[-1]),
                epoch=int(epochs[0]),chroma_tile=[x,y],native_motion=[],registration=[],persistent=[],
                evidence=None,conflicts=None)
    if x+32>width//2 or y+32>height//2:
        result['reason']='partial_current_border';return result
    original=[];candidate=[]
    for c in range(3):
        factor=1 if c else 2;side=32*factor;xx,yy=x*factor,y*factor
        original.append(history[c][:,yy:yy+side,xx:xx+side])
        candidate.append(base[c][yy:yy+side,xx:xx+side])
        result['native_motion'].append(tile(history[c],base[c],depth,side,16*factor,4,xx,yy,native_match=True))
        result['registration'].append(_registration(history[c],depth,side,16*factor,xx,yy,result['native_motion'][-1]))
    candidate_joint=_co_located(candidate)
    result['unaligned']=measure(_co_located(original),candidate_joint,depth,ids,pts)
    proposed=[(m['dy'],m['dx']) for m in result['registration']]
    if any(m['fit_samples']<16 for m in result['native_motion']):
        result['reason']='insufficient_search_support';return result
    if proposed[1]!=proposed[2] or proposed[0]!=tuple(2*v for v in proposed[1]):
        result['reason']='inconsistent_native_component_motion';return result
    dy,dx=proposed[1];result['chroma_offset']=[dy,dx]
    if dy or dx:
        if not all(m['motion_supported'] and m['anchor_supported'] for m in result['registration']):
            result['reason']='motion_not_independently_supported';return result
    aligned=[];coordinates=[]
    for c in range(3):
        factor=1 if c else 2;side=32*factor;component=[];locations=[]
        for frame in range(8):
            xx=(x+(7-frame)*dx)*factor;yy=(y+(7-frame)*dy)*factor
            if xx<0 or yy<0 or xx+side>history[c].shape[2] or yy+side>history[c].shape[1]:
                result['reason']='insufficient_full_history_overlap';return result
            component.append(history[c][frame,yy:yy+side,xx:xx+side]);locations.append([xx,yy,side,side])
        aligned.append(np.array(component));coordinates.append(locations)
    for c in range(3):
        result['persistent'].append(reference(moments(aligned[c],candidate[c],depth,ids,pts),LIMITS))
    if not (dy or dx) and not all(p['anchors_supported'] for p in result['persistent']):
        result['reason']='stationary_source_anchors_missing';return result
    result['registration_supported']=True
    result['history_coordinates']=coordinates
    result['aligned_native_sha256']=[[
        hashlib.sha256(np.ascontiguousarray(frame,dtype='<u2').tobytes()).hexdigest()
        for frame in component] for component in aligned]
    result['candidate_native_sha256']=[hashlib.sha256(np.ascontiguousarray(p,dtype='<u2').tobytes()).hexdigest() for p in candidate]
    result['evidence']=measure(_co_located(aligned),candidate_joint,depth,ids,pts)
    result['conflicts']=consistency(result['evidence'])
    result['persistent_detail_conflicts']=[bool(abs(p['mean_error'])>.125
        or (p['anchors_supported'] and not p['within_limits'])) for p in result['persistent']]
    return result


def diagnose(history, base, depth, ids, pts, epochs, x, y):
    return diagnose_prepared(prepare(history,base,depth,ids,pts,epochs),x,y)
