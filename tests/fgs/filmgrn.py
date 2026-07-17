"""Small, dependency-free reader and comparator for AOM filmgrn1 tables."""

import math


PARAM_NAMES = (
    "ar_coeff_lag",
    "ar_coeff_shift",
    "grain_scale_shift",
    "scaling_shift",
    "chroma_scaling_from_luma",
    "overlap_flag",
    "cb_mult",
    "cb_luma_mult",
    "cb_offset",
    "cr_mult",
    "cr_luma_mult",
    "cr_offset",
)
PLANE_MARKERS = {"sY": "y", "sCb": "cb", "sCr": "cr"}
COEFF_MARKERS = {"cY": "y", "cCb": "cb", "cCr": "cr"}


class FilmGrainTableError(ValueError):
    pass


def _integers(tokens, line_number):
    try:
        return [int(token, 10) for token in tokens]
    except ValueError as error:
        raise FilmGrainTableError(f"line {line_number}: expected integer") from error


def parse(text):
    """Parse filmgrn1 text into JSON-serializable dictionaries."""
    lines = [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1)
             if line.strip()]
    if not lines or lines[0][1] != "filmgrn1":
        raise FilmGrainTableError("missing filmgrn1 header")
    entries = []
    current = None
    for line_number, line in lines[1:]:
        tokens = line.split()
        marker = tokens[0]
        values = _integers(tokens[1:], line_number)
        if marker == "E":
            if len(values) != 5:
                raise FilmGrainTableError(f"line {line_number}: E requires 5 values")
            current = {
                "start": values[0],
                "end": values[1],
                "apply_grain": bool(values[2]),
                "random_seed": values[3],
                "update_parameters": bool(values[4]),
                "params": {},
                "scaling_points": {"y": [], "cb": [], "cr": []},
                "ar_coeffs": {"y": [], "cb": [], "cr": []},
            }
            entries.append(current)
            continue
        if current is None:
            raise FilmGrainTableError(f"line {line_number}: {marker} before first entry")
        if marker == "p":
            if len(values) != len(PARAM_NAMES):
                raise FilmGrainTableError(
                    f"line {line_number}: p requires {len(PARAM_NAMES)} values")
            current["params"] = dict(zip(PARAM_NAMES, values))
        elif marker in PLANE_MARKERS:
            if not values:
                raise FilmGrainTableError(f"line {line_number}: {marker} requires a count")
            count = values[0]
            if count < 0 or len(values) != 1 + 2 * count:
                raise FilmGrainTableError(
                    f"line {line_number}: {marker} count does not match its points")
            current["scaling_points"][PLANE_MARKERS[marker]] = [
                values[index:index + 2] for index in range(1, len(values), 2)
            ]
        elif marker in COEFF_MARKERS:
            current["ar_coeffs"][COEFF_MARKERS[marker]] = values
        else:
            raise FilmGrainTableError(f"line {line_number}: unknown marker {marker}")
    for entry in entries:
        if entry["start"] < 0 or entry["end"] <= entry["start"]:
            raise FilmGrainTableError("entry has an invalid time interval")
        if entry["apply_grain"] and entry["update_parameters"]:
            if not entry["params"]:
                raise FilmGrainTableError("grain entry is missing p parameters")
            lag = entry["params"]["ar_coeff_lag"]
            luma_count = 2 * lag * (lag + 1)
            expected = {"y": luma_count, "cb": luma_count + 1, "cr": luma_count + 1}
            for plane, count in expected.items():
                if len(entry["ar_coeffs"][plane]) != count:
                    raise FilmGrainTableError(
                        f"{plane} coefficient count {len(entry['ar_coeffs'][plane])} != {count}")
    return entries


def load(path):
    with open(path) as source:
        return parse(source.read())


def representative(entries):
    """Select the longest entry that carries an updated grain model."""
    candidates = [entry for entry in entries
                  if entry["apply_grain"] and entry["update_parameters"]]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: entry["end"] - entry["start"])


def _curve(points):
    if not points:
        return [0.0] * 256
    points = sorted(points)
    result = []
    right = 0
    for value in range(256):
        while right < len(points) and points[right][0] < value:
            right += 1
        if right == 0:
            result.append(float(points[0][1]))
        elif right == len(points):
            result.append(float(points[-1][1]))
        else:
            x0, y0 = points[right - 1]
            x1, y1 = points[right]
            fraction = (value - x0) / max(x1 - x0, 1)
            result.append(y0 + fraction * (y1 - y0))
    return result


def _rms(values):
    return math.sqrt(sum(value * value for value in values) / max(len(values), 1))


def _curve_comparison(candidate, reference, plane):
    candidate_curve = _curve(candidate["scaling_points"][plane])
    reference_curve = _curve(reference["scaling_points"][plane])
    candidate_shift = (candidate["params"]["scaling_shift"]
                       + candidate["params"]["grain_scale_shift"])
    reference_shift = (reference["params"]["scaling_shift"]
                       + reference["params"]["grain_scale_shift"])
    candidate_curve = [value / (1 << candidate_shift) for value in candidate_curve]
    reference_curve = [value / (1 << reference_shift) for value in reference_curve]
    difference = [left - right for left, right in zip(candidate_curve, reference_curve)]
    reference_rms = _rms(reference_curve)
    return {
        "candidate_rms": _rms(candidate_curve),
        "reference_rms": reference_rms,
        "rms_ratio": _rms(candidate_curve) / reference_rms if reference_rms else None,
        "relative_rmse": _rms(difference) / reference_rms if reference_rms else None,
    }


def _coeff_comparison(candidate, reference, plane):
    candidate_values = candidate["ar_coeffs"][plane]
    reference_values = reference["ar_coeffs"][plane]
    count = min(len(candidate_values), len(reference_values))
    if count == 0:
        return {"count": 0, "rmse": None, "cosine": None}
    candidate_scale = float(1 << candidate["params"]["ar_coeff_shift"])
    reference_scale = float(1 << reference["params"]["ar_coeff_shift"])
    left = [value / candidate_scale for value in candidate_values[:count]]
    right = [value / reference_scale for value in reference_values[:count]]
    difference = [a - b for a, b in zip(left, right)]
    denominator = math.sqrt(sum(value * value for value in left)
                            * sum(value * value for value in right))
    cosine = sum(a * b for a, b in zip(left, right)) / denominator if denominator else None
    return {"count": count, "rmse": _rms(difference), "cosine": cosine}


def compare(candidate, reference):
    """Compare representative parameter entries in normalized synthesis units."""
    if candidate is None or reference is None:
        return {
            "candidate_has_grain": candidate is not None,
            "reference_has_grain": reference is not None,
            "scaling": {},
            "coefficients": {},
            "parameter_delta": {},
        }
    parameter_delta = {
        name: candidate["params"][name] - reference["params"][name]
        for name in PARAM_NAMES
    }
    return {
        "candidate_has_grain": True,
        "reference_has_grain": True,
        "scaling": {
            plane: _curve_comparison(candidate, reference, plane)
            for plane in ("y", "cb", "cr")
        },
        "coefficients": {
            plane: _coeff_comparison(candidate, reference, plane)
            for plane in ("y", "cb", "cr")
        },
        "parameter_delta": parameter_delta,
    }
