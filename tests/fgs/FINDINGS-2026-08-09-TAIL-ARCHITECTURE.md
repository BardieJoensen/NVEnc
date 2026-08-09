# Tail-first architecture gate: source texture works; strength must be decoupled — 2026-08-09

This was an offline research gate. It did not change the Tdarr flow, production
binary, image, worker state or queued media. `modelsrc` and the response path
remain default-off research controls.

## Outcome

Source-derived fitting is the correct architectural direction for the AV1 AR
texture model, but the current `modelsrc=on` implementation is not ready for
production. On the six decision-eligible titles it roughly halves both luma
amplitude error and texture error at effectively unchanged size and base
quality. It simultaneously over-delivers chroma V and worsens the darkest luma
band. The important result is therefore not "turn source fitting on"; it is
that AR texture provenance and strength-curve provenance must become separate
choices.

The old upper spatial tail did not reproduce as a temporal synthesis-amplitude
tail. The shared-mask spatial verifier remains useful as an energy/destruction
alarm, but it is not a gain-calibration oracle: retained base detail, ringing
and spatial texture are part of what it observes.

## Measurement correction: use ratio of means, not mean of ratios

The first published amplitude tables used the mean of per-frame standard-
deviation ratios. That repeats the Jensen-bias failure already documented in
`FINDINGS-2026-08-05-CHROMA-DIAGNOSIS.md`: noisy small denominators inflate the
mean even when the aggregate variances are correct. Commit `0de18413` made the
ratio of aggregate means canonical, retained the old statistic and its Jensen
gap as diagnostics, and bumped the measurement to
`scene-grid-v3-ratio-of-means`. All 105 scene/plane reports were regenerated
from the same streams, source masks and frame grid. Coverage and decoder
verdicts did not change.

The correction does not retract the architecture result. It strengthens the
luma amplitude result and narrows the chroma-V regression:

| statistic | initial mean-of-ratios | corrected ratio-of-means |
| --- | ---: | ---: |
| production Y amplitude / MAE | 0.854 / 0.150 | 0.848 / 0.155 |
| source Y amplitude / MAE | 1.049 / 0.078 | 1.038 / 0.076 |
| production U amplitude / MAE | 0.908 / 0.126 | 0.887 / 0.133 |
| source U amplitude / MAE | 1.074 / 0.116 | 1.048 / 0.105 |
| production V amplitude / MAE | 0.933 / 0.124 | 0.896 / 0.117 |
| source V amplitude / MAE | 1.131 / 0.176 | 1.068 / 0.127 |

The earlier statement that source fitting made V amplitude MAE 42% worse is
superseded. The corrected increase is 8.6% (6.99% with response). It remains a
release risk because the sign and magnitude vary strongly by title, not because
the corpus mean is catastrophic. The texture statistics do not divide by a
frame-local amplitude denominator and are unchanged.

## Reproducible run

The gate is reproducible through:

- `tail_architecture_gate.py`, which freezes provenance, source fractions,
  encoder commands, binaries and complete dav1d validation;
- `temporal_grain_report.py`, measurement version
  `scene-grid-v3-ratio-of-means`, which uses one source-derived static mask for all
  arms and reports zero-synthesis controls honestly;
- `tail_architecture_summary.py`, which enforces title coverage, keeps U and V
  separate, reports luma occupancy, sums bytes and scores grain-disabled bases
  directly.

The retained report is under
`/media/merged-storage/media/test-encodes/sourcefit-tail-gate-20260809`.
Its decision artifact is `summary.json`.

Binary identity was pinned rather than inferred from filenames:

| role | path | SHA-256 |
| --- | --- | --- |
| production 9.31/r4139 | `/opt/docker-apps/build/tdarr-node/nvencc` | `004e4cac325910b151485da0831b17885486c1c52ec0e001c760d0381a38d1e5` |
| candidate at `b1697415` | `~/.cache/fgs-gate/builds/pin-b1697415-1786280543/build-gate/nvencc` | `14b8c060ffa88a3d48a9cd2a162de337636e718d7066043933eda3fee5856d2a` |

Every arm used the production QVBR and bilateral settings. There were five
arms:

1. plain AV1 with no film-grain synthesis;
2. the production binary and residual-fitted bilateral FGS;
3. the candidate binary with source fitting off, to expose build drift;
4. candidate source fitting with the guarded static-source selector;
5. the same source arm with the guarded covariance/texture response.

All 35 direct streams contained exactly 600 frames and passed a complete
`libdav1d -xerror` decode. No log silently ignored the film-grain option. The
candidate had also passed all 22 GPU KAT fixtures with its negative and
positive model controls.

## Corpus and coverage

Seven exact retained sources were used: two declared lower-tail titles, a
predeclared lower-tail fallback, two centre controls and two declared upper
tails. Each title reel contains five fixed 120-frame source fractions. Metrics
sample a fixed every-sixth-frame grid within each fraction. A scene needs at
least three valid temporal pairs and a title needs at least three gradable
scenes.

Six titles supplied five of five gradable scenes: Abbott S02E02, HIMYM S04E17,
HIMYM S09E15, Korra S02E12, Planet Earth S01E06 and Trying S02E06. Korra S02E07
supplied only two of five and was excluded from corpus decisions rather than
silently averaged. Its two observations over-delivered strongly in both
source arms, so it remains a caution and a useful future coverage target, not
evidence for a release decision.

Planet Earth is soft-telecined progressive film despite its container
`field_order=tt` and 29.97 metadata. The gate decodes progressive pixels and
retimestamps them to 24000/1001; frame MD5s proved the operation changed
timestamps, not pixels.

