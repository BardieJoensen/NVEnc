# Motion confidence and causal-DC investigation — 2026-08-02

> Investigation only. Nothing in this document has been deployed to Tdarr.
> `modelsrc` remains default-off. The SAD override described below is a
> test-only switch and must not ship as a production interface.

## Question

The motion separator is the only `modelsrc` denoiser arm that reaches the
compression target on real film, but its base has directional temporal error.
This investigation asks which render-time signals localise that error and
whether it can be reduced without surrendering the temporal grain averaging
that gives motion its capture advantage.

The calibrated diagnostic is `temporal_drag.py`. It jointly regresses base
error on the previous- and next-frame directions and reports
`lag_asymmetry = b_prev - b_next`. It is not a ghosting score: causal exposure
or brightness lag also loads the previous direction.

## Reproducibility

The pinned investigation build is based on detached source commit `edd51076`.
Its binary is:

```text
/tmp/nvenc-motion-trace.UoLKjx/src/build-motion-trace/nvencc
sha256 03903e4366f897e713d5c670a0341e9b6c749b04b77e27706cf393742d5d362a
```

The build contains two opt-in diagnostics:

- `NVENC_DEGRAIN_BLOCK_TRACE`, restricted to one exact frame; and
- `NVENC_FGS_TEST_MOTION_THSAD`, a pinned experimental override whose default
  remains the production value 4000.

Trace off and trace on produced byte-identical raw output. Before and after
adding the threshold override, default output was also byte-identical:

```text
d4987e82...  old 5-frame Y4M
d4987e82...  new 5-frame Y4M, override unset
```

Raw artifacts and reports are under:

```text
/media/merged-storage/media/test-encodes/motion-confidence-20260802/
```

The 1080p AV1 arms and metric JSON are under:

```text
/media/merged-storage/media/test-encodes/motion-thsad-av1-20260802/
```

The relevant report entry points are:

- `manifest-all.json` / `report-all-dc-move32.json`;
- `manifest-sweep-high.json` / `report-sweep-high.json`;
- `manifest-taxi-f098-sweep.json` / `report-taxi-f098-dc.json`; and
- `temporal-baseline-taxi-driver.json`.

## Finding 1: SAD is a real motion-confidence control

Nine independently selected p10, median and p90 frames were traced across The
Shining, The Deer Hunter and Scarface. On blocks whose same-position temporal
change is at least 32 ten-bit code values, higher nearest-reference SAD predicts
more lag in every frame. The high-minus-low lag delta ranges from +0.098 to
+0.213 on the harmful frames and is only +0.003 to +0.004 on the clean frames.

The three worst frames were rendered at several raw SAD thresholds. Their
combined moving-block lag falls monotonically:

| `thsad` | lag asymmetry |
|---:|---:|
| 4000 | 0.2187 |
| 1600 | 0.0711 |
| 800 | 0.0217 |
| 640 | 0.0140 |

The threshold is not a sensitive affinity at its production value. For a
32x32 8-bit block, 4000 permits about 62.5 code values of average mismatch per
pixel, so ordinary mismatches retain almost the full temporal prior. This is
not a bit-depth scaling bug.

Static-flat grain capture changes little at 800 versus 4000:

| title | 4000 | 800 | absolute change |
|---|---:|---:|---:|
| The Shining | 0.8270 | 0.8210 | -0.0060 |
| The Deer Hunter | 0.8844 | 0.8722 | -0.0122 |
| Scarface | 0.9391 | 0.9369 | -0.0022 |

The 640 arm costs The Deer Hunter about 2.5%, so 800 is the best measured
experimental point rather than evidence for making the threshold arbitrarily
small.

## Finding 2: the finished AV1 result improves at 800

All arms use QVBR 29, preset p4, tune hq, 10-bit AV1, `denoiser=motion` and
`modelsrc=on`. The source clips contain 287 or 288 frames. All nine outputs pass
a complete `libdav1d -xerror` decode.

### Base-plus-grain fidelity

| title | VMAF 4000 | VMAF 800 | Butter mean 4000 | Butter mean 800 | SSIMULACRA2 4000 | SSIMULACRA2 800 |
|---|---:|---:|---:|---:|---:|---:|
| The Shining | 80.192 | 87.235 | 4.990 | 3.785 | -12.796 | -1.621 |
| The Deer Hunter | 58.968 | 65.553 | 4.229 | 3.812 | -20.643 | -14.529 |
| Scarface | 73.057 | 74.764 | 5.002 | 4.870 | -45.127 | -43.692 |

