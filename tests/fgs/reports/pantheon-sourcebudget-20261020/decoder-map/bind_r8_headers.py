#!/usr/bin/env python3
"""Bind R8 AV1 coded events to display events from syntax and IVF framing only."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

EXPECTED_IVF = "26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca"
EXPECTED_FFMPEG = "ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41"
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


# Copied only from the independently reviewed IVF/OBU framing helpers in
# aom_tu_binding.py; no source-index or libaom lag assumptions are reused.
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
    require(set(order_bits) == {6}, "unexpected order-hint width")
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
                                "coded_ordinal": event["coded_ordinal"]})
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
    parser.add_argument("ivf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "output exists")
    input_id = ident(args.ivf)
    ffmpeg_id = ident("/usr/bin/ffmpeg")
    require(input_id["sha256"] == EXPECTED_IVF, "wrong R8 IVF")
    require(ffmpeg_id["sha256"] == EXPECTED_FFMPEG, "wrong FFmpeg")
    raw_ivf = args.ivf.read_bytes()
    packets = ivf_packets(raw_ivf)
    framed = [obus(p["data"]) for p in packets]

    args.output.mkdir(parents=True)
    log_path = args.output / "trace_headers.log"
    argv = ["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "trace", "-i", str(args.ivf.resolve()),
            "-map", "0:v:0", "-c", "copy", "-bsf:v", "trace_headers", "-f", "null", "-"]
    start_wall = time.time()
    start = time.monotonic()
    with log_path.open("wb") as log:
        proc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
    end = time.monotonic()
    command = {"argv": argv, "returncode": proc.returncode, "started_unix": start_wall,
               "elapsed_seconds": end-start, "input": input_id, "ffmpeg": ffmpeg_id,
               "log": ident(log_path)}
    (args.output / "command.json").write_text(json.dumps(command, indent=2)+"\n")
    require(proc.returncode == 0 and ident(args.ivf) == input_id, "trace execution/input mutation")
    traced_packets, events, order_bits = parse_headers(log_path.read_text(errors="strict"), packets, framed)
    displays, refresh_history, implicit_key_refreshes, coded_count = lifecycle(packets, events)

    display = displays[216]
    require(display["packet_pts"] == 216, "display 216 PTS")
    require(display["kind"] == "show_existing", "display 216 is not show-existing")
    target = next(e for e in events if e.get("coded_ordinal") == display["coded_ordinal"])
    display_event = next(e for e in events if e["event_index"] == display["event_index"])
    require(target["show_frame"] == 0, "target coded event not hidden")
    require(display_event["frame_to_show_map_idx"] in target["refreshed_slots"], "target did not refresh shown slot")
    later_same_slot = [r for r in refresh_history if r["slot"] == display_event["frame_to_show_map_idx"] and
                       target["event_index"] < r["event_index"] < display_event["event_index"]]
    require(not later_same_slot, "shown slot overwritten before display")

    target_key = {k: target[k] for k in ("event_index", "coded_ordinal", "packet_index", "packet_pts",
                  "packet_event_index", "frame_type", "show_frame", "showable_frame", "order_hint",
                  "refresh_frame_flags_normalized", "refreshed_slots", "obu")}
    target_key["hidden"] = True
    target_obu_path = args.output / "target-frame.obu"
    obu_start = target["obu"]["file_offset"]
    target_obu_path.write_bytes(raw_ivf[obu_start:obu_start + target["obu"]["size"]])
    target_obu_id = ident(target_obu_path)
    require(target_obu_id["sha256"] == target["obu"]["sha256"] and
            target_obu_id["size"] == target["obu"]["size"], "target OBU extraction")
    comparison = {"derived_coded_ordinal": target["coded_ordinal"], "R9_decode_order": 210,
                  "decode_order_equal": target["coded_ordinal"] == 210,
                  "derived_order_hint": target["order_hint"], "R9_order_hint": 88,
                  "order_hint_equal": target["order_hint"] == 88}
    require(comparison["decode_order_equal"] and comparison["order_hint_equal"],
            "independent target differs from R9 metadata")

    packet_event_counts = collections.Counter(e["packet_index"] for e in events)
    obu_types = collections.Counter(o["type"] for parts in framed for o in parts)
    nonshow = [e for e in events if e["show_existing_frame"] == 0]
    show_existing = [e for e in events if e["show_existing_frame"] == 1]
    summary = {
        "ivf_packets": len(packets), "display_actions": len(displays),
        "frame_headers": len(events), "coded_non_show_existing": len(nonshow),
        "show_existing": len(show_existing),
        "hidden_coded": sum(e["show_frame"] == 0 for e in nonshow),
        "shown_coded": sum(e["show_frame"] == 1 for e in nonshow),
        "packets_with_multiple_frame_headers": sum(v > 1 for v in packet_event_counts.values()),
        "max_frame_headers_per_packet": max(packet_event_counts.values()),
        "order_hint_bits_minus_1_values": sorted(set(order_bits)),
        "implicit_shown_KEY_refresh_events": implicit_key_refreshes,
        "obu_type_counts": {str(k): v for k, v in sorted(obu_types.items())},
        "all_packets_exactly_one_display_action": True,
    }
    result = {
        "status": "bound", "scope": "R8 bitstream syntax/framing and dynamic reference-slot lifecycle only; no encoder source-order assumption.",
        "input_ivf": input_id, "ffmpeg": ffmpeg_id, "command": ident(args.output/"command.json"),
        "trace_log": ident(log_path), "script": ident(__file__),
        "binding_command": {"argv": sys.argv, "python": ident(sys.executable),
                            "python_version": sys.version},
        "framing_helper_origin": ident(FRAMING_ORIGIN), "summary": summary,
        "target_coded_event": target_key,
        "target_frame_obu": target_obu_id,
        "display_216_event": {"display_action": display, "header": display_event},
        "target_to_display_link": {"refreshed_slot": display_event["frame_to_show_map_idx"],
                                   "intervening_refreshes_same_slot": later_same_slot,
                                   "coded_event_index": target["event_index"],
                                   "display_event_index": display_event["event_index"]},
        "independent_then_R9_comparison": comparison,
        "limits": ["Header lifecycle identifies the coded event feeding display 216; it does not infer SVT input-picture order.",
                   "Target OBU is the exact frame-bearing OBU, not an assumption that an IVF packet contains one frame."],
    }
    (args.output / "events.json").write_text(json.dumps({"packets": traced_packets, "events": events,
                                                          "displays": displays}, indent=2)+"\n")
    result["events"] = ident(args.output/"events.json")
    (args.output / "result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"status": result["status"], "summary": summary,
                      "target_coded_event": target_key,
                      "display_216_event": display}, indent=2))


if __name__ == "__main__":
    main()
