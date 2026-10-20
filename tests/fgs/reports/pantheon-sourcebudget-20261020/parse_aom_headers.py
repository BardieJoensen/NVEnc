#!/usr/bin/env python3
"""Parse only AV1 frame identity/coverage fields from FFmpeg trace_headers."""
import argparse
import shutil
import subprocess
import time
import collections
import bisect
import hashlib
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('run_receipt', type=Path)
parser.add_argument('output_directory', type=Path)
args = parser.parse_args()
COMMAND = args.run_receipt.resolve()
command = json.loads(COMMAND.read_text())
assert command['status'] == 'encoded' and command['returncode'] == 0
ivf = Path(command['output']['path'])

def identity(path):
    path = Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':path.stat().st_size}

assert identity(ivf) == command['output']
ffmpeg = identity('/usr/bin/ffmpeg')
assert ffmpeg['sha256'] == 'ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41'
HERE = args.output_directory.resolve()
HERE.mkdir(parents=True, exist_ok=False)
LOG = HERE / 'trace_headers.log'
OUT = HERE / 'parsed-events.json'
shutil.copyfile(__file__, HERE / 'parse_trace_headers.py')
argv = ['/usr/bin/ffmpeg','-hide_banner','-loglevel','trace','-i',str(ivf),
        '-map','0:v:0','-c','copy','-bsf:v','trace_headers','-f','null','-']
started = time.monotonic()
with LOG.open('wb') as log:
    process = subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
execution = {'command':argv,'returncode':process.returncode,'seconds':time.monotonic()-started,
             'input':identity(ivf),'ffmpeg':ffmpeg,'log':identity(LOG),'run':identity(COMMAND)}
(HERE / 'command.json').write_text(json.dumps(execution,indent=2)+'\n')
assert process.returncode == 0 and identity(ivf) == command['output']

packet_re = re.compile(
    r"\] Packet: (?P<size>\d+) bytes(?P<key>, key frame)?, "
    r"pts (?P<pts>-?\d+), dts (?P<dts>-?\d+), duration (?P<duration>\d+)\."
)
field_re = re.compile(r"\]\s+\d+\s+(?P<name>[A-Za-z0-9_]+)\s+[01]+ = (?P<value>-?\d+)\s*$")
wanted = {
    "show_existing_frame",
    "frame_to_show_map_idx",
    "frame_type",
    "show_frame",
    "showable_frame",
    "order_hint",
    "refresh_frame_flags",
}

packets = []
events = []
current_packet = None
current_event = None
order_hint_bits_minus_1 = []

def finish_event():
    global current_event
    if current_event is None:
        return
    assert "show_existing_frame" in current_event
    if current_event["show_existing_frame"] == 0:
        for key in ("frame_type", "show_frame", "order_hint"):
            assert key in current_event, (key, current_event)
        # showable_frame is signalled only when show_frame is false.
        if current_event["show_frame"] == 1:
            current_event["showable_frame"] = None
    else:
        assert "frame_to_show_map_idx" in current_event
    events.append(current_event)
    current_event = None

for line_number, line in enumerate(LOG.read_text(errors="strict").splitlines(), 1):
    match = packet_re.search(line)
    if match:
        finish_event()
        current_packet = {
            "index": len(packets),
            "size": int(match["size"]),
            "key_packet": bool(match["key"]),
            "pts": int(match["pts"]),
            "dts": int(match["dts"]),
            "duration": int(match["duration"]),
        }
        packets.append(current_packet)
        continue
    if line.endswith(" Frame Header"):
        finish_event()
        assert current_packet is not None
        current_event = {
            "event_index": len(events),
            "packet_index": current_packet["index"],
            "packet_pts": current_packet["pts"],
            "packet_event_index": sum(e["packet_index"] == current_packet["index"] for e in events),
            "header_log_line": line_number,
        }
        continue
    if current_event is not None:
        match = field_re.search(line)
        if match and match["name"] in wanted:
            name = match["name"]
            assert name not in current_event, (name, current_event)
            current_event[name] = int(match["value"])
    elif "order_hint_bits_minus_1" in line:
        match = field_re.search(line)
        assert match and match["name"] == "order_hint_bits_minus_1"
        order_hint_bits_minus_1.append(int(match["value"]))
finish_event()

assert len(packets) == 336
assert [p["pts"] for p in packets] == list(range(336))
assert all(p["dts"] == p["pts"] and p["duration"] == 1 for p in packets)
nonshow = [e for e in events if e["show_existing_frame"] == 0]
show_existing = [e for e in events if e["show_existing_frame"] == 1]
assert set(order_hint_bits_minus_1) == {6}
order_hint_modulus = 1 << (order_hint_bits_minus_1[0] + 1)
lag_in_frames = int(command['command'][command['command'].index('-lag-in-frames')+1])
assert lag_in_frames == 25

