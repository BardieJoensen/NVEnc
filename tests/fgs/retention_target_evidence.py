"""Independent necessary PSD checks on measured source/reconstruction pairs.

This uses eigenvalues rather than the encoder's pivoted arithmetic. It does
not fit, clip coefficients, regularize a target or grant population admission.
The two spatial folds remain separate and all native luma variables are kept.
"""
import numpy as np


def target(row, variables):
    blocks, observations = row['blocks'], row['observations']
    if (type(blocks) is not int or type(observations) is not int
            or not 16 <= blocks <= 10000000
            or not blocks <= observations <= 1000000000):
        return dict(measured=False, valid=False, reason='insufficient observations')
    matrices = []
    for name in ('source', 'base', 'sourceBase'):
        a = np.asarray(row[name], dtype=np.float64)
        if a.size != variables*variables or not np.isfinite(a).all():
            return dict(measured=False, valid=False, reason='invalid pair matrix')
        matrices.append(a.reshape(variables, variables)/observations)
    source, base, cross = matrices
    full = np.block([[source, cross], [cross.T, base]])
    missing = source-base
    results = []
    for a in (full, missing):
        tolerance = max(1e-12, float(np.diag(a).max())*1e-9)
        symmetric = float(np.abs(a-a.T).max()) <= tolerance
        nonnegative_diagonal = bool(np.all(np.diag(a) >= 0))
        minimum = float(np.linalg.eigvalsh(a).min()) if symmetric else None
        results.append(dict(symmetric=symmetric, nonnegative_diagonal=nonnegative_diagonal,
                            minimum_eigenvalue=minimum, numerical_tolerance=tolerance,
                            valid=bool(symmetric and nonnegative_diagonal
                                       and minimum >= -tolerance)))
    return dict(measured=True, valid=all(r['valid'] for r in results),
                blocks=blocks, observations=observations,
                joint_pair=results[0], missing_target=results[1])


def measure(pairs):
    if len(pairs['colour']) != 2:
        raise ValueError('both colour components required')
    components = []
    for n, rows in zip((25, 26, 26), [pairs['luma'], *pairs['colour']]):
        if len(rows) != 2:
            raise ValueError('two independent folds required')
        folds = [target(row, n) for row in rows]
        components.append(dict(measured=all(f['measured'] for f in folds),
                               valid=all(f['valid'] for f in folds), folds=folds))
    if len(components) != 3:
        raise ValueError('all three native components required')
    return dict(source_admission=False, components=components)
