# AV1 film-grain analyzer tests

The synthetic tests exercise the CUDA AV1 film-grain analyzer without private
media. The full local gate also requires the pinned real-film fixtures documented
in [FIXTURES.md](FIXTURES.md). Set `NVENCC` when the binary is not at
`build-fgs-cuda/nvencc`.

**Read `TIERS.md` first.** It says which tier catches which class of defect,
and why the GPU tier is not and cannot be hosted in CI.

## Automated entry points

| | command | where it runs |
|---|---|---|
| tier 1 | `bash tests/fgs/run_cpu_tests.sh` | GitHub Actions, every push |
| tier 1 meta-check | `bash tests/fgs/selftest_can_fail.sh` | GitHub Actions, every push |
| tier 2 quick | `tests/fgs/local_gate.sh --quick --candidate-commit HEAD` | this box; pre-push hook |
| tier 2 full | `tests/fgs/local_gate.sh --full --candidate-commit HEAD` | this box, before shipping a build |

The gate requires an explicit candidate and defaults to the production bilateral
denoiser. `--candidate-commit` builds that exact commit and its pinned dependencies;
`--candidate-nvencc /path/to/nvencc` tests an existing binary. Reports record the
commit (when supplied), binary SHA-256, version, fixture hashes, and denoiser.
`--reference-control r4050` is only for validating the historical control.

Install the pre-push hook with:

```sh
ln -sf ../../tests/fgs/hooks/pre-push .git/hooks/pre-push
```

## Fast CPU tests

The synthesis-recovery tests replay the reported short accepted/rejected fit
patterns and require sustained usable analysis after a source-preserving gap.
Recovery survives low-confidence model-history resets. The ordinary safety
checks still reject unsafe grain immediately; this policy does not guarantee
that every possible future grain transition is invisible.

The full local gate also runs `flicker_regression`: it decodes aligned Amphibia,
Lost Tapes and South Park frames against pinned originals and repaired negatives,
checks originally uniform patches, and bounds whole-picture source error.
The retained defect must fail. A missing fixture is an error. The thresholds
are specific to these SDR/QVBR34 examples, and are not a library-wide visibility
score. This development test does not add work to routine Tdarr validation.

```sh
bash tests/fgs/run_cpu_tests.sh
```

This builds and runs the model-solver and `filmgrn1` parser behavior tests,
plus the Python descriptor and model-gate tests.

The feedback-stability regression uses AV1 coefficient vectors from the
September 2026 ripple report, a neighbouring stable model, and unit-pole
boundaries. The solver test also constructs finite-gain training equations
whose synthesized recurrence is unstable. The 34:06 jacket regression is
strictly stable but produces a diagonal mesh: stability alone was insufficient.
The production guard also bounds every horizontal and between-row pole below
0.95, conservatively rejecting slowly decaying feedback and preserving the
source frame. The 34:24 regression also requires a spectral check: a strongly
directional peak away from DC must not exceed both 16 times the spectrum mean
and 4 times its radial-band mean. Broad fine/coarse grain remains eligible.
This is a synthesis policy, not a bitstream-conformance rule or
a guarantee against all perceptual defects. The guard checks the
quantized coefficients on all active planes; failed certification preserves
the original frame and bypasses the temporal model-hold fallback.

For an existing AV1 file, `scan_bitstream.cpp` inspects its emitted grain
headers without decoding pixels. It exits 1 on the first uncertified model,
0 after a complete error-free scan meeting the synthesis decay policy, and 2
on a parsing or grain-syntax error. Scaling points must be strictly ordered,
and 4:2:0 must enable both chroma components or neither. These checks also cover
zero-strength models, because a decoder can reject their syntax regardless of
visible strength. `--syntax-only` checks grain headers without evaluating AR
quality and reports `valid_syntax`, never a quality verdict. Use `--stability-only` for the mathematical unit-circle
criterion. The full local gate encodes the pinned 150-second Gentlemen source,
requires a known visible mesh to fail, decodes every candidate frame, and
checks source fidelity at all three reported/reproduced scenes. The two
jacket fits must emit no synthesized luma grain; an earlier shot may acquire
a fresh ordinary-grain fit after the rejected temporal state is cleared.
An independent decoded-grain concentration check must accept that shot and
reject the retained visible mesh. All 3,600 displayed frames are additionally
measured in luma, red and blue display channels against a pinned reviewed
positive. This detects relocated/repeated texture, amplitude changes, and
changes in when grain switches on or off; source comparisons at the three
regression timestamps include the raw U/V planes too. These are fixture-specific
change detectors: an intentional model change requires fresh baseline review.
They do not provide universal visibility thresholds. The gate retains the
ordinary-grain KAT and libaom positive controls.
Zero-strength planes are ignored unless their raw grain contributes
to an active coupled plane. The
scanner omits unrelated metadata OBUs from its packet copies (some older
files contain invalid timecodes); the media file is never modified, and
every sequence/frame header is retained. An
uncertified model identifies a file for further inspection; it does not by
itself measure the visible strength of an artifact. Build it with FFmpeg
development libraries and the `trace_headers` bitstream filter available:

