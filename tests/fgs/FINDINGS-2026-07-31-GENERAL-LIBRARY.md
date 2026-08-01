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
case for a grain separator. **The matched-byte re-run below confirms both**:
at equal bytes Drag Race is still 9.47 -> 17.06 and Stormester 6.91 -> 12.78,
so neither is explained by the byte difference.

## Big Brother: the question was asked and not answered

Big Brother's source has HF 11.89 with autocorrelation peaking at lag 2
(0.080 / **0.644** / 0.331) -- not a grain profile, since grain decays
monotonically or is flat. The hypothesis was that this is processing or
compression artifacts rather than grain, and that FGS discarding 30% of it
(retention 0.696) would therefore be desirable.

The metrics do not support that reading: VMAF minimum drops 87.95 -> 78.62 and
SSIMULACRA2 p5 drops 48.50 -> 35.59. Whatever that HF energy is, removing it
cost measured quality.

The matched-byte re-run removes the remaining excuse. At `fgs@27` Big Brother
is **larger** than `plain@29` (19.1 MB against 18.3) and still loses VMAF
minimum 87.95 -> 82.32 and SSIMULACRA2 p5 48.50 -> 38.60. More bits do not
recover it, and its retention is pinned at 0.696/0.701 across both quality
points. The shortfall is architectural -- the model cannot represent that
source's HF structure -- not a bit-allocation effect.

## Retention error is title-specific in sign and magnitude

Across all ten titles measured today, FGS retention ranges 0.696 to 1.180 with
no tested variable predicting it: not grain amount, not fineness, not
autocorrelation shape, not source pipeline, not rate sensitivity. Five
hypotheses were proposed across this session and all five failed against the
next title measured.

The practical consequence is worth stating even without a mechanism: **a global
calibration constant cannot fix this.** An error of -0.30 on one title and
+0.18 on another is not a bias to tune out. Anyone reaching for "scale the
strength curve by k" will improve half the library and harm the other half.

## The matched-byte re-run, and what it settles

The corpus was re-encoded at `--qvbr 27` and `fgs@27` compared against
`plain@29`. At corpus level this lands on matched bytes: **77.8 MB -> 78.4 MB,
+0.8%**, so the missing-bits confound is gone.

| title | arm | MB | VMAF | VMAF min | SSIMU2 | SSIMU2 p5 | Butt 2n | Butt p95 | ret |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Cape Fear | plain@29 | 13.1 | **92.68** | **87.71** | **67.57** | **60.40** | **1.335** | 5.96 | 0.748 |
| Cape Fear | fgs@27 | 10.6 | 89.16 | 82.32 | 63.05 | 56.52 | 1.685 | **5.69** | **0.860** |
| Silo | plain@29 | 3.8 | **93.07** | **86.08** | **84.00** | **80.80** | **0.636** | 3.50 | 0.333 |
| Silo | fgs@27 | 3.5 | 91.79 | 84.92 | 82.57 | 79.38 | 0.758 | **3.34** | **1.016** |
| Big Brother | plain@29 | 18.3 | **96.93** | **87.95** | **70.12** | **48.50** | **1.178** | 7.74 | **0.940** |
| Big Brother | fgs@27 | 19.1 | 93.91 | 82.32 | 62.56 | 38.60 | 1.491 | **7.13** | 0.701 |
| Drag Race | plain@29 | 20.7 | **97.91** | **87.96** | **76.21** | **65.02** | **0.969** | **9.47** | **0.970** |
| Drag Race | fgs@27 | 23.2 | 94.68 | 82.35 | 62.52 | 32.70 | 1.603 | 17.06 | 1.184 |
| Supergirl | plain@29 | 9.3 | **97.60** | **94.46** | **82.16** | **78.02** | **0.653** | **4.83** | 0.652 |
| Supergirl | fgs@27 | 8.2 | 95.68 | 92.90 | 75.76 | 72.38 | 0.942 | 4.92 | **1.052** |
| Stormester | plain@29 | 12.6 | **97.08** | **93.98** | **81.66** | **77.53** | **0.741** | **6.91** | 0.831 |
| Stormester | fgs@27 | 13.8 | 94.90 | 90.55 | 78.21 | 73.15 | 0.895 | 12.78 | **0.906** |

Titles where `fgs@27` beats `plain@29`, out of six: VMAF **0**, VMAF minimum
**0**, SSIMULACRA2 **0**, SSIMULACRA2 p5 **0**, Butteraugli 2-norm **0**,
Butteraugli max-p95 **3**.

**This is the opposite of the 4K matched-rate result**, where every tail metric
favoured FGS on all four titles. The argument made there -- that mean losses
with tail gains is the signature of measurement bias rather than real loss --
**does not reproduce on 1080p general-library content.** It should not be
carried over.

What FGS still wins is grain retention, and by a wide margin: Silo's plain arm
discards two thirds of the source grain (0.333) where FGS reproduces it to
within 2% (1.016); Supergirl moves 0.652 to 1.052.

So the two measurements genuinely disagree, and nothing in this corpus resolves
it. That is the documented state of the art rather than a gap in this run:
Netflix has no full-reference quality model for FGS and validated theirs by A/B
over roughly 300 titles, and `FINDINGS-2026-07-30-TEXTURE.md` exists for the
same reason.

Two titles are not ambiguous, though. Drag Race (Butteraugli p95 9.47 -> 17.06,
while growing 12% in size) and Stormester (6.91 -> 12.78) show tail damage far
outside the movement seen elsewhere. Those are bad outcomes on their own terms,
not measurement artefacts.

### Bearing on deployment

The 4K heavy-grain routing reversal in `FINDINGS-2026-07-31-ROUTING.md` stands:
matched-byte, tails favouring FGS on all four titles. **The general-library
case has no equivalent support.** Blanket FGS on general content is currently
justified by grain retention and byte savings, not by any quality metric.

## What should happen next

1. **The 07-30 texture report on the Silo and Drag Race pairs.** Silo is the
   cleanest case of metrics disagreeing with retention; Drag Race the clearest
   damage. That detector was built for exactly this adjudication.
2. **A playback A/B**, which remains the release gate and is the only thing that
   can settle the Silo-style disagreement.
3. Only then a routing decision for reality/studio content.

## A note on the reasoning in this session

Five separate hypotheses about the retention error were proposed during this
work -- fine grain causing overshoot, autocorrelation shape, AMZN pipeline
signature, artifact-versus-detail, and rate-sensitivity splitting the corpus
into two behaviour classes. **All five were falsified by the next title
measured.** They are recorded here rather than deleted because the failures are
the useful part: with six to ten titles there is enough freedom to fit a story
to any three of them, and that is what kept happening.

## Method

`routing_check.py --qvbr 29 --frames 600 --denoiser bilateral`. Fixtures are
600-frame lossless FFV1 extracts cut from mid-episode (not frame zero, which
would score title cards) from original WEB-DL downloads, never library
transcodes. Held on NVMe; scoring re-reads the reference repeatedly and the
spinning-disk array measurably slowed the earlier 4K run.
