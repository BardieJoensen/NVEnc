# Ordinary recovery and grain carried through NVENC

D77 measures ordinary encoding separately from D75's explicit experimental
source/model schedules. Deployed `cb903a17` and branch `296068e8` produce exactly
the same video packets, clocks, metadata, grain models and decoded pictures on
all six controls. No deployment, configuration or library file changed.

The finite census uses 112 frames of known constructed grain at 1024×512,
native 8/10-bit, QVBR30 and the existing quality/lookahead/AQ settings. Its three
patterns are steady grain, 16 quiet frames followed by 96 grain frames, and
32 grain / 16 quiet / 64 grain frames. The declared 16-frame development noise
pattern repeats. Both ordinary builds and plain NVENC are encoded, totaling
18 jobs. These are mechanism controls, not independent natural footage.

AOM and dav1d agree with grain on and off across 8,064 observations. Independent
raw decoding adds 4,032 frames and 3,170,893,824 native sample comparisons. Trace
decisions and emitted grain headers are associated with every output picture.
The actual source header and output clocks are 24 fps. An initial summary used
20 fps to convert frame counts to seconds; that conversion was corrected and
the first summary retained. Frame counts, energy and decoder results were
unaffected.

The ordinary recovery mechanism deliberately holds synthesis after a quiet
interval until the model window and 24-frame stability period settle. In these
controls that produces 30 grain-off frames, or 1.25 seconds at 24 fps, followed
by the existing 16-frame synthesis ramp. The pre-encode source blend during
that ramp assumes that carried grain will survive compression. Actual NVENC
reconstruction shows that this assumption is insufficient.

For quiet-to-grain input, median luma variance during the hold is about 0.025%
of source in 8-bit and 0.010% in 10-bit. Individual coded-source frames reach
about 38%, even though synthesis remains off. After full synthesis gain returns,
median variance is about 88.5% and 83.3% of source respectively. The steady-grain
controls also reconstruct less variance than the constructed source. These
percentages describe variance, not perceived quality, VMAF or visible severity.
The 8% model bound is a diagnostic here, not a universal perceptual acceptance
criterion for ordinary encoding.

This establishes an existing recovery tradeoff in both builds and a reason to
measure actual reconstruction during temporal qualification. It does not
establish affected library scope, visibility on natural footage, or a new AV1
header/reference-state defect. Shortening the hold, reusing an unsafe old model
or boosting all grain would discard protections without solving the measured
source/codec problem. Next examine source-bound natural development transitions
and qualify a correction alongside the existing flicker, detail, quiet-source
and amplitude controls. R3/R4 and the wider roadmap remain open.

Local evidence: `roadmap-r4-ordinary-recovery-20260928/plan.json`,
`manifest.json`, `encodes.json`, `comparison.json`, `recovery-summary.json` and
per-frame `energy.json`/`traces.json` under the handoff root. Both binaries are
pinned there, including the production binary's verified SHA256. The owned
pause is released; nothing restarts automatically. Retention/FEL remain off
and reserved footage is unopened.

`ordinary-recovery.png` and `.pdf` plot the per-frame native luma variance
against source, with the actual 24 fps clocks and separate hold/ramp intervals.
`plot.py` records the reproducible Matplotlib figure; quiet intervals have no
variance denominator and are not presented as normalized energy measurements.
