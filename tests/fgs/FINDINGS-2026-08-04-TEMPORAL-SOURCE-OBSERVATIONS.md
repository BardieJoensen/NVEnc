# Temporal source observations for the grain model — 2026-08-04

> Quality-first research result. Nothing here was deployed. Production remains
> r4069 with bilateral separation, residual fitting, `modelsrc=off`, and the
> existing Tdarr route. The prototype is enabled only by an environment
> variable and cannot be selected through the public CLI.

## Decision

Keep the Tdarr routing unchanged. Restricting source-model observations to
temporally stable flat blocks is the strongest source-fit texture result so
far, but it is a model-estimation improvement, not evidence that arbitrary
content should be admitted as film grain. Per-luma strength, chroma amplitude,
semantic admission and blind playback remain open.

The usable prototype is deliberately asymmetric:

```text
bilateral separator
  -> luma source AR model: temporal-static spatial-flat blocks
  -> chroma source AR model: all spatial-flat blocks
  -> strength: existing dense source-minus-base and temporal leak closure
  -> source solver rejection: residual model fallback
```

Using the luma temporal subset for U/V was measured and rejected. It removed
useful chroma observations and made V texture substantially worse.

## Why the existing source fit still missed some films

The fixed-base correlation-margin replay first tested the smallest plausible
change: remove the shipping `0.05` correlation reduction while holding the
base pixels fixed. Six-film luma texture MAE improved from `0.0330` to
`0.0206`, but Casino regressed from `0.008` to `0.045` and Taxi Driver was
mixed. A global margin is therefore not a valid correction.

`correlation_target_report.py` then compared the CUDA correlation statistic
with adjacent-frame temporal truth on eight films. The important distinction
was the block population, not the scalar estimator:

| source statistic | MAE | bias | maximum error |
| --- | ---: | ---: | ---: |
| shipping all-flat frame median | 0.023 | +0.019 | 0.063 |
| all-flat pooled | 0.059 | +0.059 | 0.127 |
| temporal-static frame median | 0.016 | -0.008 | 0.029 |
| **temporal-static pooled** | **0.009** | **+0.002** | **0.015** |

Pooling all blocks made picture contamination dominate by energy. Pooling only
temporally stable blocks removed that contamination and used the observations
more efficiently.

The full dense AR oracle gave the same answer. Against the temporal-difference
fit, mean luma model error fell from `0.0707` with all source-flat blocks to
`0.0138` with the temporal-static subset, an 80% reduction. The largest
benefits were on Coming to America, Interstellar and The Shining; Ju-on and
Deer Hunter were already close. This is why the code prototype changes the
observation population rather than adding another coefficient regularizer.

Offline reports are retained under:

```text
/media/merged-storage/media/test-encodes/sourcefit-correlation-target-20260804/
```

## Prototype and the chroma negative result

Commit `ed2829b3` added the test-only
`NVENC_FGS_TEST_SOURCE_STATIC=on` path. It reuses the already validated
`0.8..1.3` temporal/spatial variance test and falls back to the residual model
when there is no previous frame or too little accepted evidence.

The first implementation applied the luma-derived mask to all planes. Luma
improved, but six-film V texture MAE moved in the wrong direction:

| plane | previous source fit | all-plane temporal mask |
| --- | ---: | ---: |
| Y | 0.03363 | **0.01612** |
| U | **0.01988** | 0.02503 |
| V | **0.03029** | 0.08849 |

The Shining V moved from `0.017` error to `0.173`; Interstellar and Scarface V
also regressed sharply. A luma-static decision says which picture regions are
safe for luma AR observations. It does not prove that the smaller 16x16 chroma
population has the same estimator bias.

Commit `992592a5` therefore keeps the temporal subset on luma only and restores
the established spatial-flat population for U/V. This is not a fixed chroma
multiplier and does not claim to close chroma amplitude.

## Eight-film result

The six architecture films plus held-out Ju-on and Coming to America were
encoded with the same bilateral separator and source-fit settings. Only the
source observation mask changed. Lag-1/lag-2 error is the mean absolute error
against adjacent-frame temporal truth and is independent of grain amplitude.

