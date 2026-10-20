# R9: texture loss occurs across several boundaries

The exact R8 PSYEX encode is now observed at original input, packed EncDec
coding input, complete reconstruction before loop filtering, and final output.
Both observation-off and observation-on reproduce the complete original
336-frame IVF and application reconstruction exactly. Independent review admits
the trace and analysis. This is a diagnostic of **E05 scored frame120/input216**,
not a new encode candidate or a five-frame average.

| Luma HF amplitude | Original | Coding input | Pre-loop | Post-loop |
|---|---:|---:|---:|---:|
| Shirt | .606320 | .441324 | .093667 | .054543 |
| Background | 1.676388 | 1.665486 | 1.280496 | .847762 |
| Face | 2.700847 | 2.691176 | 2.454111 | 2.150404 |

The shirt already loses27.21% of original amplitude before EncDec, but the
larger remaining loss occurs during coding: its pre-loop amplitude is84.55%
below original. Source HF correlation falls from.89655 in coding input to
.00818 pre-loop and.01779 post-loop. This is not merely a uniformly attenuated,
faithful texture. A filter-only explanation fails for this frame.

Background coding input is much closer to original: amplitude−.65% and source
HF correlation.99803. Pre-loop amplitude is−23.62%, with ACF1 error.14187 and
source HF correlation.53894. Post-loop amplitude falls to−49.43%, ACF1 error
.19030 and correlation.51743. Thus the coding and filter boundaries both matter;
the earlier shirt preprocessing loss cannot explain the background result.

Filtering is not uniformly harmful. Shirt ACF1 error improves from.19652 to
.04362, while its amplitude falls further. Across all858 frozen tiles, mean
MSE improves3.68201→3.48966 and p95 improves9.89637→9.13471; mean HF absolute
error worsens.43711→.58900 and ACF1 error worsens.23072→.25514. These tradeoffs
are why neither MSE nor texture amplitude alone is an acceptance test.

All858 original frame120 tiles and all ten complete/outside group definitions
are retained. There are120 edge,480 flat-texture and258 other tiles; **zero
frozen quiet tiles occur in this frame**. The complete R8 window's quiet and
temporal evidence remains authoritative. No quiet-region, motion or whole-window
preservation inference follows from R9. The parent inspected labeled native
geometry luma crops only; their rounded8-bit display is explicitly distinguished
from exact10-bit raw samples. No playback was observed.

## Admission and corrections

One accepted attempt, generation0, contains510 distinct64-pixel SB records
covering every visible Y/U/V sample exactly once, one complete pre-loop frame,
one post-loop frame, and the terminal record:513 records total. The runtime
rejects SB-based deblocking, grain, resize and super-resolution. Frame-level
filtering cannot start before the captured last-SB barrier. Post-loop samples
equal the independently decoder-admitted R8 frame216 in every plane.

The input differs from original in55.64% of luma samples, with MSE.175784 and
maximum difference5.5 in8-bit-equivalent levels. The trace records actual packed
EncDec input; it does not prove the samples used by every earlier search stage.
The observed preprocessing cannot yet be attributed to one component.

Independent implementation review required vertical allocation bounds and
removal of a quantizer field that would have described the next recode attempt.
Both were fixed before build. Validator review required an explicit rejection
of Python optimization and a fixed completed-build manifest hash.

The first admission attempt correctly stopped on our incorrect interpretation
of SVT's `show_existing_frame` member. Despite its misleading header comment,
the code stores a3-bit DPB slot there, separately from the show-existing flag.
The validator now checks0..7 and exact pre/post equality. Activation was not
captured; this raw member may be inactive/stale and is not used to infer a
bitstream event. Independent source review accepted this correction without
changing the trace, build, replay or quality criteria.

The worker's analysis drafts required corrections to duplicated metric logic,
group semantics, a nonexistent dictionary field and double division in luma
rendering. The integrated script uses the established `paired` function,
explicit nullable counts and exact frozen source descriptors. Functional checks
exercise complete/outside groups, constant ACF, self-error, rendering scale and
optimization rejection. Nine malformed trace variants are rejected; an in-range
post-loop pixel mutation parses but would fail the separate exact-frame binding.
These synthetic fault probes are not encode observations.

