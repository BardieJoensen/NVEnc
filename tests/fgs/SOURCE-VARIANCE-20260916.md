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
All five full-source outputs (509,315 pictures total) now strictly decode and
pass header inspection. The four selected episode repairs also have complete
source/library/candidate timestamp agreement and actual source-matched witness
review. Both HDR10 trials preserve metadata on all 720 pictures each. Exact
runtime reproduction and paired performance qualification remain pending.

The full Play Dirty dialogue witness exposed a limitation in the original
amplitude check: random regenerated grain is penalized for having different
pixels even when its strength is supported by the source. The original failed
result is retained. Candidate grain-on RMS exceeds the plain control by 0.165
codes on average, but grain-off base error exceeds it by only 0.0168 (maximum
0.0771), within the unchanged 0.05 mean / 0.15 peak margins. Source-flat fine
texture RMS is 0.786 in the original, 0.133 in the deployed encode and 0.628 in
V7. The twelve exact pictures have no strong-grain flags in the measured quiet
patches. Source/old/V7-on/V7-off stills show restored fine grain without the
harsh overlay; shirt, curtain, hair and cable structure remain present.

`amplitude_regression.py` retains its original grain-on error diagnostic and
3-code synthesis cap. It now applies the same picture-error margins to the
grain-free base and coarse displayed picture, and compares native fine-texture
energy with source-only selected tiles. Synthesized frames without adequate
source coverage cannot pass. Independent random-noise positive controls prove
the phase problem; clean-source noise, excess grain, coarse overlays, new blur,
missing coverage and prior severe encoded negatives still fail. This is a
scene-specific check, not a general noise estimator or perceptual certificate.

The dialogue tradeoff is recorded rather than hidden: SSIMULACRA2 changes from
75.161 to 73.573 and Butteraugli from 1.042 to 1.115 as fine grain is restored.
Base-only scores are 75.071 / 1.049. The retained severe negative scores
55.176 / 2.230. These are finite displayed-picture comparisons; V7 is not a
claim of a perceptual-score win on every scene. See `training-v7/dialogue-diagnosis/`,
`dialogue-review/` and `amplitude-review.json` alongside the retained original
`final-gpu/gate-1/` failure and fresh frozen-harness repeat.
