# Pantheon repair at or below original video rate

On2026-10-20 the user set a hard practicality ceiling: **at or below the original
video bitrate**. The preserved4x x264 arms are useful preservation diagnostics
and no longer practical repair candidates, regardless of their playback result.
Their playback is not a prerequisite for further authorized source-budget work.
No tested arm currently meets the complete repair requirement at this ceiling.

Use actual video packets at the same240 scored positions after96 preroll frames:
E04 <=10.029358641Mbps and E05 <=9.676522400Mbps. Decisive matched-rate contrasts
must lie in99–100% of source rate; the prior1% matching tolerance does not permit
an overshoot. Lower-rate arms may qualify for the cap but are not automatically
matched-rate causal controls. All texture/quiet/detail/banding/temporal/playback
requirements remain unchanged. Full-episode qualification is still required
before any production proposal; these are known difficult fixtures.

The first new arm, SVT preset0/tune0, fails the texture screen at9.5227592Mbps,
98.4110% of the E05 original. It is a valid under-cap practical screen, **not a
matched-rate preset comparison**. Shirt/background HF amplitude remains74.6%/
48.1% below source. Spatial structure, face errors and full-reference tails
improve descriptively against preset4, while some quiet/edge errors worsen.
Encoding336 frames took2740.622s on one SVT worker,39.64x the preserved preset4
wall time. No motion playback was observed.

[Measured result](RESULTS.md), [machine evidence](preset0-result.json),
[independent review](REVIEW.md) and [reproduction](REPRODUCE.md) document scope.
The ancillary [original H264 QP-state observation](ORIGINAL_QP.md) is validated;
it does not equate original QP with re-encode preservation.

The independent libaom SSIM/variance-AQ arm also fails at9.6243504Mbps,
99.4608% of source,389.179s/336frames. Shirt/background HF deficits84.37%/50.81%
and ACF errors .10866/.12137 fail. Broad controls improve but face detail and
VMAF/NEG regress. [Machine evidence](aom-result.json) and the same result/review
reports preserve this mixed outcome. All3decoder/sample gates pass.

The matched PSNR-tuned arm also fails at **9.639088 Mbps**, 99.613% of source,
391.652 s/336 frames. Removing the extra SSIM source-variance weighting improves
face/edge detail but leaves shirt/background HF deficits of 84.08%/48.87% and
failed spatial structure. Quiet and flat-texture controls regress on several
measures. [Direct comparison](aom-tune-comparison.json) and independent review
reject this actual policy as a repair; they do not establish a codec limit.

A byte-neutral [source-boundary trace](AOM_SOURCE_BOUNDARY.md) now shows that
all visible samples of the prescribed midpoint frame enter coding unchanged.
32 of 363 coded events have sparse differences elsewhere, at most two 10-bit
levels. The subsequent [sample neutralization](AOM_SOURCE_NEUTRALIZATION.md)
proves every coding input sample original, yet fails at9.6256032Mbps (99.474% of
source): shirt/background HF deficits84.21%/48.54% and ACF errors.07442/.09889.
Changes affect coding feedback but their removal is insufficient. Full controls
are mixed; no playback.

The subsequent [coefficient observation](AOM_COEFFICIENT_OBSERVATION.md) is
admitted and independently reviewed. On the single prescribed E05 frame, small
transforms reconstruct source texture closely before quantization. Initial FP
quantization at actual shirt qindex65 removes most of that texture, and later
optimizer/dropout removes more. Over half the shirt uses no-transform skips;
its selected64-pixel transform also loses texture before quantization. These
local mosaics are diagnostics, not repair candidates. The subsequent
[actual-precision contrast](AOM_QMAX.md) delivers shirt qindex32 and background
qindex32–36, but still fails texture preservation at38.86924Mbps (4.01686×source).
It takes441.295s for336frames across both passes. Existing trace flags isolate
substantial optimizer-only loss even at this finer precision. Broader quality
improves but quiet/local regressions remain. No playback occurred; no candidate
qualifies. [Current hypotheses](HYPOTHESES.md) and [ledger](LEDGER.md)
record evidence, scope and unchanged acceptance criteria.

Prior evidence: [causal and measured preservation report](../pantheon-rd-20261019/README.md).
Prior source-budget ROI failure is accepted; it does not prove source-budget
preservation impossible. All previous archives remain unchanged. Production,
Tdarr, torrents and library changes remain unauthorized.

The [fixed PSYEX policy](PSYEX.md) also fails at 9.62790 Mbps, 99.4976% of source,
with 370.336 s across both passes. Neutral observation proves the texture policy
executes in search, but shirt/background texture and face/edge/quiet controls
remain inadequate. The admitted [boundary observation](PSYEX_BOUNDARIES.md)
shows shirt HF .606→.441 entering coding→.094 pre-loop→.055 final on frame120.
Background enters coding nearly unchanged, then loses amplitude and structure
across both coding and filtering. Post filtering improves some pixel/ACF errors;
it is not uniformly harmful. No quiet controls occur in that single frame.
The next discriminator maps final committed blocks/TUs and residual ownership,
with explicit quantizer provenance; no production change is authorized.

