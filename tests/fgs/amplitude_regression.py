#!/usr/bin/env python3
"""Source-backed regression for the two confirmed Play Dirty amplitude witnesses.

This is a private-media release check, not a general perceptual quality score.
The supplied manifest pins source, deployed negative, candidate and a matching
ordinary NVENC reference with film-grain analysis disabled.
Both exact witness windows must pass, and the retained negative must fail each.
It deliberately does not require a perfectly flat source patch.

Regenerated grain is stochastic: comparing its individual pixels with the
source penalizes a second, independent realization even at the right strength.
Keep that original diagnostic, but judge picture preservation on the decoded
base and coarse displayed picture, and separately bound displayed fine texture
against the original. These remain finite, scene-specific release checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np

CASES = {"city": 856.333, "dialogue": 5727.583}
FRAMES = 12
# The first diagnostic used a fixed source RMS limit of four, but the exact
# same-settings no-FGS control also exceeds it (city peak 4.908). Preserve that
# diagnostic, and test added damage against the independently encoded control.
PROVISIONAL_SOURCE_RMS_LIMIT = 4.0
SOURCE_RMS_EXCESS_LIMIT = .15
SOURCE_RMS_MEAN_EXCESS_LIMIT = .05
SYNTHESIS_RMS_LIMIT = 3.0
PTS = re.compile(rb" n:\s*\d+ pts:\s*-?\d+ pts_time:([-+0-9.eE]+)")


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def signature(path):
    value = Path(path).stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def decode(path, start, directory, name, grain=None):
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=codec_name,width,height,start_time", "-of", "json", str(path),
    ], timeout=60))["streams"][0]
    width, height = probe["width"], probe["height"]
    if (width, height) != (1920, 800):
        raise ValueError("witness geometry changed")
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-copyts", "-xerror", "-threads", "2"]
    if grain is not None:
        if probe["codec_name"] != "av1":
            raise ValueError("expected an AV1 output")
        command += ["-c:v", "libdav1d", "-filmgrain", str(grain)]
    # Short excerpts can retain their original nonzero PTS. Decode those from
    # their beginning; absolute seeking is ambiguous for such Matroska files.
    if abs(float(probe.get("start_time", 0))) < .1:
        command += ["-ss", str(max(0, start - .5))]
    command += ["-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
                "-frames:v", str(FRAMES), "-fps_mode", "passthrough",
                "-vf", f"select='gte(t,{start-.0021:.9f})',format=yuv420p16le,showinfo",
                "-filter_threads", "1", "-f", "rawvideo", "-"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (name + "-command.json")).write_text(json.dumps(command, indent=2) + "\n")
    with (directory / (name + ".log")).open("wb") as log:
        decoded = subprocess.run(command, stdout=subprocess.PIPE, stderr=log, check=True, timeout=240)
    count = width * height * 3 // 2
    if len(decoded.stdout) != FRAMES * count * 2:
        raise ValueError("missing or partial decoded witness pictures")
    times = [float(t) for t in PTS.findall((directory / (name + ".log")).read_bytes())][:FRAMES]
    if (len(times) != FRAMES or abs(times[0] - start) > .0021
            or not all(np.isfinite(times)) or any(b <= a for a, b in zip(times, times[1:]))):
        raise ValueError("incomplete or ambiguous witness timing")
    samples = np.frombuffer(decoded.stdout, dtype="<u2").reshape(FRAMES, count)
    luma = samples[:, :width * height].reshape(FRAMES, height, width).astype(np.float32) / 256.0
    return times, luma


def assess(source, on, off, reference):
    if (source.shape != on.shape or on.shape != off.shape or off.shape != reference.shape
            or source.ndim != 3 or len(source) != FRAMES):
        raise ValueError("incomplete source/on/off coverage")
    if not all(np.isfinite(x).all() for x in (source, on, off, reference)):
        raise ValueError("nonfinite witness pixels")
    difference = on - source
    grain = on - off
    source_rms = np.sqrt(np.mean(difference * difference, axis=(1, 2), dtype=np.float64))
    synthesis_rms = np.sqrt(np.mean(grain * grain, axis=(1, 2), dtype=np.float64))
    reference_difference = reference - source
    reference_rms = np.sqrt(np.mean(reference_difference * reference_difference, axis=(1, 2), dtype=np.float64))
    excess = source_rms - reference_rms
    legacy_source_passed = bool(excess.max() <= SOURCE_RMS_EXCESS_LIMIT and excess.mean() <= SOURCE_RMS_MEAN_EXCESS_LIMIT)
    base_rms = np.sqrt(np.mean((off-source)**2, axis=(1, 2), dtype=np.float64))
    base_excess = base_rms - reference_rms
    base_passed = bool(base_excess.max() <= SOURCE_RMS_EXCESS_LIMIT
                       and base_excess.mean() <= SOURCE_RMS_MEAN_EXCESS_LIMIT)
    frames, height, width = source.shape
    if height % 16 or width % 16:
        raise ValueError("source-energy coverage requires complete 16x16 tiles")

    def reduce(values, size):
        return values.reshape(frames, height//size, size, width//size, size).mean(axis=(2, 4))

    # Preserve low-frequency colour/structure in the displayed image too. The
    # base check above still covers every pixel, including fine picture detail.
    coarse_rms = np.sqrt(np.mean(reduce(on-source, 8)**2, axis=(1, 2), dtype=np.float64))
    reference_coarse = np.sqrt(np.mean(reduce(reference-source, 8)**2, axis=(1, 2), dtype=np.float64))
    coarse_excess = coarse_rms - reference_coarse
    coarse_passed = bool(coarse_excess.max() <= SOURCE_RMS_EXCESS_LIMIT
                         and coarse_excess.mean() <= SOURCE_RMS_MEAN_EXCESS_LIMIT)

    # Select low-structure tiles from source 4x4 means only. Measure native
    # two-dimensional high-frequency energy with a normalized Haar diagonal;
    # independent grain samples are compared by strength, not random phase.
    low = reduce(source, 4).reshape(frames, height//16, 4, width//16, 4)
    flat = np.ptp(low, axis=(2, 4)) < 6
    flat_counts = flat.sum(axis=(1, 2))
    energies = {}
    for name, values in (("source", source), ("candidate", on), ("reference", reference)):
        high = (values[:, ::2, ::2] - values[:, ::2, 1::2]
                - values[:, 1::2, ::2] + values[:, 1::2, 1::2]) * .5
        energy = (high*high).reshape(frames, height//16, 8, width//16, 8).mean(axis=(2, 4))
        energies[name] = np.sqrt(np.sum(np.where(flat, energy, 0), axis=(1, 2), dtype=np.float64)
                                 / np.maximum(flat_counts, 1))
    texture_excess = energies['candidate'] - np.maximum(energies['source'], energies['reference'])
    # Never clear a synthesized frame from absent source coverage. A frame
    # without synthesis is already covered by the two picture checks.
    supported = (flat_counts >= 16) | (synthesis_rms == 0)
    texture_passed = bool(supported.all() and texture_excess.max() <= SOURCE_RMS_EXCESS_LIMIT
                          and texture_excess.mean() <= SOURCE_RMS_MEAN_EXCESS_LIMIT)
    source_passed = base_passed and coarse_passed and texture_passed
    synthesis_passed = bool(synthesis_rms.max() <= SYNTHESIS_RMS_LIMIT)
    return dict(passed=source_passed and synthesis_passed,
                source_comparison_passed=source_passed, synthesis_passed=synthesis_passed,
                source_luma_rms=source_rms.tolist(), synthesis_luma_rms=synthesis_rms.tolist(),
                reference_source_luma_rms=reference_rms.tolist(), source_rms_excess=excess.tolist(),
                source_rms_excess_limit=SOURCE_RMS_EXCESS_LIMIT,
                source_rms_mean_excess_limit=SOURCE_RMS_MEAN_EXCESS_LIMIT,
                synthesis_rms_limit=SYNTHESIS_RMS_LIMIT,
                base_source_check=dict(passed=base_passed, source_luma_rms=base_rms.tolist(), excess=base_excess.tolist()),
                displayed_coarse_source_check=dict(passed=coarse_passed, block_size=8,
                    source_luma_rms=coarse_rms.tolist(), reference_source_luma_rms=reference_coarse.tolist(), excess=coarse_excess.tolist()),
                source_texture_check=dict(passed=texture_passed, source_flat_tile_counts=flat_counts.tolist(),
                    flat_hf_rms={name:value.tolist() for name,value in energies.items()}, excess=texture_excess.tolist()),
                legacy_pixelwise_on_check=dict(passed=legacy_source_passed,
                    scope="Original unchanged diagnostic; independent regenerated grain can raise pixelwise error while restoring source texture. Release requires base, displayed coarse picture and source-energy checks instead."),
                provisional_absolute_source_check=dict(limit=PROVISIONAL_SOURCE_RMS_LIMIT,
                    candidate_passed=bool(source_rms.max() <= PROVISIONAL_SOURCE_RMS_LIMIT),
                    reference_passed=bool(reference_rms.max() <= PROVISIONAL_SOURCE_RMS_LIMIT),
                    scope="Original diagnostic retained; independently shown to reject ordinary QVBR30 compression in the city witness."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-nvencc", type=Path,
                        help="Release check: require the manifest's encoded candidate to name this binary SHA")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    encoder_sha = sha(args.candidate_nvencc) if args.candidate_nvencc else None
    if encoder_sha and manifest['candidate'].get('encoder_sha256') != encoder_sha:
        raise ValueError('candidate artifact was not recorded for the requested encoder')
    files = {name: Path(manifest[name]["path"]) for name in ("source", "negative", "candidate", "reference")}
    before = {name: signature(path) for name, path in files.items()}
    if len(set(before.values())) != 4:
        raise ValueError("source, negative, candidate and reference must be distinct files")
    for name, path in files.items():
        if sha(path) != manifest[name]["sha256"]:
            raise ValueError(name + " identity changed")
    results = []
    for name, start in CASES.items():
        directory = args.output / name
        source_times, source = decode(files["source"], start, directory, "source")
        reference_times, reference = decode(files["reference"], start, directory, "reference-on", 1)
        reference_off_times, reference_off = decode(files["reference"], start, directory, "reference-off", 0)
        if (reference_times != reference_off_times or not np.array_equal(reference, reference_off)
                or any(abs(a-b) > .0021 for a,b in zip(source_times, reference_times))):
            raise ValueError("compression reference contains grain or is not source-aligned")
        del reference_off
        result = dict(case=name, seconds=source_times, frames=FRAMES, arms={})
        for arm in ("negative", "candidate"):
            on_times, on = decode(files[arm], start, directory, arm + "-on", 1)
            off_times, off = decode(files[arm], start, directory, arm + "-off", 0)
            if on_times != off_times or any(abs(a-b) > .0021 for a, b in zip(source_times, on_times)):
                raise ValueError("source and synthesis pictures are not uniquely paired")
            result["arms"][arm] = assess(source, on, off, reference)
        result["passed"] = (result["arms"]["candidate"]["passed"]
                            and not result["arms"]["negative"]["synthesis_passed"])
        results.append(result)
    if any(signature(path) != before[name] for name, path in files.items()):
        raise ValueError("input changed during qualification")
    if encoder_sha and sha(args.candidate_nvencc) != encoder_sha:
        raise ValueError('encoder changed during qualification')
    report = dict(complete=True, passed=all(r["passed"] for r in results), cases=results,
                  encoder_identity_checked=bool(encoder_sha), encoder_sha256=encoder_sha,
                  manifest=manifest, manifest_sha256=sha(args.manifest),
                  scope="Two pinned SDR/QVBR30 witnesses, every matched frame. Unchanged synthesis-amplitude cap, base-picture and displayed coarse source error relative to an independent same-settings no-FGS reference, plus source-supported fine-texture energy. Original pixelwise grain-on diagnostic is retained. Tight scene-specific margins are not a universal perceptual threshold or whole-film certificate.")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(passed=report["passed"], report=str(args.output / "report.json"))))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
