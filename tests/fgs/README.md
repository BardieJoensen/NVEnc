# AV1 film-grain analyzer tests

These tests exercise the CUDA AV1 film-grain analyzer without requiring any
copyrighted media. Set `NVENCC` when the binary is not at
`build-fgs-cuda/nvencc`.

**Read `TIERS.md` first.** It says which tier catches which class of defect,
and why the GPU tier is not and cannot be hosted in CI.

## Where the measurement docs live

They are **not in this repo**. `TIERS.md` and the FINDINGS files cite them by
bare filename, which is unresolvable from here and reads as "file not found":

| document | path |
|---|---|
| measurement campaign, metric behaviour | `/opt/docker-apps/docs/fgs-measurement-campaign.md` |
| open questions, blind-spot table, process rules | `/opt/docker-apps/docs/fgs-open-questions.md` |
| pipeline robustness backlog | `/opt/docker-apps/docs/video-pipeline-robustness-backlog.md` |
| evidence write-ups | `/opt/docker-apps/docs/evidence/` |

**Before interpreting any full-reference score on grainy content**, read the
SSIMULACRA2 section of `fgs-measurement-campaign.md`. SSIMULACRA2, VMAF and
Butteraugli are *inverse* to grain retention here — about -392 SSIMULACRA2
points per unit of retention — because synthesised grain is statistically
faithful but not pixel-identical, so a full-reference metric scores it as error
and ranks the encode that destroyed the most grain highest. The metric is valid
and useless for ranking, not broken. Use grain retention and no-reference CAMBI
to rank instead.

## Automated entry points

| | command | where it runs |
|---|---|---|
| tier 1 | `bash tests/fgs/run_cpu_tests.sh` | GitHub Actions, every push |
| tier 1 meta-check | `bash tests/fgs/selftest_can_fail.sh` | GitHub Actions, every push |
| tier 2 quick | `tests/fgs/local_gate.sh --quick` | this box; pre-push hook |
| tier 2 full | `tests/fgs/local_gate.sh --full` | this box, before shipping a build |

Install the pre-push hook with:

```sh
ln -sf ../../tests/fgs/hooks/pre-push .git/hooks/pre-push
```

## Fast CPU tests

```sh
bash tests/fgs/run_cpu_tests.sh
```

This builds and runs the model-solver and `filmgrn1` parser behavior tests,
plus the Python descriptor and model-gate tests.

## GPU known-answer tests

```sh
python3 tests/fgs/fgs_kat.py
```

The generated fixtures cover white and correlated grain, intensity-dependent
strength, luma/chroma correlation, fine-detail preservation, clean material,
HDR, scene cuts, fixed residual retention, and content-adaptive `retain=auto`.
The tests require FFmpeg with a dav1d decoder exposing the `filmgrain` switch.

## Retention sweep

```sh
python3 tests/fgs/retain_sweep.py --bits both
```

This reports base-layer retention, source-position correlation, synthesized
grain, total played-out grain, and encoded bytes for each retain value.  It
verifies the retention mechanism on synthetic grain; it does not say whether
synthesis is worth the bits on real material.

## Matched-bitrate routing comparison

```sh
python3 tests/fgs/matched_rate_sweep.py --clip <clip.mkv> --ref <ffvhuff-ref.mkv> \
    [--svt <same-size-svt.mkv>] [--rate 31700]
```

This encodes plain, fixed-retention, and `retain=auto` variants at one VBR
target and scores them against a reference, reporting grain energy (HF sigma)
and grain size (residual autocorrelation) next to the full-reference metrics.
Read those two together: full-reference metrics reward pixel-aligned grain and
are therefore biased against synthesis, while HF sigma alone cannot tell
correct grain from correctly-sized grain.  Requires copyrighted media, so it is
not part of the automated suite.

## Reproducible before/after benchmark

```sh
python3 tests/fgs/benchmark.py --output /tmp/fgs-before.json --label before
python3 tests/fgs/benchmark.py --output /tmp/fgs-after.json --label after \
    --compare-to /tmp/fgs-before.json
```

