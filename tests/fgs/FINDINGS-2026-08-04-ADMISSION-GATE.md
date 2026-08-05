# Phase A: admission on non-grain content — 2026-08-04

> **Audit resolution, 2026-08-05: the verdict below is withdrawn.** This
> experiment was designed and judged without reading
> `FINDINGS-2026-08-04-SHADOW-ADMISSION.md` and
> `FINDINGS-2026-08-04-SOURCEFIT-ADMISSION.md`, which already covered most of
> it and had already established the correct adjudication standard. Applying
> that standard reverses the conclusion: these titles are quality-positive
> under source fitting, exactly like the CG scenes the shadow campaign
> re-labelled. The failed reasoning is retained below so the mistake stays
> visible; see "Audit" at the end for what actually holds.

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

---

# Audit, 2026-08-05

## What this experiment got wrong

It was run without reading `FINDINGS-2026-08-04-SHADOW-ADMISSION.md` or
`FINDINGS-2026-08-04-SOURCEFIT-ADMISSION.md`. Three consequences.

**The sigma finding was already in the repo.** Shadow admission had already
rejected a fixed amplitude floor, on better evidence, citing Interstellar at
`1.285`, The Shining at `1.266` and Silo at `0.857`. The Shining measurement
above (`1.31`) reproduces theirs. It was presented as new; it was not.

**The damage measure was one this project had already disqualified.** VMAF p1
was used to rank the arms on content where the candidate delivers 15--29% more
grain and markedly coarser grain. Both are penalised by VMAF by construction:
`FINDINGS-2026-08-02-METRIC-SENSITIVITY.md` measured the presence penalty and
`FINDINGS-2026-08-03-AMPLITUDE-MATCHED-TEXTURE.md` measured a further 0.8--1.5
point penalty for coarser grain at fixed energy. The observed `-1.21` to
`-3.10` is the expected metric response to correct behaviour, not evidence of
damage.

**The pass condition demanded the wrong thing.** It required the candidate not
to "signal materially more grain on content that has none". Shadow admission
had already established that origin is the wrong label to demand, and that the
question is whether an interval carries stochastic texture that the separator
removes, the AV1 model represents and playback restores at the right amplitude.
These titles carry temporal texture of `0.90`--`1.62` codes — The Shining, a
genuine 35 mm title, sits at `1.31`. They are not content that "has none".

## The adjudication that was never run

Same clips, same tool, played total and texture against adjacent-frame source
truth. Lower is better in every column.

| title | \|amplitude err\| prod | cand | \|lag-1 err\| prod | cand | \|lag-2 err\| prod | cand |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DenTid | 0.122 | **0.005** | 0.119 | **0.047** | 0.070 | **0.008** |
| Tuner | **0.020** | 0.111 | 0.130 | **0.020** | 0.075 | **0.011** |
| TrainToBusan | 0.163 | **0.000** | 0.103 | **0.040** | 0.061 | 0.063 |

Played totals move `0.878 -> 1.005`, `0.980 -> 1.111` and `0.837 -> 1.000`.
The candidate is closer to source truth on amplitude for 2 of 3, on lag-1 for
3 of 3 and on lag-2 for 2 of 3.

This is the Migration/Elio pattern reproduced on three further titles: content
labelled clean by origin still carries representable stochastic texture, and
source fitting restores it substantially better than the residual fit. **Phase
A does not fail. It confirms the shadow-admission result on new material.**

The one real defect is Tuner's `1.111` over-delivery. That belongs to the open
amplitude-closure family alongside chroma V and the per-luma bands, not to
admission.

## What survives

- **The end-to-end encode measurement itself.** Shadow admission ran tables and
  statistics with `changes_output: false`; this ran complete encodes and
  decodes on untouched originals and confirms no arm exceeds plain in size and
  no VMAF-min collapse reproduces (`87.7`--`90.1` against the 2026-07
  campaign's `31`--`60`).
- **The table-point proxy correction.** The emitted curve's mean scaling point
  is not a strength measure — `grain_scale_shift` differs between arms and the
  mean is unweighted by luma occupancy, giving a 2.23x point ratio against a
  1.15x delivered ratio on Tuner. Any future admission or strength work must
  use delivered synthesis amplitude.
- **The block-count CV observation**, as an untested lead only. It is not among
  the shadow campaign's axes, and coverage heterogeneity appears there only as
  a nuisance state rather than a candidate discriminator. Its resolution/content
  confound is unresolved and the 24-scene shadow corpus is the right place to
  test it, not three titles.

## What was already the real open problem

Per shadow admission: admission needs a **quality-labelled negative** — an
interval where source fitting demonstrably synthesizes persistent picture or
codec structure that temporal truth says is not noise. Every gate so far has
only been tested against inputs where source fitting helps, including all three
titles here. Nothing in this experiment moved that, and no admission rule can
be called validated until such a specimen exists.
