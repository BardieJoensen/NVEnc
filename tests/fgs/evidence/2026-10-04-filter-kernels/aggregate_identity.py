#!/usr/bin/env python3
"""Consolidate explicit identity reports against a frozen requirements manifest.

Exit 0: all required campaigns/repeats complete and observed state unions equal.
Exit 1: invalid evidence, incompatible scope, or a new candidate state.
Exit 2: incomplete evidence or a known production state not yet observed in candidate.
This is finite-sample state-set evidence, never a proof of future determinism.
The manifest supplies arms, cases, exact normalized scopes, mandatory historical
reports, completed final campaigns, decoder identity, and minimum repeat counts.
Raw diagnostics and AV1 encodes are separate observations, never paired surfaces.
No encoders, source readers, or GPU tools are invoked.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


def check(condition, message):
    if not condition:
        raise ValueError(message)


def valid_hash(value, length=32):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def artifact(path, expected_md5=None):
    path = Path(path).resolve()
    before = path.stat()
    md5, strong = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            md5.update(block); strong.update(block)
    after = path.stat()
    check((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
          (after.st_size, after.st_mtime_ns, after.st_ctime_ns), f"Artifact changed while reading: {path}")
    check(expected_md5 is None or md5.hexdigest() == expected_md5, f"Artifact MD5 mismatch: {path}")
    return {"path": str(path), "md5": md5.hexdigest(), "sha256": strong.hexdigest(), "bytes": after.st_size}


def option(argv, name):
    check(argv.count(name) == 1 and argv.index(name) + 1 < len(argv), f"Require one {name}")
    return argv[argv.index(name) + 1]


def normalize_scope(argv, arm, item):
    """Only substitute pinned paths; retain every effective option and its order."""
    check(isinstance(argv, list) and all(isinstance(x, str) for x in argv), "Invalid argv")
    prefix = arm.get("prefix", []) + [arm["binary"]]
    check(argv[:len(prefix)] == prefix, "argv binary/prefix differs from manifest")
    result = list(argv)
    result[len(prefix) - 1] = "<binary>"
    check(Path(option(argv, "-i")).resolve() == Path(item["path"]).resolve(), "argv source differs from manifest")
    result[result.index("-i") + 1] = "<source:" + item["sha256"] + ">"
    for name, placeholder in (("-o", "<output>"), ("--film-grain-table-out", "<table>")):
        option(argv, name)
        result[result.index(name) + 1] = placeholder
    return result


def decode_scope(argv, ivf, decoder_sha256):
    check(valid_hash(decoder_sha256, 64), "Missing decoder SHA256")
    check(Path(option(argv, "-i")).resolve() == Path(ivf).resolve(), "Decoder input mismatch")
    before_input = argv[:argv.index("-i")]
    check(option(before_input, "-c:v") == "libdav1d" and option(before_input, "-filmgrain") == "0", "Decoder must explicitly disable libdav1d grain before input")
    check("-xerror" in before_input and option(before_input, "-threads") == "2", "Decoder strict/two-thread settings differ")
    result = list(argv)
    result[0] = "<decoder:" + decoder_sha256 + ">"
    result[result.index("-i") + 1] = "<ivf>"
    formats = [i for i, token in enumerate(result) if token == "-f"]
    check(len(formats) == 2 and [result[i + 1] for i in formats] == ["framemd5", "md5"], "Unexpected decode hash outputs")
    for i in formats:
        check(i + 2 < len(result), "Missing decode hash path")
        result[i + 2] = "<" + result[i + 1] + ">"
    return result


def snapshot(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return json.loads(data), {"path": str(path), "sha256": sha(data), "bytes": len(data)}


def summarize_states(rows, keys):
    counts = Counter(tuple(r[k] for k in keys) for r in rows)
    return [{"state": dict(zip(keys, state)), "runs": count} for state, count in sorted(counts.items())]


def compare(rows, keys):
    selected = {role: [r for r in rows if r["role"] == role] for role in ("reference", "candidate")}
    states = {role: set(tuple(r[k] for k in keys) for r in records) for role, records in selected.items()}
    return {"keys": keys, "equal": bool(states["reference"]) and states["reference"] == states["candidate"],
            "states": {role: summarize_states(records, keys) for role, records in selected.items()},
            "missing_candidate": [dict(zip(keys, s)) for s in sorted(states["reference"] - states["candidate"])],
            "new_candidate": [dict(zip(keys, s)) for s in sorted(states["candidate"] - states["reference"])]}


def aggregate(requirements_path, extra_reports=(), decode_reports=()):
    req, req_meta = snapshot(requirements_path)
    check(req.get("version") == 1, "Unsupported requirements version")
    cases = {x["name"]: x for x in req["cases"]}
    check(len(cases) == len(req["cases"]) and cases, "Duplicate/empty required cases")
    check(Counter(x["kind"] for x in cases.values()) == Counter(req["required_case_counts"]), "Required case counts differ")
    for role in ("reference", "candidate"):
        check(valid_hash(req[role]["sha256"], 64), f"Invalid {role} binary SHA256")
    report_specs = {str(Path(x["path"]).resolve()): x for x in req["reports"]}
    check(len(report_specs) == len(req["reports"]), "Duplicate required reports")
    for p in extra_reports:
        report_specs.setdefault(str(Path(p).resolve()), {"path": str(p), "require_complete": True})
    result = {"status": "pending", "identity_pass": False, "requirements": req_meta,
              "script_sha256": sha(Path(__file__).read_bytes()), "reference": req["reference"], "candidate": req["candidate"],
              "reports": [], "decode_reports": [], "runs": [], "excluded": [], "errors": [], "pending": [], "comparisons": {},
              "notes": ["Raw whole-file/pixel/table hashes belong to separate raw diagnostic runs; they are not captures of the surfaces submitted during AV1 runs.",
                        "Production state union includes every compatible deployed-binary row in all required historical and supplied extension reports.",
                        "Profile rows contribute known states but never satisfy minimum unprofiled repeat counts. No state frequency equality is claimed.",
                        "Raw media deleted by the original harness is represented by its pinned report receipt; retained IVF/table artifacts are rehashed here."]}
    decodes = {}
    for path in decode_reports:
        try:
            doc, meta = snapshot(path)
            meta["complete"] = doc.get("complete")
            meta["decoder"] = doc["decoder"]
            result["decode_reports"].append(meta)
            if not doc.get("complete"):
                result["pending"].append(f"Decode receipt incomplete: {path}")
            check(doc["decoder"]["sha256"] == req["decoder_sha256"], "Decode receipt binary SHA mismatch")
            for row in doc["decodes"]:
                key = str(Path(row["ivf_path"]).resolve())
                check(key not in decodes, f"Duplicate profile decode receipt: {key}")
                decodes[key] = {**row, "receipt": meta, "decoder_sha256": doc["decoder"]["sha256"]}
        except (OSError, ValueError, KeyError, TypeError) as error:
            result["errors"].append(f"Decode receipt {path}: {error}")
    seen = {}
    for path, spec in report_specs.items():
        try:
            doc, meta = snapshot(path)
        except FileNotFoundError:
            result["pending"].append(f"Required report missing: {path}")
            continue
        except (OSError, ValueError) as error:
            result["errors"].append(f"Report {path}: {error}")
            continue
        meta.update({k: doc[k] for k in ("complete", "identity_pass", "observed_state_sets_equal", "manifest_sha256", "harness_sha256", "helper_sha256", "kat_module_sha256", "filmgrn_module_sha256", "pins", "ffmpeg", "failure") if k in doc})
        meta["require_complete"] = spec.get("require_complete", True)
        result["reports"].append(meta)
        if spec.get("sha256") and spec["sha256"] != meta["sha256"]:
            result["errors"].append(f"Historical/completed report SHA256 changed: {path}")
            continue
        if meta["require_complete"] and not doc.get("complete"):
            result["pending"].append(f"Required campaign incomplete: {path}")
        arms = {x["name"]: x for x in doc["manifest"]["arms"]}
        inputs = {x["name"]: x for x in doc["manifest"]["inputs"]}
        for index, original in enumerate(doc["runs"]):
            location = {"report": path, "row": index, "input": original.get("input"), "arm": original.get("arm"), "directory": original.get("directory")}
            role = next((role for role in ("reference", "candidate") if original.get("arm") == req[role]["name"] and original.get("binary_sha256") == req[role]["sha256"]), None)
            if role is None or original.get("stage") == "plain" or not original.get("complete"):
                result["excluded"].append({**location, "reason": "non-target binary/arm" if role is None else "plain control" if original.get("stage") == "plain" else "incomplete row"})
                continue
            try:
                name, arm = original["input"], arms[original["arm"]]
                check(name in cases, f"Unrequired case {name}; keep a separate comparison")
                item, case = inputs[name], cases[name]
                check(arm["sha256"] == req[role]["sha256"] == original["binary_sha256"], "Manifest/row binary mismatch")
                check(item["sha256"] == case["source_sha256"] == original["source_sha256"], "Source SHA mismatch")
                for pin_path, expected in ((arm["binary"], arm["sha256"]), (item["path"], item["sha256"])):
                    check(doc["pins"][str(Path(pin_path).resolve())]["sha256"] == expected, "Manifest/source/binary pin mismatch")
                profiled = "encode_argv" in original
                stage = "av1" if profiled else original["stage"]
                check(stage in ("raw", "av1"), "Unknown identity stage")
                argv = original["encode_argv"] if profiled else original["argv"]
                scope = normalize_scope(argv, arm, item)
                check(scope == case["scopes"][stage], f"Incompatible {stage} argv scope: {json.dumps(scope)}")
                check(item["frames"] == case["frames"] and int(option(argv, "--frames")) == case["frames"], "Requested frame count mismatch")
                if not profiled:
                    check(original["returncode"] == 0, "Nonzero encode return code")
                row = {**original, **(original["ivf"] if profiled else {}), **location, "role": role, "stage": stage, "profiled": profiled, "scope": scope}
                row.pop("profile", None)
                row.pop("ivf", None)
                frame_count = row["frames"] if stage == "raw" else row["packets"]
                check(frame_count == case["frames"] and (not profiled or row["encoded_frames"] == frame_count), "Observed frame count mismatch")
                check(row["width"] > 0 and row["height"] > 0, "Invalid geometry")
                check(all(valid_hash(row[k]) for k in (("file_md5", "pixel_md5", "table_md5") if stage == "raw" else ("file_md5", "table_md5"))), "Malformed MD5")
                frame_hashes = row["frame_md5"] if stage == "raw" else row["packet_md5"]
                check(len(frame_hashes) == frame_count and all(valid_hash(h) for h in frame_hashes), "Per-frame/packet hashes missing")
                directory = Path(row["directory"]).resolve()
                check(directory.is_relative_to(Path(path).parent), "Artifact directory escapes report campaign")
                output = Path(option(argv, "-o")).resolve()
                table = Path(option(argv, "--film-grain-table-out")).resolve()
                check(output.parent == directory and table.parent == directory, "argv artifact directories differ")
                row["artifacts"] = {"table": artifact(table, row["table_md5"])}
                if stage == "av1" or output.exists():
                    row["artifacts"]["output"] = artifact(output, row["file_md5"])
                else:
                    check(row.get("raw_deleted_after_hash") is True, "Missing raw artifact without deletion receipt")
                    row["artifacts"]["output"] = {"path": str(output), "md5": row["file_md5"], "deleted_after_original_hash": True, "sha256": None}
                if stage == "raw":
                    check(row["depth"] == case["output_depth"] and row["frame_bytes"] == row["width"] * row["height"] * 3 // 2 * (2 if row["depth"] == 10 else 1), "Raw pixel geometry/depth mismatch")
                else:
                    receipt = decodes.get(str(output)) if profiled else row
                    if receipt is not None:
                        decoder_sha = receipt["decoder_sha256"] if profiled else doc["ffmpeg"]["sha256"]
                        check(decoder_sha == req["decoder_sha256"], "Decoder identity mismatch")
                        if profiled:
                            check(receipt["ivf_sha256"] == row["artifacts"]["output"]["sha256"] and receipt["ivf_md5"] == row["file_md5"], "Decode receipt IVF mismatch")
                            row["decoded_receipt"] = receipt["receipt"]
                            row.update({k: receipt[k] for k in ("decode_argv", "decoded_pixel_md5", "decoded_frame_md5", "decoded_frames", "decoded_pix_fmt")})
                        check(decode_scope(row["decode_argv"], output, decoder_sha) == case["decode_scope"], "Incompatible decode scope")
                        check(row["decoded_frames"] == frame_count and len(row["decoded_frame_md5"]) == frame_count and valid_hash(row["decoded_pixel_md5"]) and all(valid_hash(h) for h in row["decoded_frame_md5"]), "Invalid decoded hashes/frame count")
                    else:
                        row["decode_note"] = "Profile-only state has no grain-off decode receipt; excluded only from decoded comparison"
                key = (role, stage, str(output))
                signature = sha(json.dumps({k: row[k] for k in ("file_md5", "table_md5", "scope", "source_sha256")}, sort_keys=True).encode())
                if key in seen:
                    check(seen[key] == signature, "Conflicting duplicate run receipt")
                    result["excluded"].append({**location, "reason": "duplicate artifact/run"})
                else:
                    seen[key] = signature
                    result["runs"].append(row)
            except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
                result["errors"].append({**location, "error": str(error)})
    for name, case in cases.items():
        rows = [r for r in result["runs"] if r["input"] == name]
        summary = {"source_sha256": case["source_sha256"], "frames_per_run": case["frames"], "counts": {}}
        for role in ("reference", "candidate"):
            summary["counts"][role] = {}
            for stage in ("raw", "av1"):
                count = sum(r["role"] == role and r["stage"] == stage and not r["profiled"] for r in rows)
                summary["counts"][role][stage] = count
                minimum = req.get("minimum_repeats", 5)
                if count < minimum:
                    result["pending"].append(f"{name} {role} {stage}: {count}/{minimum} unprofiled repeats")
        for label, stage, keys in (("raw", "raw", ["file_md5", "pixel_md5", "table_md5"]), ("av1", "av1", ["file_md5", "table_md5"]), ("decoded_grain_off", "av1", ["decoded_pixel_md5", "decoded_pix_fmt"])):
            selected = [r for r in rows if r["stage"] == stage and (label != "decoded_grain_off" or "decoded_pixel_md5" in r)]
            summary[label] = compare(selected, keys)
            if summary[label]["missing_candidate"]:
                result["pending"].append(f"{name} {label}: candidate is missing {len(summary[label]['missing_candidate'])} known production state(s)")
            if summary[label]["new_candidate"]:
                result["errors"].append(f"{name} {label}: {len(summary[label]['new_candidate'])} candidate state(s) absent from production union")
            if not summary[label]["states"]["reference"]:
                result["pending"].append(f"{name} {label}: no reference state")
        summary["profile_runs_without_decode"] = sum(r["stage"] == "av1" and r["profiled"] and "decoded_pixel_md5" not in r for r in rows)
        summary["campaigns"] = {}
        for campaign in sorted(set(r["report"] for r in rows)):
            subset = [r for r in rows if r["report"] == campaign]
            summary["campaigns"][campaign] = {
                "raw": compare([r for r in subset if r["stage"] == "raw"], ["file_md5", "pixel_md5", "table_md5"]),
                "av1": compare([r for r in subset if r["stage"] == "av1"], ["file_md5", "table_md5"])}
        result["comparisons"][name] = summary
    result["status"] = "fail" if result["errors"] else "pending" if result["pending"] else "pass"
    result["identity_pass"] = result["status"] == "pass"
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--requirements", type=Path, required=True)
    ap.add_argument("--report", type=Path, action="append", default=[], help="Additional completed extension report; required reports come from manifest")
    ap.add_argument("--decoded-report", type=Path, action="append", default=[])
    ap.add_argument("--output", type=Path, required=True, help="New file; existing receipts are never overwritten")
    args = ap.parse_args()
    check(not args.output.exists(), "Output already exists")
    result = aggregate(args.requirements, args.report, args.decoded_report)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2); stream.write("\n")
    print(json.dumps({"status": result["status"], "cases": len(result["comparisons"]), "admitted_runs": len(result["runs"]), "errors": result["errors"], "pending": result["pending"]}, indent=2))
    return {"pass": 0, "fail": 1, "pending": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