## Scope, cost and next discriminator

Confidence is high for the measured boundaries of this one frame and exact
policy. R9 does not separate prediction, partition/search, scalar quantization,
coefficient optimization or skips within the coding boundary. It supplies no
per-TU realized quantizer, final search-route survival or local coded-bit cost.
It does not prove a codec limit or general source-rate infeasibility.

Because the output is unchanged, the actual R8 scored rate remains
**9.6279048Mbps**,99.4976% of original, and full336 rate10.25718343Mbps.
The original two-pass cost remains370.33577s for336frames. Diagnostic pass2
off/on replays cost315.34260s/312.55793s on nice10/CPU0–7; these are not replacement
candidate-speed measurements. Complete R8 GPU scores are reused, not rerun.

The next primary question is which final committed blocks/TUs own the remaining
coding loss. Capture final predictor-only/skip versus nonzero residual coverage,
mode/transform/EOB and quantizer provenance, joining the exact pre-loop surface.
A stored qindex or a stale coefficient buffer is insufficient evidence of actual
quantization. The implementation must account for MD reuse before making such
claims. Public TF-off remains a separate possible intervention; it also changes
reference/analysis behavior and would not isolate the dominant coding loss.

No candidate qualifies, no production proposal is supported, and no technical
blocker or required human playback has been established.

## Evidence and reproduction

Use [compact measurements](psyex-boundary-result.json),
[admission](psyex-boundary/admission.json),
[independent outcome review](psyex-boundary/outcome-review.md),
[implementation review](psyex-boundary/implementation-review.md),
[validator review](psyex-boundary/validator-review.md) and
[analysis review](psyex-boundary/analysis-review.md).
The [contract](ROUND9_BOUNDARY_CONTRACT.md) and
[private build package](psyex-boundary/README.md) fix scope and provenance.

Session root:
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`.
R9 artifacts are in `parent/psyex-boundary-r9/`: full source/build manifests,
logs, binaries, off/on receipts, `runs/on-1/boundary.bin`,
`admitted-1/records.json`, its four stage `.yuv` files, `analysis-1.json`,
`visuals-1/` and fault-check receipts.
Prior archives remain immutable.

Decisive hashes:

- Trace: `023247030b240a0ec68d88c39d5aef365fb06bb9e64a411aabdbbc6c8c491b8b`.
- Full admission: `f6a7a6d3221f15fb789419a43cd3f1b61372ffb99e325cd1ee131962ed5be7fc`.
- Full analysis: `b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5`.
- App: `bcb5321635dd391199eb9b440015ad3061f042023a45bab31f37f5791fb9ff69`.
- Library: `481c93f01a807d2c73ba73678946d1f0809cd9207ee873ae9ff53674374767bf`.

Actual invocation pattern, with repository report directory as working directory:

```bash
python3 replay_psyex_boundary.py off off-1 APP_SHA LIBRARY_SHA
python3 replay_psyex_boundary.py on on-1 APP_SHA LIBRARY_SHA
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" \
  validate_psyex_boundary.py off-1 on-1 \
  "$OBS/completed-build-pins.json" "$OBS/admitted-1"
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" \
  check_psyex_boundary_admission.py "$OBS/runs/on-1/boundary.bin" \
  "$ROOT/worker/psyex-r8/runs/e05-1440/psyex-1x1/recon.yuv" "$OBS/fault-checks-1"
nice -n 10 taskset -c 8-11 "$ROOT/analysis-venv/bin/python" \
  analyze_psyex_boundary.py "$OBS/admitted-1/admission.json" \
  "$OBS/analysis-1.json" --plot-dir "$OBS/visuals-1"
```

Set ROOT to the session root, OBS to its `parent/psyex-boundary-r9` directory,
and app/library hashes to the exact values above. Outputs are deliberately
fresh-only; use new tags/directories for a new validation and never overwrite
preserved evidence.
