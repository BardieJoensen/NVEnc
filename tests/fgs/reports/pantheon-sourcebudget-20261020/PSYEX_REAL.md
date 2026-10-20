# R15: real preservation at a disqualifying rate

The legal TF-off/public-QP1 PSYEX arm passes both predeclared E05 numerical
texture screens, with substantially improved full-window controls. It uses
**190.4115432 Mbps, 19.6777x the original packet rate**, so it fails the user's
practical ceiling. No playback or full-episode qualification occurred. This is
high-rate feasibility evidence, not a repair or a minimum-rate finding.

The [contract](ROUND15_REAL_CONTRACT.md), [compact result](psyex-real-result.json),
[independent review](psyex-real/round15-outcome-review.md) and
[frozen reproduction manifest](psyex-real/manifest.json) bind the evidence.
All original-rate, texture, clean-region, detail, banding and temporal criteria
remain unchanged. E04 is not tested by this arm.

## Policy and intervention delivery

The unchanged admitted R8 PSYEX app/library encoded the untouched 336-frame E05
fixture. The only policy changes were TF disabled and public min/max QP both1;
fresh statistics were used for both passes. Requested10313kbps is not achieved
rate. Static QP was not manually set: the API default35 is temporarily43 during
first pass, then VBR setup derives30 from this request. Public QP1 maps to internal
qindex4, not the internalq1 used in R13/R14. See the frozen source audit and
effective-QP addendum.

Both R11 encoder observation replays produce byte-identical IVF, reconstruction
and statistics to the unmodified encode. All336 samples agree across the app,
dav1d, libaom and NVDEC; the240 metric samples match positions96:336 exactly.
Independent syntax parsing maps display216/scored120 to hidden coded event314,
coded ordinal210. That mapping was rederived, not assumed from R8.

On that frame, full coding input is byte-identical to the original on all planes.
All4809 traced final owners are positive-EOB, with no skipped quantizer calls.
Every pixel in the three frozen shirt/background/face regions receives **actual
forward qindex4**, joined exactly to independent decoder q/DQ/EOB/IQM, source,
predictor and preloop reconstruction. This is a delivered precision intervention
on the traced population, not a claim about every TU of every frame.

R15's chosen support/transforms reconstruct the original almost exactly in the
local raw-coefficient diagnostic. Shirt rawHF is.606303 versus.606320 original;
scalarq4 gives.572234, final.577348. All shirt transforms are at most16 pixels
wide/high, and every target pixel has residual support. Preloop equals postloop
on this frame. Later optimizer/noise-normalization stages make small, mixed
changes. Changed q/DQ/EOB does not necessarily mean changed pixels.

These observations contrast with R8's retained skips/large transforms and
source-processing loss, but do not isolate any one cause: prediction, support,
transforms, references, source processing and precision changed together.
The local raw diagnostic is not a deployable encode or a coded-bit measurement.

## Preserved texture and remaining regressions

Five-frame midpoint screen, using the same untouched source and fixed ROIs:

| Region | Source HF | R15 HF | HF error | ACF1 error | Source HF correlation |
|---|---:|---:|---:|---:|---:|
| Shirt |.619353|.596923|−3.622%|.021890|.930812|
| Background |1.778495|1.753108|−1.427%|.005418|.989364|

Both pass HF±10% and ACF-error≤.05. Across all240 fixed-ROI rows, shirt HF error
ranges−8.760% to+1.690%; background−5.362% to+.484%. Shirt ACF error reaches.05528
once, while its p95 is.02122. No all-frame maximum gate was preregistered, so
this tail remains reported rather than silently redefining acceptance.

All12870 frozen control tiles have lower MSE than R8; overall mean/p95 fall
5.6172/15.0627 to.09766/.16877. Not every descriptor improves:41 HF-error pairs
and612 ACF-error pairs worsen. The51 quiet tiles all improve MSE and HF absolute
error; mean HF error falls.08624→.01717. Ten of50 evaluable quiet ACF errors
worsen. Signed quiet HF excess is positive on9/51 tiles, with p95+.00615 and
maximum+.01066 at frame200,x920,y728. This small control population does not
prove exhaustive absence of source-clean noise.

