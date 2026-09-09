# Automatic retention: grain recovery, detail preservation and cost

Core `9b8217ec92b9b9df13830a4a9714b49c96485021` passes the controlled
cost/detail, texture-residual, nine decoded edge/grain cases, real-footage
checks, CPU suite and final GPU gate. Qualification is complete for this
optional-mode improvement. Production remains on qualified core `497caa64`, with ordinary
`retain=0`. Automatic retention remains optional.

Candidate SHA-256:
`151650189b2edb24e99d023764ea8379cbcd26dbc332262632314eae88aa28ac`.
The incremental build retains the base Meson version label r4245; the binary
hash and `candidate-edges-build.json` identify the actual tested core sources.

## Changes

The amplitude recovery fit used a smoothed brightness curve and spent scaling
points on interpolated, unoccupied bins. It could reject a sharp curve that
AV1 can represent, causing expensive whole-source preservation. Recovery now
uses occupied-bin amplitudes and actual measured brightness, pools coincident
quantized brightness positions, and simplifies within AV1's 14 luma / 10
chroma scaling-point budgets using observation-weighted error.

This retry still requires the normal AR solver, synthesis guards and existing
strict quantized amplitude check. Invalid or incomplete intensity evidence
cannot qualify; the existing source fallback and recovery hysteresis remain.
The debug field `strengthRefit` identifies successful occupied-bin recovery.

Optional bilateral auto extends averaging along supported structure while
limiting averaging across it. Block-texture protection follows local noise,
so a frame-wide weak-noise median cannot switch off protection in a noisier
region. A separate pixel-centred edge cue spans analysis-block boundaries.
Confident edges get full directional protection independently of the weak-noise
ramp. Confidence varies continuously; historical pixels are not blended.

Ordinary/fixed retention, FFT3D and motion retain their existing filter
support. The retention ceiling and source-preservation fallback are unchanged.

## Controlled results

These compare the final candidate with the preceding directional-auto study
at QP 20 and `retain-max=0.1`, using identical deterministic sources. A second
sweep also exercises 0.5. There is no QP increase to obtain savings.

| Known-clean picture | Size versus previous auto | Detail-transfer diagnostic, previous → new |
| --- | ---: | ---: |
| Fine directional detail | −5.15% | 0.564 → 0.901 |
| Coarse directional detail | −2.45% | 0.635 → 0.713 |
| Woven detail | +5.66% | 0.397 → 0.718 |
| Moving woven detail | +5.72% | 0.393 → 0.717 |
| PQ woven detail | +5.93% | 0.456 → 0.799 |
| PQ directional detail | +7.37% | 0.818 → 0.942 |
| Sharp brightness-dependent grain | −47.78% | 0.997 → 0.988 |

The last case now costs about 10% above the historical ordinary/default
output, instead of about 111% above it. Calling that curve intrinsically
unrepresentable in the preceding cost report was too strong: it was a
limitation of that fitter. All representable sharp-curve controls recover
without source fallback. Some cases deliberately spend more bits for more
measured detail; this is not a universal size reduction.

Nine 48-frame recovery controls cover SDR, PQ, HLG, shifted, horizontal and
diagonal boundaries, a mid-scene strength-curve change, and 20-band SDR/PQ
negatives that exceed the available fit capacity. Every picture is decoded
with grain on and off, and the emitted synthesis is checked. Representable
cases must meet per-band grain bounds and an edge-error bound chosen before
the accepted prototype: at most 0.25 extra 8-bit code values of mean edge error
relative to prior source preservation. Both 20-band negatives preserve source
frames without synthesis on all 48 pictures, with decoded pixels identical
to the previous source-preservation output. The final pixel-equality assertion
was also checked directly against both saved decoded files, without re-encoding.
Encoding quantization still applies.

Representative mean edge errors, previous → new: SDR 0.279 → 0.248,
PQ 0.081 → 0.109, horizontal 0.252 → 0.253, diagonal 0.310 → 0.509.
Across representable cases, per-band median grain amplitudes are 0.878–1.051
of the source. The eight texture-residual cases are 0.902–0.993 of source
high-frequency residual amplitude. These diagnostics include encoding error
and are not percentages of overall picture quality or HDR perceptual fidelity.

