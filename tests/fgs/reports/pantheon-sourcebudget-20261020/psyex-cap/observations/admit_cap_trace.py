#!/usr/bin/env python3
"""Admit all-picture delivered q and committed coverage before quality claims."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_cap_trace import fingerprint, read_records
from provenance import validate as validate_provenance

SELECTED = {
    sb for sb in range(510)
    if ((sb % 30 * 64 < 1400 and sb % 30 * 64 + 64 > 1200 and
         sb // 30 * 64 < 750 and sb // 30 * 64 + 64 > 650) or
        (sb % 30 * 64 < 1200 and sb % 30 * 64 + 64 > 950 and
         sb // 30 * 64 < 230 and sb // 30 * 64 + 64 > 50))
}
assert len(SELECTED) == 28
# Pinned source definitions.h:901-907; full source manifest includes this table.
TX_DIMS = list(zip(
    (4, 8, 16, 32, 64, 4, 8, 8, 16, 16, 32, 32, 64, 4, 16, 8, 32, 16, 64),
    (4, 8, 16, 32, 64, 8, 4, 16, 8, 32, 16, 64, 32, 16, 4, 32, 8, 64, 16)))


def lambda_check(application, rows, entries):
    active = application["old_lambda_active"]
    assert active in (0, 1)
    assert all(entry["lambda_refreshed"] == active for entry in entries.values())
    if not active:
        assert not rows
        return dict(active=False, factors=0)
    assert rows
    synth = rows[0]["synth_blk_size"]
    assert synth in (16, 32)
    cols, nrows = 1920 // synth, (1080 + synth - 1) // synth
    expected = {i for i in range(cols * nrows)
                if ((i // cols * synth) // 64) * 30 + (i % cols * synth) // 64 in SELECTED}
    found = {row["factor_index"]: row for row in rows}
    assert len(found) == len(rows) == 28 * (64 // synth)**2
    assert set(found) == expected
    ratios = defaultdict(list)
    for i, row in found.items():
        assert (row["synth_blk_size"], row["factor_cols"], row["factor_rows"]) == (synth, cols, nrows)
        for key in ("lambda_before", "lambda_after", "lambda_original"):
            assert math.isfinite(row[key]) and row[key] > 0
        sb = ((i // cols * synth) // 64) * 30 + (i % cols * synth) // 64
        ratios[sb].append(row["lambda_after"] / row["lambda_original"])
    for sb, values in ratios.items():
        # %.17g preserves binary64 round trips; 1e-12 relative conservatively
        # covers multiplication/division rounding, without an absolute allowance.
        assert max(values) - min(values) <= 1e-12 * max(values), ("lambda ratio", sb, values)
    return dict(active=True, factors=len(rows), synth=synth, cols=cols, rows=nrows,
                after_over_original_by_sb={str(sb): [min(v), max(v)] for sb, v in ratios.items()},
                before_min=min(x["lambda_before"] for x in rows),
                before_max=max(x["lambda_before"] for x in rows),
                after_min=min(x["lambda_after"] for x in rows),
                after_max=max(x["lambda_after"] for x in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provenance_index", type=Path)
    ap.add_argument("provenance_index_sha")
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    started = time.monotonic()
    scripts_before = [fingerprint(Path(__file__).with_name(x)) for x in
                      ("admit_cap_trace.py", "read_cap_trace.py", "provenance.py")]
    runs, index_identity = validate_provenance(args.provenance_index, args.provenance_index_sha)
    receipt = runs["trace"]
    receipt_path = Path(__file__).resolve().parent / "runs" / receipt["tag"] / "command.json"
    before = fingerprint(receipt_path)
    trace = receipt["outputs"]["r18-trace.bin"]
    assert fingerprint(trace["path"]) == trace
    assert not args.out.exists()
    groups = defaultdict(lambda: defaultdict(list))
    sequences = defaultdict(lambda: defaultdict(list))
    kinds = Counter()
    for record in read_records(trace["path"]):
        kinds[record["kind"]] += 1
        groups[record["picture"], record["generation"]][record["kind"]].append(record["data"])
        sequences[record["picture"], record["generation"]][record["kind"]].append(record["sequence"])
    assert {picture for picture, _ in groups} == set(range(336))
    summaries = []
    accepted_totals = Counter()
    all_attempt_totals = Counter()
    accepted_pre_q, accepted_post_q = Counter(), Counter()
    decode_orders = {}
    order_hints = {}
    for picture in range(336):
        generations = sorted(gen for pic, gen in groups if pic == picture)
        assert generations == list(range(len(generations))), picture
        for generation in generations:
            data = groups[picture, generation]
            assert len(data[1]) == 1, ("cap application", picture, generation)
            application = data[1][0]
            assert application["count"] == 28 and application["delta_q_res"] == 1
            assert application["old_delta_q_present"] in (0, 1)
            assert application["old_delta_q_res"] in (0, 1, 2, 4, 8)
            if application["old_delta_q_present"]:
                assert application["old_delta_q_res"] in (1, 2, 4, 8)
            assert application["recode"] == int(generation > 0)
            assert application["attempt"] == generation
            entries = {entry["sb"]: entry for entry in application["entries"]}
            assert len(application["entries"]) == len(entries) == 28 and set(entries) == SELECTED
            for sb, entry in entries.items():
                assert (entry["x"], entry["y"]) == (sb % 30 * 64, sb // 30 * 64)
                assert entry["selected"] == 1
                assert 0 < entry["post"] == min(entry["pre"], 4)
                assert entry["pre"] <= 255
            decode_orders.setdefault(picture, application["decode_order"])
            assert application["decode_order"] == decode_orders[picture]
            order_hints.setdefault(picture, application["order_hint"])
            assert application["order_hint"] == order_hints[picture]
            seq = sequences[picture, generation]
            assert all(value > seq[1][0] for kind in (2, 3, 4, 5, 7) for value in seq[kind])
            assert all(value < seq[1][0] for value in seq[8])
            lambda_result = lambda_check(application, data[8], entries)
            is_final = generation == generations[-1]
            assert len(data[6]) == int(is_final), ("accepted generation", picture, generation)
            if is_final:
                accepted = data[6][0]
                assert accepted["accepted"] == 1 and accepted["expected_selected_sb"] == 28
                assert accepted["sb_total_count"] == 510
                assert accepted["decode_order"] == application["decode_order"]
                assert accepted["order_hint"] == application["order_hint"]
                assert seq[6][0] > max(value for kind, values in seq.items() if kind != 6 for value in values)
            by_sb = {}
            for kind in (3, 4, 7):
                rows = data[kind]
                assert len(rows) == 28
                by_sb[kind] = {row["sb"]: row for row in rows}
                assert set(by_sb[kind]) == SELECTED
                for sb, row in by_sb[kind].items():
                    assert (row["x"], row["y"]) == (sb % 30 * 64, sb // 30 * 64)
            blocks = defaultdict(list)
            for row in data[2]:
                assert row["sb"] in SELECTED
                blocks[row["sb"]].append(row)
            units = {}
            for row in data[5]:
                key = row["sb"], row["mds_idx"], row["tu"]
                assert key not in units and row["sb"] in SELECTED
                units[key] = row
            used = set()
            counts = Counter()
            for sb in sorted(SELECTED):
                post = entries[sb]["post"]
                assert by_sb[3][sb]["qindex"] == post
                assert by_sb[7][sb]["md_qindex"] == by_sb[7][sb]["sb_qindex"] == post
                assert by_sb[4][sb]["picture_bypass"] == by_sb[4][sb]["md_bypass"] == 0
                assert by_sb[4][sb]["fixed_partition"] in (0, 1)
                counts["fixed_partition_" + str(by_sb[4][sb]["fixed_partition"]) + "_sbs"] += 1
                committed = sorted(blocks[sb], key=lambda row: row["ordinal"])
                assert len(committed) == by_sb[3][sb]["final_blk_cnt"]
                assert [row["ordinal"] for row in committed] == list(range(len(committed)))
                cover = np.zeros((64, 64), dtype=np.uint8)
                tu_cover = np.zeros_like(cover)
                offset = 0
                for block in committed:
                    assert block["sb_qindex"] == block["block_qindex"] == post
                    assert block["coeff_offset"] == offset
                    x = block["block_x"] - (sb % 30) * 64
                    y = block["block_y"] - (sb // 30) * 64
                    w, h = block["block_w"], block["block_h"]
                    assert w > 0 and h > 0 and 0 <= x < x+w <= 64 and 0 <= y < y+h <= 64
                    assert not cover[y:y+h, x:x+w].any()
                    cover[y:y+h, x:x+w] = 1
                    tw, th, ntu = block["tx_w"], block["tx_h"], block["txb_count"]
                    assert tw > 0 and th > 0 and tw * th * ntu == w * h
                    assert len(block["eob_y"]) == len(block["tx_type"]) == ntu
                    assert block["skip_mode"] in (0, 1) and block["block_has_coeff"] in (0, 1)
                    if block["skip_mode"]:
                        assert block["block_has_coeff"] == 0 and not any(block["eob_y"])
                        counts["syntax_skip_mode_blocks"] += 1
                    if not any(block["eob_y"]) and block["block_has_coeff"]:
                        counts["luma_zero_chroma_possible_blocks"] += 1
                    if any(block["eob_y"]):
                        assert block["block_has_coeff"] == 1
                    for tu in range(ntu):
                        key = sb, block["mds_idx"], tu
                        assert key in units and key not in used
                        used.add(key)
                        unit = units[key]
                        assert unit["qindex"] == post and unit["offset"] == offset
                        assert unit["eob"] == (0 if block["skip_mode"] else block["eob_y"][tu])
                        assert unit["type"] == block["tx_type"][tu]
                        assert 0 <= unit["tx"] < len(TX_DIMS) and TX_DIMS[unit["tx"]] == (tw, th)
                        assert unit["eob"] <= min(tw, 32) * min(th, 32)
                        assert unit["invoked"] in (0, 1) and unit["skipped"] in (0, 1)
                        ux, uy = unit["x"] - sb % 30 * 64, unit["y"] - sb // 30 * 64
                        assert x <= ux < ux+tw <= x+w and y <= uy < uy+th <= y+h
                        assert not tu_cover[uy:uy+th, ux:ux+tw].any()
                        tu_cover[uy:uy+th, ux:ux+tw] = 1
                        if unit["invoked"]:
                            assert not block["skip_mode"]
                            assert unit["qinfo_count"] == 1 and unit["skipped"] == 0
                            assert unit["actual_qindex"] == unit["requested_qindex"] == post
                            assert unit["seg_delta"] == 0
                            counts["invoked_tus"] += 1
                            counts["invoked_pixels"] += tw * th
                            eob_class = "positive" if unit["eob"] else "zero"
                            counts["invoked_eob_" + eob_class + "_tus"] += 1
                            counts["invoked_eob_" + eob_class + "_pixels"] += tw * th
                        else:
                            assert unit["qinfo_count"] == 0 and unit["skipped"] == 1 and unit["eob"] == 0
                            counts["uninvoked_tus"] += 1
                            counts["uninvoked_pixels"] += tw * th
                            skip_class = "syntax_skip_mode" if block["skip_mode"] else "non_skip_mode_uninvoked"
                            counts[skip_class + "_tus"] += 1
                            counts[skip_class + "_pixels"] += tw * th
                        counts["total_tus"] += 1
                        counts["selected_pixels"] += tw * th
                        counts["tx_" + str(tw) + "x" + str(th) + "_pixels"] += tw * th
                        offset += tw * th
                    counts["committed_blocks"] += 1
                assert cover.all() and tu_cover.all() and offset == 4096
                counts["committed_sbs"] += 1
            assert used == set(units), "uncommitted or missing final TU"
            assert counts["committed_sbs"] == 28
            assert counts["selected_pixels"] == counts["invoked_pixels"] + counts["uninvoked_pixels"] == 28 * 4096
            assert counts["total_tus"] == counts["invoked_tus"] + counts["uninvoked_tus"]
            assert counts["invoked_pixels"] == counts["invoked_eob_positive_pixels"] + counts["invoked_eob_zero_pixels"]
            assert counts["uninvoked_pixels"] == counts["syntax_skip_mode_pixels"] + counts["non_skip_mode_uninvoked_pixels"]
            all_attempt_totals.update(counts)
            if is_final:
                accepted_totals.update(counts)
                accepted_pre_q.update(entry["pre"] for entry in entries.values())
                accepted_post_q.update(entry["post"] for entry in entries.values())
            summaries.append(dict(picture=picture, generation=generation,
                                  accepted=is_final, counts=dict(counts),
                                  old_base_qindex=application["old_base_qindex"],
                                  old_delta_q_present=application["old_delta_q_present"],
                                  old_delta_q_res=application["old_delta_q_res"],
                                  new_delta_q_res=application["delta_q_res"],
                                  lambda_delivery=lambda_result))
    assert len(set(decode_orders.values())) == 336
    assert accepted_totals["selected_pixels"] == 336 * 28 * 4096
    assert sum(accepted_pre_q.values()) == sum(accepted_post_q.values()) == 336 * 28
    assert fingerprint(receipt_path) == before and fingerprint(trace["path"]) == trace
    assert fingerprint(args.provenance_index) == index_identity
    assert [fingerprint(x["path"]) for x in scripts_before] == scripts_before
    result = dict(status="all_picture_quantizer_and_committed_coverage_admitted",
                  script=fingerprint(__file__), reader=fingerprint(Path(__file__).with_name("read_cap_trace.py")),
                  receipt=before, trace=trace, selected_sbs=sorted(SELECTED),
                  provenance_index=index_identity, scripts=scripts_before,
                  records=dict(kinds), accepted_totals=dict(accepted_totals),
                  all_attempt_totals=dict(all_attempt_totals),
                  accepted_pre_q_sb_counts=dict(accepted_pre_q),
                  accepted_post_q_sb_counts=dict(accepted_post_q),
                  attempts=summaries, seconds=time.monotonic() - started,
                  limitations=["Separate native coefficient/decoder admission and all-frame decoder identity still required.",
                               "Stored q on uninvoked skip units is not an executed quantizer or independent syntax q.",
                               "Lambda population/scaling consistency verified; absolute RD-mult formula is bound to the reviewed executed native function, not independently recomputed.",
                               "Non-skip-mode uninvoked classification uses observed skip flags and the source's MD-skip route; it is not independent bitstream syntax.",
                               "Exact original lambda values remain in the hash-bound trace."])
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(fingerprint(args.out)))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python prohibited")
    main()
