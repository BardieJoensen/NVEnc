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

Real-title testing is handled separately by `campaign.py`; source paths in that
script are local configuration and media is never committed.