The JSON records the repository revision and status, encoder binary hash, GPU,
tool versions, complete suite output, durations, KAT summary metrics, and the
retention sweep. Keep the `before` file unchanged while developing; it remains
valid even after rebuilding `NVEncC` because the binary hash is embedded.

The checked-in `baselines/2026-07-17-fft3d.json` snapshot is the quality and
bitrate baseline for this branch before reference-driven analyzer changes. Add
new result files rather than overwriting it.

The corresponding optimized snapshot is
`baselines/2026-07-17-optimized.json`.  See
`FINDINGS-2026-07-17.md` for the synthetic and CUDA-scored real-title
before/after results, interpretation, and remaining limits.
See `FINDINGS-2026-07-29-PERFORMANCE.md` for the subsequent CUDA speed profile,
bilateral/FFT3D trade-off, coarse-grain diagnostic, and production metric
priorities.
See `FINDINGS-2026-07-30-TEXTURE.md` for the amplitude-independent real-film
texture detector, common-base NVEnc/libaom comparison, and r4047 labelled
negative.
See `FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md` FIRST if you are about to
quote a retention number: whole-frame HF sigma counts encoder ringing as grain,
and per-title retention scalars are single draws from distributions with sd up
to 0.746. It corrects several numbers in the 2026-07-31 documents and lists six
falsified hypotheses. `flat_retention.py` is the flat-block shared-mask
estimator.
See `FINDINGS-2026-07-31-GENERAL-LIBRARY.md` for six 1080p library-typical
titles at the production QVBR: a 17.4% corpus byte saving, large grain-retention
gains, but full-reference metrics favouring the plain arm because the FGS arm
spends 17.4% fewer bits. Needs a matched-byte re-run before it means anything.
See `FINDINGS-2026-07-31-ROUTING.md` for the matched-rate re-test of the
"heavy 35mm is better served by a plain tuned encode" conclusion, which no
longer holds: run it with `routing_check.py`.
See `FINDINGS-2026-07-31-MODEL-STATS.md` for the model-stats and flat-metrics
speed-ups, the setup/accumulation timing method, seven measured CUDA variants
(five rejected), and why fusing the two bilateral passes is not worth doing.
See `FINDINGS-2026-07-31-WIENER-PSD.md` for the coarse-grain plan: FFT3D's
Wiener gain uses a scalar noise power where libaom uses a per-bin PSD.
`wiener_psd_sim.py` reproduces the current 0.366 capture offline and measures
what a PSD derived from the already-available lag-one correlation would give.

Real-title testing is handled separately by `campaign.py`; source paths in that
script are local configuration and media is never committed.

## Grain-texture report

Grain energy and clean-base fidelity do not establish that synthesized grain
has the right spatial or temporal texture. Generate an amplitude-independent
texture report from aligned raw YUV420 streams with:

```sh
python3 tests/fgs/texture_report.py \
    --source-raw source.yuv --clean-raw clean-reference.yuv \
    --arm nvenc=nvenc-on.yuv,nvenc-off.yuv \
    --arm libaom=libaom-on.yuv,libaom-off.yuv \
    --width 3840 --height 2160 --bits 10 --frames 24 \
    --title taxi --build r4050 --output /tmp/taxi-texture.json
```

The source residual is `source - clean-reference`; each synthesized arm is
`grain-on - grain-off`. The evaluator freezes candidate-independent 32x32 flat
patches from the source/clean pair and calculates every descriptor separately
inside source-luma bands. It reports normalized radial spectra, lagged spatial
autocorrelation, anisotropy, and normalized local-energy flicker for both a
strict core mask and a relaxed mask. Empty or under-sampled luma bands are
`N/A`, never passes. The JSON also reports each comparison's absolute movement
between the two masks as a threshold-sensitivity diagnostic; it does not turn
that movement into another fixture-derived pass/fail bound.

The report keeps median sigma as an explicitly labelled energy diagnostic, but
does not use amplitude in any texture distance. Interpret energy with the
retention monitor and clean-detail substitution with the base-fidelity canary;
each detector answers one question.

For aligned media, let the wrapper decode all inputs and require a labelled
texture-difference pair to separate:

