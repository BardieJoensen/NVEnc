# General-library FGS behaviour at the production operating point, 2026-07-31

## Result

Six 1080p library-representative titles, 600 frames each, `--qvbr 29`
(the production setting), plain versus FGS. **This is a different question from
`FINDINGS-2026-07-31-ROUTING.md`**, which held bytes fixed: here the *quality
setting* is fixed and the byte saving is the output.

| title | src HF | plain MB / ret | FGS MB / ret | bytes |
| --- | ---: | --- | --- | ---: |
| Cape Fear | 5.92 | 13.1 / 0.748 | 8.4 / 0.856 | **-35.9%** |
| Supergirl | 2.50 | 9.3 / 0.652 | 6.6 / 1.048 | **-29.0%** |
| Silo | 1.89 | 3.8 / 0.333 | 2.9 / 1.016 | **-23.7%** |
| Big Brother | 11.89 | 18.3 / 0.940 | 15.7 / 0.696 | -14.2% |
| Stormester | 2.55 | 12.6 / 0.831 | 11.2 / 0.898 | -11.1% |
| Drag Race | 12.08 | 20.7 / 0.970 | 19.5 / 1.180 | -5.8% |
| **corpus** | | **77.8 MB** | **64.3 MB** | **-17.4%** |

Grain retention improves dramatically on the genuinely grainy titles. Silo's
plain arm keeps only 0.333 of source grain energy at QVBR 29 and FGS keeps
1.016; Supergirl moves 0.652 to 1.048.

## The full-reference metrics do not endorse this, and that matters

| title | arm | VMAF | VMAF min | SSIMU2 | SSIMU2 p5 | Butt 2n | Butt p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cape Fear | plain | **92.68** | **87.71** | **67.57** | **60.40** | **1.335** | 5.96 |
| Cape Fear | fgs | 88.64 | 81.67 | 61.94 | 55.36 | 1.717 | **5.94** |
| Silo | plain | **93.07** | **86.08** | **84.00** | **80.80** | **0.636** | **3.50** |
| Silo | fgs | 91.39 | 84.34 | 81.87 | 78.62 | 0.769 | 3.76 |
| Big Brother | plain | **96.93** | **87.95** | **70.12** | **48.50** | **1.178** | **7.74** |
| Big Brother | fgs | 93.51 | 78.62 | 60.84 | 35.59 | 1.549 | 7.86 |
| Drag Race | plain | **97.91** | **87.96** | **76.21** | **65.02** | **0.969** | **9.47** |
| Drag Race | fgs | 94.32 | 82.07 | 60.63 | 31.85 | 1.670 | 17.22 |
| Supergirl | plain | **97.60** | **94.46** | **82.16** | **78.02** | **0.653** | **4.83** |
| Supergirl | fgs | 95.43 | 92.64 | 74.82 | 71.44 | 0.965 | 5.26 |
| Stormester | plain | **97.08** | **93.98** | **81.66** | **77.53** | **0.741** | **6.91** |
| Stormester | fgs | 94.56 | 89.79 | 77.16 | 71.87 | 0.933 | 12.78 |

Lower is better for Butteraugli. **The plain arm wins essentially every metric
on every title, mean and tail alike.**

This is the opposite of the matched-rate 4K result, where every tail metric
favoured FGS on all four titles. The two are not contradictory -- they are
different experiments -- but the difference is exactly the thing that must not
be glossed: here FGS is spending **17.4% fewer bits**, so this is not a
like-for-like quality comparison. Some of the gap is the known synthesis
penalty; some is simply having less data.

**How much of each is unknown from this run.** That is the central limitation.

## Two titles look like real damage, not bias

The synthesis penalty should be roughly uniform. These are not:

- **Drag Race**: SSIMULACRA2 p5 collapses 65.02 -> 31.85 and Butteraugli p95
  nearly doubles 9.47 -> 17.22, for only 5.8% byte saving. Its retention also
  overshoots to 1.180.
- **Stormester**: Butteraugli p95 6.91 -> 12.78, for 11.1% saving.

A tail metric nearly doubling is a different magnitude from the ~10% mean
movement seen elsewhere, and Drag Race pays it for the smallest saving in the
corpus. Saturated studio lighting with hard chroma edges is a plausible worst
case for a grain separator. These two need a matched-byte re-run before FGS is
considered safe on that content class.

## Big Brother: the question was asked and not answered

Big Brother's source has HF 11.89 with autocorrelation peaking at lag 2
(0.080 / **0.644** / 0.331) -- not a grain profile, since grain decays
monotonically or is flat. The hypothesis was that this is processing or
compression artifacts rather than grain, and that FGS discarding 30% of it
(retention 0.696) would therefore be desirable.

The metrics do not support that reading: VMAF minimum drops 87.95 -> 78.62 and
SSIMULACRA2 p5 drops 48.50 -> 35.59. Whatever that HF energy is, removing it
cost measured quality. Either it was real detail, or the FGS arm's 14% smaller
size is doing the damage. Unresolved.

## Retention error is title-specific in sign and magnitude

Across all ten titles measured today, FGS retention ranges 0.696 to 1.180 with
no tested variable predicting it: not grain amount, not fineness, not
autocorrelation shape, not source pipeline. Three hypotheses were proposed and
all three failed against the next title.

The practical consequence is worth stating even without a mechanism: **a global
calibration constant cannot fix this.** An error of -0.30 on one title and
+0.18 on another is not a bias to tune out. Anyone reaching for "scale the
strength curve by k" will improve half the library and harm the other half.

## What should happen next

1. **A matched-byte re-run of this corpus.** Encode the FGS arm at a lower QVBR
   so both arms land on the same size, as `FINDINGS-2026-07-29-PERFORMANCE.md`
   did for Silo with QVBR 27 against 29. That separates the synthesis penalty
   from the missing 17.4% of bits, which this run cannot do.
2. **The 07-30 texture report on the Drag Race and Stormester pairs**, which is
   the detector built for "was real detail replaced by synthesized texture".
3. Only then a routing decision for reality/studio content.

## Method

`routing_check.py --qvbr 29 --frames 600 --denoiser bilateral`. Fixtures are
600-frame lossless FFV1 extracts cut from mid-episode (not frame zero, which
would score title cards) from original WEB-DL downloads, never library
transcodes. Held on NVMe; scoring re-reads the reference repeatedly and the
spinning-disk array measurably slowed the earlier 4K run.
