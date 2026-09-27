"""Join measured facts only when every candidate stage has the same identity.

This is a finite development adapter, not a source classifier. These facts
cannot grant detail clearance. Quiet-region facts and necessary detail vetoes
may be supplied separately for the exact same native candidate.
Population coverage and final joint compatibility are separate inputs.
"""
import hashlib
import json

PIXEL_BITS, MODEL_BITS = 145, 14


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def subject(record):
    return {k: record[k] for k in ('depth', 'identity', 'hashes', 'fractions')}


def checks(value, allowed):
    measured, passed = value['measured'], value['passed']
    if (type(measured) is not int or type(passed) is not int or measured < 0 or passed < 0
            or measured & ~allowed or passed & ~measured):
        raise ValueError('measurement grants checks outside its scope')
    return measured, passed


def combine(pixel_bytes, model_bytes, expected_subject, quiet_bytes=None, detail_veto_bytes=None):
    """The caller supplies the independent current candidate identity.

    Exact file and canonical subject digests prevent accidentally combining a
    neighboring picture, earlier fraction/model or different reconstruction.
    They establish association, not the truth of externally supplied evidence.
    """
    pixel, model = json.loads(pixel_bytes), json.loads(model_bytes)
    expected = digest(expected_subject)
    if (digest(subject(pixel)) != expected or digest(model['subject']) != expected
            or model['subject_sha256'] != expected
            or model['pixel_evidence_sha256'] != hashlib.sha256(pixel_bytes).hexdigest()):
        raise ValueError('candidate source/base/model/output association differs')
    if len(pixel['checks']) != 3 or len(model['checks']) != 3:
        raise ValueError('all native components required')
    def associated(raw, label):
        if raw is None: return None
        record = json.loads(raw)
        if (digest(record['subject']) != expected or record['subject_sha256'] != expected
                or record['pixel_evidence_sha256'] != hashlib.sha256(pixel_bytes).hexdigest()
                or record['layout'] != {k: pixel['source_moments'][k]
                                        for k in ('width', 'height', 'depth')}
                or len(record['checks']) != 3):
            raise ValueError(f'native {label} evidence association/layout differs')
        return record
    quiet = associated(quiet_bytes, 'quiet')
    detail = associated(detail_veto_bytes, 'detail veto')
    result = []
    for c, (p, m) in enumerate(zip(pixel['checks'], model['checks'])):
        pm, pp = checks(p, PIXEL_BITS); mm, mp = checks(m, MODEL_BITS)
        measured, passed = pm | mm, pp | mp
        if quiet is not None:
            qm, qp = checks(quiet['checks'][c], 64)
            measured |= qm; passed |= qp
        if detail is not None:
            dm, dp = checks(detail['checks'][c], 32)
            if dp:
                raise ValueError('necessary detail veto cannot grant clearance')
            measured |= dm
            passed &= ~dm
        result.append(dict(measured=measured, passed=passed,
                           failed=measured & ~passed, unmeasured=255 & ~measured))
    return dict(subject_sha256=expected, model_id=int(expected[:15], 16) or 1,
                checks=result, source_admission=False,
                detail_and_quiet_unmeasured=all(r['unmeasured'] & 96 == 96 for r in result),
                detail_unmeasured=all(r['unmeasured'] & 32 for r in result),
                quiet_evidence_supplied=quiet is not None, detail_veto_supplied=detail is not None,
                association='Exact declared source/pristine/rounded/reconstruction/decoded '
                            'plane hashes, frame clock, fractions, video and model identity.')
