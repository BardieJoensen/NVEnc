#!/usr/bin/env python3
"""Bind a selected admitted R16 midpoint-refinement display 216 to its coded AV1 event."""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

EXPECTED_CONTRACT = "9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82"
EXPECTED_BASE_CONTRACT = "5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71"
EXPECTED_ENCODER = "5804a1a5985d0676975abe28fba2d8c7a8d6af71c2f70d39dab11436bf2941e4"
EXPECTED_INPUT = "232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4"
EXPECTED_FFMPEG = "ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41"
EXPECTED_R8_RECEIPT = "ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138"
EXPECTED_R8_RATE = 9.6279048
EXPECTED_SOURCE_RATE = 9.6765224
EXPECTED_OUTER = "93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858"
W, H = 1920, 1080
FRAMING_ORIGIN = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/aom_tu_binding.py")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def ident(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, "size": path.stat().st_size}


def strict_json(path):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "duplicate JSON key: " + key)
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(RuntimeError("nonfinite JSON: "+value)))


def require_live_record(record, label):
    require(isinstance(record, dict) and set(record) >= {"path", "sha256", "size"},
            label + " identity schema")
    live = ident(record["path"])
    require(live == record, label + " live identity")
    return live


def load_encoder(path, expected_sha):
    require(expected_sha == EXPECTED_ENCODER, "unreviewed encoder SHA")
    live = ident(path)
    require(live["sha256"] == expected_sha, "selected encoder script hash")
    spec = importlib.util.spec_from_file_location("r16_frozen_encoder", live["path"])
    require(spec is not None and spec.loader is not None, "cannot load selected encoder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(callable(getattr(module, "validate_chain", None)), "frozen encoder lacks validate_chain API")
    return module, live


def validate_outer(path, expected_sha, receipt, encoder_id):
    outer_id = ident(path)
    require(outer_id["sha256"] == expected_sha, "selected outer receipt SHA")
    outer = strict_json(path)
    require(outer.get("status") == "complete" and outer.get("returncode") == 0,
            "outer execution incomplete")
    before, after = outer.get("inputs_before"), outer.get("inputs_after")
    require(isinstance(before, list) and before == after and before, "outer identity drift")
    for index, record in enumerate(before):
        require_live_record(record, "outer input "+str(index))
    require(any(row["sha256"] == EXPECTED_OUTER for row in before), "wrong outer wrapper")
    require(any(row == encoder_id for row in before), "outer did not bind selected encoder")
    require_live_record(outer["log"], "outer log")
    command = outer.get("command")
    require(isinstance(command, list) and len(command) >= 10, "outer command schema")
    require(command[:6] == ["/usr/bin/nice", "-n", "10", "/usr/bin/taskset", "-c", "8-11"],
            "outer execution controls")
    require(any(Path(row["path"]).resolve() == Path(command[6]).resolve() for row in before),
            "outer Python was not identity-bound")
    require(Path(command[7]).resolve() == Path(encoder_id["path"]), "outer encoder path")
    require(command[8:10] == [receipt["tag"], str(receipt["request_kbps"])], "outer selected arm")
    calibration = receipt["calibration"]
    require(calibration.get("phase") == "midpoint-refinement", "wrong calibration phase")
    if calibration["attempt"] == 1:
        low, high = receipt["bracket"]["low"], receipt["bracket"]["high"]
        require(command[10:] == ["--low-receipt", low["path"],
                                 "--low-receipt-sha", low["sha256"],
                                 "--high-receipt", high["path"],
                                 "--high-receipt-sha", high["sha256"]],
                "initial midpoint endpoint arguments")
    else:
        previous = calibration["previous_receipt"]
        require(command[10:] == ["--previous-receipt", previous["path"],
                                 "--previous-receipt-sha", previous["sha256"]],
                "refinement predecessor arguments")
    return outer_id, outer


# Copied only from the independently reviewed IVF/OBU framing helpers in
# aom_tu_binding.py; no prior source-index or lag assumptions are reused.
def ivf_packets(data):
    require(len(data) >= 32 and data[:4] == b"DKIF", "not IVF")
    version, header_size = struct.unpack_from("<HH", data, 4)
    fourcc, width, height, rate, scale, count, unused = struct.unpack_from("<4sHHIIII", data, 8)
    require((version, header_size, fourcc, width, height, rate, scale, count, unused) ==
            (0, 32, b"AV01", W, H, 24, 1, 336, 0), "unexpected IVF header")
    packets = []
    offset = 32
    while offset < len(data):
        require(offset + 12 <= len(data), "partial IVF packet header")
        size, pts = struct.unpack_from("<IQ", data, offset)
        payload = offset + 12
        require(size > 0 and payload + size <= len(data), "invalid IVF packet size")
        require(pts == len(packets), "noncanonical IVF PTS")
        raw = data[payload:payload + size]
        packets.append({"index": len(packets), "pts": pts,
                        "header_file_offset": offset, "payload_file_offset": payload,
                        "size": size, "sha256": hashlib.sha256(raw).hexdigest(), "data": raw})
        offset = payload + size
    require(offset == len(data) and len(packets) == 336, "IVF packet population")
    return packets


def obus(data):
    out = []
    pos = 0
    while pos < len(data):
        start = pos
        header = data[pos]
        pos += 1
        require(header & 0x80 == 0 and header & 1 == 0 and header & 2, "invalid OBU header")
        kind = (header >> 3) & 15
        require(kind in (1, 2, 3, 4, 5, 6, 7, 8, 15), "unsupported OBU type")
        if header & 4:
            require(pos < len(data) and data[pos] & 7 == 0, "invalid OBU extension")
            pos += 1
        size = 0
        for i in range(8):
            require(pos < len(data), "partial OBU size")
            byte = data[pos]
            pos += 1
            size |= (byte & 127) << (7 * i)
            if not byte & 128:
                break
        else:
            raise RuntimeError("unterminated OBU size")
        require(size < 2**32 and pos + size <= len(data), "invalid OBU payload size")
        pos += size
        raw = data[start:pos]
        out.append({"type": kind, "packet_start": start, "packet_end": pos,
                    "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    require(pos == len(data), "OBU trailing data")
    return out


PACKET_RE = re.compile(r"] Packet: (?P<size>\d+) bytes(?P<key>, key frame)?, "
                       r"pts (?P<pts>-?\d+), dts (?P<dts>-?\d+), duration (?P<duration>\d+)\.")
FIELD_RE = re.compile(r"]\s+\d+\s+(?P<name>[A-Za-z0-9_]+)\s+[01]+ = (?P<value>-?\d+)\s*$")
WANTED = {"show_existing_frame", "frame_to_show_map_idx", "frame_type", "show_frame",
          "showable_frame", "order_hint", "refresh_frame_flags"}


def parse_headers(log, packets, framed):
    traced_packets, events = [], []
    current_packet = current_event = None
    order_bits = []

    def finish():
        nonlocal current_event
        if current_event is None:
            return
        require("show_existing_frame" in current_event, "header missing show_existing_frame")
        events.append(current_event)
        current_event = None

    for line_number, line in enumerate(log.splitlines(), 1):
        match = PACKET_RE.search(line)
        if match:
            finish()
            current_packet = {"index": len(traced_packets), "size": int(match["size"]),
                              "key_packet": bool(match["key"]), "pts": int(match["pts"]),
                              "dts": int(match["dts"]), "duration": int(match["duration"])}
            traced_packets.append(current_packet)
            continue
        if line.endswith(" Frame Header"):
            finish()
            require(current_packet is not None, "frame header before packet")
            current_event = {"event_index": len(events), "packet_index": current_packet["index"],
                             "packet_pts": current_packet["pts"],
                             "packet_event_index": sum(e["packet_index"] == current_packet["index"] for e in events),
                             "header_log_line": line_number}
            continue
        match = FIELD_RE.search(line)
        if current_event is not None and match and match["name"] in WANTED:
            name = match["name"]
            require(name not in current_event, "duplicate field in frame header")
            current_event[name] = int(match["value"])
        elif current_event is None and match and match["name"] == "order_hint_bits_minus_1":
            order_bits.append(int(match["value"]))
    finish()

    require(len(traced_packets) == len(packets) == 336, "trace packet count")
    for observed, packet in zip(traced_packets, packets):
        require(observed["index"] == packet["index"] and observed["size"] == packet["size"] and
                observed["pts"] == packet["pts"] and observed["dts"] == packet["pts"] and
                observed["duration"] == 1, "trace/IVF packet mismatch")
        frame_obus = [o for o in framed[packet["index"]] if o["type"] in (3, 6)]
        packet_events = [e for e in events if e["packet_index"] == packet["index"]]
        require(len(frame_obus) == len(packet_events), "frame-header/OBU count mismatch")
        for event, obu in zip(packet_events, frame_obus):
            event["obu"] = dict(obu)
            event["obu"]["file_offset"] = packet["payload_file_offset"] + obu["packet_start"]
    require(len(set(order_bits)) == 1, "inconsistent order-hint width")
    return traced_packets, events, order_bits


def lifecycle(packets, events):
    slots = [None] * 8
    coded_ordinal = 0
    displays = []
    implicit_key_refreshes = []
    refresh_history = []
    for packet in packets:
        packet_events = [e for e in events if e["packet_index"] == packet["index"]]
        actions = []
        for event in packet_events:
            show_existing = event["show_existing_frame"]
            require(show_existing in (0, 1), "show_existing_frame domain")
            if show_existing:
                require("frame_to_show_map_idx" in event and 0 <= event["frame_to_show_map_idx"] < 8,
                        "show-existing slot")
                slot = event["frame_to_show_map_idx"]
                resolved = slots[slot]
                require(resolved is not None, "show-existing references empty slot")
                event["resolved_coded_ordinal"] = resolved["coded_ordinal"]
                event["resolved_event_index"] = resolved["event_index"]
                actions.append({"kind": "show_existing", "event_index": event["event_index"],
                                "slot": slot, "coded_ordinal": resolved["coded_ordinal"],
                                "coded_event_index": resolved["event_index"]})
                continue

            for key in ("frame_type", "show_frame", "order_hint"):
                require(key in event, "coded header missing "+key)
            require(event["frame_type"] in range(4) and event["show_frame"] in (0, 1), "coded header domain")
            event["coded_ordinal"] = coded_ordinal
            coded_ordinal += 1
            if event["show_frame"]:
                actions.append({"kind": "shown_coded", "event_index": event["event_index"],
                                "coded_ordinal": event["coded_ordinal"],
                                "coded_event_index": event["event_index"]})
            raw_flags = event.get("refresh_frame_flags")
            if event["frame_type"] == 0 and event["show_frame"] == 1:
                flags = 255
                event["refresh_normalization"] = "implicit shown KEY refreshes all 8 slots"
                implicit_key_refreshes.append(event["event_index"])
            else:
                require(raw_flags is not None and 0 <= raw_flags <= 255, "missing refresh flags")
                flags = raw_flags
                event["refresh_normalization"] = "explicit syntax"
            event["refresh_frame_flags_normalized"] = flags
            refreshed = []
            key = {"event_index": event["event_index"], "coded_ordinal": event["coded_ordinal"],
                   "packet_index": event["packet_index"], "order_hint": event["order_hint"],
                   "obu_sha256": event["obu"]["sha256"]}
            for slot in range(8):
                if flags & (1 << slot):
                    slots[slot] = key
                    refreshed.append(slot)
                    refresh_history.append({"slot": slot, **key})
            event["refreshed_slots"] = refreshed
        require(len(actions) == 1, "packet does not have exactly one display action")
        action = actions[0]
        action["display_index"] = len(displays)
        action["packet_index"] = packet["index"]
        action["packet_pts"] = packet["pts"]
        displays.append(action)
    require(len(displays) == 336 and [d["display_index"] for d in displays] == list(range(336)),
            "display count/order")
    return displays, refresh_history, implicit_key_refreshes, coded_ordinal


def main():
    if not __debug__:
        raise RuntimeError("Do not disable binding checks")
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt-sha", required=True)
    parser.add_argument("--encoder-script", type=Path, required=True)
    parser.add_argument("--encoder-sha", required=True)
    parser.add_argument("--outer-receipt", type=Path, required=True)
    parser.add_argument("--outer-receipt-sha", required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "output exists")
    receipt_id = ident(args.receipt)
    require(receipt_id["sha256"] == args.receipt_sha, "selected command receipt SHA")
    receipt = strict_json(args.receipt)
    require(receipt.get("status") == "encoded" and receipt.get("returncode") == 0, "encode incomplete")
    require(receipt.get("case") == "e05-1440" and isinstance(receipt.get("request_kbps"), int), "wrong arm")
    encoder, encoder_id = load_encoder(args.encoder_script, args.encoder_sha)
    require(receipt.get("executed_script") == encoder_id,
            "selected receipt was not issued by selected encoder")
    require_live_record(receipt["script"], "selected encoder snapshot")
    require(receipt["script"]["sha256"] == encoder_id["sha256"] and
            receipt["script"]["size"] == encoder_id["size"], "encoder snapshot differs")
    require(getattr(encoder, "CONTRACT_SHA", None) == EXPECTED_CONTRACT, "encoder contract constant")
    require(getattr(encoder, "R8_COMMAND_SHA", None) == EXPECTED_R8_RECEIPT, "encoder R8 constant")
    require(receipt.get("settings") == getattr(encoder, "POLICY", None), "wrong R16 policy")
    require(receipt["settings"].get("--enable-tf") == "0" and
            "--min-qp" not in receipt["settings"] and "--max-qp" not in receipt["settings"],
            "wrong intervention")
    # The frozen runner owns the recursively fail-closed calibration semantics.
    # Its final API must return the selected receipt and every live chain path.
    chain_receipt, chain_paths = encoder.validate_chain(args.receipt.resolve(), args.receipt_sha)
    require(chain_receipt == receipt and isinstance(chain_paths, list) and chain_paths,
            "validate_chain result schema")
    for index, path in enumerate(chain_paths):
        require(Path(path).is_file(), "missing calibration-chain path "+str(index))
    chain_resolved = {Path(path).resolve() for path in chain_paths}
    base_contract = Path("/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND16_TF0_BUDGET_CONTRACT.md").resolve()
    require(ident(base_contract)["sha256"] == EXPECTED_BASE_CONTRACT and base_contract in chain_resolved,
            "legacy R16 contract absent from validated refinement lineage")
    for endpoint in ("r16-tf0-tbr10014", "r16-tf0-tbr10070"):
        endpoint_path = (Path("/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/worker/psyex-r16-tf0-budget/runs/e05-1440") / endpoint / "command.json").resolve()
        require(endpoint_path in chain_resolved, "legacy bracket endpoint absent: "+endpoint)
    outer_id, outer = validate_outer(args.outer_receipt, args.outer_receipt_sha, receipt, encoder_id)
    require(receipt["input"]["sha256"] == EXPECTED_INPUT, "wrong fixture")
    require(receipt["contract"]["sha256"] == EXPECTED_CONTRACT, "wrong contract")
    require(receipt["r8_command_receipt"]["sha256"] == EXPECTED_R8_RECEIPT, "wrong R8 comparator")
    require_live_record(receipt["r8_command_receipt"], "R8 receipt")
    require(receipt.get("identity_before") == receipt.get("identity_after"), "R16 identity drift")
    for path, digest in receipt["identity_before"].items():
        require(Path(path).is_file() and ident(path)["sha256"] == digest, "stale R16 identity: "+path)
    require(receipt.get("within_source_ceiling") is True and
            receipt.get("matched_rate_comparable") is True, "selected receipt rate flags")
    source_rate = float(receipt["source_mbps"])
    actual_rate = float(receipt["actual_mbps"])
    require(source_rate == EXPECTED_SOURCE_RATE and .99 * source_rate <= actual_rate <= source_rate,
            "selected source-rate interval")
    require(.99 * EXPECTED_R8_RATE <= actual_rate <= 1.01 * EXPECTED_R8_RATE,
            "selected rate is not within 1% of R8")
    packet_id = require_live_record(receipt["packet_window"], "packet window")
    packet = strict_json(packet_id["path"])
    require(float(packet["source_mbps"]) == source_rate and float(packet["actual_mbps"]) == actual_rate and
            packet["within_source_ceiling"] is True and packet["matched_rate_comparable"] is True,
            "packet-window rate disagreement")
    require(packet["mkv"]["selected_indices"] == [96, 336] and
            float(packet["mkv"]["actual_mbps"]) == actual_rate, "packet-window scored interval")
    ivf = Path(receipt["ivf_output"]["path"]).resolve()
    input_id = ident(ivf)
    require(input_id == receipt["ivf_output"], "live IVF differs from receipt")
    ffmpeg_id = ident("/usr/bin/ffmpeg")
    require(ffmpeg_id["sha256"] == EXPECTED_FFMPEG, "wrong FFmpeg")
    raw_ivf = ivf.read_bytes()
    packets = ivf_packets(raw_ivf)
    framed = [obus(packet["data"]) for packet in packets]

    args.output.mkdir(parents=True)
    log_path = args.output / "trace_headers.log"
    argv = ["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "trace", "-i", str(ivf),
            "-map", "0:v:0", "-c", "copy", "-bsf:v", "trace_headers", "-f", "null", "-"]
    start_wall = time.time()
    start = time.monotonic()
    with log_path.open("wb") as log:
        proc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
    command = {"argv": argv, "returncode": proc.returncode, "started_unix": start_wall,
               "elapsed_seconds": time.monotonic()-start, "input": input_id,
               "encode_receipt": receipt_id, "ffmpeg": ffmpeg_id, "log": ident(log_path)}
    (args.output / "command.json").write_text(json.dumps(command, indent=2)+"\n")
    require(proc.returncode == 0 and ident(ivf) == input_id and ident(args.receipt) == receipt_id,
            "trace execution/input mutation")
    traced_packets, events, order_bits = parse_headers(log_path.read_text(errors="strict"), packets, framed)
    displays, refresh_history, implicit_key_refreshes, coded_count = lifecycle(packets, events)

    display = displays[216]
    require(display["packet_pts"] == 216, "display216 PTS")
    target = next(e for e in events if e.get("coded_ordinal") == display["coded_ordinal"])
    display_event = next(e for e in events if e["event_index"] == display["event_index"])
    require(target["show_existing_frame"] == 0, "resolved target is not coded")
    if display["kind"] == "show_existing":
        require(target["show_frame"] == 0, "show-existing target not hidden")
        slot = display_event["frame_to_show_map_idx"]
        require(slot in target["refreshed_slots"], "target did not refresh shown slot")
        intervening = [r for r in refresh_history if r["slot"] == slot and
                       target["event_index"] < r["event_index"] < display_event["event_index"]]
        require(not intervening, "shown slot overwritten before display")
    else:
        require(display["kind"] == "shown_coded" and target["event_index"] == display_event["event_index"] and
                target["show_frame"] == 1, "shown-coded link")
        slot = None
        intervening = []

    # The experiment requires an exact frame-bearing OBU. Fail rather than call
    # a bare type-3 frame header (without following tile groups) a coded frame.
    require(target["obu"]["type"] == 6, "target uses split frame-header/tile-group OBUs; unit framing needed")
    target_key = {key: target.get(key) for key in ("event_index", "coded_ordinal", "packet_index",
                  "packet_pts", "packet_event_index", "frame_type", "show_frame", "showable_frame",
                  "order_hint", "refresh_frame_flags_normalized", "refreshed_slots")}
    target_key["obu"] = target["obu"]
    target_obu_path = args.output / "target-frame.obu"
    obu_start = target["obu"]["file_offset"]
    target_obu_path.write_bytes(raw_ivf[obu_start:obu_start + target["obu"]["size"]])
    target_obu_id = ident(target_obu_path)
    require(target_obu_id["sha256"] == target["obu"]["sha256"] and
            target_obu_id["size"] == target["obu"]["size"], "target OBU extraction")

    packet_event_counts = collections.Counter(event["packet_index"] for event in events)
    obu_types = collections.Counter(obu["type"] for parts in framed for obu in parts)
    nonshow = [event for event in events if event["show_existing_frame"] == 0]
    shown_existing = [event for event in events if event["show_existing_frame"] == 1]
    summary = {
        "ivf_packets": len(packets), "display_actions": len(displays), "frame_headers": len(events),
        "coded_non_show_existing": len(nonshow), "show_existing": len(shown_existing),
        "hidden_coded": sum(event["show_frame"] == 0 for event in nonshow),
        "shown_coded": sum(event["show_frame"] == 1 for event in nonshow),
        "packets_with_multiple_frame_headers": sum(value > 1 for value in packet_event_counts.values()),
        "max_frame_headers_per_packet": max(packet_event_counts.values()),
        "order_hint_bits_minus_1_values": sorted(set(order_bits)),
        "implicit_shown_KEY_refresh_events": implicit_key_refreshes,
        "obu_type_counts": {str(key): value for key, value in sorted(obu_types.items())},
        "all_packets_exactly_one_display_action": True,
    }
    result = {
        "status": "bound",
        "scope": "R16 midpoint-refinement bitstream syntax/framing and dynamic reference-slot lifecycle; no old event/order/source-order assumption.",
        "encode_receipt": receipt_id, "outer_execution": outer_id,
        "encoder_script": encoder_id, "calibration_chain_paths": [str(Path(p).resolve()) for p in chain_paths],
        "calibration_chain": [ident(p) for p in chain_paths],
        "input_ivf": input_id, "ffmpeg": ffmpeg_id,
        "command": ident(args.output/"command.json"), "trace_log": ident(log_path),
        "script": ident(__file__),
        "binding_command": {"argv": sys.argv, "python": ident(sys.executable), "python_version": sys.version},
        "framing_helper_origin": ident(FRAMING_ORIGIN), "summary": summary,
        "target_coded_event": target_key, "target_frame_obu": target_obu_id,
        "display_216_event": {"display_action": display, "header": display_event},
        "target_to_display_link": {"kind": display["kind"], "refreshed_slot": slot,
                                   "intervening_refreshes_same_slot": intervening,
                                   "coded_event_index": target["event_index"],
                                   "display_event_index": display_event["event_index"]},
        "limits": [
            "Header lifecycle identifies the coded event feeding decoded display index 216; decoder/sample admission must separately bind that display to original fixture frame216.",
            "Target OBU is exact only because this run uses an OBU_FRAME; split OBU_FRAME_HEADER plus TILE_GROUP input is rejected.",
            "No R8/R9/R10 event ordinal, order hint, hidden-frame status, or source-picture-order mapping is assumed."
        ],
    }
    (args.output / "events.json").write_text(json.dumps({"packets": traced_packets, "events": events,
                                                          "displays": displays}, indent=2)+"\n")
    result["events"] = ident(args.output/"events.json")
    (args.output / "result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "summary": summary,
                      "target_coded_event": target_key, "display_216_event": display}, indent=2))


if __name__ == "__main__":
    main()
