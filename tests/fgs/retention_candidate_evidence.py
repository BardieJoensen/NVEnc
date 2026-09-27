"""Join measured facts only when every candidate stage has the same identity.

This is a finite development adapter, not a source classifier. Even a complete
set of facts in this module leaves detail and quiet-region checks unknown.
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


def combine(pixel_bytes, model_bytes, expected_subject):
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
    result = []
    for p, m in zip(pixel['checks'], model['checks']):
        pm, pp = checks(p, PIXEL_BITS); mm, mp = checks(m, MODEL_BITS)
        measured, passed = pm | mm, pp | mp
        result.append(dict(measured=measured, passed=passed,
                           failed=measured & ~passed, unmeasured=255 & ~measured))
    return dict(subject_sha256=expected, model_id=int(expected[:15], 16) or 1,
                checks=result, source_admission=False,
                detail_and_quiet_unmeasured=True,
                association='Exact declared source/pristine/rounded/reconstruction/decoded '
                            'plane hashes, frame clock, fractions, video and model identity.')