```sh
g++ -std=c++17 -O2 -I NVEncCore tests/fgs/scan_bitstream.cpp \
    -o /tmp/fgs-scan $(pkg-config --cflags --libs --static libavformat libavcodec libavutil)
/tmp/fgs-scan /path/to/episode.mkv
```

## Read-only decoded grain inspector

`tools/fgs/grain_inspect.cpp` measures decoder grain applied to the same decoded
picture, using dav1d's grain-off decode followed by `dav1d_apply_grain`. It writes
one CSV row per displayed frame, plus an explicit completion record. The tool
requires FFmpeg and dav1d development libraries:

```sh
g++ -std=c++17 -O2 -Wall tools/fgs/grain_inspect.cpp -o /tmp/fgs-grain-inspect \
    $(pkg-config --cflags --libs libavformat libavcodec libavutil dav1d)
/tmp/fgs-grain-inspect input.mkv output.csv
/tmp/fgs-grain-inspect input.mkv excerpt.csv 390 405
/tmp/fgs-grain-inspect --correlations input.mkv all-offsets.csv
```

The default compatibility method samples nine native 48x48 patches per frame. It converts grain-on
and grain-off pictures to approximate clipped RGB8 display values, subtracts
each patch mean, and measures RMS and directional autocorrelation. Red and blue
are display channels, not raw chroma planes. The output is a review index; it
cannot establish whether a whole film is damaged or justify replacing it.
HDR/BT2020 and non-I420 inputs need different display calibration and are
rejected. This does not measure lost source detail, and grain outside the sampled
patches can be missed. It is intended for background auditing and release tests,
not full-duration validation on every Tdarr job.

`--correlations` additionally emits all twelve signed autocorrelations per
channel (`acf_0` through `acf_11`), in offset order `(1,0), (0,1), (1,1), (-1,1),
(2,0), (0,2), (2,2), (-2,2), (3,0), (0,3), (3,3), (-3,3)`. Release tests compare
this vector: the strongest offset can swap at a near-tie without a meaningful
texture change. The default compact audit CSV remains unchanged.

`--extended` adds complete spatial coverage and SDR/PQ/HLG reference-display
measurements, including a separate green channel and local directional scores.
The new scores use PU21 units and must not reuse the legacy thresholds.
The [review tool guide](../../tools/fgs/README.md) includes bounded/resumable
window and batch commands, interactive heatmaps, display assumptions, performance
limits and calibration evidence. These diagnostics do not add pixel analysis to
ordinary Tdarr validation.

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

The experimental fidelity branch has a controlled detail/size experiment:

```sh
python3 tests/fgs/fidelity_compare.py --baseline /path/to/pinned-old-nvencc \
    --candidate /path/to/pinned-new-nvencc --output-dir /path/to/new-experiment
python3 tests/fgs/fidelity_regression.py /path/to/new-experiment/report.json
python3 tests/fgs/repeatability_regression.py /path/to/new-experiment/report.json
```

It measures known clean detail separately from independent grain on sixteen
deterministic sources, including a grain-strength transition, coarse grain,
asymmetric chroma, weak grain, moving/disappearing woven detail and 10-bit PQ. Arms include the old default,
old `retain=auto`, and new `retain=auto`. The candidate QP search stops at the
first encoding no larger than old auto, or reports that none fits by QP 32.
That is a discrete size bound, not an exactly matched rate. Weak grain and
temporal fallback checks reject the first prototype's observed regressions.
The fixture-specific checks do not establish universal perceptual quality.
The moving-detail projection is computed per frame before temporal aggregation;
otherwise a moving pattern can cancel in the average reference and hide damage.
Weak-grain controls require identical decoded bases and bound grain-amplitude
change; corrected strength-knot positions may change synthesized samples.

`--reuse-baseline /path/to/prior-experiment` reuses old arms only after checking
the binary, source geometry and hashes, encoded file and decoded pixel hashes.
Source files and all candidate encodes are retained. Do not compare small-frame
execution times as a throughput benchmark.

