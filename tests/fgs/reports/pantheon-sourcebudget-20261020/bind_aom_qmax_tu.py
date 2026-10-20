#!/usr/bin/env python3
"""Fresh coded/display binding and frame-level q bounds for an R7 stream."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from aom_tu_binding import ROOT, identity, ivf_packets, obus
from validate_aom_qmax_decoders import parse_framemd5


def bound(record):
    observed = identity(record["path"])
    assert observed == {**record, "path": str(Path(record["path"]).resolve())}, record
    return Path(record["path"])


parser = argparse.ArgumentParser()
parser.add_argument("off_receipt", type=Path)
parser.add_argument("parsed_events", type=Path)
parser.add_argument("decoder_validation", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
assert not args.output.exists()
off = json.loads(args.off_receipt.read_text())
assert off["status"] == "encoded" and off["arm"] == "off" and off["returncode"] == 0
assert off["exact_installed_ivf"]
installed_path = bound(off["source_command"])
installed = json.loads(installed_path.read_text())
assert installed["status"] == "diagnostic_encoded" and installed["returncode"] == 0
ivf = bound(off["output"])
installed_ivf = installed_path.parent / "out.ivf"
assert identity(installed_ivf)["sha256"] == installed["ivf_sha256"] == off["output"]["sha256"]
parsed = json.loads(args.parsed_events.read_text())
parse_dir = args.parsed_events.parent
parse_receipt = json.loads((parse_dir / "receipt.json").read_text())
parse_command = json.loads((parse_dir / "command.json").read_text())
assert parse_receipt["status"] == "pass" and parse_command["returncode"] == 0
for record in parse_receipt["files"].values():
    bound(record)
assert parse_command["run"] == identity(args.off_receipt)
assert parse_command["input"] == off["output"] == parse_receipt["input_ivf"]
assert parsed["command_receipt"]["sha256"] == identity(args.off_receipt)["sha256"]
assert parsed["command_receipt"]["lag_in_frames"] == 25
log_path = bound(parsed["input_log"])
assert parse_command["log"] == parsed["input_log"]
parser_script = Path(__file__).with_name("parse_aom_headers.py")
assert identity(parser_script)["sha256"] == "6adfc1947424e3e7f607e144b1cd31a5670022fba3544999620ed059abdfa5d2"
assert parse_receipt["files"]["parse_trace_headers.py"]["sha256"] == identity(parser_script)["sha256"]
decoder = json.loads(args.decoder_validation.read_text())
assert decoder["status"] == "admitted"
assert decoder["all336_allplanes_libaom_dav1d_NVDEC_exact"]
assert decoder["run_receipt"] == identity(installed_path)
assert decoder["input_ivf"] == identity(installed_ivf)
assert bound(decoder["output"]) and decoder["output"]["sha256"] == installed["mkv_sha256"]
decoder_script = Path(__file__).with_name("validate_aom_qmax_decoders.py")
assert identity(decoder_script)["sha256"] == "bb2e0256100ad70e02753c0fc19c0cc62f2ed189f08d50335b3ab421983b5ca9"
assert decoder["source_script"] == identity(decoder_script)
assert bound(decoder["script"]) and decoder["script"]["sha256"] == decoder["source_script"]["sha256"]
assert decoder["identity_before"] == decoder["identity_after"]
tool_identity = decoder["identity_before"]
for name in ("ffmpeg", "ffprobe"):
    bound(tool_identity[name]["file"])
    assert tool_identity[name]["file"]["sha256"] == installed["expected_identity"][name + "_sha256"]
    assert tool_identity[name]["version"]["returncode"] == 0
for lib in tool_identity["libraries"].values():
    bound(lib["file"])
bound(tool_identity["gpu"]["file"])
assert tool_identity["gpu"]["driver"]["returncode"] == 0
assert tool_identity["decoders"]["returncode"] == 0
assert bound(decoder["input_probe"])
assert [r["name"] for r in decoder["commands"]] == ["dav1d", "libaom", "nvdec"]
for row in decoder["commands"]:
    assert row["returncode"] == 0
    assert row["argv"] == decoder["planned_commands"][row["name"]]
    assert json.loads(bound(row["receipt"]).read_text()) == {
        k: v for k, v in row.items() if k != "receipt"}
    bound(row["output"])
    bound(row["log"])
    assert row["argv"][-1] == row["output"]["path"]
    if row["name"] == "dav1d":
        assert row["output"] == decoder["decoded_raw"]
    else:
        assert parse_framemd5(row["output"]["path"]) == decoder["hashes"]
decoded_raw = bound(decoder["decoded_raw"])
assert len(decoder["hashes"]) == 336
packets = ivf_packets(ivf.read_bytes())
framed = [obus(p["data"]) for p in packets]
events = parsed["events"]
assert parsed["summary"]["all_packets_exactly_one_display_action"]
for p, parts in zip(packets, framed):
    actual = [e for e in events if e["packet_index"] == p["index"]]
    assert len(actual) == sum(o["type"] in (3, 6) for o in parts)
assert {e["expected_source_index"] for e in events} == set(range(336))
lines = log_path.read_text().splitlines()
fields = ("base_q_idx", "delta_q_present", "delta_q_res", "using_qmatrix",
          "segmentation_enabled", "segmentation_update_map", "segmentation_update_data")
pattern = re.compile(r"\]\s+\d+\s+([A-Za-z0-9_]+)\s+[01]+\s+=\s+(-?\d+)\s*$")
quant_headers = []
for i, event in enumerate(events):
    start = event["header_log_line"] - 1
    end = events[i + 1]["header_log_line"] - 1 if i + 1 < len(events) else len(lines)
    assert lines[start].endswith("Frame Header")
    observed = {}
    for line in lines[start + 1:end]:
        match = pattern.search(line)
        if match and match[1] in fields:
            assert match[1] not in observed, (event, match[1])
            observed[match[1]] = int(match[2])
    if not event["show_existing_frame"]:
        assert "base_q_idx" in observed and 0 <= observed["base_q_idx"] <= 32
        assert observed.get("using_qmatrix") == 0
        if observed["base_q_idx"] > 0:
            assert observed.get("delta_q_present") in (0, 1)
        if observed.get("delta_q_present"):
            assert observed.get("delta_q_res") in (0, 1, 2, 3)
        quant_headers.append({"event": event, "fields": observed})
    else:
        assert not observed, (event, observed)
coded = [e for e in events if e["expected_source_index"] == 216
         and not e["show_existing_frame"]]
assert len(coded) == 1, "ambiguous target coded event; investigate instead of choosing"
event = coded[0]
target = [o for o in framed[event["packet_index"]] if o["type"] in (3, 6)][event["packet_event_index"]]
assert target["type"] == 6, "separate frame-header/tile-group target needs explicit binding"
display = [e for e in events if e["packet_index"] == 216
           and (e["show_existing_frame"] or e.get("show_frame"))]
assert len(display) == 1 and display[0]["expected_source_index"] == 216
frame_bytes = 1920 * 1080 * 3
assert decoded_raw.stat().st_size == 336 * frame_bytes
with decoded_raw.open("rb") as stream:
    stream.seek(216 * frame_bytes)
    decoded = stream.read(frame_bytes)
assert len(decoded) == frame_bytes and hashlib.md5(decoded).hexdigest() == decoder["hashes"][216]
baseline_binding_path = ROOT / "parent/tu-observation/binding-v2/binding.json"
baseline_binding = json.loads(baseline_binding_path.read_text())
assert identity(baseline_binding_path)["sha256"] == "ffcf7f4d7640f33aa9f3b0bcf3fba26b00e636a2feb2714107bb10c2b48aa612"
original_path = bound(baseline_binding["outputs"]["original.yuv"])
original = original_path.read_bytes()
assert len(original) == frame_bytes
assert hashlib.md5(original).hexdigest() == "94fa8bde346a2a52d40b26f8183afea5"
assert installed["input"]["sha256"] == "232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4"
assert identity(installed["input"]["path"])["sha256"] == installed["input"]["sha256"]
inputs = {
    "ivf": identity(installed_ivf), "private_off_ivf": identity(ivf),
    "installed_command": identity(installed_path),
    "private_off_command": identity(args.off_receipt),
    "parsed_events": identity(args.parsed_events),
    "parser_command": identity(parse_dir / "command.json"),
    "parser_receipt": identity(parse_dir / "receipt.json"), "parser": identity(parser_script),
    "header_log": identity(log_path), "decoder_validation": identity(args.decoder_validation),
    "decoder_validator": identity(decoder_script),
    "decoded_raw": identity(decoded_raw), "mkv": decoder["output"],
    "baseline_binding": identity(baseline_binding_path),
    "source_original": identity(original_path),
    "frozen_controls": baseline_binding["inputs"]["frozen_controls"],
}
assert all(bound(v) for v in inputs.values())
args.output.mkdir(parents=True)
outputs = {}
for name, contents in (("target.obu", target["data"]),
                       ("decoded_y.u16", decoded[:1920 * 1080 * 2]),
                       ("original.yuv", original)):
    path = args.output / name
    path.write_bytes(contents)
    outputs[name] = identity(path)
result = {
    "status": "bound", "script": identity(__file__), "inputs": inputs, "outputs": outputs,
    "scope": "Fresh R7 stream; coded/display locations derived independently, never inherited from R3.",
    "coded_event": event, "display_event": display[0], "coded_quant_headers": quant_headers,
    "all_coded_base_qindex_at_most32": True,
    "all336_ivf_and_obu_framing_exact": True,
    "target_packet_file_offset": packets[event["packet_index"]]["file_offset"],
    "target_obu_packet_offsets": [target["start"], target["end"]],
    "target_obu_md5": hashlib.md5(target["data"]).hexdigest(),
    "decoded_y_md5": hashlib.md5(decoded[:1920 * 1080 * 2]).hexdigest(),
    "target_source": baseline_binding["target_source"],
}
assert all(bound(v) for v in inputs.values())
(args.output / "binding.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("status", "coded_event", "display_event")}, indent=2))
