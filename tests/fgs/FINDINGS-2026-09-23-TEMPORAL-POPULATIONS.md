# Structured source populations: temporal evidence

The new CPU reference measures whether temporal source information can help
separate persistent detail from grain in regions rejected by R1. It is an
offline research tool, with no encoder call sites or population acceptance bits.
R1's source rules, 8% variance / 0.08 covariance limits and reserved corpus are
unchanged. Automatic partial retention remains unfinished.

## Measurement and its limits

`temporal_population_reference.py` takes eight adjacent source tiles and the
actual rounded current retained base. On common 4:2:0 coordinates, Y is the
2x2 source average. Three older frames form one history average and four form
the other. The current picture belongs to neither history group.

For a stationary scene with independent zero-mean grain, cross covariance of
`current - history_A` and `current - history_B` estimates the current grain
covariance while cancelling persistent structure. The two histories do not
share their noise. The tool also reports the asymmetric source/base residual
cross covariance, covariance of removed material with persistent structure,
history disagreement and differences at temporal lags 1, 2 and 3.

Those assumptions are necessary, not facts about a source merely because its
pictures are adjacent. Motion, temporal correlation, exposure changes and cuts
can invalidate the estimate. Negative estimates remain signed; no PSD repair,
clipping or favorable population reassignment hides them. HDR results use
native code units scaled to 8-bit units, not perceptual light or display units.

This direction follows the separation of film-grain estimation from picture
detail: AOM's [draft technical report](https://aomedia.org/docs/CWG-C051o_TR_AOMedia_film_grain_synthesis_technology_v2.pdf)
describes selecting flat regions because denoising can remove structure. NVIDIA's
[temporal-noise-reduction documentation](https://docs.nvidia.com/vpi/algo_tnr.html)
also treats motion detection as part of temporal filtering. The new estimator
is our conditional diagnostic, not an implementation or qualification of either
system.

## Independent controls

Eight new tests cover an independent scalar covariance oracle, cross-matrix
orientation, cancellation of static texture, depth/offset invariance, quiet
source, exact source preservation, persistent detail removal, invalid source
history and signed negative estimates. An explicit zero-grain moving sinusoid
produces a large positive apparent grain estimate. It remains a mandatory
counterexample: temporal energy alone cannot approve synthesis.

The complete CPU run passes 193 Python tests in 27 suites and 29 C++ programs.
This change affects CPU research tooling only; no encoder rebuild or repeated
ordinary-mode GPU comparison is needed.

## Two real development windows

Two eight-frame Shining HDR windows end at existing development frames 30 and
210. Independent software decoding matches every captured source/previous
plane and timestamp: 49,766,400 native samples across twelve plane comparisons.
The initial decoder invocation subtracted the source's 125 ms start offset;
its clock assertion failed. An explicit `-copyts` retry passes and produces
identical pixel bytes. The failed clock attempt remains recorded.

All 3,960 complete co-located tiles are measured with the prior fixed rounded
fractions Y=0.1 and Cb/Cr=0.25. This is a diagnostic operating point, including
the unqualified Cr fraction, not a selected policy. Each component/frame also
has 46,080 partial-border samples, reported separately and left unqualified.
The original R1 population identities and support counts match exactly.

For rejected Cb tiles, median lag-three versus lag-one difference energy is
1.29 and 1.33 in the two windows; rejected Cr medians are 1.71 and 1.96.
Stationary independent grain would have equal expected difference energy
across lags. These results point to nonstationarity or temporal correlation;
they do not identify motion as the sole cause. Negative conditional variance
estimates also occur and remain visible in the report.

Consequently this study does **not** make the previously rejected regions safe
to synthesize. It establishes a reusable measurement and demonstrates why simply
using temporal differences would overstate confidence. Motion/stationarity and
temporal-correlation evidence must precede a new population acceptance rule.
Terminal component/frame source preservation remains the valid fallback.

## Evidence and next work

In the evidence root from [the handoff](WORK-TO-PRODUCTION.md), read
`roadmap-r3-temporal-populations-20260923/manifest.json`, `decode.json`,
`report.json`, `tiles.jsonl`, `cpu.log` and `cleanup.json`. The source is already
admitted development footage; reserved qualification excerpts remain unopened.
The study uses CPU only and does not pause workers, change media or schedule work.

Next R3 work is a separately frozen motion/stationarity and temporal-correlation
study with known-source controls before any new acceptance rule. Model fitting
on these conditional variances alone is not sufficient. The independent seed
correction's full-title runtime cost can be qualified separately while R3 remains
open; it does not depend on enabling retention.

That [frozen follow-up is now complete](FINDINGS-2026-09-23-STATIONARITY-CONTROLS.md):
the necessary diagnostics catch several controls but still miss fast zero-grain
motion and persistent-noise ambiguity. No population was promoted. Read the
follow-up decision before attempting model integration from these measurements.