A reviewed [fixed-input grain diagnostic](GRAIN_FIXED_INPUT.md) on the improved
preset0 base preserves a local quiet/texture input conflict. It rejects the
measured white16 probe, not all legal grain models or other bases. No estimator
was fitted and no source-clean criterion was relaxed.

The [R10 final decoder map](DECODER_MAP.md) rejects predictor-only syntax as the
dominant target coverage explanation:91.84%shirt/94.84%background has positive
EOB. Native residuals improve pixel error but barely restore shirt HF. Exact
all336 output/preloop/OBU bindings pass. Next is committed encoder coefficient
lineage, not another settings sweep. No repair/playback/blocker is established.

The admitted [R11 committed coefficient trace](PSYEX_COEFFICIENTS.md) now localizes
the decisive exercised-TU loss to initial scalar FP quantization. Actual shirt
qindex71 maps raw native-inverse HF.3930 to.0937; later processing changes no
shirt units. Exact off/on bytes and all2151positive decoder joins pass after an
independently verified storage permutation. Face34.37% no-quantizer coverage,
upstream shirt loss and postloop changes remain separate. Next is a fixed-decision
scalar-rule versus precision diagnostic. No source-budget repair or playback
acceptance has been demonstrated.

The [R12 scalar diagnostic](PSYEX_SCALAR.md) rejects same-q scalarB: it prunes
more and worsens all three ROIs. NativeFPq32 improves background/face locally,
but shirt amplitude stays41.39%ofsource and ACFerror worsens to.393. Every new
native arm matches directC exactly; independent metrics agree<1e-12. These
fixed-decision local images have no bitrate or repair claim. The
[R13 contract](ROUND13_FINE_CONTRACT.md) chooses one q1 precision closure before
upstream/decision-policy work; no candidate or playback acceptance exists.

The [R13 near-fine replay](PSYEX_FINE.md) nearly reaches the raw local inverse
but still fails shirt texture:62.79%sourceHF,ACFerror.0821. Independent arrays
and metrics pass; q1 remains nonlossless and has no encoded-rate claim. Stop
local precision sweeps. The [R14 source contract](ROUND14_SOURCE_CONTRACT.md)
isolates original input samples from retained transform/skip decisions next.

The [R14 original-source replay](PSYEX_SOURCE.md) recovers shirt amplitude to
86.50% of source and passes local ACF, but still misses the amplitude gate.
Every new native path and independent reconstruction passes. It identifies
material input-processing loss while retaining decision/support limitations.
The next discriminator is a real source-off, near-fine precision bundle with
actual quantizer and packet-cost verification; no practical candidate exists.

The [R15 real bundle](PSYEX_REAL.md) demonstrates numerical preservation:
five-frame shirt/background HF errors−3.622%/−1.427%, ACFerrors.02189/.00542.
Actualq4 is independently joined on all4809 traced positive TUs, with original
coding input and no skipped support in the three frame120 ROIs. All12870 control
tile MSEs improve, with small local HF/ACF regressions retained. The cost is
190.41154Mbps,19.6777xoriginal, and692.477s/336frames across two passes. It is
disqualified as a practical repair and has no playback acceptance.
The [R16 contract](ROUND16_TF0_BUDGET_CONTRACT.md) selects the missing original-
budget TF-off policy comparison with normal allocation and no QP bounds.

The completed [R16 matched-rate comparison](PSYEX_TF0_BUDGET.md) fails both
texture screens at9.6698472Mbps (99.9310%source),372.254s. New native evidence
proves original coding input on observed frame120 and allshirtpositive residual support, then large
loss at actual scalarq71. Raw fixed-choice shirt reconstruction still retains
only86.74%sourceHF; later filtering adds loss. Full-window tails are mixed, with
material SSIMULACRA2 low-tail regressions. Independent derivations, corrections,
GPU metrics and stills are frozen in the linked outcome package. R17 selects
one q4 fixed-choice diagnostic on these new captures; no practical candidate,
playback acceptance or technical blocker exists.

The completed [R17 fixed-choice q4 diagnostic](PSYEX_Q4.md) restores shirt HF
21.01→86.08%source and background to99.61%, with exact native and independent
reconstruction controls. Shirt remains deficient, concentrated in64x64 support.
It supplies no encoded rate or playback result. The next question is whether a
delivered spatial cap changes real encoder decisions at an affordable packet cost.

The [R18 real spatial cap](PSYEX_CAP.md) demonstrably delivers qindex4 to all
invoked selected units across336pictures; observer output and all independent
decoders match exactly. It costs12.6716968Mbps (30.95% above original),214.344583s
across two passes. Texture and displaced damage have not yet been assessed.
Both child agents hit a runtime usage limit during the remaining independent
review/control work. The [specific blocker and restart](R18_RESOURCE_BLOCKER.md)
separate completed evidence from unfinished checks. No practical repair or
production proposal is supported.
