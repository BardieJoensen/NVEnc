#!/usr/bin/env python3
"""Admit a bitstream-neutral source trace and compare its complete population."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(os.environ.get(
    "PANTHEON_SOURCEBUDGET_ROOT",
    "/tmp/downloads/codex-work/pantheon-sourcebudget-20261020",
))
pristine_tag, trace_tag = sys.argv[1:]
base = ROOT / "parent/source-boundary"
out = base / (trace_tag + "-validated.json")
assert not out.exists()


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(path):
    return {"path": str(path), "sha256": sha(path)}


def bound(record):
    assert sha(record["path"]) == record["sha256"], record["path"]


installed_path = ROOT / "worker/runs/e05-1440/aom-psnr-1x2/command.json"
installed = read(installed_path)
bound(installed["input"])
assert sha(ROOT / "worker/runs/e05-1440/aom-psnr-1x2/out.ivf") == installed["ivf_sha256"]
replays = []
for arm, tag in (("pristine", pristine_tag), ("trace", trace_tag)):
    path = base / "runs" / tag / "command.json"
    run = read(path)
    assert (run["arm"], run["tag"], run["status"], run["returncode"]) == (arm, tag, "encoded", 0)
    for name in ("source_command", "input", "input_after", "build_receipt", "library",
                 "ldd_output", "stats_original", "stats_before", "stats_after",
                 "script", "ffmpeg", "output", "log"):
        bound(run[name])
    assert run["build_receipt"]["sha256"] == "2dea15541d56a6aec48e24d082b35f66a54415989aac2e4f8b6f0eeee112738e"
    assert run["script"]["sha256"] == sha(Path(__file__).resolve().parent / "replay_aom_trace.py")
    assert run["ffmpeg"]["sha256"] == installed["ffmpeg"]["sha256"]
    assert run["source_command"] == {
        **identity(installed_path), "size": installed_path.stat().st_size
    }
    assert run["input"]["sha256"] == installed["input"]["sha256"]
    assert run["input"] == run["input_after"]
    assert run["stats_original"]["sha256"] == installed["passes"]["pass1"]["pass1_stats_snapshot"]["sha256"]
    assert run["stats_before"]["sha256"] == run["stats_after"]["sha256"] == run["stats_original"]["sha256"]
    actual = list(run["command"])
    expected = list(installed["commands"]["pass2"])
    assert Path(actual[-1]).resolve() == Path(run["output"]["path"]).resolve()
    assert Path(actual[actual.index("-passlogfile") + 1] + "-0.log").resolve() == Path(run["stats_before"]["path"]).resolve()
    assert Path(actual[actual.index("-i") + 1]).resolve() == Path(run["input"]["path"]).resolve()
    for cmd in (actual, expected):
        cmd[cmd.index("-passlogfile") + 1] = "LOCAL_STATS_PATH"
        cmd[-1] = "LOCAL_OUTPUT_PATH"
    assert actual == expected
    assert run["exact_installed_ivf"]
    assert run["output"]["sha256"] == installed["ivf_sha256"]
    build = read(run["build_receipt"]["path"])
    assert run["library"] == build[arm]
    library_path = Path(run["library"]["path"]).resolve()
    loaded = re.findall(
        r"^\s*libaom\.so\.3 => (\S+)", Path(run["ldd_output"]["path"]).read_text(), re.M
    )
    assert len(loaded) == 1 and Path(loaded[0]).resolve() == library_path
    assert Path(run["environment_overrides"]["LD_LIBRARY_PATH"]).resolve() == library_path.parent
    fd = run["environment_overrides"]["AOM_TRACE_FD"]
    if arm == "pristine":
        assert fd is None
    else:
        assert int(fd) >= 3 and str(int(fd)) == fd
    for group in ("source_files", "build_files"):
        for records in build[group].values():
            for record in records.values():
                bound(record)
    bound(build["patch"])
    bound(build["trace_build_execution"])
    for record in build["tools"].values():
        bound(record)
    for record in build["ubuntu_patch_series"]:
        bound(record)
    replays.append(run)
assert replays[0]["build_receipt"] == replays[1]["build_receipt"]
assert replays[0]["output"]["sha256"] == replays[1]["output"]["sha256"]

reconstruction_dir = ROOT / "worker/aom-source-verify-v3-20261020T100425Z"
reconstruction_path = reconstruction_dir / "source-domain-receipt.json"
assert sha(reconstruction_path) == "adaef450fb9f272e62033b7a409380cbefd71fb1ce1f010d8ff69074e3bca755"
reconstruction = read(reconstruction_path)
assert reconstruction["status"] == "source-domain-verified"
manifests = {
    name: read(reconstruction_dir / (name + "-source-manifest.json"))
    for name in ("reconstructed", "pristine2", "traced")
}
domain = set(manifests["reconstructed"])
assert len(domain) == 1294
assert domain <= set(manifests["pristine2"]) and domain <= set(manifests["traced"])
assert all(manifests["reconstructed"][k] == manifests["pristine2"][k] for k in domain)
differences = sorted(k for k in domain if manifests["pristine2"][k] != manifests["traced"][k])
assert differences == ["av1/av1.cmake", "av1/encoder/encoder.c"]
for arm, name in (("pristine", "pristine2"), ("trace", "traced")):
    for file, record in build["source_files"][arm].items():
        assert record["sha256"] == manifests[name][file]
reconstruction_evidence = {
    "receipt": identity(reconstruction_path),
    **{name: identity(reconstruction_dir / (name + "-source-manifest.json")) for name in manifests},
}
patch_rows = (reconstruction_dir / "patch-receipts.tsv").read_text().splitlines()
assert len(patch_rows) == len(build["ubuntu_patch_series"]) == 7
for index, (line, expected) in enumerate(zip(patch_rows, build["ubuntu_patch_series"]), 1):
    position, name, log_path, digest, rc = line.split("\t")
    assert int(position) == index and int(rc) == 0
    assert name == Path(expected["path"]).name and digest == expected["sha256"]
    reconstruction_evidence["patch_log_" + str(index)] = identity(Path(log_path))
reconstruction_evidence["patch_receipts"] = identity(reconstruction_dir / "patch-receipts.tsv")
archives = {}
for line in (reconstruction_dir / "input-archive-sha256.txt").read_text().splitlines():
    digest, path = line.split(maxsplit=1)
    path = Path(path.strip().lstrip("*"))
    assert sha(path) == digest
    archives[path.name] = digest
assert build["source_tar_sha256"] in archives.values()
assert build["debian_tar_sha256"] in archives.values()
reconstruction_evidence["archives"] = identity(reconstruction_dir / "input-archive-sha256.txt")

input_path = base / "input-planes.json"
inputs = read(input_path)
for name in ("source", "historical", "script"):
    bound(inputs[name])
assert inputs["source"]["sha256"] == installed["input"]["sha256"]
assert inputs["all336_whole_md5_equal_historical"] and inputs["source_unchanged"]
assert [f["source_index"] for f in inputs["frames"]] == list(range(336))
by_hash = {f["whole_md5"]: f for f in inputs["frames"]}
assert len(by_hash) == 336

coverage_dir = ROOT / "reviewer/round4-coverage"
coverage_receipt = read(coverage_dir / "receipt.json")
bound(coverage_receipt["input_ivf"])
bound(coverage_receipt["ffmpeg"])
assert coverage_receipt["input_ivf"]["sha256"] == installed["ivf_sha256"]
for record in coverage_receipt["files"].values():
    bound(record)
coverage = read(coverage_dir / "parsed-events.json")
expected_keys = collections.Counter(
    tuple(e["hook_match_key"]) for e in coverage["events"] if not e["show_existing_frame"]
)
assert len(expected_keys) == sum(expected_keys.values()) == 363
assert coverage["summary"]["all_packets_exactly_one_display_action"]

trace = replays[1]["trace"]
bound(trace)
records = []
actual_keys = collections.Counter()
for line in Path(trace["path"]).read_bytes().splitlines(keepends=True):
    assert line.endswith(b"\n") and len(line) < 2048
    row = json.loads(line)
    assert row["record_version"] == 3
    assert [row[k] for k in ("bit_depth", "highbd", "width", "height", "uv_width", "uv_height")] == [
        10, 1, 1920, 1080, 960, 540
    ]
    assert row["subsampling"] == [1, 1]
    for key in ("strides_a", "strides_b"):
        assert len(row[key]) == 2 and row[key][0] >= 1920 and row[key][1] >= 960
    source = by_hash[row["unfiltered_md5"]]
    assert row["unfiltered_plane_md5"] == source["plane_md5"]
    assert len(row["source_plane_md5"]) == len(row["neq"]) == len(row["maxabs"]) == 3
    assert row["source_ptr_equal"] in (0, 1)
    for p, count in enumerate((1920 * 1080, 960 * 540, 960 * 540)):
        assert 0 <= row["neq"][p] <= count and 0 <= row["maxabs"][p] <= 1023
        same = row["source_plane_md5"][p] == row["unfiltered_plane_md5"][p]
        assert same == (row["neq"][p] == 0) == (row["maxabs"][p] == 0)
    unchanged = sum(row["neq"]) == 0
    assert unchanged == (row["source_md5"] == row["unfiltered_md5"])
    if row["source_ptr_equal"]:
        assert unchanged
    assert row["show_frame"] in (0, 1) and row["showable_frame"] in (0, 1)
    assert 0 <= row["order_hint"] < 128
    key = (
        source["source_index"], row["frame_type"], row["show_frame"],
        0 if row["show_frame"] else row["showable_frame"], row["order_hint"],
        255 if row["frame_type"] == 0 and row["show_frame"] else row["refresh_frame_flags"],
    )
    actual_keys[key] += 1
    records.append(row | {"source_index": source["source_index"], "hook_match_key": key,
                          "all_visible_samples_unchanged": unchanged})
assert actual_keys == expected_keys
assert len(records) == 363 and len({r["source_index"] for r in records}) == 336
groups = {}
for name, pool in (
    ("all", records), ("hidden", [r for r in records if not r["show_frame"]]),
    ("shown", [r for r in records if r["show_frame"]]),
):
    groups[name] = {
        "coded_events": len(pool),
        "changed_events": sum(not r["all_visible_samples_unchanged"] for r in pool),
        "different_pointer_events": sum(not r["source_ptr_equal"] for r in pool),
        "unequal_samples": [sum(r["neq"][p] for r in pool) for p in range(3)],
        "maxabs": [max(r["maxabs"][p] for r in pool) for p in range(3)],
    }
result = {
    "status": "admitted", "pristine_equals_installed": True, "trace_equals_pristine": True,
    "all336_source_indices_bound": True, "all363_coded_events_matched": True,
    "all_unfiltered_whole_and_plane_hashes_exact": True,
    "summary": groups, "events": sorted(records, key=lambda r: r["hook_match_key"]),
    "provenance": {
        "script": identity(Path(__file__).resolve()), "input_planes": identity(input_path),
        "coverage_receipt": identity(coverage_dir / "receipt.json"),
        "pristine_run": identity(base / "runs" / pristine_tag / "command.json"),
        "trace_run": identity(base / "runs" / trace_tag / "command.json"),
        "installed_run": identity(installed_path),
        "source_reconstruction": reconstruction_evidence,
    },
    "scope": "Observed visible coding-source samples at the pre-SSIM boundary; not an ablation of prediction, allocation, or quantization.",
    "playback_observed": False,
}
out.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"status": result["status"], "summary": groups, "output": str(out)}, indent=2))
