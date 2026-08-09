# Strength provenance isolation: fixed residual strength does not close the tails — 2026-08-09

This was an offline, default-off research gate. It did not change the Tdarr
flow, production binary or image, worker state, routing, or queued media.

## Outcome

The experiment confirms the architectural split, but rejects both proposed
fixed strength assignments as a production solution:

- source-derived AR texture remains the right direction;
- the darkest-luma excess follows source-derived **strength**, not source AR
  texture;
- replacing all strength curves with residual-derived curves restores the
  darkest band but gives back most of the source-fit gain everywhere else;
- replacing only V strength with residual-derived strength changes the corpus
  from mild V over-delivery to mild under-delivery and does not beat production
  V amplitude error;
- changing strength also changes AR update cadence in the current temporal
  hold state, so texture and strength are not yet cleanly separable over time.

Do not deploy either strength-provenance hook. `modelsrc` and the response path
remain default-off. Production remains the bilateral residual-fit path.

## Reproducible gate

The parent gate and retained reels are under:

`/media/merged-storage/media/test-encodes/sourcefit-tail-gate-20260809`

The child gate, reports, manifest and summary are under:

`/media/merged-storage/media/test-encodes/sourcefit-strength-provenance-20260809`

Run and summarize with:

```sh
python3 tests/fgs/strength_provenance_gate.py \
  --candidate-nvencc ~/.cache/fgs-gate/builds/pin-76284306-1786293893/build-gate/nvencc
python3 tests/fgs/strength_provenance_summary.py
```

The pinned candidate was built from `76284306`; its SHA-256 is
`f16e9e4878992c2120773b518e26cf5f1c24d0c036fb328110c26535c5899eb4`.
The no-hook parent source arm used the independently pinned `b1697415` binary,
SHA-256
`14b8c060ffa88a3d48a9cd2a162de337636e718d7066043933eda3fee5856d2a`.

The child kept the parent source reels, QVBR, bilateral separator, static-source
selector, five fixed scenes, source-only common block masks and corrected
ratio-of-means oracle. It added three arms:

1. `source-control`: source AR and source strength, with no new hook;
2. `texture-residual-all`: source AR with residual strength on Y/U/V;
3. `texture-source-yu`: source AR/strength on Y/U and residual strength on V.

All 21 new streams contain exactly 600 frames and passed complete libdav1d
decoding. Six titles supplied five of five gradable scenes. Korra S02E07 again
had only two gradable scenes and remains observation-only. The no-hook control
passed the semantic-table, played-pixel and grain-disabled-base oracle on all
seven retained titles before their reports were admitted.

## Corpus result

Thirty decision-eligible scenes produced:

| plane | arm | delivered amplitude | amplitude MAE | texture MAE |
| --- | --- | ---: | ---: | ---: |
| Y | production | 0.848 | 0.155 | 0.132 |
| Y | source | 1.038 | 0.076 | 0.081 |
| Y | residual strength Y/U/V | 0.867 | 0.137 | 0.106 |
| Y | source strength Y/U, residual V | 1.038 | 0.076 | 0.081 |
| U | production | 0.887 | 0.133 | 0.166 |
| U | source | 1.048 | 0.105 | 0.088 |
| U | residual strength Y/U/V | 0.890 | 0.132 | 0.095 |
| U | source strength Y/U, residual V | 1.048 | 0.105 | 0.088 |
| V | production | 0.896 | 0.117 | 0.189 |
| V | source | 1.068 | 0.127 | 0.115 |
| V | residual strength Y/U/V | 0.893 | 0.122 | 0.121 |
| V | source strength Y/U, residual V | 0.890 | 0.124 | 0.121 |

The controls behave as expected in aggregate. Keeping source strength on Y/U
reproduces the source arm there. Moving all planes to residual strength moves
their amplitudes back toward production because production also fits strength
from the residual.

The important negative result is V. Residual V strength improves MAE only from
`0.127` to `0.124`, remains worse than production's `0.117`, and changes the
mean from `1.068` to `0.890`. It swaps a small excess for a slightly larger
deficit rather than estimating the missing grain.

It is also not consistent by title:

| title | source V MAE | residual-strength V MAE | safer fixed choice |
| --- | ---: | ---: | --- |
| Abbott S02E02 | 0.045 | 0.144 | source |
| HIMYM S04E17 | 0.127 | 0.091 | residual |
| HIMYM S09E15 | 0.129 | 0.111 | residual |
| Korra S02E12 | 0.169 | 0.141 | residual, weakly |
| Planet Earth S01E06 | 0.100 | 0.177 | source |
| Trying S02E06 | 0.193 | 0.079 | residual |

A plane-wide V switch therefore cannot be the independent chroma estimator.
The estimator has to follow the varying source/base relationship in time and
content. This agrees with `FINDINGS-2026-08-05-CHROMA-DIAGNOSIS.md`, which
found temporal variability and saturation dependence rather than plane
identity to be the surviving chroma mechanisms.

## Per-luma localization

The darkest-band failure follows strength provenance exactly:

