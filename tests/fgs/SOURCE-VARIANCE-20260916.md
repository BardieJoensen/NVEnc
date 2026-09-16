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
arbitrary motion. Spatial denoising estimates stay independent of the training
exclusions. Ordinary strength fits use the physical intensity-bin centres.

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
`canary-rate-diagnostic/` and the current `training-v6/` build/trial receipts.
Whole-source, HDR, performance and final runtime qualification remain pending.
