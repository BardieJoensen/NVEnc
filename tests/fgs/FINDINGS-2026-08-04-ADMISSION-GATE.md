# Phase A: admission on non-grain content — 2026-08-04

> Measurement only. Nothing deployed. Production remains r4069 bilateral /
> residual, `modelsrc` default-off, source-static behind an environment
> variable.

Executes Phase A of `NEXT-2026-08-04.md`. Sources are untouched originals from
`/tmp/downloads/movies`, never library copies. One lossless FFV1 288-frame clip
per title; every arm scored against that same clip. Arms share the bilateral
separator and QVBR 29: plain, production `modelsrc=off`, and candidate
`modelsrc=on` + `NVENC_FGS_TEST_SOURCE_STATIC=on`.

Artifacts: `/media/merged-storage/media/test-encodes/admission-gate-20260804/`.

## A correction to how the pass condition was measured

The pre-registered condition said the candidate "must not signal materially
more grain on content that has none", and the first operationalisation was the
mean luma scaling point of the emitted table. **That proxy is invalid** and it
overstates the regression by roughly a factor of two:

| title | table point ratio | after `grain_scale_shift` | delivered synthesis ratio |
| --- | ---: | ---: | ---: |
| DenTid | 2.65 | 1.33 | **1.29** |
| Tuner | 2.23 | 2.23 | **1.15** |
| TrainToBusan | 2.40 | 1.20 | **1.24** |

Two independent reasons. `grain_scale_shift` differs between arms, so raw
points are not comparable; and the curve mean is unweighted by luma occupancy,
so strength signalled in bins the picture does not occupy inflates it — which
is the same curve-population effect Phase C exists to investigate. Tuner shows
the second effect alone, with identical shifts and a 2.23x point ratio against
a 1.15x delivered ratio.

**Delivered synthesis amplitude is the only trustworthy measure**, and every
number below uses it.

## Result: the condition fails, but not the way it failed in July

| title | arm | bytes vs plain | VMAF | VMAF p1 | VMAF min |
| --- | --- | ---: | ---: | ---: | ---: |
| DenTid | plain | — | 98.204 | 95.62 | 95.29 |
| | production | -10.3% | 96.446 | 93.46 | 93.26 |
| | **candidate** | -10.6% | 95.175 | **91.60** | **90.10** |
| Tuner | plain | — | 98.098 | 94.38 | 94.06 |
| | production | -10.8% | 97.407 | 91.49 | 91.04 |
| | **candidate** | -10.9% | 96.792 | **90.28** | **89.89** |
| TrainToBusan | plain | — | 98.749 | 94.93 | 94.00 |
| | production | -22.7% | 97.326 | 92.27 | 92.18 |
| | **candidate** | -23.1% | 96.180 | **89.17** | **87.73** |

The candidate is worse than production on VMAF p1 on all three titles, by
`-1.86`, `-1.21` and `-3.10`, and delivers 15--29% more synthesised grain.
**Phase A fails as written.**

Two things it is important not to overstate:

- **The 2026-07 catastrophe does not reproduce.** That campaign recorded VMAF
  min of 31--60 on non-grain content against plain's 94--96. Here the candidate
  holds 87.7--90.1. The collapse was fixed by the intervening work
  (detail protection, scene-cut handling, template clipping,
  `grain_scale_shift`), and this architecture does not reintroduce it.
- **No arm is larger than plain.** The other July failure mode — FGS producing
  bigger files than a plain encode on clean content — is also gone; both FGS
  arms save 10--23%.

The damage is a few VMAF points, not a collapse.

## The candidate is not hallucinating grain

It is doing exactly what it was built to do, on content where that is not
wanted. Against adjacent-frame source truth on the same clips:

| title | source truth lag-1 | production synth lag-1 | candidate synth lag-1 |
| --- | ---: | ---: | ---: |
| DenTid | 0.772 | 0.182 | **0.420** |
| Tuner | 0.472 | 0.041 | **0.233** |
| TrainToBusan | 0.458 | 0.141 | **0.389** |

