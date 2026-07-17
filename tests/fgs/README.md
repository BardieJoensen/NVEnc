# AV1 film-grain analyzer tests

These tests exercise the CUDA AV1 film-grain analyzer without requiring any
copyrighted media. Set `NVENCC` when the binary is not at
`build-fgs-cuda/nvencc`.

## Fast CPU tests

```sh
bash tests/fgs/run_cpu_tests.sh
```

This builds and runs the model-solver and `filmgrn1` parser behavior tests.

## GPU known-answer tests

```sh
python3 tests/fgs/fgs_kat.py
```

The generated fixtures cover white and correlated grain, intensity-dependent
strength, luma/chroma correlation, clean material, HDR, scene cuts, and fixed
residual retention. The tests require FFmpeg with a dav1d decoder exposing the
`filmgrain` switch.

## Retention sweep

```sh
python3 tests/fgs/retain_sweep.py --bits both
```

This reports base-layer retention, source-position correlation, synthesized
grain, total played-out grain, and encoded bytes for each retain value.

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

Real-title testing is handled separately by `campaign.py`; source paths in that
script are local configuration and media is never committed.

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
