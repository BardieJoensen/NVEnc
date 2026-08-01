# Retention decomposition across ten titles, 2026-08-01

## Result

Retention was decomposed into base leakage and synthesised layer at six scenes
per title, using `retention_over_one.py` from `/opt/docker-apps/scripts`. The
grain-on decode minus the grain-off decode measures the synthesised layer in
absolute terms, which removes the divisor entirely.

| title | leak (med) | synth (med) | total (med) | **total sd** |
| --- | ---: | ---: | ---: | ---: |
| Scarface | 0.051 | 0.976 | 0.978 | **0.017** |
| Taxi Driver | 0.237 | 1.036 | 1.062 | **0.032** |
| The Shining | 0.174 | 0.935 | 0.950 | 0.063 |
| Silo | 0.080 | 1.131 | 1.135 | 0.085 |
| Casino | 0.236 | 0.981 | 1.008 | 0.094 |
| Supergirl | 0.159 | 1.173 | 1.194 | 0.102 |
| Stormester | 0.355 | 1.256 | 1.308 | 0.202 |
| Big Brother | 0.292 | 0.780 | 0.936 | 0.222 |
| Cape Fear | 0.149 | 1.273 | 1.284 | 0.230 |
| Drag Race | 0.409 | 0.804 | 0.948 | **0.746** |

**Median accuracy is unremarkable everywhere.** Every title sits between 0.936
and 1.308. There is no title that is systematically, grossly wrong.

**Variance is the discriminator, and it splits by content type:** real film
(Scarface, Taxi, Shining, Casino) has total sd 0.017-0.094; processed digital
(Supergirl, Stormester, Big Brother, Cape Fear, Drag Race) has 0.102-0.746.

## The measurement was the problem

Three estimators, same file, same encode:

| estimator | Taxi FGS | The Shining FGS | Drag Race FGS |
| --- | ---: | ---: | ---: |
| `campaign.py::hf_sigma` (whole frame) | 0.919 | 1.154 | 1.180 |
| `flat_retention.py` (flat, shared mask) | 0.743 | 1.062 | 3.773 |
| decomposition, median of 6 scenes | 1.062 | 0.950 | **0.948** |

Two conclusions follow, and both invalidate earlier work in this repository.

**Whole-frame HF sigma counts encoder ringing as grain.** It inflates the
retention of whichever arm has more coding artifacts, which is the arm that
destroyed the grain. It is the same bias direction as the full-reference
metrics. Every retention number produced by `campaign.py` and
`matched_rate_sweep.py`, including those in the 2026-07-31 findings, carries it.

**Per-title scalars are single draws from wide distributions.** Drag Race's
scene-to-scene sd is 0.746: one sample can read 0.95 or 3.77 depending on which
scene it lands in. `FINDINGS-2026-07-31-GENERAL-LIBRARY.md` reported it as
1.180 and this document originally reported 3.773; the median across six scenes
is 0.948. Its defect is instability, not bias, which is a different defect
needing a different fix.

## Corrections to earlier findings

- **The Shining does not over-signal.** Reported at 1.154 from the whole-frame
  estimator; the decomposition gives 0.950. The autocorrelation-shape hypothesis
  built on that overshoot was explaining an artifact.
- **Drag Race does not over-synthesise by 3.8x.** Median 0.948, sd 0.746.
- **Plain-encode retention was overstated.** Flat-block measurement puts plain
  at 0.10-0.64 where whole-frame reported 0.33-0.97.

## Six falsified hypotheses

Recorded because the failure rate is the finding. Each was proposed from
per-title scalars that are now known to be single draws from distributions with
sd up to 0.746:

1. Fine grain causes over-synthesis. Falsified by Scarface, the finest grain and
   the most accurate title.
2. Autocorrelation shape predicts the error. Falsified by Cape Fear, the most
   non-monotone profile, which under-signalled.
3. The lag-2-peaked signature is an AMZN pipeline artifact. Falsified by Drag
   Race, same pipeline, opposite signature.
