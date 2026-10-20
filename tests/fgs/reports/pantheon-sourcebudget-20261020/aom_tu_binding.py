#!/usr/bin/env python3
"""Independently bind the hidden source216 coded OBU to decoded display216."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

ROOT = Path(os.environ.get("PANTHEON_SOURCEBUDGET_ROOT",
                          "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020"))
IVF_SHA = "ab233b3874583fbbb75f9bd9e91a63ff19efeae9a57e7639ca4fc499c7662052"


def identity(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, "size": path.stat().st_size}


def ivf_packets(data):
    assert len(data) >= 32 and data[:4] == b"DKIF"
    version, header_size = struct.unpack_from("<HH", data, 4)
    fourcc, width, height, rate, scale, count, unused = struct.unpack_from(
        "<4sHHIIII", data, 8)
    assert (version, header_size, fourcc, width, height, rate, scale, count, unused) == (
        0, 32, b"AV01", 1920, 1080, 24, 1, 336, 0)
    packets = []
    offset = 32
    while offset < len(data):
        assert offset + 12 <= len(data)
        size, pts = struct.unpack_from("<IQ", data, offset)
        start = offset + 12
        assert size > 0 and start + size <= len(data)
        assert pts == len(packets)
        packets.append({"index": len(packets), "pts": pts, "file_offset": start,
                        "data": data[start:start + size]})
        offset = start + size
    assert offset == len(data) and len(packets) == 336
    return packets


def obus(data):
    out = []
    pos = 0
    while pos < len(data):
        start = pos
        header = data[pos]
        pos += 1
        assert header & 0x80 == 0 and header & 1 == 0 and header & 2
        kind = (header >> 3) & 15
        assert kind in (1, 2, 3, 4, 5, 6, 7, 8, 15)
        if header & 4:
            assert pos < len(data) and data[pos] & 7 == 0
            pos += 1
        size = 0
        for i in range(8):
            assert pos < len(data)
            byte = data[pos]
            pos += 1
            size |= (byte & 127) << (7 * i)
            if not byte & 128:
                break
        else:
            raise AssertionError("unterminated OBU size")
        assert size < 2 ** 32 and pos + size <= len(data)
        pos += size
        out.append({"type": kind, "start": start, "end": pos, "data": data[start:pos]})
    assert pos == len(data)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run = ROOT / "worker/runs/e05-1440/aom-psnr-1x2"
    paths = {
        "ivf": run / "out.ivf", "decoder_validation": run / "decoder-validation.json",
        "r3_command": run / "command.json", "mkv": run / "out.mkv",
        "decoded_raw": run / "dav1d-decoded.yuv", "frozen_controls": run / "controls.json",
        "parsed_events": ROOT / "parent/source-neutralize/parser-control/parsed-events.json",
        "parser_command": ROOT / "parent/source-neutralize/parser-control/command.json",
        "parser": Path(__file__).parent / "parse_aom_headers.py",
        "input_planes": ROOT / "parent/source-boundary/input-planes.json",
        "source_raw": ROOT / "fixtures/e05-1440/source.yuv",
    }
    bound = {key: identity(p) for key, p in paths.items()}
    assert bound["ivf"]["sha256"] == IVF_SHA
    assert bound["parsed_events"]["sha256"] == "34958123add027a4bd649c6212d0cb9184bf31117b5c19dc117730d2ed9ff0d0"
    assert bound["parser"]["sha256"] == "6adfc1947424e3e7f607e144b1cd31a5670022fba3544999620ed059abdfa5d2"
    assert bound["decoder_validation"]["sha256"] == "f2238e801f6fdd72f7b425870669fe4c1ee9bf789d15332e328552bc7fa09e85"
    assert bound["input_planes"]["sha256"] == "d4e7e47ac1c042bd3bbfcba559b55964e8389999cddd6c1b330c9a9c706146de"
    assert bound["source_raw"]["sha256"] == "ca3356ad056ee70ddb483acc2a4a0dac8ccd98d70b9096d8b4786d49a1f88fd3"
    decoder = json.loads(paths["decoder_validation"].read_text())
    assert decoder["all336_allplanes_libaom_dav1d_NVDEC_exact"]
    assert decoder["decoded_raw"]["sha256"] == bound["decoded_raw"]["sha256"]
    r3 = json.loads(paths["r3_command"].read_text())
    assert r3["status"] == "encoded" and r3["returncode"] == 0
    assert r3["ivf_sha256"] == bound["ivf"]["sha256"]
    assert r3["mkv_sha256"] == bound["mkv"]["sha256"] == decoder["output"]["sha256"]
    parse_command = json.loads(paths["parser_command"].read_text())
    parsed = json.loads(paths["parsed_events"].read_text())
    assert parse_command["returncode"] == 0
    assert parse_command["input"]["sha256"] == bound["ivf"]["sha256"]
    assert identity(parse_command["input"]["path"]) == parse_command["input"]
    assert identity(parse_command["run"]["path"]) == parse_command["run"]
    assert all(parsed["command_receipt"][key] == parse_command["run"][key]
               for key in ("path", "sha256"))
    assert parsed["command_receipt"]["lag_in_frames"] == 25
    assert identity(parse_command["log"]["path"]) == parsed["input_log"] == parse_command["log"]
    packets = ivf_packets(paths["ivf"].read_bytes())
    framed = [obus(p["data"]) for p in packets]
    events = parsed["events"]
    for p, parts in zip(packets, framed):
        observed = [e for e in events if e["packet_index"] == p["index"]]
        assert len(observed) == sum(b["type"] in (3, 6) for b in parts)
    coded = [e for e in events if e.get("expected_source_index") == 216
             and not e["show_existing_frame"]]
    assert len(coded) == 1
    event = coded[0]
    assert event["hook_match_key"] == [216, 1, 0, 1, 108, 128]
    assert event["packet_index"] == 215 and event["packet_event_index"] == 3
    packet = packets[event["packet_index"]]
    parts = framed[event["packet_index"]]
    assert [b["type"] for b in parts] == [2, 6, 6, 6, 6, 6]
    assert [len(b["data"]) for b in parts] == [2, 118798, 53047, 40859, 28408, 28037]
    target = [b for b in parts if b["type"] in (3, 6)][event["packet_event_index"]]
    assert (target["start"], target["end"]) == (212706, 241114)
    assert hashlib.sha256(target["data"]).hexdigest() == "18390f9b9ca737001b9a7171609d34104ef790710a821e5345a0b981a271a6b2"
    display = [e for e in events if e["packet_index"] == 216]
    assert len(display) == 1 and display[0]["show_existing_frame"] == 1
    assert display[0]["frame_to_show_map_idx"] == 7
    assert display[0]["expected_source_index"] == 216
    frame_bytes = 1920 * 1080 * 3
    with paths["decoded_raw"].open("rb") as stream:
        stream.seek(216 * frame_bytes)
        decoded = stream.read(frame_bytes)
    assert len(decoded) == frame_bytes
    assert hashlib.md5(decoded).hexdigest() == decoder["hashes"][216] == "e90f32ebe95bdd91b2f2e928ef6995e3"
    decoded_y = decoded[:1920 * 1080 * 2]
    assert hashlib.sha256(decoded_y).hexdigest() == "448a6aaa58affff9bed9bb66a81948b44d97caea7019f59878ec3afad58a7956"
    with paths["source_raw"].open("rb") as stream:
        stream.seek(120 * frame_bytes)
        original = stream.read(frame_bytes)
    assert len(original) == frame_bytes
    assert hashlib.md5(original).hexdigest() == "94fa8bde346a2a52d40b26f8183afea5"
    planes = json.loads(paths["input_planes"].read_text())
    assert planes["source_unchanged"] and planes["all336_whole_md5_equal_historical"]
    assert (planes["width"], planes["height"], planes["bit_depth"]) == (1920, 1080, 10)
    target_source = [r for r in planes["frames"] if r["source_index"] == 216]
    assert len(target_source) == 1
    target_source = target_source[0]
    assert target_source["whole_md5"] == hashlib.md5(original).hexdigest()
    cuts = (0, 1920 * 1080 * 2, 1920 * 1080 * 5 // 2, frame_bytes)
    assert target_source["plane_md5"] == [
        hashlib.md5(original[a:b]).hexdigest() for a, b in zip(cuts, cuts[1:])]
    args.output.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for name, data in (("target.obu", target["data"]), ("decoded_y.u16", decoded_y),
                       ("original.yuv", original)):
        path = args.output / name
        path.write_bytes(data)
        artifacts[name] = identity(path)
    assert all(identity(paths[k]) == v for k, v in bound.items())
    receipt = {
        "status": "bound", "scope": "Exact installed R3 stream only; reuse requires IVF identity.",
        "script": identity(__file__), "inputs": bound, "outputs": artifacts,
        "coded_event": event, "display_event": display[0],
        "target_packet_file_offset": packet["file_offset"],
        "target_obu_packet_offsets": [target["start"], target["end"]],
        "target_obu_md5": hashlib.md5(target["data"]).hexdigest(),
        "decoded_y_md5": hashlib.md5(decoded_y).hexdigest(),
        "target_source": target_source,
        "all336_ivf_and_obu_framing_exact": True,
    }
    (args.output / "binding.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in ("status", "coded_event",
                                                   "target_obu_md5", "decoded_y_md5")}, indent=2))


if __name__ == "__main__":
    main()
