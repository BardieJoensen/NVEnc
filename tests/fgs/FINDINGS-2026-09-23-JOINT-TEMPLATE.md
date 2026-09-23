# Finite colour templates and final encoder evidence

September 23, 2026. This advances R3; **automatic retention is unfinished**.
R1/R2 are complete. R3 still needs whole-picture population/model evidence and
automatic output selection; R4–R8 still require temporal, independent quality,
quality-per-byte, speed and deployment qualification. Production automatic
retention and FEL remain disabled.

## Finite model

`NVEncFilmGrainJointTemplate.h` generates the native finite Y/Cb/Cr templates
for 4:2:0, including distinct colour seed initialization, signed integer AR
rounding, the rounded native 2x2 luma driver and internal template clipping.
An absent curve has an inactive template. A present zero-strength colour curve
still generates its internal template, an important distinction when one
component is source-preserved under shared chroma point-count syntax.

The finite moments keep native component energy, the common-coordinate
unrounded average-Y/Cb/Cr matrix and the rounded AR driver separate. They
include means; covariance consumers must subtract the corresponding means.
Nominal gains use the actual bit depth and grain-scale shift. Every result is
bound to its parameters and explicit finite seed ensemble. It is not a
worst-seed bound, a stationary gain or a complete displayed-picture prediction.
Strength lookup, output rounding, overlap and final picture clipping remain
separate required checks.

Pinned unchanged AOM synthesis agrees exactly on 6,144 three-plane template
sets and 57,323,520 samples: depths 8/10/12, lags 0–3, AR shifts 6–9, grain
shifts 0–3, eight component activity patterns and four seeds. Independent
direct offset/position enumeration agrees exactly on 228 moments. Twelve
stored AOM vectors cover strong clipping and both signs of colour coupling.
Deliberately wrong colour-seed, luma-driver rounding and nominal-gain variants
all fail. Twelve-bit coverage is for the pure model, not NVENC output support.

## Encoder integration

Commit `66c10412` adds optional `template_seeds` to the existing explicit
`--film-grain-joint-probe` manifest. It accepts 1–32 unique integer seeds and:

- Captures the actual final grain syntax and native base after retention and
  recovery, before lossy compression, bound to frame ID, PTS and history epoch.
- Computes finite joint-template moments from those exact final parameters.
  The declared ensemble is distinct from NVENC's later per-frame seed choice.
- Collects separate common-colour source cohorts alongside the unchanged
  per-component populations. It never substitutes a smaller denominator into
  sums from a larger population.
- Includes the fourth native frame and second moment buffer in the existing
  byte preflight. Successful completion requires every requested final model.

The option changes neither image/model decisions nor retention settings.
The extra work occurs only with `template_seeds`; ordinary mode remains off.
Invalid point counts, point order, shared 4:2:0 syntax and active offset ranges
reject the evidence request. Grain-off frames ignore stale model fields.
The source-reference tool now independently checks both populations.

The first CUDA build exposed a legacy `clamp` macro collision in the new
template call path. Commit `ca6f355c` protects the standard-library calls and
adds a macro-present regression. The rebuilt encoder succeeds; its binary SHA
is `5e49168962ca620f707b1abdb56afa357cbafa42089b4ff03368b2a4e1ed5dd7`.
The complete CPU suite passes. This binary has **not yet passed its GPU/output
comparison**; the last such comparison remains `5826421d`.

## Interrupted GPU qualification

The finite manual plan compares previous, candidate, original probe and final
model probe on 240-frame SDR/HDR windows. It also compares final native pixels
with raw encoder output, actual displayed AV1 parameters through dav1d, and
finite captured-model moments through unchanged AOM. Source identity, complete
decoding, clocks, metadata, common-cohort moments and failure paths are required.
The comparison code is prepared; its new capture acceptance remains unrun.

The September 23 attempt stopped **before acquiring a pause or starting any
GPU encode**. A concurrent host `apt upgrade` installed NVIDIA 595.91.07, while
the running kernel retained 595.71.05. NVML reports a driver/library mismatch;
Emby and `tdarr-node` also fail container startup for that reason. The new
driver exists for both installed kernels. Finish host maintenance before
manually retrying. Nothing is scheduled to launch automatically. This is a
host availability blocker, not evidence of encoder output damage.

Private evidence is under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`:

- `roadmap-r3-joint-template-20260923/`: finite plan, pinned AOM implementation,
  exact comparison, stored vectors and rejected mutations.
- `roadmap-r3-final-model-20260923/`: build receipts, CPU results, manual
  integration plan and tools, existing-output decoder controls and host blocker.

Read those stage reports and the root handoff before resuming. Keep original
sources, the unopened qualification corpus and the prior qualified comparison
build. Whole-picture acceptance and useful automatic selection are still the
next model work after the new capture is qualified; finite-template agreement
alone cannot approve a partial-retention candidate.