| title | previous source-fit Y error | temporal-static Y error | played Y total |
| --- | ---: | ---: | ---: |
| Casino | 0.008 | 0.010 | 0.948 |
| Interstellar | 0.065 | **0.034** | 0.981 |
| Scarface | 0.027 | **0.004** | 0.992 |
| Taxi Driver | 0.030 | **0.008** | 1.022 |
| The Deer Hunter | 0.021 | **0.017** | 0.969 |
| The Shining | 0.051 | **0.032** | 0.987 |
| Ju-on | **0.006** | 0.010 | 1.021 |
| Coming to America | 0.115 | **0.037** | 0.986 |
| **macro mean** | **0.0404** | **0.0189** | — |

The eight-film macro texture error falls 53.3%. The fine-grain held-out title
stays close; the coarse-grain held-out title improves by about 3x. This is the
desired fine/coarse differentiation: the estimator does not widen every film,
it follows the source evidence.

On the original six-film corpus, the corrected hybrid keeps chroma texture at
least as accurate as the previous source fit:

| plane | previous texture MAE | corrected hybrid | previous/hybrid played-total mean |
| --- | ---: | ---: | ---: |
| Y | 0.03363 | **0.01741** | 0.991 / 0.983 |
| U | 0.01988 | **0.01897** | 0.976 / 0.970 |
| V | 0.03029 | **0.02898** | 1.100 / 1.087 |

The amplitude columns are not a release pass. Taxi Driver V remains `1.182`
and The Shining V `1.330`. Deer Hunter's populated `0.250--0.375` luma band
remains high at `1.158`, while Taxi Driver's thin `0.375--0.500` band is low at
`0.893`. Texture estimation is now much better; per-luma and per-plane strength
are still separate problems.

Artifacts:

```text
/media/merged-storage/media/test-encodes/sourcefit-static-real-20260804/
/media/merged-storage/media/test-encodes/sourcefit-film-holdout-gate-20260804/
```

## Base fidelity, bytes and bitstream safety

The grain-disabled base remains equivalent to the earlier bilateral source-fit
candidate. Across the six-film 1080p centre crops, mean VMAF changes by
`+0.0163`; the largest title movement is Deer Hunter at `+0.0618`, and The
Shining remains pixel-identical. Held-out base VMAF moves `+0.0037` on Ju-on
and `-0.0164` on Coming to America.

Encoded bytes move by at most `+0.211%` on the six films. Ju-on is `-0.150%`
and Coming to America `-0.075%`. This is a grain-quality change, not a new
compression claim.

All eight candidate streams pass complete `libdav1d -xerror` decoding.

Pinned build:

```text
commit  992592a5ee155f6d9e9a38747f98ca90c4d87b4f
binary  /home/bardie/.cache/fgs-gate/builds/
        pin-ed2829b39d519e2bfc163a5ce5334759c453348d-1785807218/
        build-gate-static/nvencc
SHA256  f89f8b5d5bbd2835354aee0f5884139b82cfb8a1cb1cf68c9ad9cd0c48a97545
```

The FilmGrain CUDA object was recompiled and the final binary relinked for the
exact committed revision in the retained full-build pinned clone. The CPU suite
passes 170/170. The full bilateral/QVBR-29 KAT
passes 19/22; its three failures reproduce identically with the feature off:
the documented bilateral `coarse_detail` edge bound and the two existing
fixed-retain checks. They are baseline limitations, not movements caused by
the observation mask. The focused six-test smoke set passes with the feature
on.

With the feature off, the elementary AV1 stream remains byte-identical to the
pre-prototype binary:

```text
MD5=edf7ab966d05dcbe896d667ba7822312
```

## What is working and what remains open

Working:

- the bilateral separator remains the trusted base operator;
- source fitting is the correct architecture for admitted film grain;
- temporal-static luma observations remove most picture contamination without
  suppressing fine-grain Ju-on;
- chroma retains its previous texture accuracy; and
- default-off behavior and production routing are unchanged.

Still open:

1. **Per-luma strength.** Fix the Taxi/Deer opposite band errors without a
   corpus multiplier or another global response model.
2. **Chroma amplitude.** Build and validate an independent U/V temporal
   strength estimate; do not reuse the luma mask as a chroma AR gate.
3. **Semantic admission.** Shadow the independent film-like axes on a larger
   untouched corpus. Better source-model fit cannot be admission because it
   also fits animation texture and ringing better.
4. **Blind playback.** Once strength is credible, compare production residual
   grain with this bilateral/source candidate, concentrating on coarse texture,
   bright flat regions and chroma crawl.

Only after those four gates should `modelsrc` or the Tdarr flow change.
