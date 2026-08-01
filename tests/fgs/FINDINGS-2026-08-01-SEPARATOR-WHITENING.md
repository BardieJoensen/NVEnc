# The separator is what loses the grain's spatial correlation, 2026-08-01

## Result

`FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md` established that synthesised
grain is the right strength and the wrong size: amplitude within ~8% of source,
lag-1 autocorrelation at 0.43-0.72 of it. It left the cause open between the
separator and the AR fit, and guessed at the AR fit.

That guess was wrong. Splitting the chain stage by stage puts the entire loss in
the separator, and the production denoiser is the worst of the three shipped.

`psd=on` on the unmerged branch captures more grain still, but a new fixture
shows it does so by taking real detail --- the defect that kept it out of
production, now reproducible on demand rather than suspected.

> **CORRECTION, same session.** An earlier version of this document concluded
> from the fixtures that `motion` beats the production `bilateral` "on every
> axis measured". Real 4K film says the opposite, decisively, and the fixture
> conclusion was wrong. See "The fixtures are all static" below. The separator
> localisation and the PSD strength results are unaffected --- they are
> measured on residuals and on real film --- but no denoiser recommendation
> survives.

## The chain, on ground truth

Real film cannot answer this. A source's own autocorrelation is inflated by
picture structure that no flat-block mask fully removes, so "Taxi Driver source
0.811 -> residual 0.601" is not evidence of whitening. The `coarse_luma` KAT
fixture injects grain of known correlation onto a smooth base and writes the
ideal clean base alongside, so the injected grain is exactly source minus ideal.

Injected truth: sigma 6.012, lag-1 **0.839**, lag-2 **0.499**.

| denoiser | residual sigma | residual lag1 | residual lag2 | implied lag1 | implied lag2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bilateral | 2.681 (44.6%) | 0.655 | **0.105** | 0.655 | 0.075 |
| fft3d | 3.413 (56.8%) | 0.687 | **0.162** | 0.709 | 0.170 |
| motion | 3.900 (64.9%) | **0.797** | **0.415** | 0.773 | 0.342 |
| fft3d + `psd=on` | 4.637 (**77.1%**) | **0.801** | **0.428** | 0.782 | 0.352 |

"Implied" is the correlation the fitted AR coefficients encode, obtained by
running the spec's AR recursion over them (`ar_acf.py`). **It tracks the
residual to within 0.01-0.02 on lag-1 in every arm.** The fit is not losing
anything; it is faithfully reproducing a residual that arrives already whitened.

The decoder is not losing anything either. On Taxi Driver the fitted
coefficients imply lag-1 0.604 and the decoded synth layer measures 0.569.

And it is not our solver. libaom's `noise_model` fitted to the *identical*
residual implies lag-1 0.593 against our 0.604 on Taxi and 0.559 against 0.567
on Casino, with AR cosine similarity 0.997 and 0.999. Both fitters agree,
because both are given the same whitened input.

## The mechanism: the separator is a high-pass

The row that names it is the grain **left behind** in the clean base:

| denoiser | leftover sigma | leftover lag1 | leftover lag2 |
| --- | ---: | ---: | ---: |
| bilateral | 4.166 | 0.910 | **0.711** |
| fft3d | 3.790 | 0.912 | **0.737** |
| motion | 3.212 | 0.886 | **0.643** |
| fft3d + `psd=on` | 2.599 | 0.889 | 0.715 |

The grain the separator fails to extract is *more* correlated than the grain
that went in (0.711 against 0.499). It keeps the fine, near-white end of the
grain spectrum and leaves the coarse end in the base, where the encoder then
spends bits on it or quantises it away.

That single fact explains the whole cluster of open symptoms: the 36-45% capture
ratio, the "right strength wrong size" synthesis, and why coarse 35mm is the
worst case. They are one defect seen from three directions.

### Why `psd=on` is the matching fix and not a coincidence

