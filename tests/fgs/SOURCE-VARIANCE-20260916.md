# Source variance and temporal training, September 16

Status: experimental; **not qualified or deployed**. Ordinary `2fa6cfd0`
remains installed and paused under the user-authorized excessive-grain fix.
No trial output replaces library media. The current handoff is in the fidelity
worktree's `tests/fgs/WORK-TO-PRODUCTION.md`.

The source ceiling bounds gross grain excess using 8x8 native luma variance and
the strongest model value over each observed intensity range. It limits conflicts
above `max(3, 2*sigma+1)` toward `1.5*sigma+0.5`, with existing source restoration
and temporal controls. Total variance includes detail; it is not a noise estimate.

The original scored top-decile fallback misclassified repeated roof texture as
random grain. Temporal training now excludes repeating blocks using two adjacent
source pairs. The finite matcher covers nine small integer translations, not
arbitrary motion. Both denoising strength and model training use the corroborated
observations. Keeping excluded texture in the denoising estimate blurred the
jacket in a rejected intermediate candidate, even though its grain model passed
the periodic-texture check. Ordinary strength fits use the physical intensity-bin
centres.

Initial candidates that preserved the first two source pictures passed the
excess-grain tests, but failed the unchanged Taxi base-fidelity canary. A controlled
raw/table replay reproduced that loss exactly. Replacing only the first two raw
base pictures with the existing clean base restored passing metrics: SSIMULACRA2
delta changed from -1.861 to -0.212 and Butteraugli from +0.094 to +0.007. Thus
startup base complexity changes later NVENC bit allocation. The first two
pictures cannot simply be omitted from the quality measurement. A separate
uncorroborated early-model experiment did not fix this and must not be deployed.

The current trial holds a bounded two-frame lookahead in bilateral mode. At
startup, future source pairs can qualify current-frame training without advancing
causal history or importing future model statistics. Scene, noise and timestamp
continuity are required. Repeated texture remains excluded. Unqualified one/two-
picture inputs retain their source; normal drain emits every queued picture in
order. The change adds three source surfaces and bounded startup observations;
throughput, memory and short-input behaviour require measured qualification.
It does not enable optional automatic retention.

Failed predecessors and thresholds remain recorded. The frame-paired independent
libaom comparison now uses native luma occupancy and matching table intervals;
its existing 0.80–1.25 bound is unchanged. The marginal colour-patch check permits
codec variation only when independently decoded synthesis is exactly zero and
same-settings no-FGS compression explains it. Known-bad controls must still fail.
Neither correction waives the base canary or permits replacing a periodic
positive without complete source comparison and fresh repetition.

Local evidence root:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/source-variance/`.
Read `training-v3/failure-review.json`, `training-v5/`, `canary-model-trace/`,
`canary-rate-diagnostic/`, `training-v6/failure-review.json` and the current
`training-v7/` build/trial receipts. Core `cb903a17` corrects the V6 jacket blur;
the independent base canary and native time-paired libaom comparison pass.
All 3,600 periodic-source pictures were compared. The eight reviewed stills
include the largest source-error changes and both original jacket witnesses.
The deliberate schedule change has a separately pinned positive; it needs a
fresh repeat. All earlier positives and failures remain recorded.

The periodic regression now also tests the grain-free base against the original
at the two detailed jacket witnesses. Its independent reference remains the
older amplitude build, even when the grain-schedule positive changes. The bound
is reference RMS * 1.10 + 0.10 in 8-bit-equivalent codes. The retained V6 encoded
negative fails at both witnesses (luma RMS 1.572/1.741); V7 passes (0.669/0.666,
versus reference 0.655/0.626). This checks detail that aggregate grain descriptors
can miss. It is a fixture regression, not a universal perceptual threshold.
The 84.5-second mesh witness still requires exactly zero synthesis; the 66-second
witness permits the reviewed tiny grain while separately protecting base detail.
Whole-source, HDR, performance and final runtime qualification remain pending.
