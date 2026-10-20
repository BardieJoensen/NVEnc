# R16: temporal filtering disabled at the original packet budget

Status: completed, independently reviewed matched-rate negative result.
TF-off alone fails both E05 texture screens. No practical candidate or playback
acceptance exists.

The [contract](ROUND16_TF0_BUDGET_CONTRACT.md) tests the admitted R8 policy with
only temporal filtering disabled and the bitrate request calibrated to
99–100% of the untouched original's 9.6765224 Mbps scored-window packet rate.
No public QP bounds or static QP change are used. TF-off changes the coding
input and reference/search policy together; this is not an isolated pixel
ablation.

The first request, 10313 kbps, produced **9.8804608 Mbps** over scored frames
96:336, exceeding the ceiling. Its full 336-frame rate was 10.2541509 Mbps.
Passes took 64.6435 and 311.1749 seconds, totaling **375.8184 seconds**.
This arm is ineligible for the decisive quality comparison. The prescribed
proportional corrections used fresh two-pass statistics:

| Request kbps | Scored Mbps | Full336 Mbps | Two-pass seconds | Eligibility |
|---:|---:|---:|---:|---|
| 10313 | 9.8804608 | 10.2541509 | 375.8184 | Above source |
| 10070 | 9.7013600 | 10.0236371 | 373.0344 | Above source |
| 10014 | 9.3933528 | 9.9653091 | 375.4678 | Under cap; outside matched interval |

The last request decrease produced a much larger scored-rate change per kbps
than the preceding decrease. The [method addendum](ROUND16_RATE_REFINEMENT.md)
therefore replaces proportional feedback with bounded midpoint refinement
between the measured 10014/10070 endpoints, starting at 10042. Only bitrate
request and fresh paths change. The source ceiling and matched-rate interval
remain fixed. Endpoint-equal rates are allowed as quantizer plateaus; they still
narrow the request bracket and do not by themselves imply nonmonotonicity.
The [completed calibration records](psyex-tf0/calibration-initial/manifest.json)
retain both later attempts and the reviewed method correction.

The [refinement preflight](psyex-tf0/refinement-preflight/manifest.json) freezes
the corrected runner/replay, independent binder, observation/scoring wrappers,
no-encode preview and synthetic validation controls. Review rejected an
incomplete lineage validator and a replay incorrectly based on the old R8
encode. The parent replaced them with explicit endpoint/predecessor validation
and replay of the selected refinement's own pass-two command and statistics.
Four valid synthetic states and five corrupted states behaved as prescribed;
these are software controls, not measured encodes. The first real midpoint
request is 10042. No quality gate was changed.

That request produced **9.6698472 Mbps**, 99.9310% of source and 0.4356% above
R8's measured rate. Its 240 scored packets contain 12,087,309 bytes. The full
336-frame rate is 10.001128 Mbps. Passes took 65.073485 and 307.180646 seconds,
totaling **372.254131 seconds**. Independent review confirms the exact bracket,
outer command, fresh statistics and packet sum. Calibration stops at this
eligible arm; see the [selected calibration](psyex-tf0/selected-calibration/manifest.json).
Decoder agreement, bitstream mapping and coefficient observation subsequently
passed. Quality results below remain separate from those validity checks.

The [preflight manifest](psyex-tf0/preflight/manifest.json) preserves the exact
runner, provenance, packet records, commands, reviews and prepared validation
scripts. Preparation reviews required corrections to recursive calibration
lineage, live dependency hashes and recorded packet-rate checks. The final
runner and replay were released after those corrections. An outer execution
receipt retains failures even before the inner runner can create its receipt.
The early inline lineage smoke lacks preserved source; its limited provenance
is explicitly recorded and is not substituted for review of the actual runner.

## Completed quality result

