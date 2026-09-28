# Exact constant endpoint protection

D80 follows the [source-bound natural recovery witness](FINDINGS-2026-09-28-NATURAL-RECOVERY.md):
an exact black letterbox region survives compression unchanged but receives
small synthesized grain. Ordinary quiet-source statistics intentionally exclude
clipped endpoints because they cannot estimate the active image's noise.

`07cb2874` adds a separate exact-evidence guard. A complete native region of at
least 8x8 luma samples must have identical minimum and maximum at nominal black
or white. Limited and full range use their actual native endpoints. The guard
does not classify weak shadow grain or non-endpoint constant areas as this case.
Colour needs its own zero direct variance, at least 8x8 native samples, a valid
decoder range and a strength lookup that indexes luma directly. Shared Y/colour
curves are outside this narrow implementation so luma evidence cannot suppress
unmeasured colour. Unsupported lookup changes clear the corresponding colour
state; depth/range changes clear all endpoint state.

Endpoint caps are independent of the older active-image source caps. Detecting
black bars therefore does not activate that guard's chroma policy elsewhere.
The existing bounded curve envelope never raises synthesis. Existing source
blending accounts for the reduced curve; copying source still precedes lossy
NVENC and is not a decoded-preservation guarantee. Caps retain the established
24-fresh-frame hold and 16-step release, survive ordinary fit-history resets,
and reset with the stream/recovery epoch. Main recovery timing is unchanged.

All observations reuse existing source metrics, with no added source pixel
readback or GPU synchronization. CPU tests cover every possible constant native
luma code at 8/10-bit limited/full range, uncertain colour/shadow negatives,
native curve envelopes, missing-model behaviour and domain/lifetime changes.
The complete suite passes 275 Python tests in 38 suites and 55 C++ programs.
The Linux encoder builds successfully; SHA256 is
`86773a2bc4dd7e740617df2bcff75171d2ce510b30092df560b51360194754a8`.

All 24 before/after GPU encodes complete successfully. The ten constructed
cases cover both depths, steady grain, limited/full-range bars, uncertain
shadow/colour and bar disappearance/re-entry. Two original development excerpts
cover 2,160 SDR and 720 PQ frames. Independent AOM and dav1d agree on all
32,000 frame observations with grain both enabled and disabled. An additional
4,480 raw synthetic pictures match the independent hashes. All 83,884,961
tested exact endpoint samples in the patched synthetic output receive zero
added grain. The old output supplies nonzero negative controls. Steady and
weak-shadow controls remain exact; uncertain colour does not gain protection.
Synthetic centre measurements and grain-off pictures remain exact. All paired
clocks/metadata and natural recovery/fallback decisions remain unchanged.

The natural source comparison measures 81 frames from each excerpt, retaining
the original fixed tile populations and source clocks. In Gentlemen, all
18,061,937 tested samples where source and reconstructed luma share the exact
endpoint receive zero added grain. The maximum constant-tile luma grain RMS
falls from 0.369466 to 0.012353 in normalized 8-bit code units; Cb falls from
0.240924 to zero. The residual luma number includes other constant regions and
source/reconstruction mismatches; it does not contradict the exact-endpoint
result or establish universal black-bar equality. Dragon has no qualifying
luma endpoint tile in this window; its constant-colour grain measures do not
change. These are native-code comparisons, not calibrated HDR visibility.

The generic bounded refit can reduce other brightness levels when the AV1 knot
budget is full, and source blending before lossy NVENC can propagate changes.
Consequently, 2,031/2,160 SDR and 443/720 HDR decoded pictures differ from the
pre-fix branch in both grain modes. These counts are not damaged-frame counts.
The maximum non-endpoint luma-curve reduction is 41 strength units in SDR and
two in HDR. Source review of 12 SDR frames around the worst reduction finds
mean luma base/source RMS improving from 1.533900 to 1.492170; coarse displayed
luma error also improves in every reviewed frame. Small chroma/local changes
occur in both directions. This targeted review does not qualify every scene.
The excerpt sizes change by +0.0275% SDR and +0.8557% HDR. Shared-service encode
times are recorded but are not controlled throughput evidence.

The first natural comparison stopped on a valid baseline mismatch and remains
preserved. Pre-D80 `c6c53646` differs from archived production `cb903a17` only at
SDR ordinals 1,874–1,877 with grain enabled, and 1,877 with grain disabled.
The original measured window, including its preceding source frame, is exact
in both modes. `natural_v2.py` reuses earlier measurements only within that
explicitly verified window and separately records the complete-output mismatch.
Source review of 12 frames around the four changed pictures finds very small
differences: luma base/source RMS changes only at 1,877, by -0.000415;
coarse displayed luma error changes between -0.000094 and +0.000017.
An isolated control disables only the occupied-strength recovery retry. Its
8,640 independent AOM/dav1d observations agree and reproduce all 2,160 archived
production pictures, in both grain modes, and all production models exactly.
The retry at ordinal 1,773 therefore explains these four later changed pictures.
This attribution is specific to the measured comparison.

The existing periodic, four-scene flicker, mixed-source, variance-support and
training-support subset finishes with eight passing checks and one failure,
using unchanged assertions and retained negatives. The periodic fixture passes
its ripple scan and independent jacket-detail controls but flags 26 additional
grain-on pictures at ordinals 3,207–3,232 and nearby amplitude/correlation changes.
All known negative examples still fail. The original periodic still assertions
at 24, 66 and 84.5 seconds, which the earlier change alert prevented from running,
also pass independently; the retained mesh still fails its concentration bound.
Two additional pre-D80/retry-disabled controls complete 28,800 independent
decoded observations. Pre-D80 has the same 26 additional grain-on pictures;
disabling only its occupied-strength retry removes that scheduling difference.
D80 versus pre-D80 preserves scheduling, amplitude, texture and temporal
assertions but still triggers isolated signed-correlation alerts in red on two
frames and blue on three (three unique ordinals: 2,860, 2,863 and 3,395).
The retry-disabled control versus the older positive also has isolated
correlation alerts. Their source/repeat review is completed below. The failed
old-reference result is retained; the new reference has an explicit separate
review record. This subset is not the full release gate. The older
full-movie amplitude manifest currently references four unavailable media
artifacts; its source and paired outputs must be restored or properly rebuilt
before that mandatory full-history qualification can run. No substitute
library transcode is treated as an original source.

