# R18 absolute local quantizer cap

Status: policy controls, actual packet accounting, all-frame decoder/color
validation and independent display binding pass. Quantizer-trace and quality
admission remain in progress. **No preservation or repair result is claimed.**

The [contract](ROUND18_ABSOLUTE_CAP_CONTRACT.md) tests a real qindex cap of4 on28
fixed64x64 superblocks intersecting the E05 shirt and background regions. The
initial and every recode application follow ordinary SB normalization. Selected
q becomes `min(pre,4)`; unselected stored q, frame/public QP and existing lambda
activation remain unchanged. Already-active TPL factors are refreshed only in
selected SBs from original factors. Global delta-q resolution1/presence is an
explicit confound. First-pass policy stays unchanged and statistics must be
regenerated exactly. Search/partition/transform decisions may respond naturally.

This follows [R17's fixed-choice failure](PSYEX_Q4.md): q4 restored substantial
shirt texture but still missed the local amplitude and ACF gates, with remaining
error concentrated in64x64 support. R18 tests actual decision feedback and coded
cost; the coefficient diagnostic cannot supply either. The first cap run may
overshoot as a diagnostic. The practical ceiling remains at or below original
actual packet rate, with99–100% required for decisive matched-rate contrasts.
No budget calibration is authorized by this experiment before preservation.

The [frozen preflight manifest](psyex-cap/preflight/manifest.json) preserves the
portable six-file patch, full1,790-file source manifest, build/run scripts,
commands, tool identities, logs and independent reviews. It identifies the
private binaries as external artifacts. Reproduce from the pinned R11 source:
apply `source-freeze-1/r18-cap.patch` with `patch -p1`, verify the complete manifest,
then use the prepared private build and outer execution commands. Historic
receipts contain their actual scratch paths; relocation must preserve their
provenance rather than rewrite them.

The final patch is `5f03edf1ba320c84006e65484e88742ffb60b2de422b73b10346ea90ca9ed5d0`;
source manifest is `f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca`.
The completed build pins are
`c0e389a6ca98513c5b4117b48dab02552b7f21ea978585974243f747803e1fe7`.
The private Release build completed in51.951s. Its compiler/manifest/library
checks passed, and the exact no-encode baseline command preview passed.

[Independent source release](psyex-cap/preflight/reviews/round18-source-release.md)
and [harness review](psyex-cap/preflight/reviews/round18-harness-review-revision3.md)
authorize only the private control sequence. Earlier reviews rejected missing
actual-q/committed coverage, accepted-generation mismatch, duplicate skip
lifecycle, observer-off checks, incomplete decode identity and manifest ordering.
The parent corrected the lambda-path activation gate and the final skip branch;
the reviewer verified the final source. Rejected drafts remain in active scratch
for later archival. No production source, installed binary or configuration changed.

The [completed control package](psyex-cap/controls/manifest.json) preserves
baseline/pass1/cap receipts, the failed first trace, media validation, syntax
binding and the separately reviewed observer correction/build.

| Measurement | Result |
|---|---:|
| Cap-disabled control | Exact R16 IVF and all 336 reconstruction frames |
| Fresh first-pass statistics | Exact prior statistics |
| Fresh first pass | 65.209987 s |
| Cap second pass, observer disabled | 149.134597 s |
| Total two-pass encoding time | 214.344583 s |
| Full 336-frame remuxed video packet rate | 14.0277971 Mbps |
| Scored 240-frame packet rate | 12.6716968 Mbps |
| Original scored packet rate | 9.6765224 Mbps |
| Scored rate relative to original | 1.3095300 (30.9530% above ceiling) |

All 336 whole-YUV frame hashes agree between encoder reconstruction, dav1d,
libaom and NVDEC. Dimensions, limited BT.709, 10-bit planes, timestamps and
packet counts pass. Independent header/ref-slot mapping finds 502 frame headers,
336 coded pictures and 166 show-existing events. Display 216 resolves to coded
ordinal 210, event 314, order hint 88; this permits reuse of the existing native
coefficient observer. It does not yet establish native coefficient agreement.

The faster observed cap pass is recorded without a causal explanation; decision
and recode behavior can change under this intervention. The rate exceeds the
user's practical ceiling and is diagnostic only. No requested-rate inference or
coefficient count is used as coded-bit evidence.

The first observer replay failed after 4.199 s with an invalid coefficient-cursor
subtraction. Its partial trace is rejected. The [control addendum](ROUND18_OBSERVER_CORRECTION.md)
explains why the cursor is conditional, specifies a committed-layout prefix
correction and separates policy-build from observer-build provenance. Independent
review verified the observer-only three-file diff. The corrected private build
completed; its fresh replay is now required to reproduce the immutable cap IVF,
all 336 reconstruction frames and statistics exactly. No acceptance gate changed.

Next require all-picture/all-attempt delivered-q, committed geometry and lambda
evidence; native coefficient joins; and the established full quality, temporal
and control window. Source-budget redistribution is conditional on preservation.
No playback has been observed and no production change is proposed.