| source-luma band | production amplitude / MAE | source strength | residual strength |
| --- | ---: | ---: | ---: |
| 0.000–0.125 | 0.931 / 0.083 | 1.115 / 0.124 | 0.935 / 0.080 |
| 0.125–0.250 | 0.791 / 0.209 | 1.022 / 0.036 | 0.790 / 0.210 |
| 0.250–0.375 | 0.835 / 0.165 | 1.056 / 0.071 | 0.840 / 0.161 |
| 0.375–0.500 | 0.834 / 0.166 | 1.074 / 0.108 | 0.836 / 0.164 |

Residual strength is marginally best only in the populated darkest band. It
then reproduces production's large deficit in the much larger `0.125–0.250`
population and gives back source fitting's gain through the rest of the luma
range. Conversely, source strength is clearly better outside the darkest band.

This localizes the next luma work to a per-bin estimator. It does **not**
authorize hardcoding a `0.125` threshold from six titles. A candidate should
use measurable confidence or source/base evidence, remain continuous across
luma, and pass leave-one-title-out validation before entering CUDA.

## The temporal state still couples texture and strength

The CPU solver substitution holds source-derived coefficients while replacing
only strength observations. The emitted streams do not always preserve that
isolation because the anti-twinkle state machine compares and holds one combined
AV1 parameter object. A strength-curve change can choose a different pending
snapshot and therefore a different AR table.

Across all seven titles:

| arm | frames with identical emitted texture fields | fully isolated titles |
| --- | ---: | ---: |
| residual strength Y/U/V | 2927 / 4135 (70.8%) | 0 / 7 |
| source strength Y/U, residual V | 4026 / 4135 (97.4%) | 4 / 7 |

There were no grain-presence mismatches. This is update-cadence coupling, not
the solver accidentally using the wrong coefficient statistics. It means a
future strength-only gate should first split texture history from strength
history, or explicitly measure their interaction rather than calling the arm
purely strength-only.

Strength also affects the encoded base. Residual strength changed base pixels
on seven of seven titles; direct comparison with the source control averaged
VMAF `97.803` and p1 `95.357`. The V-only substitution kept four of seven bases
pixel-identical; the three changed bases averaged VMAF `99.026` and p1 `97.381`.
Those are treatment/control comparisons, not source-fidelity scores. The
systematic all-residual movement is consistent with film-grain parameters
influencing NVENC decisions, but the independently observed control jitter
prevents a pixel-exact causal claim. Finished-stream testing cannot assume an
invariant base either way.

Size is not a decision boundary here. Relative to the source arm, residual
strength changed summed bytes by `-0.0077%` and the V-only substitution by
`+0.0159%`.

## A control trap exposed during the run

The strict no-hook oracle stopped twice and revealed two distinct sources of
run-to-run variation:

- one HIMYM S09E15 control had identical analyzer-table semantics but different
  grain-disabled base and played pixels; three exact repeats with both pinned
  binaries reproduced the parent;
- one Planet Earth control had identical base pixels but one different luma
  scaling curve over one short table interval. Repeats showed the old and new
  binaries can both produce that variant. Another repeat had parent-identical
  table semantics but a different base, and a third reproduced table, base and
  played pixels exactly.

The failed artifacts and repeats are retained under the child gate's
`repeats/` directory. Nothing was silently accepted and the official controls
were regenerated until the predeclared semantic and decoded-pixel oracle
passed.

This rules out commit `76284306` as the direct cause of either difference. It
also disproves the stronger assumption that one encode is a deterministic
control. The analyzer can cross a curve-simplification boundary, while NVENC
can independently choose a different base encode. Their perceptual magnitude
is not established by hashes alone. Future gates must retain and report repeat
variance; they must not silently reroll a failed control or weaken equality to
make a run pass.

## Decision and next sequence

1. **Keep source AR texture and source Y/U strength as the leading
   architecture.** Their corpus gains survive this isolation test.
2. **Reject fixed residual V strength.** It does not improve on production
   amplitude and it gives back some texture accuracy.
3. **Make temporal state separable.** Add a guarded prototype with independent
   texture and strength hold/update histories so a strength experiment cannot
   select a different AR snapshot by accident.
4. **Make the harness repeat-aware.** Quantify analyzer-table and NVENC-base
   jitter on the exact controls before comparing smaller treatment effects.
5. **Prototype per-luma closure offline.** Preserve source-derived strength
   where it wins and investigate why the darkest population prefers residual
   evidence. Use continuous, measurable confidence and leave-one-title-out
   validation, not a fixture-derived luma cutoff.
6. **Build an independent temporal chroma-amplitude estimator.** Keep U and V
   separate, use ratio-of-means, and test time/saturation conditioning. Do not
   reuse the rejected fixed residual-V substitution or a whole-plane gain.
7. Re-run the same corpus, full dav1d and base-fidelity gates before any
   response closure, blind review, routing change or production promotion.

Admission remains independent and open. This gate used grain-bearing positives
to localize model behavior; it did not prove when ordinary content should be
admitted to FGS.
