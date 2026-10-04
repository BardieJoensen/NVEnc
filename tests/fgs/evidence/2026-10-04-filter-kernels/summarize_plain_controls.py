#!/usr/bin/env python3
"""Offline receipt audit for the explicitly selected final plain controls."""
import hashlib
import json
from pathlib import Path
import re
import statistics
import aggregate_identity as agg
import repeat_identity as identity

TASK = Path(__file__).resolve().parent
REPORTS = TASK / "reports"


def read(name):
    path = REPORTS / name
    data = path.read_bytes()
    return json.loads(data), {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def removed(argv, options):
    output, i = [], 0
    while i < len(argv):
        if argv[i] in options:
            i += 2
        else:
            output.append(argv[i]); i += 1
    return output


def main():
    requirements = json.loads((TASK / "identity-requirements.json").read_text())
    required = {c["name"]: c for c in requirements["cases"]}
    union, union_pin = read("aggregate-identity-final.json")
    names = ["kernels-kat-plain-controls-v2", "kernels-real-identity", "kernels-real-plain-retuned", "kernels-silo-plain-qvbr",
             "kernels-kat-plain-controls", "kernels-silo-plain-v2", "kernels-silo-plain-refinement"]
    docs = {name: read(name + "/report.json") for name in names}
    selected = {}
    for name, case in docs["kernels-kat-plain-controls-v2"][0]["cases"].items():
        selected[name] = ("kernels-kat-plain-controls-v2", [(i, r) for i, r in enumerate(case["runs"]) if r.get("matched")])
    for name in ("losttapes", "taxi_hdr"):
        selected[name] = ("kernels-real-identity", [(i, r) for i, r in enumerate(docs["kernels-real-identity"][0]["runs"]) if r.get("input") == name and r.get("stage") == "plain" and r.get("complete")])
    for name in ("amphibia", "gentlemen"):
        selected[name] = ("kernels-real-plain-retuned", [(i, r) for i, r in enumerate(docs["kernels-real-plain-retuned"][0]["cases"][name]["runs"]) if r.get("matched")])
    selected["silo_partial"] = ("kernels-silo-plain-qvbr", [(i, r) for i, r in enumerate(docs["kernels-silo-plain-qvbr"][0]["runs"]) if r.get("matched")])
    assert set(selected) == set(required)
    result = {"complete": False, "all_controls_match_every_known_fgs_rate": False, "relative_tolerance": 0.03,
              "aggregate_identity_receipt": {**union_pin, "status": union["status"], "identity_pass": union["identity_pass"]},
              "source_reports": {name: pin for name, (_, pin) in docs.items()}, "cases": {}, "excluded_attempts": [],
              "note": "This audits plain-control bitrate matching only, not grain quality or identity qualification. Every admitted FGS state/rate in the specified aggregate is included. Source media is not reopened; original source/binary pins are retained. No new encodes or decodes are run."}
    accepted_directories = set()
    for name, (report_name, controls) in selected.items():
        assert controls, name
        doc, report_pin = docs[report_name]
        assert doc["complete"] and not doc.get("validated_only"), report_name
        case = required[name]
        fgs = [r for r in union["runs"] if r["input"] == name and r["stage"] == "av1"]
        assert fgs and all(r["source_sha256"] == case["source_sha256"] for r in fgs)
        source_rates = sorted(set(r["payload_kbps"] for r in fgs))
        reference = next(r for r in fgs if r["role"] == "reference")
        source, binary = agg.option(reference["argv"], "-i"), reference["argv"][0]
        assert doc["pins"][source]["sha256"] == case["source_sha256"]
        assert doc["pins"][binary]["sha256"] == requirements["reference"]["sha256"]
        summary = {"kind": case["kind"], "source_sha256": case["source_sha256"], "frames": case["frames"],
                   "source_pin": doc["pins"][source], "binary_pin": doc["pins"][binary], "source_report": report_pin,
                   "fgs_rates_kbps": source_rates, "fgs_range_kbps": [min(source_rates), max(source_rates)],
                   "target_median_kbps": statistics.median(r["payload_kbps"] for r in fgs),
                   "fgs_states": [dict(zip(("ivf_md5", "table_md5", "payload_kbps"), state)) for state in sorted(set((r["file_md5"], r["table_md5"], r["payload_kbps"]) for r in fgs))],
                   "controls": []}
        for index, row in controls:
            assert row["complete"] and row["returncode"] == 0
            argv = row["argv"]
            assert argv[0] == binary and agg.option(argv, "-i") == source
            assert not any("film-grain" in x or "filmgrn" in x for x in argv)
            strip = {"--cqp", "--qvbr", "--vbr", "--av1-film-grain", "--film-grain-table-out", "-o"}
            if case["kind"] == "kat":
                strip.add("--max-bitrate")
            assert removed(argv, strip) == removed(reference["argv"], strip), (name, "scope")
            output = Path(agg.option(argv, "-o"))
            parsed = identity.inspect_ivf(output, case["frames"])
            for key in ("file_md5", "packets", "width", "height", "rate", "scale", "timestamps", "packet_md5", "payload_bytes", "payload_kbps"):
                assert parsed[key] == row[key], (name, key)
            assert [row[k] for k in ("width", "height", "rate", "scale")] == [reference[k] for k in ("width", "height", "rate", "scale")]
            decoder_path = row["decode_argv"][0]
            decoder = doc["pins"].get(decoder_path, doc.get("ffmpeg"))
            assert decoder and decoder["path"] == decoder_path
            assert decoder["sha256"] == requirements["decoder_sha256"]
            assert agg.decode_scope(row["decode_argv"], output, decoder["sha256"]) == case["decode_scope"]
            directory = Path(row["directory"])
            hashfile, framefile = directory / "grain-off.md5", directory / "grain-off.framemd5"
            match = re.fullmatch(r"MD5=([0-9a-f]{32})\s*", hashfile.read_text())
            assert match and match[1] == row["decoded_pixel_md5"]
            records = [line.split(",") for line in framefile.read_text().splitlines() if line and not line.startswith("#")]
            assert len(records) == row["decoded_frames"] == case["frames"]
            assert [r[5].strip() for r in records] == row["decoded_frame_md5"]
            expected_bytes = row["width"] * row["height"] * 3 // 2 * (2 if case["output_depth"] == 10 else 1)
            assert all(int(r[4]) == expected_bytes for r in records)
            deviations = [row["payload_kbps"] / rate - 1 for rate in source_rates]
            rate_mode = next(flag for flag in ("--vbr", "--qvbr", "--cqp") if flag in argv)
            summary["controls"].append({"report_row_or_case_run_index": index, "directory": str(directory), "requested_mode": rate_mode[2:],
                "requested_value": agg.option(argv, rate_mode), "actual_payload_kbps": row["payload_kbps"],
                "relative_deviation_against_fgs_rates_in_order": deviations, "worst_absolute_relative_deviation": max(abs(x) for x in deviations),
                "matches_every_known_fgs_rate": all(abs(x) <= 0.03 for x in deviations), "argv": argv,
                "decode_argv": row["decode_argv"], "decoder_pin": decoder, "decoded_frames": row["decoded_frames"], "decoded_pixel_md5": row["decoded_pixel_md5"],
                "artifacts": {"ivf": agg.artifact(output, row["file_md5"]), "grain_off_md5": agg.artifact(hashfile), "grain_off_framemd5": agg.artifact(framefile)}})
            accepted_directories.add(str(directory))
        summary["accepted_control_range_kbps"] = [min(c["actual_payload_kbps"] for c in summary["controls"]), max(c["actual_payload_kbps"] for c in summary["controls"])]
        summary["worst_absolute_relative_deviation"] = max(c["worst_absolute_relative_deviation"] for c in summary["controls"])
        summary["matched"] = all(c["matches_every_known_fgs_rate"] for c in summary["controls"])
        result["cases"][name] = summary
    for report_name, (doc, pin) in docs.items():
        containers = doc.get("cases", {"campaign": doc})
        for name, container in containers.items():
            rows = container.get("runs", [])
            omitted = [r for r in rows if r.get("directory") not in accepted_directories and (report_name != "kernels-real-identity" or r.get("stage") == "plain")]
            if omitted or not doc["complete"]:
                result["excluded_attempts"].append({"report": report_name, "case": name, "report_complete": doc["complete"], "failure": doc.get("failure"),
                    "attempts": [{k: r[k] for k in ("input", "trial", "repeat", "directory", "complete", "matched", "returncode", "payload_kbps", "requested_vbr_kbps", "requested_qvbr", "relative_mismatch") if k in r} for r in omitted],
                    "reason": "Earlier/interrupted calibration or superseded plain attempts; never used as accepted controls."})
    result["complete"] = True
    result["all_controls_match_every_known_fgs_rate"] = all(c["matched"] for c in result["cases"].values())
    result["case_count"] = len(result["cases"])
    result["accepted_run_count"] = sum(len(c["controls"]) for c in result["cases"].values())
    result["worst_absolute_relative_deviation"] = max(c["worst_absolute_relative_deviation"] for c in result["cases"].values())
    target = REPORTS / "plain-control-summary.json"
    with target.open("x") as stream:
        json.dump(result, stream, indent=2); stream.write("\n")
    print(json.dumps({k: result[k] for k in ("complete", "all_controls_match_every_known_fgs_rate", "case_count", "accepted_run_count", "worst_absolute_relative_deviation")}, indent=2))
    for name, case in result["cases"].items():
        print(name, case["fgs_range_kbps"], case["accepted_control_range_kbps"], 100 * case["worst_absolute_relative_deviation"])


if __name__ == "__main__":
    main()