## Rejected approaches and regression evidence

- Fitting bucket centres instead of measured brightness made files smaller but
  produced about 1.7 times the source grain in some weak-grain bands. The
  decoded band checks reject that prototype even though synthesis scanning
  alone accepts it.
- Core `fd8b1113` passed the initial six grain-amplitude cases and real-footage
  checks, but the added edge check exposed softening: SDR edge error 1.002
  versus 0.279 previously. It is superseded and is not an accepted release.
  The final harness re-ran this binary and rejected it specifically for edge
  softening, while its grain and synthesis checks passed.
- Local edge detection alone, a stronger confidence ramp, and narrower support
  left roughly 0.64 code values of edge error. Removing the noise ramp from
  confirmed pixel-edge protection fixed that remaining regression. The
  ineffective narrower-support change was discarded.
- A separate 0.05-ceiling study saved more space but lost measured coarse woven
  detail, so it was not chosen as the general trial setting.

These failed artifacts are retained separately. A cost score alone cannot
qualify an automatic-retention change.

## Qualification and operating limits

CPU suite: passed. Final controlled sweep: 16 cases at two retention ceilings,
passed. Texture residual: eight cases, passed. Decoded recovery/edge suite:
nine cases, passed. Final real-footage checks: passed, including all 16 complete
grain-on/off decoded outputs. The three ordinary-mode real-clip pairs have
identical decoded pixels. Final quick GPU gate: passed (known-answer fixtures,
table export/failure paths and both model-gate controls).

The real test uses equal 0.1 ceilings, paired old/new/new/old encodes of the
150-second Gentlemen source clip, and the pinned Taxi, Silo and Alien clips.
It checks complete grain-on/off decoding, synthesis safety, frame/property
preservation, unchanged ordinary-mode pixels and the known jacket samples.

All real encodes are complete. The paired Gentlemen timings are 65.09 / 67.94
seconds for previous auto and 69.55 / 70.20 seconds for the new mode: about
5.05% more wall time, with 1.16% fewer output bytes. These ran alongside the
existing repair work, so they are a bounded shared-hardware measurement.
The 24-frame Taxi, Silo and Alien outputs change by −0.28%, +0.35% and +0.45%
respectively; their short timings are dominated by startup and are not useful
whole-film speed forecasts. All real-output decodes, property checks,
synthesis scans and jacket checks passed, including both candidate repeats.

The trial operating point remains `retain=auto,retain-max=0.1`. This is not a
file-size cap. Fine directional and PQ woven synthetic clips still cost about
95% and 79% more than ordinary/default encoding respectively; uncapped auto
can cost substantially more. Difficult frames can still require complete
source preservation. Whole-library storage and speed cannot be predicted
from these short controls.

No Tdarr validation stage, production flow, library replacement, repair service,
playback-yield policy or recovery-download hold was changed by this work.
The unrelated FFprobe XML/AddressSanitizer investigation remains deferred.

## Evidence

Reports: `/opt/docker-apps/logs/fgs-ripple-repair-20260906/auto-retention-20260909`.
Encoded/decoded artifacts: `/tmp/downloads/fgs-auto-retention-20260909`.

- `candidate-edges-build.json`: final binary, build image and source hashes.
- `qualification-edges.json`: each final stage and actual exit status.
- `controlled-edges-summary.json`, `texture-edges-final.json`: decoded results.
- `preservation-pixels.json`: final fallback pixel-equality assertion checked
  against the saved decoded files.
- `strength-edges-final/report.json` and `real-edges-final/report.json` in the
  artifact root: source, harness and binary identities with detailed results.
- `prototype-disposition.json`, `edge-negative-fd8.json` and
  `rejected-centres-control.log` / `rejected-edges-control.log`: rejected
  candidates and negative controls.
- `qualification.json` and names without `edges` refer to the superseded
  `fd8b1113` build and must not be used to qualify the final candidate.