Face MSE is.07465, strong-edge gradient MAE.27432 and gradient ratio.99844.
Full-reference results and tails support broad numerical preservation:

| Metric | R8 | R15 |
|---|---:|---:|
| VMAF mean / p1 excluding frame0 |92.60 /81.66|99.64 /98.65|
| VMAF-NEG mean |90.90|99.30|
| PSNR-Y mean |40.50|59.54|
| SSIMULACRA2 mean / campaign p5 |53.74 /38.59|96.21 /95.49|
| Butteraugli2-norm mean / campaign max-distance p95 |1.663 /8.56|.152 /.85|
| Full-reference CAMBI mean |.14153|0|

Campaign percentile summaries use its existing rounding/order convention; the
review separately reports NumPy-derived raw-frame tails. GPU metrics use
campaign.py and the required CUDA paths. Full-reference CAMBI is zero on every
scored frame. This is numerical evidence, not a guarantee against visible banding.

Across239 transitions, temporal-HF-correlation absolute error mean/p95 falls
.07518/.26074→.00415/.01415 for shirt and.03444/.11653→.00135/.00459 for background.
Fixed-region correlation is descriptive and not motion-compensated. Native-size
stills show source-like fine shirt texture in R15; **no player/display playback
was observed**. The [stills manifest](psyex-real/stills-manifest.json) binds all
three native-size panels and their exact source surfaces.

## Rate, runtime and scope

Scored Matroska video packets at positions96:336 measure190.4115432Mbps versus
original9.6765224Mbps and R8's9.6279048Mbps. Full336-frame rate is204.0344194Mbps.
Packet/remux evidence is in the encoder receipt; container size and requested
rate are not used as quality-comparison rates.

The two passes took73.3558+619.1211=**692.4769 seconds for336frames**,1.870x R8's
370.3358 seconds. This is a bounded shared-host run with lp1 and CPU0–7, not an
isolated throughput benchmark or full-episode estimate. Neutral replay and
validation times are separate diagnostics, not included in encoding time.

Confidence is high that this precise bundle preserves the measured E05 texture
statistics and substantially reduces these numerical errors at its actual rate.
Confidence is high that it is disqualified by the source-rate ceiling. Minimum
necessary precision, affordable spatial allocation, E04 behavior and perceptual
acceptance remain unknown. No codec-limit, NVENC-defect or FGS-only conclusion
follows. There is no production-change proposal.

## Independent review and corrections

The reviewer independently reconstructed native-ROI descriptors and summarized
all240 texture/metric rows and51 quiet controls before receiving the parent's
conclusion. It accepted a high-rate numerical feasibility result and rejected
practical qualification. The parent inspected decisive native joins, packet
costs, complete control summaries and the native-size shirt panel.

Pre-execution review corrected public-QP versus internal-q terminology and the
effective static-QP chain. The first scoring execution failed before metrics:
the old fingerprint helper returned path/SHA while the new native receipt also
contained size. The smallest correction checks recorded canonical path, SHA and
live size separately; a first fix's tautological path comparison was also caught
before rerun. The successful second run retains every gate. Reporting review
also added explicit assessment/control-table cross-binding and clarified that
coefficient-state changes need not change pixels. Failed receipts/drafts remain
preserved, not relabeled as successful measurements.

## Next discriminator and reproduction

The [R16 contract](ROUND16_TF0_BUDGET_CONTRACT.md) selects the missing source-budget
TF-off policy arm, with normal allocation and no QP bounds. It changes only the
TF flag from R8 plus rate-only calibration and fresh statistics. A failure must
be classified using actual support and scalar loss before selecting allocation
or decision tracing; coarse q alone is not sufficient.

[Reproduction notes](psyex-real/README.md) link literal commands, pinned tools,
inputs, scripts, receipts, independent derivations and metric artifacts.
Large traces/media/full control tiles remain hash-bound in the active scratch
root `/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`; later rounds still
depend on them. Archival/cleanup is pending a valid stopping condition, and old
archives remain immutable.
