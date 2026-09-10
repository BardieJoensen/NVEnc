# Retention development while the ripple repair has priority

Status: preparation and CPU qualification complete. The new CUDA-filter changes
have not been built or qualified on the GPU. Production stays on ordinary
`497caa64`; the previously qualified optional reference remains `9c1664d4`.
The user deferred substantial encode, decode, metric and speed campaigns until
the running repair finishes.

The objective is fast, efficient compression with faithful picture detail and
grain in SDR and HDR. A storage allowance needs comparisons against the live
encoder, including spending the same extra bytes on ordinary FGS at a higher
quality setting. Previous auto-versus-auto improvements do not establish that
trade for the current candidate. The policy decision is therefore deferred
until there is useful quality-per-byte and playback evidence.

## Existing evidence without new encodes

`retention_diagnostics.py` reads completed logs in one streaming pass. All six
full-episode logs match their recorded hashes and frame counts. Initial analysis
took 7.38 seconds under a one-core CPU quota. No media payload was decoded.

| Source | Covariance events | Earlier colour veto | Successful recovery followed by final source preservation |
| --- | ---: | ---: | ---: |
| South Park S23E01 | 21,216 | 21,106 | 48 / 48 successful recoveries |
| The Gentlemen S01E01 | 69,290 | 68,479 | 604 / 684 successful recoveries |
| House of the Dragon S03E08 | 96,568 | 83,692 | 7,307 / 7,691 successful recoveries |

The old filter calculated covariance even when the earlier colour condition
prevented consuming that result. That condition rules out 173,277 of 187,074
calculations (92.625%). This counts avoidable calls; it is not a 92.625% encoder
speedup. Their runtime share has not been measured in isolation.

An unsuccessful recovery with valid covariance can mean either a failed model
fit or rejection of freshly fitted colour. Earlier aggregate reports called
this a rejected fit; that attribution was too specific. The analyzer preserves
the ambiguity as `model_or_fresh_colour_unknown`. The combined colour veto
also cannot distinguish sparse evidence, spatial correlation or luma coupling.
These are model decisions, not labels of damaged media.

## Changes prepared in the fork

`chroma_restore_reason` exposes the first failed eligibility condition while
the existing boolean API retains its qualified behavior. It distinguishes
signalled coupling, too few observations, invalid/missing energy, spatial
correlation and measured luma coupling. Configuration failures are separate.
The present SDK bit field cannot represent an out-of-range shift; that
defensive reason remains reserved.

The filter records both held-model colour decisions and, when reached, both
fresh-model decisions. It separates covariance not attempted, rejected
covariance, failed recovery fitting and failed fresh-colour eligibility.
Whole-source reasons distinguish early flat-block rejection, missing model,
feedback rejection, missing adjacent picture, amplitude/local/colour failure,
covariance recovery, the DC guard and recovery hysteresis. Multiple current
reasons can coexist; hysteresis alone is no longer mistaken for a new failure.

Covariance is now calculated only when the existing colour and minimum-frame
conditions permit using it. The target is local scratch; the old code could
not consume it when either condition failed. No fit threshold, retention
limit, source-preservation rule or recovery condition is relaxed. Cached
mismatch results avoid duplicate scans just to populate the diagnostics.

CPU boundary tests cover both colour components, positive/negative coupling,
observation limits, spatial correlation, invalid evidence and unchanged input
structures. A separate probe compiles the actual `9c1664d4` CPU model and the
edited model against the same 20,000 generated cases. All 40,000 component
decisions match, including 10,875 accepted decisions. The full CPU suite passes
in 28.3 seconds with a one-core quota and low scheduling priority. Six tests
cover the diagnostic parser; seven cover the tradeoff planner/comparator.

CUDA compilation, raw-base/grain-table comparison and the existing GPU
regressions, including `chroma_coupling_entry`, are deferred. Final encodes
must remain within the established repeated-encode variation. CPU equivalence
does not certify decoded pictures or speed.

## References and comparison preparation

Twenty-five existing files have additional hard links in dedicated reference
directories. They include three original full episodes, Bridge and Shining
source excerpts, lossless diagnostic clips, the libaom source/base pair, a
known ripple negative and ordinary/auto outputs. No media payload was copied.
The five primary sources total 15,126,585,999 bytes: those blocks remain
allocated if earlier paths are removed. Other linked diagnostics and outputs
also remain until review ends.

Links were checked for the same inode and unchanged recorded size/mtime.
Expected payload hashes come from completed qualification records and must
be reread before experiments. Hard links protect against removal of the old
directory entry, but share its contents. Never edit or transcode them in place.

`retention_tradeoff.py prepare` creates 70 explicit commands for seven windows:
animation, ordinary SDR live action, the Gentlemen jacket, two modern UHD HDR
windows, Bridge and coarse-grain Shining. Each has production FGS, qualified
auto and plain AV1 at three QVBR settings, plus a fixed-retention candidate
control to isolate the binary change. Binaries, sources, windows and metadata
flags are pinned. The tool does not execute those commands. Routine windows
are predetermined and await scene review. Confirmed clean SDR and fine-grain
UHD originals would broaden calibration; one-second lossless regressions are
not title benchmarks.

The comparator selects measured primary-video byte matches within 3%; this is
a measurement tolerance, not a Tdarr size allowance. Missing matches request
more operating points. Failed quality checks are excluded; mismatched source
windows cannot be paired. Different metric/model/display definitions have no
computed score delta. Numerical scores alone never establish a visible gain.
SVT setting calibration and metric execution remain deferred.

## Upstream review and next implementation choices

[SVT's documented pipeline](https://raw.githubusercontent.com/AOMediaCodec/SVT-AV1/main/Docs/Appendix-Film-Grain-Synthesis.md)
separates denoising, flat-region selection and residual-model estimation.
Its Wiener filtering and per-picture modeling are useful comparisons, but
do not establish that changing our denoiser would improve real footage.
`reference_compare_real.py` already compares libaom and this estimator with
the same source and clean base. Extend that comparison to separate filtering
problems from fitting problems.

[libaom's model](https://aomedia.googlesource.com/aom/+/refs/heads/main/aom_dsp/noise_model.c)
(reviewed blob `562252b3bb2c0c82df0fc0c908e1304deedd70c6`) estimates colour's
luma-correlated contribution and adjusts its remaining noise strength. This
supports investigating joint luma/colour recovery if new diagnostics show
coupling dominates. Our component-restoration rule is narrower because it
substitutes source colour while changing luma synthesis. Removing that rule
would discard a known protection; upstream code does not justify doing so.

The first post-repair diagnostic runs should identify whether to prioritize
additional independent observations, correlated-colour recovery, or fit
calibration. Use those failures to select small CPU-replay or GPU controls.
Then compare quality per byte across retained real sources. Better model
coverage and a worthwhile visible benefit remain development objectives.

Evidence lives under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/`:
`existing-log-analysis.json`, `chroma-equivalence.json`, `cpu-suite.json`,
`reference-retention.json`, `comparison-manifest.json`, `comparison-plan.json`.
No deployment or automated post-repair encode job was scheduled.
