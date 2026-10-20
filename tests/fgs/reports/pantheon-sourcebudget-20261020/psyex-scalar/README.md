# R12 reproduction and provenance

Scratch:
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/parent/psyex-scalar-r12`.
The full result, native arrays, visuals, intermediate revisions and private
library remain at the exact hash-bound paths in `../psyex-scalar-result.json`.
Session archival remains pending active investigation. R11 and earlier evidence
remain immutable.

`build.py` reads the exact R11 Ninja library object list and compiler definitions,
verifies its complete source manifest, and links `native.c` into a new private
library. It never rebuilds R11. Completed build2 binds all objects, source,
compiler, commands and before/after identities. A fresh reproduction needs fresh
output paths and explicitly regenerated identities; old pins cannot be copied
onto a different binary.

The helper uses direct native C and initialized native runtime high-bit-depth
FP/B facades, plus C and native runtime inverse. Every arm must agree exactly.
The wrapper copies inputs to private aligned storage and verifies their integrity.
Only the observed eight transform sizes are supported by the direct inverse path.
Zero EOB returns the predictor. Nonlossless R11 state is inherited and required.

Observed commands, already complete:

```sh
ROOT=/tmp/downloads/codex-work/pantheon-sourcebudget-20261020
P="$ROOT/parent/psyex-scalar-r12"
python3 "$P/build.py"
"$ROOT/analysis-venv/bin/python" "$P/run.py"
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" "$P/render.py"
```

`run.py` records actual outer argv, return code, elapsed time and immutable
dependencies; `experiment.py` records its actual inner argv and result. All
baseline controls complete before either novel arm is calculated. The result
requires every C/runtime comparison to pass. Failures never yield an admitted
result. Scripts reject optimized Python.

`native-arrays.npz` preserves flat q/DQ/native-inverse arrays for all three arms.
The detailed result maps each invoked token to coefficient and pixel offsets,
native dimensions and actual tables. The 720 uninvoked owners retain R11 native
predictors. Full native arrays are preserved; only visible support is clipped
for metrics. Original, coding-input and local diagnostic semantics are explicit.

Build1 was preparation only and produced no trace outcome. It was superseded
after design review required C/runtime comparisons beyond the baseline. The
pre-fix driver is preserved for the baseline-table alias correction. No encode,
production binary, library media or configuration was changed.