The candidate reproduces the texture of the noise that is actually present far
more faithfully than production does, on all three. The content genuinely
carries a faint noise field; source fitting measures it correctly and plays it
back. On material where nobody wants that field reproduced, fidelity is purely
a cost.

**This is an admission problem, not an architecture problem.** The model is
right and it is being asked the wrong question.

## The obvious gate is dead

The 2026-07 proposal was to "skip/off when measured sigma below ~2". Measuring
the film corpus and the clean corpus in the same 8-bit domain with the same
tool kills it:

| title | class | source sigma (8-bit) | source lag-1 | accepted blocks/frame | **CV of block count** |
| --- | --- | ---: | ---: | ---: | ---: |
| Scarface | film | 3.27 | 0.289 | 951 | **0.019** |
| Taxi Driver | film | 2.49 | 0.796 | 917 | **0.136** |
| Train to Busan | clean | 1.62 | 0.458 | 403 | 0.492 |
| DenTid | clean | 1.37 | 0.772 | 100 | 0.584 |
| **The Shining** | **film** | **1.31** | 0.640 | 2039 | **0.081** |
| Tuner | clean | 0.90 | 0.472 | 309 | 0.837 |

**The Shining — a genuine 35mm title the whole architecture exists for — has
less temporal grain energy than Train to Busan, a digital clean title.** A
threshold at 2.0 would reject The Shining, Taxi Driver borderline, and keep
nothing useful.

Texture fails too: Scarface's real grain reads lag-1 `0.289`, below Tuner's
clean `0.472`, and DenTid's compression noise reads `0.772` against Taxi's
grain at `0.796`.

| discriminator | film range | clean range | separates? |
| --- | --- | --- | --- |
| source sigma | 1.31--3.27 | 0.90--1.62 | **no** |
| source lag-1 | 0.29--0.80 | 0.46--0.77 | **no** |
| block-count CV | **0.019--0.136** | **0.492--0.837** | **yes, 3.6x gap** |

Neither of the two quantities this project has spent two weeks perfecting can
tell film grain from clean-content noise. That is worth stating plainly: the
fidelity axes and the admission axis are independent, and progress on one has
bought nothing on the other.

## What did separate: stationarity

Film grain is a property of the stock — present uniformly across the frame and
stable across the title. Compression and sensor noise track local complexity
and rate, so the region that qualifies as flat-and-static swings frame to
frame. The coefficient of variation of the accepted block count per frame is
already computed by the existing selector and separates the two classes with a
3.6x gap between the worst film (0.136) and the best clean title (0.492).

Counting noise does not explain it. Poisson sampling would give
`1/sqrt(N)` — `0.033` for Taxi, `0.057` for Tuner, `0.022` for The Shining —
which is 3.7x to 15x smaller than what is observed in every case.

**This is a lead, not a result.** Three limitations, all disqualifying on their
own:

1. six titles, five frames each; a CV from five samples is barely an estimate;
2. **content class and resolution are perfectly confounded** — every film is 4K
   and every clean title is 1080p. A 4K clean title or a 1080p grainy title
   would break the tie, and until one is measured this could be a resolution
   effect wearing a content label;
3. the clean corpus is three titles of one broad kind. Animation, CGI and
   already-transcoded WEB-DL are the classes that failed hardest in July and
   none is represented here.

Do not build a gate on this until at least (2) is resolved.

## Verdict

1. **Keep the architecture.** It is measuring correctly; the failure is that it
   is allowed to run on material it should decline.
2. **Reject unconditional operation.** The candidate is consistently worse than
   production on clean content, and production is itself worse than plain.
   Neither should run on this material.
3. **Reject the sigma threshold** before anyone implements it.
4. Next measurement is the confound in the stationarity lead: one 4K clean
   title and one 1080p grainy title, same instrument. That is decisive and
   cheap, and it is worth more than any further amplitude work.

Sinister was in the plan as the boundary case and was not measured — the
download directory holds only a `.nfo` and an `_unpack` folder for it.