For an implementation change expected to preserve decoded pixels, replay all
fixed-QP and selected size-bound arms from a completed experiment:

```sh
python3 tests/fgs/fidelity_replay.py --prior /path/to/completed-experiment \
    --candidate /path/to/new-nvencc --scanner /path/to/fgs-scan \
    --output-dir /path/to/new-replay
```

The replay verifies source/old-output identities, exact full decoded hashes in
both grain modes and complete syntax scans. Its report links the two binary
identities explicitly. It never relabels the original quality measurements.

For the existing private real-film fixtures and a longer ABBA timing run:

```sh
python3 tests/fgs/fidelity_real.py --baseline /path/to/pinned-old-nvencc \
    --candidate /path/to/pinned-new-nvencc --scanner /path/to/fgs-scan \
    --output-dir /path/to/new-real-experiment
```

This verifies source hashes, decodes every output with grain on and off, checks
the full grain syntax/texture scan, compares default decoded pixels, and checks
the original jacket regression. Real-film grain has no known clean ground
truth; the pilot does not infer better grain texture from lower pixel error.
Timing on a shared GPU includes other workloads. See
`FINDINGS-2026-09-08-FIDELITY.md` and `FINDINGS-2026-09-08-REPEATABILITY.md`
for the measured gains and trade-offs.

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
See `FINDINGS-2026-07-31-MODEL-STATS.md` for the model-stats and flat-metrics
speed-ups, the setup/accumulation timing method, seven measured CUDA variants
(five rejected), and why fusing the two bilateral passes is not worth doing.

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
`taxi-metric-gamer.json` from the [pinned fixture set](FIXTURES.md) is stage
`model_negative` of the local gate.

### Measured size admission for fidelity trials

`trial_admission.py` consumes a **completed** `production_compare.py` report.
It verifies the expected candidate build, source and encoded-file hashes, both
full decodes, synthesis scans, timestamps and declared video properties. It also
probes both containers to require video-only AV1. The default byte limit is 10%
above the complete production-baseline encode of that same input.

```sh
python3 tests/fgs/trial_admission.py \
  --report /scratch/trial/report.json --case episode \
  --expected-candidate-sha256 CANDIDATE_BINARY_SHA256 \
  --output-dir /scratch/admitted/episode
```

Within budget, it writes an independent candidate copy and a decision receipt
in the new staging directory. Above budget, it writes `keep_source`, stages no
candidate and exits 3. Missing or changed evidence fails closed. It never raises
the quantizer, disables a fidelity safeguard, substitutes the cheaper baseline,
or replaces a library file. The source remains available in either case.

This is an additional **trial admission** gate, not a perceptual-quality score or
an enabled Tdarr policy. It does not compare against the source's file size and
does not extrapolate a clip to a whole title. A hard limit relative to the old
encoder requires its complete measured output (or an independently verified,
matching existing baseline); short samples and `retain-max` cannot supply that
guarantee. Full paired trials have an extra encode cost. Reusing a pinned,
completed baseline avoids that encode, while keeping fresh validation.

### Full-frame HDR metadata traces

`hdr_metadata_trace.py record` decodes every frame with FFprobe, requiring the
expected source SHA-256 and frame count. Its streamed trace covers timestamps,
mastering display and content light metadata, and parsed Dolby Vision/HDR10+
fields exposed by the decoder. `compare` requires complete, unchanged traces and
checks stream color properties and Dolby Vision configuration as well.

```sh
python3 tests/fgs/hdr_metadata_trace.py record \
  --source /scratch/source.mkv --expected-sha256 SOURCE_SHA256 \
  --frames FRAME_COUNT --output-dir /scratch/source-metadata
python3 tests/fgs/hdr_metadata_trace.py compare \
  --reference /scratch/source-metadata --candidate /scratch/candidate-metadata
```

MDCV coordinates and luminance are compared in AV1's specified fixed-point
representations: 1/65536 for chromaticities, 1/16384 for minimum luminance, and
1/256 for maximum luminance. This accepts the required format rounding without
accepting missing metadata. HEVC's raw RPU side-data buffer is not emitted by the
AV1 decoder; the comparison instead requires the parsed Dolby Vision fields.
The tested cross-codec configuration mapping is HEVC profile 8 without an
enhancement layer to AV1 profile 10. Other source-profile conversions require
separate evidence. These offline traces add no work to normal Tdarr validation.

Keep the recorder's default grain application enabled. The local FFprobe build
used for the September 2026 trials fails when its XML printer encounters
exported film-grain side data with grain application disabled. The normal XML
path completed all full HDR comparisons. Separate pixel-only grain-off decodes
remain part of `production_compare.py` and also pass.