Every metric moves in the better direction on all three titles. Butteraugli
p95 also improves: 10.155 to 4.663, 7.130 to 4.637 and 6.191 to 5.355.

### Compression

| title | plain bytes | FGS 4000 bytes | saving | FGS 800 bytes | saving |
|---|---:|---:|---:|---:|---:|
| The Shining | 4,433,144 | 2,483,041 | 43.99% | 2,474,060 | 44.19% |
| The Deer Hunter | 12,034,331 | 6,961,119 | 42.16% | 7,638,334 | 36.53% |
| Scarface | 10,621,944 | 4,815,016 | 54.67% | 5,160,159 | 51.42% |

The stricter gate spends some bytes on Deer Hunter and Scarface because more
current-frame picture survives, but every arm remains beyond the original
30–40% compression target.

### Grain delivery

Played-total temporal amplitude is stable:

| title | 4000 | 800 |
|---|---:|---:|
| The Shining | 1.020 | 1.013 |
| The Deer Hunter | 0.956 | 0.956 |
| Scarface | 0.992 | 0.991 |

Synthesised lag-1 and lag-2 texture are unchanged to the reported precision.
The fidelity gain therefore comes from preserving the base, not weakening or
finerising the emitted grain.

## Finding 3: Taxi Driver exposes another mechanism

Taxi Driver's 287-frame baseline has overall lag asymmetry 0.1833. Its response
is largest in low-motion bins and its p90 frame 98 measures 0.3432. On that
frame, lowering `thsad` from 4000 to 800 changes the moving-block result only
from 0.3668 to 0.3458. High-SAD blocks do not explain it.

The trace ABI reserves `srcAvg` and `refAvg`, but the current CUDA exporter
explicitly writes zero to both. Adding a production GPU pass merely to test a
hypothesis would be unjustified, so `motion_confidence.py` now derives the same
quantity offline from decoded source frames, exact integer-pel motion vectors
and the selected per-reference mix.

For Taxi frame 98 at `thsad=4000`:

| measure | value |
|---|---:|
| actual moving-block lag | 0.3668 |
| lag predicted by selected-reference DC | 0.2949 |
| residual lag | 0.0719 |
| prediction/error correlation | 0.7528 |
| zero-intercept gain | 0.9442 |

At `thsad=800`, the residual is still 0.0717. This cleanly separates the SAD
failure from causal brightness-state drag.

The same calculation is nearly exact on the three control titles' moving
blocks:

| title | actual lag | predicted lag | residual | correlation | gain |
|---|---:|---:|---:|---:|---:|
| The Shining | 0.1702 | 0.1668 | 0.0034 | 0.9916 | 1.0116 |
| The Deer Hunter | 0.1687 | 0.1667 | 0.0020 | 0.9936 | 1.0105 |
| Scarface | 0.1665 | 0.1668 | -0.0003 | 0.9961 | 0.9870 |

This changes the interpretation: the lag probe is directly measuring the
accepted causal reference blend, not only bad motion vectors. SAD rejection
remains justified by the rendered quality results, but lowering SAD further is
not the right answer for Taxi's low-motion remainder.

## Monitoring limitation found

The validated base-fidelity canary creates its clean reference with the
reference binary's separator. It therefore passes accidental extra smoothing
such as r4047's widening, but it cannot certify an intentional separator
change against source truth. When the candidate at 800 restores current-frame
detail relative to the 4000 separator, the canary reports an alert
(SSIMULACRA2 delta -60.291, Butteraugli delta +2.924) even though VMAF,
Butteraugli, SSIMULACRA2 and grain delivery all improve against the lossless
source.

That alert is not to be ignored; it documents the canary's oracle scope. A
separator-changing candidate needs a source-referenced arm in addition to the
matched-binary substitution canary.

## Finding 4: mean alignment removes the symptom but worsens separation

The proposed local-mean alignment was tested offline at several window sizes.
An 11x11 correction nearly eliminates the measured directional lag on the
controls, but it does so by moving picture variation into the residual:

| title | lag before | lag after | capture before | capture after |
|---|---:|---:|---:|---:|
| The Shining | 0.1987 | 0.0013 | 0.8270 | 0.8036 |
| The Deer Hunter | 0.1995 | 0.0052 | 0.8844 | 0.8774 |
| Scarface | 0.1640 | 0.0064 | 0.9391 | 0.9371 |