FFT3D's Wiener rule is `gain = (P - sigma) / P` with a **scalar** sigma
(`NVEncFilterDenoiseFFT3D.cuh:366`). A scalar sigma is the statement that the
noise is white --- equal power in every frequency bin. Coarse film grain is the
opposite: its power is concentrated at low and mid spatial frequencies. So the
rule subtracts a flat noise floor from a sloped noise spectrum, over-removing
where grain is weak and under-removing where it is strong. The extracted
residual is whitened by construction, and what is left behind is the coarse tail
--- which is exactly the leftover-correlation row above.

Shaping sigma per bin by an AR(1) PSD removes that assumption, and the measured
effect is the one predicted: capture 56.8% -> 77.1%, lag-2 retention
0.325 -> 0.857. The mechanism was identified independently of this measurement
(`FINDINGS-2026-07-31-WIENER-PSD.md`), which is why the agreement carries weight.

**The earlier evaluation of `psd=on` understated it badly.** It was recorded as
"coarse capture 41% -> 45%", measured end-to-end after encode and decode with
the whole-frame estimator. Measured at the stage the change actually acts on,
the separator output, it is 56.8% -> 77.1%. The change was nearly shelved on a
number produced by the same estimator that has now misled this work three times.

## Real film reproduces the ranking

Taxi Driver, 4K, source lag-1 0.811 / lag-2 0.477 (structure-inflated, so read
the ordering rather than the absolute):

| denoiser | residual sigma | residual lag1 | residual lag2 |
| --- | ---: | ---: | ---: |
| bilateral | 1.122 | 0.601 | **0.095** |
| fft3d | 1.532 | 0.682 | **0.201** |
| motion | 1.409 | **0.733** | **0.337** |
| fft3d + `psd=on` | 1.943 | **0.785** | **0.434** |
| *source* | *2.353* | *0.811* | *0.477* |

Same order, same magnitude of separation. `psd=on` recovers a residual whose
correlation is within a few percent of the source's on both lags, on real 35mm.
Casino behaves the same way.

## The production setting is the worst arm

`denoiser=bilateral` is what the tdarr integration path, `campaign.py`'s
consumers, and essentially every script under `/opt/docker-apps/scripts` pass.
NVEncC's own default is `fft3d`; `bilateral` was chosen deliberately.

The reason is recorded in `silo_fgs_retest.py`:

