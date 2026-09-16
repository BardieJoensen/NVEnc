# Source-supported grain, September 16

Status: **candidate c7249cfb is not qualified or deployed**. The ordinary
production core remains `2fa6cfd0`, binary
`ef4799f6e7110e1057d8f728586d45e382b1ce3aa75c035403da35f05ca4b946`.
Tdarr admission is temporarily paused under the latest excessive-grain fix
authorization. FEL remains disabled and automatic-retention campaigns manual.

Two remaining causes were reproduced against unchanged originals. Small, weakly
textured or near-white regions could receive far more grain than their source
variance supported. In Severance S02E02 the light-panel source sigma is 0.977
codes versus 13.865 codes of added synthesis. Separately, the spatial selector
mistook repeated roof/foliage structure for grain-training evidence. In Chestnut
Man S01E02 around 106.125 seconds, 196–198 of 198 selected blocks contain repeated
structure, leaving fewer than the 40 required independent training blocks.
These are source-backed examples, not a diagnosis of every audit flag.

The correction has two parts:

- Existing source-tile analysis collects 8x8 raw luma variance. The model's
  maximum strength across each observed intensity range, including enclosed
  knots and a four-code reconstruction margin, is checked against that variance.
  Gross excess above `max(3, 2*sigma+1)` is limited towards `1.5*sigma+0.5`.
  Total source variance includes detail; this ceiling is not a noise estimator.
- Bilateral training excludes repeating structure using two adjacent source
  pairs. An existing repeatability kernel covers small integer motion and
  removes a local plane. Strict spatial flats can train immediately; uncertain
  top-decile candidates wait for two source pairs. Insufficient evidence keeps
  source pixels. Initial observation does not enter the long rejection hold;
  an actual rejected fit retains the existing hold and recovery protection.

Curve limiting uses existing residual restoration and temporal controls.
The variance calculation adds no source pass or host synchronization. Temporal
training adds one GPU kernel and a previous-luma copy to ordinary bilateral mode,
covered by an existing barrier. It does not enable optional automatic retention.
Runtime, size and long-source behavior still require qualification.

The earlier 95736a03 prototype passed the old suite but still replaced roof
texture. The f588b7b8 range correction alone also failed. The first temporal
candidate, 8408dfff, improved real scenes but entered a long startup hold and
failed short grain fixtures/export. These failed trials remain explicit controls.
Current c7249cfb fixes that startup distinction.

The synthetic training fixture uses the same spatial distribution for moving
repeated texture and independent grain, in 8/10-bit CQP/QVBR. The range-only
negative fails all four repeated-texture checks; c7249cfb passes all eight arms,
including nonzero independent synthesis and preserved displayed variance.
Thin-highlight/weak-texture controls and ten fresh real pilots also complete.
The CPU suite and unchanged table-export tests pass. The initial KAT only fails
its synthesis-from-first-frame assumption. Its replacement measures displayed
noise against the actual source in every startup picture and band, requires
0.60–1.35 amplitude and a usable independent-grain fit by picture two, and keeps
all later bounds. CPU controls reject single-picture gaps and excessive flashes.
The fresh broad GPU gate, full-source validation, HDR controls and timings are
pending. Do not publish a new positive baseline merely because output changes.

Live evidence:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/source-variance/`
contains `repeated-training-diagnosis/`, failed `training-qualification/`, and
current `training-v2/`. The canonical handoff is the fidelity worktree's
`tests/fgs/WORK-TO-PRODUCTION.md`. No trial output has replaced library media.
