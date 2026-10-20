#!/usr/bin/env python3
"""Independently map the new cap stream's displayed frames to coded AV1 events."""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HELPER = ROOT / "reviewer/round16-refine-binding/bind_refine_headers.py"
HELPER_SHA = "5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc"
PROVENANCE_SHA = "b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f"
READER_SHA = "08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8"
FFMPEG_SHA = "ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41"


def ident(path):
    import hashlib
    path = Path(path).resolve()
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(path=str(path), sha256=digest, size=path.stat().st_size)


def load(path, digest, name):
    assert ident(path)["sha256"] == digest
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cap", type=Path)
    ap.add_argument("cap_sha")
    ap.add_argument("outer", type=Path)
    ap.add_argument("outer_sha")
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(status="preflight", script=ident(__file__), scope="Dynamic bitstream/reference-slot mapping; no quality or source-sample claim.")
    def save():
        (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    save()
    try:
        assert not any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT"))
        assert ident(HERE / "read_cap_trace.py")["sha256"] == READER_SHA
        prov = load(HERE / "provenance.py", PROVENANCE_SHA, "r18_binding_provenance")
        runner = load(prov.RUN, prov.RUN_SHA, "r18_binding_runner")
        helper = load(HELPER, HELPER_SHA, "r18_header_functions")
        cap = runner.read_receipt(args.cap, args.cap_sha, "cap")
        assert cap["pins"]["sha256"] == prov.PINS_SHA
        assert cap["pins"]["path"] == str(prov.BUILD / "completed-build-pins.json")
        assert ident(args.outer)["sha256"] == args.outer_sha
        invocation = ["cap", cap["tag"], cap["pins"]["path"], cap["pins"]["sha256"],
                      "--control", cap["control"]["path"], "--control-sha", cap["control"]["sha256"],
                      "--parent", cap["parent"]["path"], "--parent-sha", cap["parent"]["sha256"]]
        prov.outer(ident(args.outer), prov.RUN, prov.RUN_SHA, invocation)
        ivf = Path(cap["outputs"]["out.ivf"]["path"])
        assert ident(ivf) == cap["outputs"]["out.ivf"]
        assert ident("/usr/bin/ffmpeg")["sha256"] == FFMPEG_SHA
        paths = [Path(__file__), HERE / "provenance.py", HERE / "read_cap_trace.py",
                 HELPER, prov.RUN, args.cap, args.outer, ivf, Path("/usr/bin/ffmpeg"),
                 Path(cap["pins"]["path"])]
        before = [ident(p) for p in paths]
        raw_ivf = ivf.read_bytes()
        packets = helper.ivf_packets(raw_ivf)
        framed = [helper.obus(p["data"]) for p in packets]
        log_path = args.out / "trace_headers.log"
        argv = ["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "trace", "-i", str(ivf),
                "-map", "0:v:0", "-c", "copy", "-bsf:v", "trace_headers", "-f", "null", "-"]
        result.update(status="running", argv=argv, inputs_before=before)
        save()
        started = time.monotonic()
        with log_path.open("xb") as log:
            process = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
        command = dict(argv=argv, returncode=process.returncode, seconds=time.monotonic()-started,
                       input=ident(ivf), encode_receipt=ident(args.cap), ffmpeg=ident("/usr/bin/ffmpeg"),
                       log=ident(log_path))
        (args.out / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        assert process.returncode == 0
        traced, events, order_bits = helper.parse_headers(log_path.read_text(), packets, framed)
        displays, history, implicit, coded_count = helper.lifecycle(packets, events)
        coded = {event["coded_ordinal"]: event for event in events if not event["show_existing_frame"]}
        assert len(coded) == coded_count == 336
        assert {d["coded_ordinal"] for d in displays} == set(coded), "coded/display mapping is not bijective"
        display = displays[216]
        target = coded[display["coded_ordinal"]]
        display_event = events[display["event_index"]]
        assert target["obu"]["type"] == 6, "split header/tile-group target needs explicit framing"
        slot = None
        if display["kind"] == "show_existing":
            slot = display_event["frame_to_show_map_idx"]
            assert not target["show_frame"] and slot in target["refreshed_slots"]
            assert not any(row["slot"] == slot and target["event_index"] < row["event_index"] < display_event["event_index"] for row in history)
        else:
            assert display["kind"] == "shown_coded" and target["event_index"] == display_event["event_index"]
        start, size = target["obu"]["file_offset"], target["obu"]["size"]
        target_path = args.out / "target-frame.obu"
        target_path.write_bytes(raw_ivf[start:start+size])
        assert ident(target_path)["sha256"] == target["obu"]["sha256"] and ident(target_path)["size"] == size
        target_key = {key: target.get(key) for key in ("event_index", "coded_ordinal", "packet_index",
                      "packet_pts", "packet_event_index", "frame_type", "show_frame", "showable_frame",
                      "order_hint", "refresh_frame_flags_normalized", "refreshed_slots", "obu")}
        counts = Counter(e["packet_index"] for e in events)
        nonshow = list(coded.values())
        summary = dict(ivf_packets=len(packets), display_actions=len(displays), frame_headers=len(events),
                       coded_non_show_existing=len(coded), show_existing=len(events)-len(coded),
                       hidden_coded=sum(not e["show_frame"] for e in nonshow),
                       shown_coded=sum(e["show_frame"] for e in nonshow),
                       packets_with_multiple_frame_headers=sum(n > 1 for n in counts.values()),
                       max_frame_headers_per_packet=max(counts.values()),
                       order_hint_bits_minus_1_values=sorted(set(order_bits)),
                       implicit_shown_KEY_refresh_events=implicit,
                       all_packets_exactly_one_display_action=True)
        (args.out / "events.json").write_text(json.dumps(dict(packets=traced, events=events, displays=displays), indent=2) + "\n")
        after = [ident(p) for p in paths]
        assert before == after
        result.update(status="bound", inputs_after=after, helper=ident(HELPER),
                      encode_receipt=ident(args.cap), outer_execution=ident(args.outer),
                      input_ivf=ident(ivf), ffmpeg=ident("/usr/bin/ffmpeg"),
                      command=ident(args.out / "command.json"), trace_log=ident(log_path),
                      events=ident(args.out / "events.json"), target_frame_obu=ident(target_path),
                      target_coded_event=target_key, summary=summary,
                      display_216_event=dict(display_action=display, header=display_event),
                      target_to_display_link=dict(kind=display["kind"], refreshed_slot=slot,
                                                  coded_event_index=target["event_index"],
                                                  display_event_index=display_event["event_index"]),
                      limits=["No old coded ordinal, packet, order hint or reference slot is assumed.",
                              "Encoder all-picture trace identities and decoder/sample agreement are separate admission joins."])
        save()
        print(json.dumps(dict(status="bound", summary=summary, target=target_key, result=ident(args.out / "result.json"))))
    except BaseException as error:
        result.update(status="failed", error=repr(error))
        save()
        raise


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("optimized Python prohibited")
    main()