Taxi Driver's frame 98 moves from 0.3267 to 0.1279, but leakage rises from
0.4291 to 0.5005. Combining alignment with `thsad=800` over-corrects further.
The lag reduction is therefore not evidence of a better separator. This
candidate is rejected.

## Finding 5: a centred window removes causal direction

A pinned prototype changed the motion window from causal references to
centred references. Five frames (two past plus two future) over-smooth all
three controls, so matching the causal arm's reference count matters. The
useful prototype is three frames: one past, current and one future.

On Taxi Driver at `thsad=640`, the full-frame joint regression is symmetric:

| coefficient | value |
|---|---:|
| previous-frame projection | 0.1835 |
| next-frame projection | 0.1853 |
| lag asymmetry | -0.0018 |

The causal baseline's lag asymmetry is +0.1833. This is direct evidence that
the centred window removes the causal direction rather than merely hiding it
from the probe.

The initial quality comparison accidentally mixed `thsad=640` and
`thsad=800`. Re-encoding both schedulers at 640 gives the actual isolated
effect:

| title | centred byte saving | delta VMAF | delta SSIMULACRA2 | delta Butteraugli |
|---|---:|---:|---:|---:|
| The Shining | 4.40% | -0.247 | -1.693 | +0.035 |
| The Deer Hunter | 8.36% | -0.392 | -0.296 | -0.003 |
| Scarface | 4.39% | +0.219 | +0.050 | -0.014 |
| Taxi Driver | 9.18% | +0.163 | +0.637 | -0.035 |

All deltas are source-referenced and positive means better for VMAF and
SSIMULACRA2; negative means better for Butteraugli. All outputs pass a full
`libdav1d -xerror` decode. Centred lookahead is therefore a real compression
gain and a clear Taxi/Scarface improvement, but not a universal quality win.
It is not approved for production.

The candidate currently over-delivers played grain on Taxi (1.136 total) and
The Shining (1.037). Scaling the already-emitted table to close each measured
total is useful only as an oracle: it brings Taxi to 1.006 and improves all
three metrics over causal 640 (VMAF +1.019, SSIMULACRA2 +6.320,
Butteraugli -0.454), while The Shining reaches 1.004 and nearly matches causal
640 (VMAF -0.040, SSIMULACRA2 -0.180, Butteraugli -0.035). A global multiplier
is not an implementation proposal; prior luma-band experiments show that it
can conceal a wrong curve.

Artifacts are under:

```text
/media/merged-storage/media/test-encodes/motion-bidir-controls-20260802/
/media/merged-storage/media/test-encodes/motion-bidir-av1-20260802/
```

## Pipeline defect found while testing delayed output

The centred filter exposed a generic terminal-filter drain bug. At EOF the
pipeline tried to submit an encoder surface even when a delayed CUDA filter
returned zero frames, and it did not repeatedly pass the null marker needed to
drain later frames. Commit `d1ae5cd5` fixes the scheduler independently of the
motion experiment.

The fix was verified three ways:

- direct centred output contains all 288 frames and decodes cleanly;
- direct and two-stage centred encodes have identical grain tables, elementary
  AV1 MD5 and grain-disabled decoded frame hashes; and
- causal output before and after the scheduler fix has an identical grain
  table and elementary AV1 MD5.

This scheduler correction does not enable centred motion, `modelsrc`, or any
production Tdarr option.

## Next falsifiable experiment

The remaining centred-window quality loss is plausibly caused by asymmetric
admission at disocclusions: the past and future references currently earn
independent SAD affinities. A block can therefore retain one temporal side
when the other side has no matching picture.

Prototype a paired-confidence gate in the pinned build: for the one-past,
one-future experiment, admit both references at the lower of their two raw
affinities. This keeps the temporal estimate centred and rejects one-sided
matches. Compare it at the same `thsad=640` against both centred-independent
and causal baselines.

It is promoted only if it recovers The Shining and The Deer Hunter's metric
giveback without losing Taxi Driver's directional correction or surrendering
the measured compression advantage. Grain delivery, luma-band texture, output
size and complete `libdav1d -xerror` decode remain required. A failure is still
useful: it would rule out asymmetric confidence as the cause and redirect the
work toward overlap/motion-estimation error rather than more strength tuning.
