# Optional retention: copied colour range and recovery

Commits `5ac90482` and `53d3ff3f` protect the existing `retain=auto` path when
AV1's active zero-strength colour curve would still clamp a copied source
component. This is an experimental-path correction, not a production rollout
or completion of the new partial-retention model. Ordinary Tdarr remains on
`cb903a17`, with retention and FEL disabled.

## Reproduced failure and correction

A synthetic limited-range 10-bit source has independent noisy Y/Cb and constant
Cr=1000. The old optional path copies Cr exactly before compression and emits
a present, all-zero Cr curve alongside active Cb. With grain disabled, the
ordinary lossy output stays near 1000. With grain enabled, every Cr sample in
all 240 frames becomes 960. Independent AOM and dav1d reproduce the clamp at
the qualified QVBR30 control. A neutral Cr=512 control remains unchanged.

The guard measures complete source chroma min/max/counts in the existing GPU
source-statistics pass, including tiny borders too small for noise estimation.
It reuses existing source reads and metrics readback. The ordinary kernel
specialization does not perform those range reductions. Missing or invalid
coverage fails closed for a copied component with an active zero curve.
Absent curves and explicitly full-range output do not trigger this clamp guard.

When such a copied component contains nominal out-of-range samples, automatic
retention copies the whole original frame into the NVENC input and disables
grain. It resets the existing synthesis recovery state. This preserves source
input; NVENC compression remains lossy. A single excursion can therefore
increase fallback frequency and bytes. Those costs still need qualification.

The first implementation checked after recovery counting. A 40-frame unsafe
interval then allowed synthesis to return after only nine subsequent safe
frames. That retained negative led to `53d3ff3f`: check before recovery counting
and again after final curve rounding, while aggregating the source range only
once. Unsafe frames cannot earn recovery credit.

## Completed qualification

- Full CPU suite: 185 Python tests in 26 suites plus 29 C++ programs.
- Actual NV12/P010 encodes cover 8/10-bit source, copied Cb/Cr, upper/lower range
  excursions, isolated frames, 40-frame intervals and repeated alternation.
- A single bottom-right chroma sample in a 258x258 picture exercises the 1x1
  partial block. Both depths report the complete 16,641 colour samples and
  reject the unsafe frame. Noise estimation remains unchanged on small borders.
- All four transition/border sequences resume synthesis at frames 84, 183 and
  240: 24 safe frames after each last excursion. The existing 16-step ramp starts
  at 1/16. Unsafe and recovery-held frames have no decoded synthesis.
- Eight synthetic controls pass all-frame AOM/dav1d agreement, complete clocks
  and source/base checks. Across 84 native captures, 8,297,628 component samples
  have valid complete counts; source-fallback captures directly match source.
- Neutral and full-range controls preserve both grain-mode pictures against
  `b2a6daeb`. Ordinary SDR/HDR preserve all decoded pixels, clocks, metadata and
  grain decisions. Together these positive checks cover 7,584 decoded observations.

The qualified binary is:

```
commit 53d3ff3f50c5ac66d714a2f36d594df0ebbb000e
SHA256 a0d760f57bbb2ff7b423ed3c117e6a09535b1e04941e80430182045df89bcaf2
```

Planar specializations compile, but this stage has not directly executed their
range kernels. Existing native census/layout qualification remains separate.
The range guard does not certify arbitrary lossy overshoot at nominal bounds,
active grain components, or the unfinished whole-picture partial-retention fit.

## Separate decoder-compatibility finding

The initial synthetic controls at QVBR20 signal AV1 level index 23, which the
older AOM 3.8.2 decoder rejects. A bitrate cap does not resolve this; explicit
levels 4.0 and 5.1 fail NVIDIA initialization. It reproduces with the previous
`b2a6daeb` binary, with automatic grain, a grain table and plain NVENC. QVBR30
signals index 31 on both noisy and constant input and passes both decoders.
The source/fallback qualification above uses the declared QVBR30 controls.

The root cause of this setting-dependent compatibility issue remains open.
Do not describe QVBR20 as independently decoder-qualified, or silently change
production quality settings to hide it. No library damage scope follows from
these small generated fixtures. The original failures and each bounded control
remain recorded for the next investigation.

## Evidence and next work

Read `roadmap-r3-runtime-range-20260923/report.json` in the evidence root from
[the handoff](WORK-TO-PRODUCTION.md). It pins builds, failures, successful
comparisons and all pause receipts. Every owned pause is released; worker limits
are unchanged. No test is scheduled to restart.

R3 still needs qualified population-specific evidence or an explicit terminal
fallback, then actual bounded partial-retention selection. R4–R8 remain open.
The reserved qualification corpus is unopened. The separate level-signalling
finding also needs diagnosis before a broader experimental release.
