#!/usr/bin/env python3
import os
import sys
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import motion_cycle


def _summary(frame):
    return {
        "version": 1,
        "frame": frame,
        "sad_limit": 100,
        "layout": {
            "blocks": 9,
            "blocks_x": 3,
            "blocks_y": 3,
            "directions": 2,
            "block_size": 32,
            "overlap": 16,
            "step": 16,
            "pel": 1,
        },
    }


def _blocks(next_vector, previous_vector):
    blocks = {}
    for by in range(3):
        for bx in range(3):
            block = by * 3 + bx
            refs = []
            for slot, (side, vector) in enumerate((
                    ("next", next_vector), ("prev", previous_vector))):
                refs.append({
                    "slot": slot,
                    "delta": 1,
                    "side": side,
                    "dx": vector[0],
                    "dy": vector[1],
                    "sad": 10,
                    "disabled": 0,
                    "valid_motion": 1,
                    "under_sad": 1,
                    "selected": 1,
                    "mix": 0.25,
                })
            blocks[block] = {
                "version": 1,
                "frame": 10,
                "block": block,
                "block_x": bx,
                "block_y": by,
                "source_mix": 0.5,
                "reference_mix": 0.5,
                "refs": refs,
            }
    return blocks


class MotionCycleTest(unittest.TestCase):
    def test_inverse_fields_close_the_cycle(self):
        traces = {
            9: (_summary(9), _blocks((2, 0), (-4, 0))),
            10: (_summary(10), _blocks((4, 0), (-2, 0))),
            11: (_summary(11), _blocks((2, 0), (-4, 0))),
        }
        records = motion_cycle.cycle_records(traces, 10)
        self.assertEqual(len(records), 18)
        self.assertTrue(all(record["cycle_error_px"] == 0.0
                            for record in records))
        self.assertTrue(all(record["paired_admitted"] for record in records))

    def test_inconsistent_reverse_field_is_measured_at_endpoint(self):
        traces = {
            9: (_summary(9), _blocks((2, 0), (-4, 0))),
            10: (_summary(10), _blocks((4, 0), (-2, 0))),
            11: (_summary(11), _blocks((2, 0), (-1, 0))),
        }
        records = motion_cycle.cycle_records(traces, 10)
        following = [record for record in records
                     if record["side"] == "next"]
        previous = [record for record in records
                    if record["side"] == "prev"]
        self.assertTrue(all(record["cycle_error_px"] == 3.0
                            for record in following))
        self.assertTrue(all(record["cycle_error_px"] == 0.0
                            for record in previous))

    def test_auc_is_tie_correct(self):
        self.assertEqual(motion_cycle._auc([False, True], [0.0, 1.0]), 1.0)
        self.assertEqual(motion_cycle._auc([False, True], [1.0, 0.0]), 0.0)
        self.assertEqual(motion_cycle._auc([False, True], [1.0, 1.0]), 0.5)


if __name__ == "__main__":
    unittest.main()