All336 app/dav1d/libaom/NVDEC/native decoder outputs agree exactly; encoder and
decoder instrumentation are neutral. Independent syntax binding maps the target
to event314/coded210, and all2870 final-owner tokens are admitted, including
2130 positive-EOB units. On the observed target frame216/scored120, coding input
equals the original on all planes; source-boundary equality was not measured on
every frame.
The [outcome manifest](psyex-tf0/outcome/manifest.json) freezes85 source artifacts
(1.92MB) plus compact support, with external traces/media/large controls identified.
It includes commands, receipts, native admission, GPU campaign results, full-window
metrics, review derivations and grayscale stills.

| Five-frame texture screen | HF error vs source | ACF absolute error | Result |
|---|---:|---:|---|
| Shirt | −83.7379% | .175840 | Fail |
| Background | −41.4265% | .111610 | Fail |

Required amplitude tolerance remains±10%, paired with ACF error≤.05. General
scores do not override failure: VMAF92.61, NEG90.91, PSNR-Y40.57, SSIM.9913,
SSIMULACRA2 mean53.67 and Butteraugli mean1.656. Compared with R8, SSIMULACRA2
min/p1/p5 regress from25.37/32.62/38.59 to18.56/20.07/35.00, and PSNR-Y p1 falls
36.25→35.58. CAMBI improves (mean.28585→.20175; p95.8798→.6618).
All12870 control tiles are paired: mean HF absolute error improves
.6485→.6073 while p99 worsens1.495→1.715. Quiet MSE improves, but edge positive
HF maximum worsens. Temporal correlation errors are mixed. No whole-window,
source-clean, banding or temporal acceptance is claimed from these mixed results.

The selected arm costs372.2541s for336frames across both passes, versus
R8's370.3358s (+0.52%). This is bounded-fixture cost, not full-episode throughput.
Its actual9.6698472Mbps rate meets the original cap but its texture does not.

## What the native stages establish

On frame216/scored120, all20000 shirt pixels invoke final quantization and have
positive EOB at actualq71. Background has43912 positive-EOB pixels,48 invoked
zero-EOB pixels and1040 uninvoked pixels, at actualq79–87 on invoked support.
Face has81472 uninvoked pixels out of240000; that missing support stays separate.

| Frame120 stage | Shirt HF | Background HF | Face HF |
|---|---:|---:|---:|
| Original/coding input | .606320 | 1.676388 | 2.700847 |
| Fixed-choice raw native inverse | .525892 | 1.664646 | 2.520497 |
| Initial scalar | .127405 | 1.307269 | 2.433143 |
| Native preloop | .127405 | 1.307366 | 2.433012 |
| Native postloop | .068659 | .872906 | 2.141630 |

Initial scalar quantization is the dominant observed coefficient-stage loss for
the shirt under these fixed decisions. Later optimizer stages change no shirt
units, one background unit and five face units; the noise stage changes none.
Raw shirt reconstruction already misses amplitude, so scalar improvement alone
cannot be assumed sufficient. Filtering further changes texture and also improves
some pixel/structure errors; it is not uniformly harmful. Single-frame stage
localization does not causally explain every full-window regression.

The independent reviewer reconstructed token masks and recomputed preloop/postloop
group SSE directly from native surfaces, with exact agreement. An earlier check
only summed already-grouped SSE; the parent rejected that as insufficient spatial
verification. The preserved addendum limits raw/scalar checks to aggregate closure.
Other preserved failures were schema binding errors, a missing dependency in the
system Python and an uninvoked-token parser case. Corrections changed no metric
formula or gate.

The parent inspected the three native-size grayscale panels (source/R8/R16),
confirming visible shirt smoothing in these stills. There was no color-display
or motion playback observation. The next [R17 diagnostic](ROUND17_FIXED_Q4_CONTRACT.md)
uses one nativeq4 point on the new TF-off captures, with exact baseline controls.
This differs from prior TF-on/original-source replays because its predictors,
transforms and final ownership came from a real matched-rate TF-off encode.
It has no bitrate or deployability claim. A fixed-choice failure cannot reject
a real low-q policy that changes search and transform decisions.