4. Big Brother's high-frequency energy is artifacts, so discarding it is
   desirable. Falsified by the metrics dropping when it was discarded.
5. FGS's advantage scales with the quality target. Falsified by Cape Fear and
   Supergirl moving 0.6 and 1.5 points against Silo's 11.5.
6. Base leakage is constant in absolute terms. Falsified within one command:
   `base_hf` spans 3.1 to 182.9.

The common defect is fitting structure to three or four points of a noisy
per-title scalar. The decomposition's within-title spread is what makes that
visible.

## What is measurable and what is not

`total = sqrt(base^2 + synth^2)` holds to +/-0.001 on 12 of 14 checked rows.
That is expected physics for two independent fields rather than a discovery, but
it confirms the decomposition is self-consistent and the layers are independent,
and it means the relation can be inverted.

The consequence is a computable systematic correction: to land at total 1.0,
synthesis must be scaled by `sqrt(1 - leak^2)`. Taxi leaks 0.237 and synthesises
at 1.036 where 0.971 would be correct, so it lands at 1.062. The encoder already
performs exactly this compensation for *intentional* retention -- the `retain`
parameter scales signalled synthesis by `sqrt(1 - retain^2)` -- but nothing
compensates for *unintentional* base leakage.

This is small (3-7% on the film titles) and does not explain Cape Fear's synth
1.273 at leak 0.149, which is a strength-curve error independent of leakage.

## Synthesised grain is about half as spatially correlated as the source

Decomposing the layers and measuring lag-1 autocorrelation inside the source's
flat mask, rather than only their amplitude:

| | flat sigma | lag-1 ACF |
| --- | ---: | ---: |
| Taxi, source | 0.400 | **+0.370** |
| Taxi, base (leaked) | 0.106 | +0.330 |
| Taxi, synth layer | 0.371 | **+0.195** |
| Casino, source | 0.253 | **+0.410** |
| Casino, base (leaked) | 0.070 | **-0.090** |
| Casino, synth layer | 0.215 | **+0.184** |

Amplitude is close (0.371 against 0.400; 0.215 against 0.253) while
**correlation is roughly halved on both titles**. This reproduces across the
wider corpus: the fgs/source lag-1 ratio is 0.72 (Taxi), 0.60 (Casino), 0.43
(The Shining), 0.61 (Drag Race) on every source with lag-1 above 0.17.

The synthesised grain is the right strength and the wrong *size*, consistently
and in one direction. That is a better description of the coarse-grain failure
than any amplitude measure, and it is consistent with capture ratios of 36-41%
on the coarse fixture.

**`base_hf` conflates two different things.** Taxi's leaked base has ACF +0.330,
genuinely retained coarse grain. Casino's is **-0.090**; negative lag-1 is the
signature of coding ringing, not grain. So "base leakage" is leaked grain on
some titles and encoder artifacts on others, which is a likely reason it
correlated with nothing above, and it matters for any gate built on
`base_ratio`.

**Casino discriminates the two causes.** Its separator leaves ringing rather
than coarse grain, so the residual handed to the fit should carry the source's
full correlation -- and synthesis still emerges at 0.184 against 0.410. That
points at the AR estimation rather than the denoiser. The AV1 model has 24 free
coefficients and demonstrated amplitude headroom (peaks 113 of 255 on Korra), so
this is a fitting outcome, not a representational limit.

The open comparison is our fitted AR coefficients against libaom's on the *same*
residual, using the pinned `noise_model` binary and `reference_compare.py`. If
libaom reproduces the source ACF and we do not, it is our solver; if neither
does, it is the lag-3 template.

## Method

`retention_over_one.py --fracs 0.10,0.25,0.40,0.55,0.70,0.85 --frames 6`, ten
titles, FGS arms from the 2026-07-31 routing and general-library campaigns.
`flat_retention.py` in this directory implements the flat-block shared-mask
estimator; its identity control (source scored against itself) returns 1.000.
