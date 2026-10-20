#!/usr/bin/env python3
"""Independent native-coefficient-layout check for the rejected R11 admission."""

import collections
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path("/tmp/downloads/codex-work/pantheon-sourcebudget-20261020")
R11 = ROOT / "parent/psyex-coeff-r11"
R10 = ROOT / "parent/aom-decoder-r10-v2"
OUT = ROOT / "reviewer/round11-dq-mismatch/result.json"


def ident(path):
    path = Path(path)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, "size": path.stat().st_size}


def c_array(text, name):
    match = re.search(
        re.escape(name) + r"\s*\[[^]]+\][^=]*=\s*\{(.*?)\};", text, re.S
    )
    assert match, name
    return np.asarray(
        [int(value) for value in re.findall(r"(?<![A-Za-z_])-?\d+", match.group(1))],
        dtype=np.int32,
    )


def transpose_index(index, width, height):
    return (index % width) * height + index // width


def transpose_values(values, width, height):
    return np.asarray(values).reshape(height, width).T.ravel()


def main():
    validator = R11 / "validate.py"
    spec = importlib.util.spec_from_file_location("r11_validator", validator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tokens, terminal = module.parse(R11 / "runs/on-1/coeff.bin")

    units = json.loads((R10 / "admitted-1/units.json").read_text())
    unit_map = np.load(R10 / "admitted-1/unit.npy")
    payload_path = R10 / "runs/on-1/payload.bin"
    payload = payload_path.read_bytes()

    svt_scan_path = R11 / "source/Source/Lib/Codec/coefficients.h"
    aom_scan_path = R10 / "source/av1/common/scan.c"
    svt_scan_text = svt_scan_path.read_text()
    aom_scan_text = aom_scan_path.read_text()

    # Transform types 0..9 use the default scan, vertical 1-D types use mrow,
    # and horizontal 1-D types use mcol in both pinned scan-order tables.
    scan_prefix = {
        **{kind: "default" for kind in range(10)},
        10: "mrow",
        11: "mcol",
        12: "mrow",
        13: "mcol",
        14: "mrow",
        15: "mcol",
    }

    scan_families = {}
    positive = []
    direct_dq_equal = 0
    transposed_dq_equal = 0
    transposed_iqm_equal = 0
    empty_iqm = 0
    type_dimensions = collections.Counter()
    first = None

    for token, record in tokens.items():
        begin = record["begin"]
        if not record["commit"]["eob"]:
            continue
        x, y, w, h = (begin[key] for key in ("x", "y", "w", "h"))
        visible_h = min(h, 1080 - y)
        ids = np.unique(unit_map[y : y + visible_h, x : x + w])
        assert len(ids) == 1
        unit = units[int(ids[0])]
        assert unit["eob"] > 0
        assert (begin["tx"], begin["type"], begin["n"]) == (
            unit["tx_size"],
            unit["tx_type"],
            unit["coeff_count"],
        )

        width, height = min(w, 32), min(h, 32)
        prefix = scan_prefix[begin["type"]]
        family = f"{prefix}_scan_{width}x{height}"
        if family not in scan_families:
            svt_scan = c_array(svt_scan_text, family)
            aom_scan = c_array(aom_scan_text, family)
            mapped_scan = np.asarray(
                [transpose_index(int(pos), width, height) for pos in svt_scan],
                dtype=np.int32,
            )
            assert len(svt_scan) == width * height
            assert np.array_equal(mapped_scan, aom_scan)
            scan_families[family] = {
                "width": width,
                "height": height,
                "entries": len(svt_scan),
                "svt_to_libaom_exact_transpose": True,
                "native_arrays_directly_equal": bool(np.array_equal(svt_scan, aom_scan)),
                "svt_first_8": svt_scan[:8].tolist(),
                "libaom_first_8": aom_scan[:8].tolist(),
            }
        else:
            svt_scan = c_array(svt_scan_text, family)
            aom_scan = c_array(aom_scan_text, family)

        assert np.array_equal(record["scan"], svt_scan)
        final = record["stages"][-1]
        decoder_dq = np.frombuffer(
            payload, dtype="<i4", count=begin["n"], offset=unit["coeff_offset"]
        )
        mapped_dq = transpose_values(final["dq"], width, height)
        direct = bool(np.array_equal(final["dq"], decoder_dq))
        mapped = bool(np.array_equal(mapped_dq, decoder_dq))
        assert mapped
        direct_dq_equal += direct
        transposed_dq_equal += mapped

        native_iqm = np.frombuffer(record["iqm"], dtype=np.uint8)
        decoder_iqm = np.frombuffer(
            payload, dtype=np.uint8, count=unit["iqm_count"], offset=unit["iqm_offset"]
        )
        if len(native_iqm):
            assert len(native_iqm) == width * height
            iqm_equal = bool(
                np.array_equal(transpose_values(native_iqm, width, height), decoder_iqm)
            )
            assert iqm_equal
            transposed_iqm_equal += 1
        else:
            assert len(decoder_iqm) == 0
            empty_iqm += 1

        type_dimensions[(begin["tx"], begin["type"], width, height)] += 1
        positive.append((token, unit["id"]))

        if token == 1:
            q = final["q"]
            encoder_nonzero = np.flatnonzero(q)
            decoder_nonzero = np.flatnonzero(decoder_dq)
            scan_positions = np.flatnonzero(q[record["scan"]])
            first = {
                "token": token,
                "unit": unit["id"],
                "tx_size": begin["tx"],
                "tx_type": begin["type"],
                "width": width,
                "height": height,
                "eob": begin["n"] if False else record["commit"]["eob"],
                "encoder_native_nonzero_indices": encoder_nonzero.tolist(),
                "decoder_native_nonzero_indices": decoder_nonzero.tolist(),
                "coded_scan_positions": scan_positions.tolist(),
                "encoder_dq_values": final["dq"][encoder_nonzero].tolist(),
                "decoder_dq_values": decoder_dq[decoder_nonzero].tolist(),
                "mapped_encoder_indices": [
                    transpose_index(int(index), width, height)
                    for index in encoder_nonzero
                ],
            }

    assert len(positive) == 2151
    assert first is not None

    result = {
        "status": "layout_mapping_proven",
        "scope": "native storage normalization only; no R11 outcome or quality inference",
        "validator": ident(validator),
        "trace": ident(R11 / "runs/on-1/coeff.bin"),
        "r10_payload": ident(payload_path),
        "source_files": {
            "svt_scan": ident(svt_scan_path),
            "svt_inverse": ident(R11 / "source/Source/Lib/Codec/inv_transforms.c"),
            "svt_quantizer": ident(R11 / "source/Source/Lib/Codec/full_loop.c"),
            "libaom_scan": ident(aom_scan_path),
            "libaom_inverse": ident(R10 / "source/av1/common/av1_inv_txfm2d.c"),
            "libaom_decoder_quant": ident(R10 / "source/av1/decoder/decodetxb.c"),
            "libaom_qmatrix": ident(R10 / "source/av1/common/quant_common.c"),
        },
        "terminal": terminal,
        "positive_units": len(positive),
        "dq_exact_after_transpose": transposed_dq_equal,
        "dq_already_equal_without_transpose": direct_dq_equal,
        "dq_require_nontrivial_transpose": len(positive) - direct_dq_equal,
        "iqm_exact_after_transpose_nonempty": transposed_iqm_equal,
        "iqm_empty_both_sides": empty_iqm,
        "scan_families": scan_families,
        "type_dimension_population": [
            {
                "tx_size": key[0],
                "tx_type": key[1],
                "coefficient_width": key[2],
                "coefficient_height": key[3],
                "count": value,
            }
            for key, value in sorted(type_dimensions.items())
        ],
        "first_failed_pair": first,
    }
    OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("optimized Python is prohibited")
    main()