The completed size admission, full HDR and repeatability follow-up is documented
in [the September 9 findings](FINDINGS-2026-09-09-TRIALS.md).

### Post-encode Tdarr replay

`tdarr_trial_pipeline.js` takes an admitted video through a pinned copy of the
actual Tdarr stream-policy, Opus, chapter/attachment, size and final-validation
plugins. Run it inside the matching Tdarr runtime image, with original media,
admitted video and evidence mounted read-only, and only a fresh scratch tree
writable. It does not run replacement or notification plugins.

```sh
node tests/fgs/tdarr_trial_pipeline.js /evidence/replay-config.json
node --test tests/fgs/test_tdarr_trial_pipeline.js
```

The configuration requires `admission`, `expected_candidate_sha256`,
`plugins_root`, `plugin_snapshot`, `plugin_snapshot_sha256`,
`audio_policy_config`, `audio_policy_sha256`, `original_language`,
`scratch_root`, `output_dir` and `expected_streams`. The snapshot supplies a
`plugin_hashes` mapping of relative plugin paths to SHA-256. Track expectations
list ordered audio `{codec, channels, language, default}`, subtitles
`{codec, language}`, and the chapter count. Use expected results established
from the fixture rather than generated by the policy being tested. HDR inputs
also require `hdr_comparison`, the completed source-to-candidate metadata
comparison. The runtime needs FFmpeg, FFprobe, mkvmerge, packet-audit and
fgs-scan at the paths expected by the pinned plugins.

The explicit fixture language substitutes for the Arr metadata lookup. The
harness translates the host source path to Tdarr's node path and requires a
resolved policy; it cannot count a preserve-everything fallback as an Opus or
language-filtering test. After assembly it checks the explicit track results,
the complete admitted video packet hash, every video timestamp, codec headers
and declared color/geometry before running the production validator. The only
allowed timing change is a common origin shift of at most 10 ms, with at most
1 ms additional timestamp rounding. The production validator independently
checks source-relative alignment of the retained tracks.

`tdarr_trial_controls.js CONFIG.json FRESH_OUTPUT_DIR FONT.ttf` runs real
container controls in the same runtime: a 7 ms common shift passes, a 250 ms
shift and substituted baseline video fail, and authoritative chapters plus a
font attachment survive reattachment with the font's bytes unchanged. It needs
mkvextract in addition to the replay dependencies. The short timing fixture
uses 72 copied packets; the substitution control compares complete videos,
because different encodes can have identical opening packets.

These are offline integration tools. They reuse already completed video
encodes and do not exercise the complete Tdarr scheduler or perform another
GPU encode. `ready_for_pilot_review` means the final scratch artifact passed;
it does not install a new encoder or enable the measured-baseline size gate in
production. For a future isolated encoder pilot, sample and full-encode
arguments must both specify the tested
`denoise=auto,chroma=auto,denoiser=bilateral,retain=auto,retain-max=0.1`, and the
same immutable candidate must resolve at `/usr/bin/nvencc` for sampling,
preflight and the full encode. The active source-relative size policy remains
distinct from the trial's measured-baseline limit.

Completed full-title results and measured validation times are recorded in
[the post-encode integration findings](FINDINGS-2026-09-09-INTEGRATION.md).

### Mixed-source grain and partial image edges

The full developer gate includes `mixed_source`. It generates deterministic
noisy backgrounds with clean foreground and colour regions, including a
disappearance/reappearance and a separate brightness found only in a partial
bottom block. Both 8-bit and 10-bit outputs must keep added grain and raw-filter
error below 0.3 native eight-bit codes in the clean regions. Genuine grain at
other levels must remain present. A conventional NVENC control separates lossy
prediction/quantization from FGS; encoded clean-region variation and mean error
may exceed that matched control by no more than 0.3 codes. Real-source flash
regression thresholds remain unchanged.

```sh
python3 tests/fgs/mixed_source_regression.py --nvencc /path/to/candidate --output /fresh/results
python3 tests/fgs/mixed_source_regression.py --nvencc /path/to/3778447e --expect-rejected --output /fresh/negative
```

The full gate uses the immutable retained 3778447e binary as its negative.
On another installation, set `FGS_GATE_MIXED_SOURCE_NEGATIVE` and
`FGS_GATE_MIXED_SOURCE_NEGATIVE_SHA256` to an explicitly retained build of that
revision. This reference must not follow the production encoder path. These
checks run in the developer gate, not once per file in the Tdarr flow.
