#!/usr/bin/env python3
"""Strict R18 binary-envelope reader; policy admission is a separate caller."""
import hashlib
import json
import math
from pathlib import Path
import struct

MAGIC = 0x31594342504E5450
HEADER = struct.Struct("<8Q")
FIELDS = {
    1: "picture decode_order order_hint attempt recode delta_q_res old_delta_q_present old_delta_q_res old_base_qindex old_lambda_active count entries",
    2: "picture generation sb ordinal coeff_offset x y sb_qindex block_qindex block_has_coeff skip_mode mds_idx block_x block_y block_w block_h tx_w tx_h tx_depth txb_count eob_y tx_type",
    3: "picture generation sb x y qindex final_blk_cnt",
    4: "picture generation sb x y picture_bypass md_bypass fixed_partition",
    5: "picture generation sb tu offset x y qindex requested_qindex actual_qindex seg_delta invoked qinfo_count skipped eob tx type mds_idx",
    6: "picture decode_order order_hint generation accepted expected_selected_sb sb_total_count",
    7: "picture generation sb x y sb_qindex md_qindex",
    8: "picture generation factor_index synth_blk_size factor_cols factor_rows lambda_before lambda_after lambda_original",
}


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, ("duplicate JSON key", key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("non-finite JSON value: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def validate_metadata(kind, row):
    assert isinstance(row, dict) and set(row) == set(FIELDS[kind].split()), (kind, row.keys())
    for key, value in row.items():
        if key in ("entries", "eob_y", "tx_type"):
            assert isinstance(value, list)
        elif key.startswith("lambda_"):
            assert type(value) in (int, float) and math.isfinite(value)
        else:
            assert type(value) is int, (key, value)
            assert value >= 0 or key == "seg_delta", (key, value)
    if kind == 1:
        for entry in row["entries"]:
            assert set(entry) == set("sb x y pre post selected lambda_refreshed".split())
            assert all(type(v) is int and v >= 0 for v in entry.values())
    if kind == 2:
        assert all(type(v) is int and v >= 0 for key in ("eob_y", "tx_type") for v in row[key])


def read_records(path):
    """Yield exact metadata and offsets, rejecting truncation or mixed streams."""
    path = Path(path)
    assert path.stat().st_size <= 512 * 1024 * 1024
    sequence = 0
    with path.open("rb") as source:
        while True:
            offset = source.tell()
            raw = source.read(HEADER.size)
            if not raw:
                break
            assert len(raw) == HEADER.size, ("truncated header", offset)
            magic, version, kind, generation, picture, seq, length, payload = HEADER.unpack(raw)
            assert magic == MAGIC and version == 2
            assert 1 <= kind <= 8 and seq == sequence
            assert 0 < length < 8192 and payload == 0
            encoded = source.read(length)
            assert len(encoded) == length, ("truncated metadata", offset)
            row = strict_json(encoded)
            validate_metadata(kind, row)
            assert row["picture"] == picture and 0 <= picture < 336
            assert row["attempt" if kind == 1 else "generation"] == generation
            yield dict(kind=kind, generation=generation, picture=picture,
                       sequence=seq, offset=offset, metadata_bytes=length, data=row)
            sequence += 1
    assert sequence > 0, "empty cap observation"


def fingerprint(path):
    path = Path(path).resolve()
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)
