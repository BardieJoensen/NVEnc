#!/usr/bin/env python3
"""Run source-fit admission as a non-routing shadow campaign.

The campaign deliberately has no mechanism that can alter an encode or emit a
production routing verdict.  It extracts pre-registered source clips, asks one
pinned candidate binary for residual-fit and temporal-static source-fit grain
tables, validates both AV1 streams with dav1d, and applies the existing
admission measurement to both tables.

The historical two-axis conjunction is reported as ``would_admit`` only so it
can be falsified on untouched material.  It remains a diagnostic: every JSON
layer also carries ``routing_verdict: null`` and ``changes_output: false``.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from general_content_gate import (  # noqa: E402
    extract_command, probe_stream, require_frames,
)
from integrated_architecture import (  # noqa: E402
    RESEARCH_ENVIRONMENT, arm_environment, build_encode_command,
    complete_task, identity, partial_path, publish_outputs, run_logged,
    write_json,
)
import sourcefit_admission_compare as compare  # noqa: E402


ARMS = {
    "residual": "production",
    "source": "bilateral-source-static",
}
ALLOWED_SOURCE_CODECS = {"h264", "hevc", "mpeg2video", "vc1"}


def load_corpus(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("authority") != "shadow-only":
        raise ValueError("corpus authority must be exactly 'shadow-only'")
    policy = document.get("shadow_policy", {})
    if policy.get("routing_authority") is not False:
        raise ValueError("shadow policy must explicitly disable routing authority")
    for key in ("cross_frame_correlation_max", "anisotropy_mismatch_max"):
        value = policy.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"invalid shadow policy value: {key}")
    samples = document.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("corpus must contain samples")
    identifiers = [sample.get("id") for sample in samples]
    if any(not isinstance(value, str) or not value for value in identifiers):
        raise ValueError("every sample needs a non-empty string id")
    duplicates = sorted(name for name, count in Counter(identifiers).items()
                        if count > 1)
    if duplicates:
        raise ValueError(f"duplicate sample ids: {', '.join(duplicates)}")
    return document


def _axis_values(entry: dict) -> tuple[float, float] | None:
    if entry.get("status") != "OK":
        return None
    evidence = entry.get("film_like_evidence") or {}
    correlation = (evidence.get("cross_frame_correlation") or {}).get("mean")
    fidelity = entry.get("model_fidelity") or {}
    held_out = (fidelity.get("distance") or {}).get("held_out") or {}
    anisotropy = held_out.get("anisotropy_abs")
    if correlation is None or anisotropy is None:
        return None
    return float(correlation), float(anisotropy)


def shadow_entry(entry: dict, policy: dict) -> dict:
    """Apply the frozen diagnostic without manufacturing a routing verdict."""
    values = _axis_values(entry)
    if values is None:
        status = "INSUFFICIENT_COVERAGE"
        correlation = anisotropy = None
        would_admit = None
    else:
        status = "MEASURED"
        correlation, anisotropy = values
        would_admit = (
            correlation <= policy["cross_frame_correlation_max"]
            and anisotropy <= policy["anisotropy_mismatch_max"]
        )
    return {
        "status": status,
        "cross_frame_correlation": correlation,
        "anisotropy_mismatch": anisotropy,
        "would_admit": would_admit,
        "routing_verdict": None,
        "changes_output": False,
    }


def shadow_report(source_fit: dict, policy: dict) -> dict:
    entries = [shadow_entry(entry, policy)
               for entry in source_fit.get("entries", [])]
    counts = Counter(
        "insufficient" if row["would_admit"] is None
        else "admit" if row["would_admit"] else "reject"
        for row in entries)
    summary = source_fit.get("summary") or {}
    title_values = None
    model = summary.get("model_fidelity")
    evidence = summary.get("film_like_evidence")
    if model is not None and evidence is not None:
        correlation = evidence.get("cross_frame_correlation")
        anisotropy = model.get("anisotropy_abs")
        if correlation is not None and anisotropy is not None:
            title_values = {
                "cross_frame_correlation": float(correlation),
                "anisotropy_mismatch": float(anisotropy),
                "would_admit": (
                    correlation <= policy["cross_frame_correlation_max"]
                    and anisotropy <= policy["anisotropy_mismatch_max"]),
            }
    return {
        "policy": policy,
        "warning": (
            "Exploratory counterfactual only. Thresholds are not a router and "
            "were frozen on an earlier corpus."
        ),
        "title_diagnostic": title_values,
        "interval_counts": {
            "admit": counts["admit"],
            "reject": counts["reject"],
            "insufficient": counts["insufficient"],
        },
        "intervals": entries,
        "routing_verdict": None,
        "changes_output": False,
    }


def run_task(name: str, command: list[str], env: dict[str, str], expected: dict,
             partials: list[Path], outputs: list[Path], manifest: Path,
             log: Path) -> dict:
    if complete_task(manifest, expected, outputs):
        print(f"[resume] {name}", flush=True)
        return json.loads(manifest.read_text(encoding="utf-8"))
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(
            f"{name}: outputs exist without matching task manifest: {existing}")
    print(f"[run] {name}", flush=True)
    elapsed = run_logged(command, env, log)
    publish_outputs(partials, outputs)
    record = {
        "input": expected,
        "outputs": [identity(path) for path in outputs],
        "elapsed_seconds": elapsed,
        "log": str(log.resolve()),
    }
    write_json(manifest, record)
    return record


def validate_dav1d(encoded: Path, ffmpeg: Path, task_dir: Path,
                   binary_identity: dict) -> dict:
    manifest = task_dir / f"{encoded.stem}-dav1d.task.json"
    expected = {
        "source": identity(encoded),
        "binary": binary_identity,
        "decoder": "libdav1d",
        "xerror": True,
    }
    if manifest.is_file():
        try:
            recorded = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            recorded = {}
        if recorded.get("input") == expected:
            print(f"[resume] {encoded.stem}-dav1d", flush=True)
            return recorded
    command = [
        str(ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-c:v", "libdav1d", "-i", str(encoded), "-map", "0:v:0",
        "-an", "-sn", "-dn", "-f", "null", "-",
    ]
    log = task_dir / f"{encoded.stem}-dav1d.log"
    elapsed = run_logged(command, os.environ.copy(), log)
    record = {
        "input": expected,
        "command": command,
        "elapsed_seconds": elapsed,
        "log": str(log.resolve()),
    }
    write_json(manifest, record)
    return record


def run_admission(kind: str, source: Path, table: Path, output: Path,
                  task_dir: Path, python_identity: dict,
                  report_tag: str = "") -> dict:
    partial = partial_path(output)
    command = [
        sys.executable, str(HERE / "sourcefit_admission_report.py"),
        "--source", str(source), "--table", str(table),
        "--json-out", str(partial),
    ]
    expected = {
        "command": command,
        "source": identity(source),
        "table": identity(table),
        "python": python_identity,
        "report_script": identity(HERE / "sourcefit_admission_report.py"),
    }
    return run_task(
        f"{source.stem}-{kind}-admission", command, os.environ.copy(),
        expected, [partial], [output],
        task_dir / f"{kind}-admission{report_tag}.task.json",
        task_dir / f"{kind}-admission{report_tag}.log")


def sample_summary(sample: dict, source_report: dict,
                   residual_report: dict, policy: dict) -> dict:
    comparison = compare.compare_reports(source_report, residual_report)
    return {
        "id": sample["id"],
        "title": sample["title"],
        "reference_class": sample["reference_class"],
        "expectation": sample["expectation"],
        "seek_fraction": sample["seek_fraction"],
        "shadow": shadow_report(source_report, policy),
        "model_comparison": comparison,
        "routing_verdict": None,
        "changes_output": False,
    }


def corpus_summary(rows: list[dict]) -> dict:
    by_class: dict[str, list[bool | None]] = defaultdict(list)
    title_consistency: dict[str, list[bool | None]] = defaultdict(list)
    for row in rows:
        value = (row["shadow"].get("title_diagnostic") or {}).get(
            "would_admit")
        by_class[row["reference_class"]].append(value)
        title_consistency[row["title"]].append(value)

    def counts(values: list[bool | None]) -> dict:
        return {
            "admit": sum(value is True for value in values),
            "reject": sum(value is False for value in values),
            "insufficient": sum(value is None for value in values),
        }

    return {
        "by_reference_class": {
            key: counts(values) for key, values in sorted(by_class.items())
        },
        "by_title": {
            key: {**counts(values), "scene_consistent": len(set(values)) == 1}
            for key, values in sorted(title_consistency.items())
        },
        "routing_verdict": None,
        "changes_output": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus", type=Path,
        default=HERE / "corpora" / "sourcefit-shadow-20260804.json")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--candidate-nvencc", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path,
                        default=Path("/usr/local/bin/ffmpeg"))
    parser.add_argument("--ffprobe", type=Path,
                        default=Path("/usr/local/bin/ffprobe"))
    parser.add_argument(
        "--samples", default="",
        help="optional comma-separated sample ids; default is the whole corpus")
    parser.add_argument(
        "--report-tag", default="",
        help="suffix for a new report schema replay, for example stochastic-v1")
    args = parser.parse_args()
    if args.report_tag and not all(
            character.isalnum() or character in "-_"
            for character in args.report_tag):
        parser.error("--report-tag may contain only letters, digits, '-' and '_'")
    report_tag = f"-{args.report_tag}" if args.report_tag else ""

    corpus_path = args.corpus.resolve()
    work = args.work.resolve()
    candidate = args.candidate_nvencc.resolve()
    ffmpeg = args.ffmpeg.resolve()
    ffprobe = args.ffprobe.resolve()
    for path in (corpus_path, candidate, ffmpeg, ffprobe):
        if not path.is_file():
            parser.error(f"missing required file: {path}")
    try:
        corpus = load_corpus(corpus_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    samples = corpus["samples"]
    if args.samples:
        selected = {value.strip() for value in args.samples.split(",")
                    if value.strip()}
        known = {sample["id"] for sample in samples}
        unknown = sorted(selected - known)
        if unknown:
            parser.error(f"unknown samples: {', '.join(unknown)}")
        samples = [sample for sample in samples if sample["id"] in selected]

    work.mkdir(parents=True, exist_ok=True)
    clip_dir = work / "clips"
    task_dir = work / "tasks"
    for directory in (clip_dir, task_dir):
        directory.mkdir(parents=True, exist_ok=True)
    candidate_identity = identity(candidate, include_hash=True)
    ffmpeg_identity = identity(ffmpeg, include_hash=True)
    python_identity = identity(Path(sys.executable), include_hash=True)
    rows = []

    for sample in samples:
        sample_id = sample["id"]
        print(f"\n== {sample_id} ==", flush=True)
        source = Path(sample["source"]).resolve()
        if not source.is_file():
            raise RuntimeError(f"{sample_id}: missing source {source}")
        stream = probe_stream(source, ffprobe)
        codec = stream.get("codec_name")
        if codec not in ALLOWED_SOURCE_CODECS:
            raise RuntimeError(
                f"{sample_id}: source codec {codec!r} is not an allowed "
                "pre-FGS codec; AV1/library outputs are forbidden")
        if stream.get("field_order") not in (None, "unknown", "progressive"):
            raise RuntimeError(
                f"{sample_id}: source is not progressive: "
                f"field_order={stream.get('field_order')}")
        frames = int(sample.get("frames", 288))
        start = float(stream["duration"]) * float(sample["seek_fraction"])
        sample_work = work / sample_id
        sample_tasks = task_dir / sample_id
        sample_work.mkdir(parents=True, exist_ok=True)
        sample_tasks.mkdir(parents=True, exist_ok=True)

        clip = clip_dir / f"{sample_id}.mkv"
        clip_partial = partial_path(clip)
        extract = extract_command(
            ffmpeg, source, clip_partial, start, frames, stream)
        extract_expected = {
            "command": extract,
            "source": identity(source),
            "binary": ffmpeg_identity,
            "source_codec": codec,
            "seek_fraction": sample["seek_fraction"],
        }
        run_task(
            f"{sample_id}-extract", extract, os.environ.copy(),
            extract_expected, [clip_partial], [clip],
            sample_tasks / "extract.task.json",
            sample_tasks / "extract.log")
        require_frames(clip, frames)

        tables: dict[str, Path] = {}
        dav1d: dict[str, dict] = {}
        for kind, arm in ARMS.items():
            encoded = sample_work / f"{kind}.mkv"
            encoded_partial = partial_path(encoded)
            table = sample_work / f"{kind}.tbl"
            table_partial = partial_path(table)
            env = arm_environment(arm)
            command = build_encode_command(
                candidate, clip, encoded_partial, table_partial, arm,
                qvbr=int(sample.get("qvbr", 29)))
            expected = {
                "command": command,
                "environment": {
                    key: env[key] for key in RESEARCH_ENVIRONMENT if key in env
                },
                "source": identity(clip),
                "binary": candidate_identity,
            }
            run_task(
                f"{sample_id}-{kind}-encode", command, env, expected,
                [encoded_partial, table_partial], [encoded, table],
                sample_tasks / f"{kind}-encode.task.json",
                sample_tasks / f"{kind}-encode.log")
            require_frames(encoded, frames)
            dav1d[kind] = validate_dav1d(
                encoded, ffmpeg, sample_tasks, ffmpeg_identity)
            tables[kind] = table

        reports = {}
        for kind, table in tables.items():
            report_path = sample_work / f"{kind}-admission{report_tag}.json"
            run_admission(
                kind, clip, table, report_path, sample_tasks,
                python_identity, report_tag)
            reports[kind] = compare.load_report(report_path)

        row = sample_summary(
            sample, reports["source"], reports["residual"],
            corpus["shadow_policy"])
        row["source"] = {
            "path": str(source), "codec": codec,
            "width": stream["width"], "height": stream["height"],
        }
        row["clip"] = identity(clip)
        row["candidate_binary"] = candidate_identity
        row["dav1d"] = dav1d
        rows.append(row)
        result_name = f"result{report_tag}.json"
        write_json(work / result_name, {
            "purpose": "shadow-only source-fit admission campaign",
            "corpus": identity(corpus_path, include_hash=True),
            "candidate_binary": candidate_identity,
            "shadow_policy": corpus["shadow_policy"],
            "samples": rows,
            "summary": corpus_summary(rows),
            "routing_verdict": None,
            "changes_output": False,
        })

    print(f"\nresult: {work / f'result{report_tag}.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