> `denoiser=bilateral` beats both `fft3d` (NVEncC's default) and `motion`
> (campaign.py's default) by a wide margin on exactly these reference metrics --
> SSIMULACRA2 30.50 vs 14.77 at equal retention.

Both halves of that justification fail against what is now measured.

**The metric is biased in exactly this direction.** `/opt/docker-apps/docs`
measures SSIMULACRA2 at **-392 points per unit of grain retention**: correctly
randomised grain is a new realisation, so a full-reference metric scores it as
error and rewards whichever denoiser destroys the most grain. Selecting a
separator on SSIMULACRA2 selects for grain destruction almost by construction,
and bilateral won because it discards the most.

**"At equal retention" was measured with the broken estimator.** Retention there
is `campaign.py::hf_sigma`, which high-passes the whole frame and therefore
counts encoder ringing as grain --- already documented in
`FINDINGS-2026-08-01-RETENTION-DECOMPOSITION.md` as having produced three false
findings in one session. It is also, being a high-pass, blind to precisely the
coarse-versus-fine distinction that separates these three denoisers. Bilateral
and motion can read "equal retention" on it while differing 4x in lag-2.

## Grain capture is not free, and `coarse_detail` prices it

Capturing more grain and preserving picture detail are the same operation
pulling in opposite directions, and no existing fixture could see the trade:
`coarse_luma` puts correlated grain over flat bands, so there is no detail to
lose, and `detail_luma` uses white grain, so a correlation-driven filter never
engages. `FINDINGS-2026-07-31-WIENER-PSD.md` names this gap as its own blind
spot and as the reason `psd=on` is not in production.

The generator already supported both axes, so the missing fixture is one spec
entry. `coarse_detail` = correlated grain over the detail pattern:

| arm | capture | detail transfer | systematic edge RMSE | plain edge RMSE |
| --- | ---: | ---: | ---: | ---: |
| bilateral (production) | 36% | 0.531 | **1.95 FAIL** | 4.56 |
| fft3d (NVEnc default) | 41% | 0.487 | 1.44 | 4.62 |
| **motion** | 40% | **0.693** | **1.43** | **3.36** |
| fft3d + `psd=on` | **48%** | 0.404 | **2.62 FAIL** | 4.23 |

Read the systematic column, not the plain one. `systematic_edge_bias_rms_8bit`
is a temporal mean bias, so random grain left in the base cancels out of it and
what remains is damage landing in the same place every frame. Plain edge RMSE is
dominated by leftover coarse grain --- which is exactly what a separator that
struggles with coarse grain leaves behind --- and so fails every arm while
saying nothing about detail. `auto_retain_detail` already made this distinction
for the same reason; `coarse_detail` inherits it.

**On this fixture** bilateral captures the least grain, retains the least
correlation (lag-2 0.211 against ground truth), *and* does the most repeatable
detail damage of the three shipped denoisers. That reads as an indictment of the
production setting. It is not one, for the reason in the next section.

**`psd=on` is a real gain with a real cost.** It buys the highest capture in the
table and pays 1.44 -> 2.62 in systematic edge damage, an 82% increase. That is
the blind spot behaving exactly as the branch's own document predicted, and it
is a sufficient reason to keep it off by default. It is now a failing test
rather than a caveat in prose.

`detail_luma` is identical with `psd=on` and `psd=off` --- same synthesised
per-band sigmas, same edge RMSE 1.89 --- confirming the intended no-op: white
grain gives rho near zero, the PSD shape stays flat, and the filter behaves as
it did before. (That was checked for the PSD arm only, not across denoisers.)

Caveat on the threshold: the 1.5 limit is inherited from `auto_retain_detail`
and fft3d clears it by 0.06, so it is provisional and should be re-derived. The
82% relative movement is not threshold-sensitive; the pass/fail labels are.

### Why `psd=on` damages detail, and what would fix it

The obvious explanation is wrong. If rho were measured over the whole frame,
picture detail would inflate it and over-shape the filter --- but rho is already
a median over the *selected flat blocks only*
(`NVEncFilterFilmGrain.cu:1368-1374`), and the fixtures confirm it empirically:
`coarse_detail` measures lag-one **0.810** against `coarse_luma`'s **0.806**.
Adding a detailed top half moved rho by 0.004. Detail is not leaking into the
estimate.

The asymmetry is in how the two quantities are applied. Sigma is **per block**
--- textured blocks deliberately fall back to the median "so their own texture
variance does not turn the denoiser into a blur" (`:1381`). The PSD shape is
**per frame**: `fft3d.noisecorr` is a scalar on the filter's param struct, and
changing it re-runs `m_fft3d->init` for the whole frame. So a shape derived
correctly from flat, grainy blocks is then applied unchanged to blocks that are
mostly picture. In those blocks the shape raises the subtracted threshold at
exactly the low and mid frequencies where the detail lives.

That predicts the fix: carry the shaping per block the way sigma already is, and
fade it out for blocks outside the flat mask. It also predicts a cheaper partial
test --- scaling rho down should cost capture slowly and recover detail quickly
if the mechanism is right, since capture depends on the shape over flat blocks
where it is correct.

Per-block shaping is not implemented, and `psd=on` reaching the filter as a
scalar is a real structural constraint rather than a tuning oversight: it needs
the FFT3D filter to accept a shape map alongside the sigma map it already takes.

The cheaper prediction was testable immediately, by making the shaping strength
a runtime scale on rho (worktree-only patch, never committed) and sweeping it.
Grain figures are from `coarse_luma` ground truth; detail figures from
`coarse_detail`:

| rho scale | lag-2 retained | capture | detail transfer | systematic edge |
| ---: | ---: | ---: | ---: | ---: |
| 0.00 (`psd=off`) | 0.325 | 41% | 0.487 | 1.44 |
| **0.25** | **0.497** | 46% | 0.455 | **1.62** |
| 0.50 | 0.659 | 50% | 0.419 | 2.04 |
| 0.75 | --- | **51%** | 0.393 | 2.58 |
| 1.00 (`psd=on` as shipped) | 0.857 | 48% | 0.404 | 2.62 |

The prediction holds: detail cost is bought back much faster than grain benefit
is given up. At quarter strength, lag-2 retention is still up 53% and capture up
5 points, for 0.18 of the 1.18 edge-RMSE increase --- 15% of the damage for a
large share of the gain.

**Full strength is past the optimum on the grain axis too.** Capture peaks at
0.75 and *falls* at 1.00 (51% -> 48%) while edge damage keeps climbing. The
shipped `psd=on` setting is strictly dominated by a weaker one: worse on both
axes than 0.75, and it is the setting the earlier 41% -> 45% evaluation was
made at. Whatever else is decided, the strength is mistuned.

Quarter-strength shaping scores systematic edge **1.62** against `bilateral`'s
**1.95** on the same fixture, with 46% capture against its 36%. That comparison
is worth recording but must not be leaned on: it is a static-fixture number, and
the section below shows static fixtures inverting the denoiser ranking outright.

What the sweep does establish, and what does not depend on the fixture being
representative, is the *shape* of the trade within the PSD arm: detail cost
grows faster than grain benefit, and full strength is dominated by 0.75 on both
axes. "PSD shaping damages detail" is a statement about a strength setting
rather than about the idea. Whether any strength is worth shipping needs the
branch's own gate --- the texture report on real film plus a playback A/B ---
which has not been run.

## The fixtures are all static, and it inverted the denoiser ranking

Matched-VBR, 288 frames, 4K, all three arms scored by the same code path in one
session. The bilateral arm reproduces `FINDINGS-2026-07-31-ROUTING.md` to two
decimals (Casino SSIMU2 60.19 against 60.18, Taxi 18.40 against 18.39), so the
harness is consistent and the comparison is sound:

| title | arm | MB | VMAF | VMAF min | SSIMU2 | SSIMU2 p5 | Butt 2n | Butt p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Casino | plain | 49.9 | **97.18** | **94.69** | **63.64** | 53.10 | **1.204** | 9.09 |
| Casino | bilateral | 44.8 | 94.92 | 92.88 | 60.19 | **55.17** | 1.489 | **7.05** |
| Casino | motion | 44.2 | 90.61 | 78.26 | 33.34 | 2.92 | 2.393 | **40.33** |
| Scarface | plain | 49.6 | **92.05** | 88.41 | -0.22 | -15.75 | **2.799** | 12.99 |
| Scarface | bilateral | 49.4 | 90.82 | **90.01** | **1.63** | **-4.40** | 3.007 | **9.83** |
| Scarface | motion | 46.1 | 89.27 | 87.02 | -14.25 | -22.42 | 3.456 | **38.15** |
| Taxi | plain | 50.7 | **94.25** | **91.96** | **29.31** | 8.93 | **2.278** | 13.77 |
| Taxi | bilateral | 51.0 | 89.72 | 88.27 | 18.40 | **10.94** | 2.746 | **10.88** |
| Taxi | motion | 50.2 | 86.84 | 84.94 | -6.46 | -18.16 | 3.459 | **23.10** |
| Shining | plain | 51.2 | **98.26** | **96.07** | **41.81** | 24.63 | **1.811** | 8.97 |
| Shining | bilateral | 47.1 | 96.37 | 94.76 | 34.27 | **25.16** | 2.251 | **8.63** |
| Shining | motion | 46.6 | 88.51 | 66.75 | 6.09 | -37.32 | 3.822 | **53.86** |

**`motion` is far worse on real film, and the metric-bias defence does not
apply to it.** That defence says synthesis depresses *mean* metrics through
pixel misalignment while the *tails* improve, and it is why bilateral's mean
losses were accepted --- bilateral does win SSIMULACRA2 p5 and Butteraugli p95
on all four titles. `motion` loses both: Butteraugli p95 goes 7.05 -> 40.33 on
Casino and 8.63 -> 53.86 on Shining, 4-6x worse than the arm it is supposed to
beat. Losing the tails as well as the mean is the signature of real damage, not
of measurement bias.

**The fixtures are static.** `base_luma` returns the identical picture for every
frame; only the grain is redrawn. Apart from a hard cut in the `cut` fixtures,
every KAT fixture is a static image --- the best possible case for a
motion-compensated denoiser, and one that never occurs in film. That was the
obvious explanation, so it was tested rather than asserted.

**It is not the explanation.** `coarse_detail_pan` adds a fractional pan (0.77,
0.31 px/frame) to the picture while leaving the measurement bands in place, so
motion compensation cannot land exactly. `motion` still ranks first:

| arm | capture | detail transfer, static | detail transfer, panning |
| --- | ---: | ---: | ---: |
| bilateral | 36% | 0.531 | 0.431 |
| fft3d | 41% | 0.487 | **0.257** |
| motion | 40% | **0.693** | **0.591** |
| fft3d + `psd=on` | 48% | 0.404 | 0.321 |

Adding motion costs every arm detail and reorders some of them --- `psd=on`
overtakes plain `fft3d`, reversing the static result --- but `motion` still
ranks first, so this does not reproduce its real-film collapse.

**The real-film damage tracks motion magnitude.** Per-frame Butteraugli against
a per-frame motion proxy, split at the title's own motion quartiles:

| title | gap, low-motion quartile | gap, high-motion quartile |
| --- | ---: | ---: |
| The Shining | 4.3 | **35.6** |
| Casino | 10.3 | 27.1 |
| Scarface | 9.1 | 22.5 |
| Taxi Driver | 4.2 | 7.9 |

All four in the same direction. It is also not a few bad frames --- `motion` is
worse on 94-100% of frames --- and not a temporal misalignment: testing offsets
-2..+2 puts the best match at 0 for both arms, with equal MSE.

So harder motion was tried. `coarse_detail_move` adds a fast pan with rotation
and zoom, making the displacement vary across the frame so no single vector fits:

| arm | detail transfer: static / pan / hard motion |
| --- | --- |
| bilateral | 0.531 / 0.431 / 0.424 |
| fft3d | 0.487 / 0.257 / 0.262 |
| **motion** | **0.693 / 0.591 / 0.500** |

`motion` does degrade fastest with motion --- it loses 0.193 where bilateral
loses 0.107 --- but it has not crossed over, so **the fixtures still cannot
reproduce the real-film result**.

The property they were missing is **disocclusion**. Every motion the generator
could produce was a geometric transform of one texture layer, so every pixel's
content existed somewhere in the previous frame and a temporal denoiser can in
principle find all of it. Real motion reveals content that was never visible:
foreground moving over background, objects entering frame, cuts. No temporal
predictor can supply that, which is exactly where a motion-compensated denoiser
has no fallback and a purely spatial one is unaffected.

That needs a second layer, so `coarse_detail_occl` adds one: a field of 36
opaque, differently-textured objects sliding over the background, alternate rows
in opposite directions. It disoccludes 21-24% of the measured region per frame
--- a single object at 11 px/frame manages 0.4%, which no aggregate measure can
see, and that is why the field is needed.

**It reverses the ranking.** Base-versus-ideal edge RMSE, the measure closest to
the structural error real film showed:

| fixture | bilateral | fft3d | **motion** |
| --- | ---: | ---: | ---: |
| `coarse_detail` (static) | 4.56 | 4.62 | **3.36** |
| `coarse_detail_pan` | 4.56 | 4.63 | **3.52** |
| `coarse_detail_move` (pan+rotate+zoom) | 4.49 | 4.60 | **3.66** |
| **`coarse_detail_occl`** | 5.11 | 4.89 | **6.79** |

`motion` is best on every single-layer fixture and worst as soon as content is
uncovered. It is not leftover grain inflating that number: `motion` captures 59%
against fft3d's 58%, so the two leave comparable residue, and the gap is 6.79
against 4.89. It is damage.

Geometric difficulty was not the variable. Rotation and zoom make the
displacement vary across the frame and barely moved `motion` (3.36 -> 3.66);
introducing content with no history moved it past both competitors in one step.

Note that `detail_transfer_gain` still ranks `motion` first here (0.723 against
0.684 and 0.650). It is a high-pass energy ratio, so ghosted or smeared detail
still counts as present --- it measures whether detail survives, not whether it
survives *in the right place*. On this fixture the edge RMSE is the measure that
matters, and the two disagree.

**What is established** is narrower than the earlier draft of this document
claimed: fixture rankings do not transfer to real film, demonstrated twice over
--- once by `motion` inverting outright, once by `psd=on` and `fft3d` swapping
places when motion is added. The claim that `motion` beats `bilateral` "on every
axis measured" was written from the fixtures before the real-film arm finished
and is withdrawn. **`bilateral` is defensible on real film.**

A methodological note worth keeping: `systematic_edge_bias_rms_8bit` is a
temporal mean, so it is only meaningful on a static picture. On the panning
fixture every arm's value *falls* (bilateral 1.95 -> 1.08) while detail
preservation simultaneously worsens on every arm, because damage that travels
with the picture averages out of a temporal mean. `coarse_detail_pan` therefore
guards `detail_transfer_gain` and reports both edge numbers as information only.

It also puts a boundary on the rest of this document. Claims measured on
residuals and on real film --- the separator localisation, the ACF chain, the
Taxi/Casino numbers --- stand. Claims resting only on static fixtures, including
the whole `coarse_detail` table, need a moving-content equivalent before they
support any decision. The PSD strength sweep is in that category.

## PSD on real film: a net loss at every strength

The PSD arm had never been measured on anything but synthetic fixtures. Matched
VBR, 288 frames, 4K, same harness as every other arm:

| title | arm | MB | VMAF | SSIMU2 | SSIMU2 p5 | Butt p95 | SSIM | ret |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Casino | fft3d | 44.5 | **95.09** | **52.08** | **45.63** | **8.84** | **0.9987** | 0.930 |
| Casino | psd 0.25 | 43.8 | 94.26 | 47.38 | 41.70 | 9.53 | 0.9982 | 0.930 |
| Casino | psd 0.50 | 43.1 | 93.33 | 43.47 | 38.11 | 10.36 | 0.9976 | 0.930 |
| Casino | psd 1.00 | 42.9 | 91.97 | 40.20 | 34.60 | 12.54 | 0.9970 | 0.911 |
| Taxi | fft3d | 51.1 | **92.04** | **4.48** | **-1.26** | **12.66** | **0.9967** | 0.935 |
| Taxi | psd 1.00 | 50.7 | 86.14 | -28.42 | -32.88 | 19.53 | 0.9895 | 0.911 |
| Shining | fft3d | 46.1 | **97.19** | **23.41** | **17.15** | **8.98** | **0.9990** | 1.177 |
| Shining | psd 1.00 | 43.7 | 94.29 | 8.46 | 2.24 | 12.54 | 0.9977 | 1.185 |

**Every metric degrades monotonically with shaping strength, and retention does
not improve.** Casino's retention is 0.930 at every strength; Taxi's falls.
Bytes drop, so the base is getting cleaner --- but what is being removed is not
turning into signalled grain.

That is the opposite of the fixture result, where shaping lifted capture from
41% to 48%, and it has a straightforward explanation. `coarse_luma` is roughly
half flat bands, where a shape derived from flat grainy blocks is correct. Real
film has very little genuinely flat area, so the same shape is applied almost
everywhere to blocks that are mostly picture, and the detail damage
`coarse_detail` isolated dominates the result.

**So PSD is not the lever.** It was built on a real mechanism --- the scalar
sigma does assert white noise, and that assertion is wrong --- but the
implementable form of the fix costs more picture than it recovers grain on real
content. Tuning the strength down does not rescue it: the metrics degrade
monotonically from the first step, and `rho=0.25` is already worse than off.

## A second amplitude loss, downstream of the fit

Separating the two stages on `coarse_luma` shows the residual is not the only
loss. `capture` is end-to-end synthesised sigma over injected; `residual` is what
the separator extracted; the last column is what survives the fit and synthesis:

| arm | residual / injected | capture / injected | **synth / residual** | AR variance gain |
| --- | ---: | ---: | ---: | ---: |
| bilateral | 0.446 | 0.36 | **0.81** | 7.3 |
| fft3d | 0.568 | 0.41 | **0.72** | 11.5 |
| motion | 0.649 | 0.40 | **0.62** | 11.7 |
| libaom, ideal clean base | 1.000 | 0.463 | **0.46** | --- |

Even handed a *perfect* residual --- libaom fitting the true grain against the
true clean base --- synthesis delivers 46% of the amplitude. That is the 46.3%
"model ceiling" recorded in `FINDINGS-2026-07-31-WIENER-PSD.md`, but read this
way it is not obviously a format limit: it is a second loss of the same size as
the separator's, and it is unexplained.

The loss tracks the AR variance gain of the fitted model, measured by running
the spec's recursion over the coefficients (`ar_acf.py`): gain 7.3 loses 19%,
gain 11.5 loses 28%, gain 11.7 loses 38%, and the ideal-clean case --- the most
correlated residual, so the highest gain --- loses 54%. Fine grain, where the AR
gain is near 1, loses nothing: `detail_luma` synthesises at 0.98-1.02.

This is the signature of a gain-normalisation error, and it is the same class as
the 2026-07-29 fixed-lattice bug, which inflated the fitted AR gain and halved
signalled strength. That one was found and corrected; this looks like a
remainder of the same kind, invisible on white grain because the gain is 1 there.

**Not established.** The correlation is four points and the mechanism has not
been traced in the code. But it is a specific, testable claim --- synthesised
amplitude should be independent of AR gain and is not --- and if it holds it is
a larger effect than anything the separator does.

## What this does not yet establish

The separator is localised; the deployment decision is not made. `motion` costs
throughput (37.9 fps against fft3d's ... see the campaign table below once
complete) and its full-reference metrics will be *worse*, for the reason above.
That is expected and is not by itself an argument against it, but neither is
this measurement an argument for shipping it: nothing here shows a viewer
prefers the result. The release gate remains a playback A/B.

What has changed is that the choice is now made on a quantity that is not
metric-biased. Lag-2 retention against ground truth is 0.211 for bilateral and
0.832 for motion, and no part of that comparison passes through a
full-reference metric or through `hf_sigma`.

## Method

`separator_acf.py --denoiser {bilateral,fft3d,motion}` on `coarse_luma`;
`layer_acf.py --clean` for the real-film residuals; `ar_acf.py` for the implied
correlation; `reference_compare_real.py` for the libaom oracle. `ar_acf.py` is
validated against constructed tables: a 0.5 horizontal tap returns h1 0.506, a
0.797 tap returns h1 0.798 with h2 0.638 = rho^2, zero taps return 0.001.
`layer_acf.py` detrends with a box mean rather than a high-pass, and the
synthesised layer is invariant to the radius (0.569 at r=4 through 0.571 at
r=16) because it has no structure to remove --- the control that the operator is
not what creates the gap.
