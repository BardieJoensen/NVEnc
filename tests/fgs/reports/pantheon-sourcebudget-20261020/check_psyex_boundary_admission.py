#!/usr/bin/env python3
"""Targeted trace-admission fault probes; synthetic mutations are not evidence."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys


def main():
    if not __debug__:
        raise RuntimeError("Do not disable fault-check assertions")
    p = argparse.ArgumentParser()
    p.add_argument("trace", type=Path)
    p.add_argument("original_recon", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    validator = Path(__file__).with_name("validate_psyex_boundary.py")
    spec = importlib.util.spec_from_file_location("boundary_validator", validator)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    attempts, post, _, _ = m.parse_trace(a.trace)
    expected_post = m.read_frame(a.original_recon, 216, 336)
    assert post == expected_post
    records = []
    with a.trace.open("rb") as f:
        while h := f.read(64):
            hdr = list(struct.unpack("<8Q", h))
            meta = json.loads(f.read(hdr[6]))
            raw = f.read(hdr[7])
            records.append([hdr, meta, raw])

    def encode(rows):
        chunks = []
        for h, meta, raw in rows:
            h = list(h)
            b = json.dumps(meta, separators=(",", ":")).encode()
            h[6], h[7] = len(b), len(raw)
            chunks.extend((struct.pack("<8Q", *h), b, raw))
        return b"".join(chunks)

    def mutate(index, part, key, value):
        rows = copy.deepcopy(records)
        rows[index][part][key] = value
        return encode(rows)

    first_sb = next(i for i, r in enumerate(records) if r[0][2] == 1)
    second_sb = next(i for i, r in enumerate(records) if r[0][2] == 1 and i > first_sb)
    accepted = next(i for i, r in enumerate(records) if r[0][2] == 2 and r[1]["do_recode"] == 0)
    post_index = next(i for i, r in enumerate(records) if r[0][2] == 3)
    original = a.trace.read_bytes()
    bad_sample = copy.deepcopy(records)
    bad_sample[first_sb][2] = struct.pack("<H", 1024) + bad_sample[first_sb][2][2:]
    duplicate_sb = copy.deepcopy(records)
    duplicate_sb[second_sb][1] = copy.deepcopy(duplicate_sb[first_sb][1])
    duplicate_sb[second_sb][2] = duplicate_sb[first_sb][2]
    missing_sb = copy.deepcopy(records)
    del missing_sb[first_sb]
    for i, r in enumerate(missing_sb):
        r[0][5] = i
    missing_sb[-1][1]["records_before_end"] = len(missing_sb)-1
    probes = {
        "truncated_payload_or_end": original[:-1],
        "trailing_byte": original+b"\0",
        "wrong_first_sequence": mutate(0, 0, 5, 2),
        "wrong_first_generation": mutate(0, 0, 3, 1),
        "duplicate_SB_ownership": encode(duplicate_sb),
        "missing_SB_renumbered_sequence": encode(missing_sb),
        "invalid_10bit_sample": encode(bad_sample),
        "accepted_changed_to_recode": mutate(accepted, 1, "do_recode", 1),
        "wrong_terminal_attempt_count": mutate(-1, 1, "attempts", 99),
    }
    a.output.mkdir(parents=True, exist_ok=False)
    temp = a.output/"synthetic-mutation.bin"
    results = []
    for name, raw in probes.items():
        temp.write_bytes(raw)
        identity = m.ident(temp)
        try:
            m.parse_trace(temp)
        except (AssertionError, ValueError, KeyError, struct.error) as e:
            results.append({"case": name, "parser_rejected": True, "error": repr(e),
                            "mutation": identity})
        else:
            raise AssertionError("Parser accepted "+name)
        finally:
            temp.unlink()
    # Framing alone cannot establish that plausible pixels are the right pixels.
    altered = copy.deepcopy(records)
    value = struct.unpack("<H", altered[post_index][2][:2])[0] ^ 1
    altered[post_index][2] = struct.pack("<H", value) + altered[post_index][2][2:]
    temp.write_bytes(encode(altered))
    identity = m.ident(temp)
    _, changed_post, _, _ = m.parse_trace(temp)
    assert changed_post != expected_post
    results.append({"case": "in_range_postloop_pixel_change", "parser_rejected": False,
                    "would_fail_exact_postloop_binding": True, "mutation": identity})
    temp.unlink()
    m.dump(a.output/"result.json", {"status": "passed", "argv": sys.argv,
           "script": m.ident(__file__), "validator": m.ident(validator),
           "python": m.ident(sys.executable), "trace": m.ident(a.trace),
           "original_recon": m.ident(a.original_recon),
           "unaltered_attempt_count": len(attempts), "cases": results,
           "scope": "Synthetic fault probes of framing and sample-binding checks; no encode observations."})
    print(json.dumps({"status": "passed", "cases": len(results)}))


if __name__ == "__main__":
    main()
