#!/usr/bin/env python3
"""Admit fresh R7 final TUs and test realized, pixel-weighted precision delivery."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

import numpy as np

from aom_tu_binding import identity

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                          "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
W, H = 1920, 1080
TX_W = [4, 8, 16, 32, 64, 4, 8, 8, 16, 16, 32, 32, 64, 4, 16, 8, 32, 16, 64]
TX_H = [4, 8, 16, 32, 64, 8, 4, 16, 8, 32, 16, 64, 32, 16, 4, 32, 8, 64, 16]


def load(path):
    return json.loads(Path(path).read_text())


def bound(value):
    assert identity(value["path"]) == value, value
    return Path(value["path"])


def md5(data):
    return hashlib.md5(data).digest()


def metadata(data, fields):
    fmt = "<" + "".join(code for _, code in fields)
    size = struct.calcsize(fmt)
    assert len(data) >= size
    row = dict(zip((name for name, _ in fields), struct.unpack_from(fmt, data)))
    return row, size


def eob(vector, scan):
    ids = np.flatnonzero(vector[scan])
    return int(ids[-1] + 1) if ids.size else 0


def vector_stats(a):
    value = a.astype(np.float64)
    return {"nonzero": int(np.count_nonzero(a)), "l1": float(np.abs(value).sum()),
            "l2_squared": float(np.square(value).sum())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("binding", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    run_path = args.run.resolve()
    run = load(run_path)
    assert run["status"] == "encoded" and run["returncode"] == 0
    assert run["arm"] == "trace" and run["exact_installed_ivf"]
    assert bound(run["output"])
    expected_ivf = run["output"]["sha256"]
    control_path = bound(run["disabled_control"])
    control = load(control_path)
    assert control["status"] == "encoded" and control["arm"] == "off"
    assert control["returncode"] == 0 and control["exact_installed_ivf"]
    assert control["library"] == run["library"] and control["build_receipt"] == run["build_receipt"]
    bound(control["output"])
    assert control["output"]["sha256"] == expected_ivf
    build = load(bound(run["build_receipt"]))
    assert build["status"] == "build_complete" and build["source_before_after_reviewed_equal"]
    expected_build_fields = (
        "baseline_source_manifest", "reviewed_source_manifest", "source_manifest_before",
        "source_manifest_after", "patch", "schema", "schema_text", "runner", "builder", "config",
    )
    expected_bindings = {key: build[key] for key in expected_build_fields}
    measured_replay = identity(Path(__file__).with_name("replay_aom_qmax_tu.py"))
    normalized = []
    for arm in (control, run):
        assert arm["build_bindings"] == expected_bindings
        assert arm["library"] == build["library"]
        for key in ("source_command", "input", "input_after", "stats_original",
                    "stats_before", "stats_after", "script", "ffmpeg", "ldd_output", "log",
                    "library", "build_receipt", "output", "baseline_observation_admission"):
            bound(arm[key])
        for value in arm["build_bindings"].values():
            bound(value)
        assert arm["input"] == arm["input_after"]
        assert arm["stats_before"] == arm["stats_after"]
        assert arm["stats_original"]["sha256"] == arm["stats_before"]["sha256"]
        assert arm["script"]["sha256"] == measured_replay["sha256"]
        command = list(arm["command"])
        assert command[-1] == arm["output"]["path"]
        assert command[command.index("-i") + 1] == arm["input"]["path"]
        assert command[command.index("-pass") + 1] == "2"
        assert command[command.index("-passlogfile") + 1] + "-0.log" == arm["stats_before"]["path"]
        command[-1] = "<OUTPUT>"
        command[command.index("-passlogfile") + 1] = "<PASSLOG>"
        normalized.append(command)
        assert arm["environment_overrides"]["LD_LIBRARY_PATH"] == str(Path(arm["library"]["path"]).parent)
    assert normalized[0] == normalized[1]
    for key in ("source_command", "input", "stats_original", "ffmpeg", "library_config",
                "library_config_command", "ldd_command", "build_receipt", "library"):
        assert control[key] == run[key], key
    assert control["environment_overrides"]["AOM_TU_TRACE_FD"] is None
    assert int(run["environment_overrides"]["AOM_TU_TRACE_FD"]) >= 0
    schema_path = bound(build["schema"])
    schema = load(schema_path)
    assert schema["version"] == 3 and schema["magic"] == 0x31525455
    binding = load(args.binding)
    assert binding["status"] == "bound"
    for value in binding["inputs"].values():
        bound(value)
    for value in binding["outputs"].values():
        bound(value)
    assert binding["inputs"]["ivf"]["sha256"] == expected_ivf
    assert run["source_command"] == binding["inputs"]["installed_command"]
    assert binding["inputs"]["private_off_command"] == run["disabled_control"]
    assert binding["all_coded_base_qindex_at_most32"]
    assert binding["script"] == identity(Path(__file__).with_name("bind_aom_qmax_tu.py"))
    target_event = binding["coded_event"]
    assert target_event["expected_source_index"] == 216 and not target_event["show_existing_frame"]
    target_quant = [r["fields"] for r in binding["coded_quant_headers"]
                    if r["event"]["event_index"] == target_event["event_index"]]
    assert len(target_quant) == 1
    target_quant = target_quant[0]
    original_run = load(bound(run["source_command"]))
    assert original_run["status"] == "diagnostic_encoded" and original_run["returncode"] == 0
    assert original_run["ivf_sha256"] == expected_ivf
    assert original_run["identity_start"] == original_run["identity_final"] == original_run["expected_identity"]
    original_command = list(original_run["commands"]["pass2"])
    original_command[-1] = "<OUTPUT>"
    original_command[original_command.index("-passlogfile") + 1] = "<PASSLOG>"
    assert normalized[0] == original_command
    assert run["input"]["sha256"] == original_run["input"]["sha256"]
    assert run["stats_original"]["sha256"] == original_run["passes"]["pass1"]["pass1_stats_snapshot"]["sha256"]
    original = Path(binding["outputs"]["original.yuv"]["path"]).read_bytes()
    source_y = np.frombuffer(original[:W * H * 2], dtype="<u2").reshape(H, W)
    target_md5 = md5(original)
    target_obu = Path(binding["outputs"]["target.obu"]["path"]).read_bytes()
    decoded_y = Path(binding["outputs"]["decoded_y.u16"]["path"]).read_bytes()
    trace_path = bound(run["trace"])
    data = trace_path.read_bytes()
    assert 0 < len(data) <= 250_000_000
    records, attempts, final = [], {}, None
    position, current = 0, None
    while position < len(data):
        assert position + 24 <= len(data)
        magic, version, kind, size, generation = struct.unpack_from("<IIIIQ", data, position)
        position += 24
        assert (magic, version) == (0x31525455, 3)
        assert position + size <= len(data) and final is None
        payload = data[position:position + size]
        position += size
        if kind == 1:
            assert current is None or attempts[current]["ended"]
            assert generation not in attempts and (current is None or generation > current)
            header, used = metadata(payload, schema["header"])
            assert used == size == 96
            assert header["generation"] == generation and header["source_index"] == 216
            assert (header["width"], header["height"], header["bit_depth"], header["subsampling"]) == (W, H, 10, 257)
            assert header["source_md5"] == header["coding_source_md5"] == target_md5
            assert [header[k] for k in ("frame_type", "show_frame", "showable_frame",
                                       "order_hint", "refresh_frame_flags")] == [
                target_event["frame_type"], target_event["show_frame"],
                target_event["showable_frame_normalized"], target_event["order_hint"],
                target_event["refresh_frame_flags_normalized"]]
            assert header["parallel_level"] == 0
            current = generation
            attempts[generation] = {"header": header, "ended": False, "records": []}
        elif kind == 2:
            assert generation == current and not attempts[current]["ended"]
            row, used = metadata(payload, schema["tu"])
            assert used == 228 and row["generation"] == generation
            attempts[generation]["records"].append((row, payload[used:]))
        elif kind == 3:
            assert generation == current and not attempts[current]["ended"]
            assert size == 8 and struct.unpack("<Q", payload)[0] == generation
            attempts[generation]["ended"] = True
        elif kind == 4:
            assert generation == current and attempts[current]["ended"]
            final, used = metadata(payload, schema["final"])
            assert used == 112 and final["generation"] == generation
            assert (final["width"], final["height"], final["show_frame"],
                    final["order_hint"], final["refresh_frame_flags"]) == (
                        W, H, target_event["show_frame"], target_event["order_hint"],
                        target_event["refresh_frame_flags_normalized"])
            assert final["source_md5"] == target_md5
            plane_bytes = W * H * 2
            pre = payload[used:used + plane_bytes]
            post = payload[used + plane_bytes:used + 2 * plane_bytes]
            packet = payload[used + 2 * plane_bytes:]
            assert len(pre) == len(post) == plane_bytes
            assert packet == target_obu and len(packet) == final["packet_size"]
            assert md5(packet) == final["packet_md5"]
            assert md5(pre) == final["preloop_md5"] and md5(post) == final["postloop_md5"]
            assert post == decoded_y
        else:
            raise AssertionError(("unknown record", kind))
    assert final is not None and position == len(data)
    assert all(a["ended"] for a in attempts.values())
    selected = attempts[current]["records"]
    assert selected
    maps = {key: np.zeros((H, W), np.uint16) for key in ("predictor", "raw", "initial", "final")}
    owner = np.full((H, W), -1, dtype=np.int32)
    scalar = {key: np.full((H, W), -1, np.int32)
              for key in ("qindex", "tx_width", "tx_height", "status", "final_eob")}
    exercised_map = np.zeros((H, W), dtype=np.uint8)
    for number, (row, payload) in enumerate(selected):
        assert row["generation"] == current and row["source_index"] == 216
        assert row["source_md5"] == target_md5 and row["plane"] == 0
        assert (row["order_hint"], row["refresh_frame_flags"], row["show_frame"],
                row["bit_depth"], row["frame_number"]) == (
                    target_event["order_hint"], target_event["refresh_frame_flags_normalized"],
                    target_event["show_frame"], 10, final["frame_number"])
        x, y, w, h = [row[k] for k in ("x", "y", "width", "height")]
        assert 0 <= x < W and 0 <= y < H and x % 4 == y % 4 == 0
        assert w in (4, 8, 16, 32, 64, 128) and h in (4, 8, 16, 32, 64, 128)
        assert x + w <= W + 127 and y + h <= H + 127
        n, status = row["coeff_count"], row["status"]
        exercised = status in (1, 5)
        assert status in (1, 2, 3, 4, 5)
        assert (n > 0) == exercised
        if exercised:
            assert 0 <= row["tx_size"] < len(TX_W)
            assert (w, h) == (TX_W[row["tx_size"]], TX_H[row["tx_size"]])
            assert n == min(w, 32) * min(h, 32)
            assert row["flags"] == 31 and 0 <= row["tx_type"] < 16
            assert 0 <= row["qindex"] <= 255 and 0 <= row["base_qindex"] <= 255
            assert row["base_qindex"] == target_quant["base_q_idx"] <= 32
            assert 0 <= row["coded_qindex"] <= 255 and -255 <= row["delta_q"] <= 255
            assert row["quant_idx"] in (0, 1) and row["quant_flags"] & ~15 == 0
            # Current final paths choose FP for trellis; B when it is disabled.
            assert row["quant_idx"] == (0 if row["quant_flags"] & 1 else 1)
            assert not row["quant_flags"] & 4 or row["quant_flags"] & 2
            assert row["dequant_dc"] > 0 and row["dequant_ac"] > 0
            assert row["lossless"] in (0, 1) and row["reduced_tx_set"] in (0, 1)
            assert row["log_scale"] in (0, 1, 2)
            assert (row["eob_final"] > 0) if status == 1 else (row["eob_final"] == 0)
        else:
            assert row["flags"] == 16
            assert row["tx_size"] == row["tx_type"] == row["qindex"] == -1
            assert row["coded_qindex"] == -1 and row["quant_idx"] == 2 ** 32 - 1
            assert row["eob_initial"] == row["eob_final"] == 0
        offset, vectors = 0, {}
        for name in schema["tu_vectors"]:
            vectors[name] = np.frombuffer(payload[offset:offset + n * 4], dtype="<i4")
            assert len(vectors[name]) == n
            offset += n * 4
        scan = np.frombuffer(payload[offset:offset + n * 2], dtype="<i2").astype(np.int32)
        offset += n * 2
        if exercised:
            assert np.array_equal(np.sort(scan), np.arange(n))
            assert eob(vectors["raw"], scan) == row["raw_eob"]
            for label in ("initial", "final"):
                assert eob(vectors[label + "_q"], scan) == row["eob_" + label]
                assert eob(vectors[label + "_dq"], scan) == row["eob_" + label]
        local = {}
        map_bytes = w * h * 2
        for name in schema["tu_maps"]:
            local[name] = np.frombuffer(payload[offset:offset + map_bytes], dtype="<u2").reshape(h, w)
            assert local[name].max() <= 1023
            offset += map_bytes
        assert md5(local["predictor"].tobytes()) == row["predictor_md5"]
        assert md5(local["final"].tobytes()) == row["preloop_md5"]
        hh, ww = min(h, H - y), min(w, W - x)
        sl = np.s_[y:y + hh, x:x + ww]
        assert np.all(owner[sl] == -1), ("overlap", number, row)
        if exercised:
            residual = np.frombuffer(payload[offset:offset + map_bytes], dtype="<i2").reshape(h, w)
            offset += map_bytes
            assert md5(residual.tobytes()) == row["residual_md5"]
            assert np.array_equal(residual[:hh, :ww].astype(np.int32),
                                  source_y[sl].astype(np.int32) - local["predictor"][:hh, :ww].astype(np.int32))
        else:
            assert all(np.array_equal(local["predictor"], v) for v in local.values())
        assert offset == len(payload)
        for name, target in maps.items():
            target[sl] = local[name][:hh, :ww]
        owner[sl] = number
        exercised_map[sl] = exercised
        for key, value in (("qindex", row["qindex"]), ("tx_width", w), ("tx_height", h),
                           ("status", status), ("final_eob", row["eob_final"])):
            scalar[key][sl] = value
        stats = {name: vector_stats(vector) for name, vector in vectors.items()} if exercised else {}
        for label, a, b in (("raw_to_initial_dq", "raw", "initial_dq"),
                            ("initial_to_final_dq", "initial_dq", "final_dq")):
            if exercised:
                stats[label] = vector_stats(vectors[a].astype(np.int64) - vectors[b].astype(np.int64))
        pixel_deltas = {}
        for a, b in (("raw", "initial"), ("initial", "final")):
            delta = local[a].astype(np.int32) - local[b].astype(np.int32)
            pixel_deltas[a + "_to_" + b] = {
                "changed_full_TU_pixels": int(np.count_nonzero(delta)),
                "full_TU_pixels": int(delta.size), "max_absolute_delta": int(np.abs(delta).max()),
                "visible_changed_pixels": int(np.count_nonzero(delta[:hh, :ww])),
            }
        records.append({
            "metadata": {k: v.hex() if isinstance(v, bytes) else v for k, v in row.items()},
            "visible_pixels": hh * ww, "coefficient_proxies_not_bits": stats,
            "pixel_deltas": pixel_deltas,
        })
    assert np.all(owner >= 0), ("holes", int(np.count_nonzero(owner < 0)))
    assert maps["final"].tobytes() == pre
    prior_path = bound(run["baseline_observation_admission"])
    assert identity(prior_path)["sha256"] == "cbe7631f8691f7edb449341d63109f02c7a9e484ac901d5cf94b932df4255a31"
    prior = load(prior_path)
    assert prior["status"] == "admitted"
    prior_maps = np.load(bound(prior["artifacts"]["maps"]), allow_pickle=False)
    assert np.array_equal(source_y, prior_maps["source"])
    delivery = {}
    for name, (x, y, w, h) in {"shirt": (1200, 650, 200, 100),
                              "background": (950, 50, 250, 180)}.items():
        sl = np.s_[y:y+h, x:x+w]
        mask = exercised_map[sl].astype(bool)
        before = prior_maps["exercised"][sl].astype(bool)
        q = scalar["qindex"][sl][mask]
        common = mask & before
        prior_q = prior_maps["qindex"][sl]
        vals, counts = np.unique(q, return_counts=True)
        old_q = prior_q[before]
        old_vals, old_counts = np.unique(old_q, return_counts=True)
        obj = {
            "xywh": [x, y, w, h],
            "full_ROI_pixels": w*h, "exercised_pixels": int(mask.sum()),
            "prior_exercised_pixels": int(before.sum()),
            "previously_exercised_now_skipped": int(np.count_nonzero(before & ~mask)),
            "previously_skipped_now_exercised": int(np.count_nonzero(mask & ~before)),
            "status_pixels": {str(int(v)): int(np.count_nonzero(scalar["status"][sl] == v))
                              for v in np.unique(scalar["status"][sl])},
            "exercised_qindex_pixel_counts": dict(zip(map(str, vals.tolist()), counts.tolist())),
            "exercised_mean_qindex": float(q.mean()) if q.size else None,
            "exercised_fraction_at_most48": float((q <= 48).mean()) if q.size else None,
            "exercised_pixels_above32": int(np.count_nonzero(q > 32)),
            "exercised_pixels_above48": int(np.count_nonzero(q > 48)),
            "prior_exercised_qindex_pixel_counts": dict(
                zip(map(str, old_vals.tolist()), old_counts.tolist())),
            "prior_exercised_mean_qindex": float(old_q.mean()) if old_q.size else None,
            "prior_exercised_fraction_at_most48": float(
                (old_q <= 48).mean()) if old_q.size else None,
            "prior_exercised_pixels_above32": int(np.count_nonzero(old_q > 32)),
            "prior_exercised_pixels_above48": int(np.count_nonzero(old_q > 48)),
            "same_pixel_exercised_in_both": int(common.sum()),
            "same_pixel_mean_qindex_change": float(
                (scalar["qindex"][sl][common] - prior_q[common]).mean()) if common.any() else None,
            "transform_pixel_counts": {
                f"{int(tw)}x{int(th)}": int(np.count_nonzero(
                    mask & (scalar["tx_width"][sl] == tw) & (scalar["tx_height"][sl] == th)))
                for tw, th in sorted(set(zip(scalar["tx_width"][sl][mask].tolist(),
                                            scalar["tx_height"][sl][mask].tolist())))
            },
            "scope": "Exercised pixels only; skips have no actual quantization observation.",
        }
        obj["delivered"] = bool(q.size and q.mean() <= 40 and (q <= 48).mean() >= .9)
        delivery[name] = obj
    args.output.mkdir(parents=True, exist_ok=False)
    maps_path = args.output / "maps.npz"
    np.savez_compressed(maps_path, source=source_y, **maps, owner=owner,
                        exercised=exercised_map, **scalar,
                        preloop=np.frombuffer(pre, "<u2").reshape(H, W),
                        postloop=np.frombuffer(post, "<u2").reshape(H, W))
    rows_path = args.output / "tu-records.json"
    rows_path.write_text(json.dumps(records, indent=2, allow_nan=False) + "\n")
    artifacts = {
        "maps": identity(maps_path), "tu_records": identity(rows_path),
        "frozen_controls": binding["inputs"]["frozen_controls"],
        "binding": identity(args.binding), "run": identity(run_path),
        "trace": run["trace"], "schema": identity(schema_path),
        "builder_receipt": run["build_receipt"], "disabled_control": run["disabled_control"],
        "baseline_admission": identity(prior_path), "baseline_maps": prior["artifacts"]["maps"],
    }
    for value in artifacts.values():
        bound(value)
    report = {
        "schema": 1, "status": "admitted", "script": identity(__file__),
        "artifacts": artifacts, "selected_generation": current,
        "attempts": [{"generation": g, "records": len(a["records"])} for g, a in attempts.items()],
        "status_legend": schema["status"], "all_visible_pixels_covered_once": True,
        "actual_final_DQ_exact_preloop": True, "postloop_exact_display216": True,
        "packed_OBU_exact_independent_binding": True,
        "source_residual_predictor_visible_exact": True,
        "instrumentation_same_binary_off_and_installed_IVF_exact": True,
        "coefficient_proxies_are_not_coded_bits": True,
        "precision_delivery": delivery,
        "precision_delivery_pass": all(r["delivered"] for r in delivery.values()),
        "parsed_target_quant_header": target_quant,
        "scope": "Local fixed-predictor mosaics, no legal-encode, bitrate or playback claim.",
    }
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "selected_generation", "attempts")}, indent=2))


if __name__ == "__main__":
    main()
