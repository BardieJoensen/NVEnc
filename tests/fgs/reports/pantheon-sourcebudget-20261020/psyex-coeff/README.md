# R11 reproduction and evidence

Canonical scratch is
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/parent/psyex-coeff-r11`.
It remains active until the investigation reaches a valid stopping point and
uses the established archive workflow. Old evidence is immutable.

This directory preserves the actual source patch, observer, scripts, source/build
identities, receipts and independent reviews. The full 19.58 MB coefficient
trace, 18.76 MB boundary trace, 6.36 MB token map, 54.04 MB detailed analysis,
native-luma panels and output media remain at the hash-bound scratch paths in
`../psyex-coeff-result.json`.

The canonical `coeff-r9-relative.patch` applies to the exact R9 source manifest
`12f345e1f738b97fd00d9b9b2978864c53df995ad7590374edc21d31004124ce`.
The resulting 1,790-file source manifest is
`c4a264dfa50cf24e5411c27719cf9e7ac118357ee8f0ee133e5a371854065b55`.
The intermediate scratch `coeff.patch` omits untracked files and is not canonical.
Build pins bind the app, loaded private library, compiler tools, exact build
commands, source before/after and outputs. Do not transplant old pins to a new
build. Fresh reproductions must regenerate reviewed identities in a new directory.

Observed commands, already completed and not needing unchanged reruns:

```sh
ROOT=/tmp/downloads/codex-work/pantheon-sourcebudget-20261020
P="$ROOT/parent/psyex-coeff-r11"
bash "$P/build_runner.sh"
python3 "$ROOT/worker/psyex-r11-replay/replay.py" off off-1
python3 "$ROOT/worker/psyex-r11-replay/replay.py" on on-1
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" "$P/validate.py" \
  "$P/runs/off-1" "$P/runs/on-1" "$P/admitted-1" \
  --pins-sha f32ace44e5e449ce0898b6566cc9bb3195a8daa2fcb0b9d7f20b0e0d8b3c54d8 \
  --replay-sha f9023e688eeacbc0c1b42defe879c0a3d93be072ea8e77e5fb4f565a4bb96747
"$ROOT/analysis-venv/bin/python" "$P/run_analysis.py"
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" "$P/fault_checks.py" \
  "$P/runs/on-1/coeff.bin" "$P/fault-run-1"
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" "$P/render.py"
```

Replay executes the exact R8 second pass and reuses verified first-pass statistics.
Off/on IVF and all336 reconstructed frames equal R8. Admission2 corrects only
native coefficient storage and effective matrix interpretation; failed admission1
is preserved. The source observer and encoded bytes did not change.

The build-pinned schema remains unchanged. Its cross-decoder normalization is
documented by `round11-dq-mismatch-review.md`: transpose adjusted native
`min(h,32) × min(w,32)` arrays to libaom storage. Actual native stage arrays remain
in SVT order. One-dimensional transforms use flat matrix15 regardless of the
frame-level matrix metadata.

The analyzer reads the admitted trace arrays, preserves all native TU domains,
clips only visible support at frame boundaries, and references original luma.
Small intersections can lack ACF support; null values and support are explicit.
The accompanying raw warnings for empty high-lag support do not create admitted
NaN values. Raw/scalar mosaics are local diagnostics, not coherent encodes.

Failed compiler state, rejected replay/analyzer drafts and the prior direct-layout
validator are retained in scratch for audit. Only the pinned final scripts are
authoritative. No production files were altered.