# Key packets delimit independent order-hint epochs. A shown coded frame's
# source index is its packet PTS. A hidden frame must use a future lookahead
# source no farther than lag-in-frames and before the next key frame. For this
# stream, the modulo order hint and those bounds resolve exactly one index.
key_packet_pts = [
    e["packet_pts"]
    for e in nonshow
    if e["frame_type"] == 0 and e["show_frame"] == 1
]
assert key_packet_pts == sorted(set(key_packet_pts)) and key_packet_pts[0] == 0
for e in nonshow:
    key_pos = bisect.bisect_right(key_packet_pts, e["packet_pts"]) - 1
    gop_start = key_packet_pts[key_pos]
    next_key = key_packet_pts[key_pos + 1] if key_pos + 1 < len(key_packet_pts) else len(packets)
    if e["show_frame"]:
        candidates = [e["packet_pts"]]
        assert e["order_hint"] == ((e["packet_pts"] - gop_start) % order_hint_modulus)
    else:
        candidates = [
            gop_start + e["order_hint"] + order_hint_modulus * wrap
            for wrap in range(4)
        ]
        candidates = [
            value
            for value in candidates
            if e["packet_pts"] <= value <= min(e["packet_pts"] + lag_in_frames, next_key - 1)
        ]
    assert len(candidates) == 1, (e, candidates)
    e["expected_source_index"] = candidates[0]
    e["showable_frame_normalized"] = e["showable_frame"] if not e["show_frame"] else 0
    e["refresh_frame_flags_normalized"] = (
        255 if e["frame_type"] == 0 and e["show_frame"] else e["refresh_frame_flags"]
    )
    e["hook_match_key"] = [
        e["expected_source_index"],
        e["frame_type"],
        e["show_frame"],
        e["showable_frame_normalized"],
        e["order_hint"],
        e["refresh_frame_flags_normalized"],
    ]

# Simulate the eight AV1 reference slots. Every packet represents one display
# time: either one shown coded frame, or one show-existing header. Show-existing
# must resolve to the source index equal to that packet's PTS.
reference_slots = [None] * 8
show_existing_resolutions = []
for packet in packets:
    packet_events = [e for e in events if e["packet_index"] == packet["index"]]
    display_actions = 0
    for e in packet_events:
        if e["show_existing_frame"]:
            display_actions += 1
            resolved = reference_slots[e["frame_to_show_map_idx"]]
            assert resolved == packet["pts"], (e, resolved, reference_slots)
            e["expected_source_index"] = resolved
            show_existing_resolutions.append(resolved)
            continue
        if e["show_frame"]:
            display_actions += 1
            assert e["expected_source_index"] == packet["pts"]
        flags = e["refresh_frame_flags_normalized"]
        for slot in range(8):
            if flags & (1 << slot):
                reference_slots[slot] = e["expected_source_index"]
    assert display_actions == 1, (packet, packet_events)

hook_keys = [tuple(e["hook_match_key"]) for e in nonshow]
assert len(set(hook_keys)) == len(hook_keys)
result = {
    "scope": "Independent bitstream-header population; packet order is not encoder hook thread order.",
    "input_log": {
        "path": str(LOG),
        "sha256": hashlib.sha256(LOG.read_bytes()).hexdigest(),
        "size": LOG.stat().st_size,
    },
    "command_receipt": {
        "path": str(COMMAND),
        "sha256": hashlib.sha256(COMMAND.read_bytes()).hexdigest(),
        "lag_in_frames": lag_in_frames,
    },
    "packets": packets,
    "events": events,
    "summary": {
        "packet_count": len(packets),
        "frame_header_count": len(events),
        "coded_non_show_existing_count": len(nonshow),
        "show_existing_count": len(show_existing),
        "hidden_coded_count": sum(e["show_frame"] == 0 for e in nonshow),
        "shown_coded_count": sum(e["show_frame"] == 1 for e in nonshow),
        "key_packet_pts": key_packet_pts,
        "unique_hook_match_keys": len(set(hook_keys)),
        "show_existing_reference_resolutions": len(show_existing_resolutions),
        "all_packets_exactly_one_display_action": True,
        "nonshow_frame_types": dict(sorted(collections.Counter(e["frame_type"] for e in nonshow).items())),
        "packets_with_multiple_frame_headers": sum(
            sum(e["packet_index"] == p["index"] for e in events) > 1 for p in packets
        ),
        "max_frame_headers_per_packet": max(
            sum(e["packet_index"] == p["index"] for e in events) for p in packets
        ),
    },
}
OUT.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result["summary"], indent=2))

receipt = {'status':'pass','method':'Reviewed FFmpeg AV1 trace_headers coded-event population',
           'input_ivf':identity(ivf),'ffmpeg':ffmpeg,'summary':result['summary'],
           'files':{name:identity(HERE/name) for name in (
               'command.json','trace_headers.log','parse_trace_headers.py','parsed-events.json')}}
(HERE/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
