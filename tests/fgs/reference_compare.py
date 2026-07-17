#!/usr/bin/env python3
"""Separate AV1 film-grain analyzer errors with libaom as an oracle.

For each synthetic fixture this runs three measurements:

  * NVEnc's complete GPU analyzer;
  * libaom using NVEnc's emitted clean base (model-fitting reference);
  * libaom using the fixture's ideal clean base (end-to-end oracle).

The libaom-vs-libaom difference isolates separation loss.  The NVEnc-vs-libaom
comparison on the same NVEnc clean base isolates model-fitting differences.
No libaom code is linked into or shipped with NVEncC.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import filmgrn
import fgs_kat as kat
import quality_metrics


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TESTS = "const_luma,ramp_luma,coarse_luma,detail_luma,chroma_corr"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def run(argv):
    started = time.monotonic()
    result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                            check=False)
    record = {
        "argv": argv,
        "returncode": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return record


def convert_y4m_to_raw(source, destination, bits):
    pixel_format = "yuv420p" if bits == 8 else "yuv420p10le"
    return run(["ffmpeg", "-v", "error", "-y", "-i", source,
                "-pix_fmt", pixel_format, "-f", "rawvideo", destination])


def convert_raw_to_y4m(source, destination, width, height, frames, bits):
    pixel_format = "yuv420p" if bits == 8 else "yuv420p10le"
    return run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pixel_format", pixel_format,
        "-video_size", f"{width}x{height}", "-framerate", "24",
        "-i", source, "-frames:v", str(frames), "-pix_fmt", pixel_format,
        "-strict", "-1", "-f", "yuv4mpegpipe", destination,
    ])


def run_aom(binary, original, clean, table, width, height, bits):
    argv = [
        binary,
        "--fps=24/1",
        f"--width={width}",
        f"--height={height}",
        f"--bit-depth={bits}",
        "--i420",
        f"--input={original}",
        f"--input-denoised={clean}",
        f"--output-grain-table={table}",
    ]
    command = run(argv)
    if not os.path.isfile(table):
        raise RuntimeError(f"libaom did not write a grain table: {table}")
    return command, filmgrn.load(table)


def run_nvenc(binary, source, clean, table, bits, denoiser):
    analyzer = f"denoise=auto,chroma=auto,denoiser={denoiser}"
    argv = [
        binary,
        "--codec", "raw",
        "--av1-film-grain", analyzer,
        "--film-grain-table-out", table,
        "--log-level", "debug",
    ]
    if bits > 8:
        argv.extend(["--output-depth", str(bits)])
    argv.extend(["-i", source, "-o", clean])
    command = run(argv)
    entries = filmgrn.load(table) if os.path.isfile(table) else []
    return command, entries


def comparison(candidate_entries, reference_entries):
    return filmgrn.compare(filmgrn.representative(candidate_entries),
                           filmgrn.representative(reference_entries))


def synthesize_table(binary, clean, table, prefix, bits, frames):
    encoded = prefix + ".mkv"
    grain_on = prefix + "-on.yuv"
    grain_off = prefix + "-off.yuv"
    argv = [binary, "--codec", "av1", "--cqp", "20",
            "--film-grain-table", table]
    if bits > 8:
        argv.extend(["--output-depth", str(bits)])
    argv.extend(["-i", clean, "-o", encoded])
    commands = {"encode": run(argv)}
    pixel_format = "yuv420p" if bits == 8 else "yuv420p10le"
    for enabled, output, name in ((1, grain_on, "decode_on"),
                                  (0, grain_off, "decode_off")):
        commands[name] = run([
            "ffmpeg", "-v", "error", "-y", "-c:v", "libdav1d",
            "-filmgrain", str(enabled), "-i", encoded,
            "-pix_fmt", pixel_format, "-f", "rawvideo", output,
        ])
    first = min(kat.SKIP, max(frames - 1, 0))
    sigma, chroma_luma_correlation = kat.measure(
        grain_on, grain_off, range(first, frames))
    sigma_8bit = sigma / kat.DS
    spatial = quality_metrics.grain_metrics(
        grain_on, grain_off, kat.W, kat.H, kat.BITS, first_frame=first)
    return {
        "sigma_8bit": sigma_8bit.tolist(),
        "mean_sigma_y_8bit": float(sigma_8bit[0].mean()),
        "chroma_luma_correlation": chroma_luma_correlation,
        "encoded_bytes": os.path.getsize(encoded),
        "spatial": spatial,
        "commands": commands,
    }


def safe_ratio(candidate, reference):
    return candidate / reference if reference > 1e-12 else None


def format_ratio(value):
    return "n/a" if value is None else f"{value:.3f}"


def compare_fixture(name, spec, work, nvencc, aom, denoiser):
    fixture = os.path.join(work, name)
    os.makedirs(fixture)
    source_y4m = os.path.join(fixture, "source.y4m")
    source_raw = os.path.join(fixture, "source.yuv")
    ideal_clean = os.path.join(fixture, "ideal-clean.yuv")
    ideal_clean_y4m = os.path.join(fixture, "ideal-clean.y4m")
    nvenc_clean_y4m = os.path.join(fixture, "nvenc-clean.y4m")
    nvenc_clean_raw = os.path.join(fixture, "nvenc-clean.yuv")
    nvenc_table = os.path.join(fixture, "nvenc.tbl")
    aom_nvenc_table = os.path.join(fixture, "aom-nvenc-clean.tbl")
    aom_ideal_table = os.path.join(fixture, "aom-ideal-clean.tbl")

    kat.apply_spec(spec)
    expected, _ = kat.generate(name, spec, source_y4m, ideal_clean)
    frames = spec.get("frames", kat.FRAMES)
    commands = {"source_to_raw": convert_y4m_to_raw(source_y4m, source_raw, kat.BITS)}
    commands["ideal_clean_to_y4m"] = convert_raw_to_y4m(
        ideal_clean, ideal_clean_y4m, kat.W, kat.H, frames, kat.BITS)
    commands["nvenc"], nvenc_entries = run_nvenc(
        nvencc, source_y4m, nvenc_clean_y4m, nvenc_table, kat.BITS, denoiser)
    commands["nvenc_clean_to_raw"] = convert_y4m_to_raw(
        nvenc_clean_y4m, nvenc_clean_raw, kat.BITS)
    separation = quality_metrics.separation_metrics(
        source_raw, ideal_clean, nvenc_clean_raw, kat.W, kat.H, kat.BITS,
        first_frame=min(kat.SKIP, max(frames - 1, 0)))
    commands["aom_nvenc_clean"], aom_nvenc_entries = run_aom(
        aom, source_raw, nvenc_clean_raw, aom_nvenc_table,
        kat.W, kat.H, kat.BITS)
    commands["aom_ideal_clean"], aom_ideal_entries = run_aom(
        aom, source_raw, ideal_clean, aom_ideal_table,
        kat.W, kat.H, kat.BITS)

    synthesis = {
        "nvenc": synthesize_table(
            nvencc, ideal_clean_y4m, nvenc_table,
            os.path.join(fixture, "synth-nvenc"), kat.BITS, frames),
        "aom_nvenc_clean": synthesize_table(
            nvencc, ideal_clean_y4m, aom_nvenc_table,
            os.path.join(fixture, "synth-aom-nvenc-clean"), kat.BITS, frames),
        "aom_ideal_clean": synthesize_table(
            nvencc, ideal_clean_y4m, aom_ideal_table,
            os.path.join(fixture, "synth-aom-ideal-clean"), kat.BITS, frames),
    }
    nvenc_sigma = synthesis["nvenc"]["mean_sigma_y_8bit"]
    aom_nvenc_sigma = synthesis["aom_nvenc_clean"]["mean_sigma_y_8bit"]
    aom_ideal_sigma = synthesis["aom_ideal_clean"]["mean_sigma_y_8bit"]
    for synthesized in synthesis.values():
        synthesized["spatial"]["spectrum_similarity_to_source"] = (
            quality_metrics.spectrum_similarity(
                synthesized["spatial"]["spectrum"], separation["true_spectrum"]))

    result = {
        "name": name,
        "bits": kat.BITS,
        "width": kat.W,
        "height": kat.H,
        "frames": frames,
        "injected_sigma_y_8bit": float(expected[0].mean() / kat.DS),
        "commands": commands,
        "tables": {
            "nvenc": nvenc_entries,
            "aom_nvenc_clean": aom_nvenc_entries,
            "aom_ideal_clean": aom_ideal_entries,
        },
        "separation": separation,
        "synthesis": synthesis,
        "synthesis_ratios": {
            "model_fit": safe_ratio(nvenc_sigma, aom_nvenc_sigma),
            "separator": safe_ratio(aom_nvenc_sigma, aom_ideal_sigma),
            "end_to_end": safe_ratio(nvenc_sigma, aom_ideal_sigma),
            "nvenc_to_injected": safe_ratio(
                nvenc_sigma, float(expected[0].mean() / kat.DS)),
            "aom_ideal_to_injected": safe_ratio(
                aom_ideal_sigma, float(expected[0].mean() / kat.DS)),
        },
        "comparisons": {
            # Same measured source-minus-NVEnc-clean residual.  Differences
            # here belong to parameter fitting/quantization, not denoising.
            "model_fit": comparison(nvenc_entries, aom_nvenc_entries),
            # Same libaom fitter, different clean bases.  This isolates how
            # much of the known grain NVEnc's separator actually extracted.
            "separator": comparison(aom_nvenc_entries, aom_ideal_entries),
            "end_to_end": comparison(nvenc_entries, aom_ideal_entries),
        },
    }
    ratios = result["synthesis_ratios"]
    print(f"  {name}: model={format_ratio(ratios['model_fit'])} "
          f"separator={format_ratio(ratios['separator'])} "
          f"end-to-end={format_ratio(ratios['end_to_end'])} "
          f"NVEnc/source={format_ratio(ratios['nvenc_to_injected'])}")
    return result


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aom-noise-model",
                        default=os.environ.get("AOM_NOISE_MODEL", ""),
                        help="libaom examples/noise_model binary")
    parser.add_argument("--aom-revision",
                        default=os.environ.get("AOM_NOISE_MODEL_REVISION", "unknown"))
    parser.add_argument("--nvencc", default=os.environ.get(
        "NVENCC", os.path.join(REPO, "build-fgs-cuda", "nvencc")))
    parser.add_argument("--denoiser", choices=("fft3d", "bilateral", "motion"),
                        default="fft3d")
    parser.add_argument("--tests", default=DEFAULT_TESTS)
    parser.add_argument("--output", required=True, help="JSON result path")
    parser.add_argument("--keep-work", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    nvencc = os.path.abspath(args.nvencc)
    aom = os.path.abspath(args.aom_noise_model) if args.aom_noise_model else ""
    for label, path in (("NVEncC", nvencc), ("libaom noise_model", aom)):
        if not path or not os.path.isfile(path) or not os.access(path, os.X_OK):
            sys.exit(f"{label} binary not found or not executable: {path or '(unset)'}")
    names = [name.strip() for name in args.tests.split(",") if name.strip()]
    invalid = [name for name in names if name not in kat.TESTS]
    if not names or invalid:
        sys.exit(f"unknown fixture(s): {','.join(invalid) if invalid else '(empty)'}")

    work = tempfile.mkdtemp(prefix="nvenc-fgs-reference-")
    report = {
        "schema": 1,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repository_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "denoiser": args.denoiser,
        "nvencc": {"path": nvencc, "sha256": sha256(nvencc)},
        "libaom": {
            "path": aom,
            "sha256": sha256(aom),
            "revision": args.aom_revision,
        },
        "tests": [],
    }
    failed = False
    print("== libaom reference comparison ==")
    try:
        for name in names:
            try:
                report["tests"].append(compare_fixture(
                    name, kat.TESTS[name], work, nvencc, aom, args.denoiser))
            except Exception as error:
                failed = True
                report["tests"].append({"name": name, "error": str(error)})
                print(f"  {name}: ERROR: {error}", file=sys.stderr)
        output = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w") as destination:
            json.dump(report, destination, indent=2, sort_keys=True)
            destination.write("\n")
        print(f"report: {output}")
        if args.keep_work:
            print(f"work: {work}")
    finally:
        if not args.keep_work:
            shutil.rmtree(work)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
