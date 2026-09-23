"""Native source projection measurement for persistent-detail vetoes.

History is source only. Luma must be measured at native resolution: averaging
2x2 pixels would hide alternating-line structure. These deterministic projections
need no claim that the removed material is grain. A pass is not population or
model admission, and missing anchors are unknown rather than a preservation pass.
"""
import numpy as np


def moments(source, base, depth, frame_ids, timestamps):
    source = np.asarray(source); base = np.asarray(base)
    if (depth not in (8, 10) or source.ndim != 3 or source.shape[0] != 8
            or source.shape[1:] != base.shape or base.ndim != 2
            or min(base.shape) < 1 or base.size > 8192*8192):
        raise ValueError('requires eight equal native source planes and one base')
    ids = np.asarray(frame_ids); pts = np.asarray(timestamps)
    if (ids.shape != (8,) or ids.dtype.kind not in 'iu' or np.any(ids < 0)
            or np.any(ids[1:] <= ids[:-1]) or np.any(ids[1:]-ids[:-1] != 1)
            or pts.shape != (8,) or pts.dtype.kind not in 'iuf'
            or not np.isfinite(pts).all() or np.any(pts[1:] <= pts[:-1])):
        raise ValueError('requires adjacent IDs and increasing finite clocks')
    for data in (source, base):
        if (data.dtype.kind not in 'iu' or np.any(data < 0)
                or np.any(data > (1 << depth)-1)):
            raise ValueError('native integer source/base required')
    scale = 1 << (depth-8)
    fields = np.array([source[-1], base, source[:3].mean(axis=0),
                       source[3:7].mean(axis=0)], dtype=np.float64).reshape(4, -1)/scale
    mean = fields.mean(axis=1)
    centered = fields-mean[:, None]
    return dict(mean=mean, covariance=centered@centered.T/base.size,
                samples=base.size, history_split=[3, 4], frame_id=int(ids[-1]))


def reference(m, limits):
    """Independent direct formula; input covariance comes from real fields."""
    c = m['covariance']; mean = m['mean']
    result = dict(anchors_supported=False, within_limits=False,
                  mean_error=float(mean[0]-mean[1]), contrast_loss=[0., 0.],
                  removed_projection_rms=[0., 0.], source_correlation=[0., 0.],
                  history_correlation=0.)
    if min(c[0, 0], c[2, 2], c[3, 3]) <= 1e-12: return result
    result['history_correlation'] = float(c[2, 3]/np.sqrt(c[2, 2]*c[3, 3]))
    anchors = result['history_correlation'] >= limits['minimum_history_history_correlation']
    within = abs(result['mean_error']) <= limits['absolute_mean_error_8bit']
    for i, h in enumerate((2, 3)):
        corr = float(c[0, h]/np.sqrt(c[0, 0]*c[h, h]));result['source_correlation'][i] = corr
        if corr < limits['minimum_source_history_correlation']:
            anchors = False;continue
        loss = float((c[0, h]-c[1, h])/c[0, h])
        projection = float(abs(c[0, h]-c[1, h])/np.sqrt(c[h, h]))
        result['contrast_loss'][i] = loss;result['removed_projection_rms'][i] = projection
        within &= (abs(loss) <= limits['relative_projected_contrast_change']
                   and projection <= limits['absolute_projected_rms_8bit'])
    result['anchors_supported'] = bool(anchors)
    result['within_limits'] = bool(anchors and within)
    return result