The complete changed interval and context, ordinals 3,191–3,264, now have a
74-frame source review. All 375 extracted raw pictures pass their clock checks;
the 300 decoded output pictures match the corresponding independent AOM hashes
from 14,400 fresh frame observations. The 2,332,800,000 temporary raw bytes are
removed with hashes/receipts after measurements. The scientific PNG/PDF
`periodic-source-quality` records the result without assigning a quality pass.
During the 26 added-grain pictures, mean base/source luma RMS rises from
0.758999 to 0.824920, and mean coarse displayed error from 0.212206 to 0.228551,
in normalized eight-bit code units. Both colour base errors improve slightly.
Every measured luma direction/scale remains below the original's texture
strength. The finest diagonal band moves from 0.085625 to 0.129012, versus
0.258101 in the source. These source-selected low-structure regions still
contain picture detail; the separate conservative noise screen finds at most
two luma tiles per picture. Thus this is mixed, descriptive source evidence,
not a proof of pure-grain fidelity or complete real-source eligibility.

Two fresh same-binary repeats complete another 28,800 independent decoded
observations. Production reproduces every old-positive picture exactly, and D80
reproduces every candidate picture exactly, with grain both on and off. Both
unchanged decoded-sequence comparisons pass. The isolated correlation changes
therefore reflect deterministic code changes rather than repeat variation.

An additional original-source review covers all correlation alerts and their
context, 40 frames across four outputs. Its 320 raw output pictures match the
existing independent AOM hashes; Python independently reproduces all nine-patch
display RMS and signed correlation measurements. The 2,239,488,000 temporary raw
bytes are removed with receipts. At ordinals 2,860/2,863 the D80/pre-D80 models
differ only in luma scaling points; colour curves, coefficients and seeds match.
At 3,395 the complete model and seed match, but lossy base differences still
alter the rounded display residual. Source errors have small changes in both
directions. Eight worst-patch contact-sheet witnesses show no displaced lines
or regular mesh; this is limited visual evidence, not a full-picture guarantee.

The 26-frame interval follows the original scene cut at 3,206. Both old and new
outputs have grain on that first picture; the old positive then turns it off
for 3,207–3,232 before ramping back up. D80 keeps it present. Sixteen additional
source-selected shirt/jacket witnesses across eight pictures show no new ripple
or blocking. Movement blur in the jacket is also present in the original.
These source/visual measurements support accepting the deliberate change for
this fixture, while preserving its mixed numerical quality evidence.

`periodic-reference-review.json` records that decision. The separately versioned
`gentlemen_endpoint_recovery_positive` is the fresh D80 repeat, SHA
`aee654a4f2e44046d8fa220a4d4f819825203ccdb61d88f2addb31e0b25044ef`.
All older positives and negatives remain. The source-detail reference stays the
older amplitude fixture, and no numerical assertion changes. Rechecking the
recorded complete sequence against the reviewed reference passes; the retained
mesh and jacket-blur examples still fail their independent checks. This resolves
the expected-behaviour review for this clip. It is not a fresh full-gate result,
full-title quality qualification, source admission or deployment approval.

`3ffeff64` separately improves release-tool preflight after discovering the
missing old amplitude media. Every required source/negative/candidate/reference
path and distinct file identity must exist before GPU stages start. The fast
mode explicitly reports that hashes and quality are unverified; the real stage
still hashes all media and binds the candidate encoder. Missing/aliased media
are exercised through the actual shell entry point with a GPU-invocation
witness. The full suite passes 278 Python tests in 38 suites and 55 C++ programs.
The actual stale manifest rejects in 0.235 seconds, before GPU initialization.
This changes developer release tooling, with no routine Tdarr validation cost.

Production stays `cb903a17`; optional retention/FEL and reserved footage remain
untouched. The 24-job, regression and causal-control pauses are released.
The same-binary repeat pause is also released. Subsequent D81 integration has
its own pause receipt; read the live handoff for current state.
No experiment starts automatically. R3–R8 and release qualification remain open.

Local evidence: `roadmap-r4-constant-endpoints-20260928/` under the handoff root,
especially `plan.json`, `implementation.json`, `full-cpu.json`, `build.json`,
`manifest.json`, `encodes.json`, `comparison.json`, `natural-baseline-review.json`,
`natural-comparison-v2.json`, `curve-review.json`, `detail-review.json`,
`baseline-detail-review.json`, `recovery-control-build.json` and the separate
regression/control execution receipts. Additional records are
`periodic-change-review.json`, `periodic-source-review.json`,
`periodic-source-summary.json`, `periodic-remaining-witnesses.json`,
`recovery-control-comparison.json`, `periodic-control-comparison.json`,
`remaining-correlation-alerts.json`, `correlation-model-review.json`,
`periodic-repeat-comparison.json`, `correlation-source-review.json`,
`correlation-visual-review.json`, `periodic-actual-visual-review.json`,
`periodic-reference-review.json`, `periodic-reviewed-reference-check.json`,
`legacy-amplitude-prerequisites.json` and `preflight-full-cpu.json`.
Hash-verified cleanup retires temporary
raw pictures after preserving their measurements and decoder receipts.