## Luma result

Thirty gradable scenes produced:

| arm | delivered amplitude mean | amplitude MAE from 1.0 | texture MAE |
| --- | ---: | ---: | ---: |
| plain | 0.538 | 0.462 | 0.290 |
| production | 0.848 | 0.155 | 0.132 |
| candidate control | 0.853 | 0.150 | 0.133 |
| source fit | 1.038 | 0.076 | 0.081 |
| source + response | 1.042 | 0.072 | 0.065 |

Relative to production, source fitting reduces luma amplitude MAE by about
51% and texture MAE by about 39%. The response arm reduces them by about 53%
and 51%, respectively.
This is a substantial, repeatable gain, not a small-fixture effect.

It is not uniform enough to ship. The occupancy-weighted darkest band behaves
in the opposite direction:

| source-luma band | blocks | production amplitude / MAE | source amplitude / MAE | response amplitude / MAE |
| --- | ---: | ---: | ---: | ---: |
| 0.000–0.125 | 23,044 | 0.931 / 0.083 | 1.115 / 0.124 | 1.117 / 0.126 |
| 0.125–0.250 | 46,397 | 0.791 / 0.209 | 1.022 / 0.036 | 1.024 / 0.040 |

Source fitting fixes the much larger second dark band, but it converts the
darkest band from a modest deficit into an excess. Both unweighted and
occupancy-weighted values are retained; a title-level mean must not hide this.

Per-title source-fit luma means range from 0.908 on Korra S02E12 to 1.146 on
HIMYM S09E15. The response is helpful in aggregate but is not a universal
normalizer: it slightly worsens texture on Korra S02E12 and HIMYM S09E15.

## Why the old tail is not an amplitude oracle

The prior spatial selector called HIMYM S09E15 and Trying S02E06 upper-tail
cases at 1.508 and 1.341. Their production temporal delivered amplitudes here
were only 0.944 and 0.902. The lower direction repeated more plausibly, but the
upper direction did not.

That does not invalidate the production monitor. It changes the question its
number answers. Shared-mask spatial high-frequency energy includes retained
base texture and codec artifacts as well as synthesized grain. Temporal
differencing removes the static picture and is the more specific oracle for
synthesis amplitude. A global gain or routing rule based on the spatial tail
would therefore tune one phenomenon as if it were another.

## Chroma result

U improves modestly in amplitude and substantially in texture:

| arm | U amplitude | U amplitude MAE | U texture MAE |
| --- | ---: | ---: | ---: |
| production | 0.887 | 0.133 | 0.166 |
| source fit | 1.048 | 0.105 | 0.088 |
| source + response | 1.039 | 0.105 | 0.089 |

V remains the less stable plane, but the corrected regression is modest rather
than the original headline:

| arm | V amplitude | V amplitude MAE | V texture MAE |
| --- | ---: | ---: | ---: |
| production | 0.896 | 0.117 | 0.189 |
| source fit | 1.068 | 0.127 | 0.115 |
| source + response | 1.064 | 0.125 | 0.115 |

Source fitting makes V texture about 39% more faithful but makes V amplitude
MAE about 8.6% worse. The corpus mean hides opposite title behavior:
source-fit V means are 0.957 on Korra S02E12 and 0.990 on Planet Earth, but
1.127 on the lower-tail HIMYM fallback, 1.129 on upper-tail HIMYM and 1.193 on
Trying. The response barely changes it. Chroma must remain per-plane; a
combined chroma number would conceal the tail.

## Size and base fidelity

Across all seven reels, production used 62,330,792 bytes versus 83,924,646 for
plain AV1, a 25.73% saving. Relative to production, candidate control was
+0.257%, source fit +0.072%, and response +0.093%. The measured texture gain is
therefore effectively free in this gate; compression is not the current
decision boundary.

Source-referenced, grain-disabled VMAF is 92.833 for production, 92.866 for
source fit and 92.867 for response. The source still contains grain, so that
score is not a clean-base oracle. Direct grain-disabled comparisons are more
honest:

| comparison | VMAF | VMAF p1 | PSNR-Y | SSIM |
| --- | ---: | ---: | ---: | ---: |
| production → candidate build drift | 97.968 | 95.617 | 57.090 | 0.999299 |
| candidate → source fit | 97.826 | 95.470 | 54.733 | 0.999204 |
| source fit → response | 97.819 | 95.457 | 54.729 | 0.999203 |

No pair is pixel-identical. The defensible conclusion is that base impact is
measurably neutral and comparable to the build-control drift, not that output
is unchanged.

## Decision and next code experiment

Do not deploy `modelsrc` or the response path, add a global gain correction,
or change routing from this result. Production remains the conservative
bilateral residual-fit implementation.

The next default-off experiment must split the two jobs currently coupled by
`modelsrc=on`:

1. fit AR texture from the source but retain residual-derived strength on all
   planes;
2. fit AR texture from the source and use source-derived strength for Y/U but
   residual-derived strength for V;
3. apply the guarded response only to the best split, if either split closes
   amplitude without surrendering the texture gain.

The same cached reels and temporal reports can test this without changing the
separator, production flow or corpus. If V and the darkest luma band follow
the source-strength choice, the fault is localized to strength provenance. If
they do not, the source AR model and emitted scaling curve still interact and
the next investigation belongs at quantization/emission rather than in another
gain heuristic.

Admission remains a separate gate. This corpus contains grain-bearing
positives; it did not produce a quality-labelled case where every FGS arm is
worse than plain.
