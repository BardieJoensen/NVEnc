"""Independent-pair check for a proposed small translation, offline only.

Training pairs use frames 0/1 and 2/3. Validation uses 4/5 and 6/7, with no
shared frames. Only the displacement chosen by training is evaluated on the
held-out pairs: there is no search on validation data. Temporal correlation can
still couple the folds; this never confers population or stationarity approval.
"""
import numpy as np

from temporal_stationarity_reference import diagnose as original_diagnose


def diagnose(source, base, depth, frame_ids, timestamps):
    result = original_diagnose(source, base, depth, frame_ids, timestamps)
    source = np.asarray(source, dtype=np.float64) / (1 << (depth-8))
    smooth = sum(source[:, :, y:y+30, x:x+30] * wy * wx
                 for y, wy in enumerate((1, 2, 1))
                 for x, wx in enumerate((1, 2, 1))) / 16
    coordinates = np.arange(4, 26, 2)
    shifts = [(0, 0)] + [(dy, dx) for dy in range(-4, 5)
                        for dx in range(-4, 5) if dy or dx]
    def cost(before, after, c, dy, dx):
        target = smooth[after, c, coordinates[:, None], coordinates]
        prediction = smooth[before, c, (coordinates+dy)[:, None], coordinates+dx]
        return float(np.mean((target-prediction)**2))
    chosen = []
    train_cost = []
    validation_zero = []
    validation_shifted = []
    for c in range(3):
        costs = [sum(cost(a, b, c, dy, dx) for a, b in [(0, 1), (2, 3)])/2
                 for dy, dx in shifts]
        index = int(np.argmin(costs))
        dy, dx = shifts[index]; chosen.append((dy, dx)); train_cost.append(costs[index])
        validation_zero.append([cost(a, b, c, 0, 0) for a, b in [(4, 5), (6, 7)]])
        validation_shifted.append([cost(a, b, c, dy, dx) for a, b in [(4, 5), (6, 7)]])
    zero = np.array(validation_zero)
    shifted = np.array(validation_shifted)
    improvement = np.zeros_like(zero)
    np.divide(zero-shifted, zero, out=improvement, where=zero > 0)
    # Keep negative validation improvements: a proposed translation can be worse.
    for c in range(3):
        result['conflicts'][c] = [v for v in result['conflicts'][c]
                                  if v != 'small_translation_evidence']
        if (chosen[c] != (0, 0) and np.all(zero[c] > .04)
                and np.all(improvement[c] > .2)):
            result['conflicts'][c].append('held_out_translation_evidence')
    result['held_out_motion'] = dict(
        train_pairs=[[0, 1], [2, 3]], check_pairs=[[4, 5], [6, 7]],
        proposed_offset=np.array(chosen), training_mse=np.array(train_cost),
        validation_zero_mse=zero, validation_proposed_mse=shifted,
        validation_improvement=improvement, validation_relative_defined=zero > 0,
        validation_searches=0)
    return result