```sh
python3 tests/fgs/texture_media_report.py \
    --source source.mkv --clean corrected-clean.y4m \
    --arm corrected=corrected.mkv --arm widened=widened.mkv \
    --frames 24 --labelled-negative widened,corrected --require-common-base \
    --output /tmp/texture-negative.json
```

The labelled-negative gate validates detector sensitivity only. It requires
both masks to exceed a deliberately loose spectrum-TV or ACF-RMSE floor with
enough source-luma coverage; it does not claim either arm is closer to the
source. That remains a descriptor-by-descriptor interpretation alongside the
base-fidelity canary.

## libaom reference comparison

Build the pinned official libaom `noise_model` example outside this repository,
then compare NVEnc's complete analyzer with libaom on generated fixtures:

```sh
ref_dir=$(mktemp -d /tmp/aom-reference.XXXXXX)
rmdir "$ref_dir"
tests/fgs/build_aom_reference.sh "$ref_dir"
AOM_NOISE_MODEL="$ref_dir/build/noise_model" \
AOM_NOISE_MODEL_REVISION=18c52422b835ba6cdde1b2342d760c6037a7fd86 \
python3 tests/fgs/reference_compare.py --output /tmp/fgs-reference.json
```

The comparison uses libaom twice: once with NVEnc's emitted clean base to
isolate model-fitting differences, and once with the fixture's exact clean base
to expose separator loss. libaom remains an optional test tool and is not a
build or runtime dependency of NVEncC.

The JSON also records same-position grain extraction, edge and flat-region
clean-base error, systematic detail loss, radial spatial-spectrum similarity,
high-frequency energy, temporal correlation, luma/chroma correlation, and
decoded synthesized-grain strength. These are diagnostics rather than a single
combined quality score.

The checked-in `baselines/2026-07-17-libaom-reference.json` report records the
pinned libaom comparison before analyzer changes. Its actual synthesis results,
not scaling-point values alone, are the reference because AR coefficients also
change the final grain variance.

Run the real-film guard with `--texture` to add NVEnc and libaom synthesis from
the same clean input:

```sh
python3 tests/fgs/reference_compare_real.py \
    --nvencc /path/to/nvencc --aom-noise-model /path/to/noise_model \
    --frames 24 --denoiser bilateral --texture \
    --json-out /tmp/fgs-real-texture.json
```

The harness hashes both grain-off decodes and invalidates the texture result if
their base pixels differ. If libaom matches the source and NVEnc does not, that
is analyzer headroom. If both miss similarly, a compact-model limit is
plausible but not proven; establishing the format ceiling requires a separately
optimized best-fit AV1 model.

`local_gate.sh` provisions the pinned `noise_model` into
`${FGS_GATE_CACHE:-~/.cache/fgs-gate}` automatically, so the manual
`mktemp -d /tmp/...` recipe above is only needed for one-off work. The gate
pins libaom by *revision*, not by binary hash: a rebuild of the same source is
not bit-identical.

## Texture model gate

Grain energy, base fidelity and the texture report all take encoded media as
their subject. None of them can answer "should this set of AR coefficients be
accepted?", and on 2026-07-30 that gap became concrete: a directly optimized
model beat the texture report's gated descriptors by ~3x while being worse on
descriptors the gate does not measure.

```sh
python3 tests/fgs/model_gate.py \
    --source taxi_src.y4m --clean taxi_clean.y4m \
    --incumbent shipping.tbl --candidate proposed.json \
    --expect reject
```

Gated descriptors (radial spectrum TV, H/V autocorrelation over lags 1-8) may
only help a candidate. Held-out descriptors (gradient anisotropy, diagonal
lag-1 autocorrelation) may only veto one. `--expect` asserts the verdict, so a
labelled adversarial specimen can be used as a negative control rather than
merely documented. Exit status is 0 for ACCEPT, 1 for REJECT, 2 for an error;
with `--expect` it is 0 when the verdict matches and 1 when it does not.

The unit-testable core runs in CI (`test_model_gate.py`); the media-backed
assertion against
`/media/merged-storage/media/test-encodes/ceiling/taxi_ceiling_q.json` is stage
`model_negative` of the local gate.
