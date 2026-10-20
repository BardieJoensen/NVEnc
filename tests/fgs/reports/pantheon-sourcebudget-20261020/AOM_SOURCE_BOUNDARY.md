# Libaom source-boundary diagnostic

The admitted trace rules out **direct loss of the prescribed E05 midpoint
texture in the coding-source preprocessing stage**. Input frame 216, scored
frame 120, reaches the encoder with every visible Y/U/V sample unchanged. The
same holds for input frame 120, used by the earlier fixed-input grain probe.
Both are hidden coded reference events, correctly mapped to their displayed
source frames. The final output still has the previously measured 84.08% shirt
and 48.87% background HF deficits and failed ACF. Loss therefore occurs after
this observed source boundary for the prescribed midpoint.

This does not establish that all preprocessing is disabled. Of 363 coded events,
32 have changed source samples: 26 hidden frames and all six shown keyframes.
33 use a distinct source-buffer pointer; one of those is sample-identical.
Across the complete coded-event population, unequal Y/U/V sample counts are
76,672 / 34,822 / 33,222, respectively 0.01019% / 0.01850% / 0.01765% of the
observed samples. These fractions count repeated coded source frames as distinct
events. Maximum change is two raw 10-bit levels, or 0.5 on the 8-bit scale.
The result cannot exclude indirect changes through reference reconstruction,
analysis, rate allocation or subsequent coding decisions.

The private pristine and instrumented outputs both exactly equal the installed
PSNR arm's IVF SHA256:
`ab233b3874583fbbb75f9bd9e91a63ff19efeae9a57e7639ca4fc499c7662052`.
Thus existing decoded-sample and GPU campaign evidence transfers without an
unchanged scoring rerun. Private pass-two times were 342.602 s and 352.677 s;
they include different instrumentation work and are diagnostic timings. The
actual candidate cost remains 391.652 s for both encode passes, 9.639088 Mbps.

All 336 original whole-frame and 1,008 plane hashes bind exactly. Independent
AV1 header parsing finds 490 headers: 363 coded events (154 hidden, 209 shown)
and 127 show-existing headers. The trace matches the complete 363-event multiset
using original-frame identity, frame/show/showable fields, order hint and refresh
flags. Every source frame is represented; 309 occur once and 27 twice. No display-
frame-count shortcut, emission-order assumption or partial trace was admitted.

[Machine result](aom-source-boundary-result.json) binds full event records,
commands, input, binary/library/build provenance, fresh source reconstruction and
independent header evidence. [Patch](aom-source-boundary.patch),
[reproduction](REPRODUCE.md) and [review/corrections](REVIEW.md) preserve the method.
Two invalid drafts were rejected before encoding. V3 is observational and its
complete stream equality demonstrates neutrality for this run. It is not a
repair, a fixed-predictor quantization experiment, or a whole-encoder TF ablation.
No motion playback was observed.
