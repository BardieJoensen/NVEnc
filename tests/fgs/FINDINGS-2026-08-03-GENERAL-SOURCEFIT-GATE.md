# General-content gate for bilateral source fitting — 2026-08-03

> Quality-first research result. Nothing in this experiment was deployed.
> Tdarr remains on r4069 with bilateral separation and residual model fitting;
> `modelsrc` remains default-off and the flow routing is unchanged.

## Decision

**Do not enable `modelsrc=on` for every existing FGS route.** The six-film
result remains valid and source fitting remains the leading model architecture
for real film grain, but it is not a universal content mode yet.

This gate also rejects the stronger claim that deployed FGS has been proved
safe on all non-film content. The current analyser emits grain over every frame
of every title tested, including animation, and the grain-disabled base already
shows measurable loss on the animation and studio controls.

There is not yet a defensible automatic routing rule to deploy. A title or
genre allow/deny list would describe this six-title sample, not the underlying
signal. Production routing therefore stays unchanged while the admission
measurement below is built and tested on more than one title per class.

## What ran

`general_content_gate.py` used original H.264 downloads, never library AV1
transcodes. Each source was cut losslessly at 33% duration for 600 frames.
Four arms separate the option under test from binary drift:

| arm | binary | analyser |
| --- | --- | --- |
| plain | deployed r4069 | none |
| deployed | deployed r4069 | bilateral, residual fit |
| candidate-control | pinned r4173 candidate | bilateral, residual fit |
| bilateral-source | same pinned r4173 candidate | bilateral, source fit |

The encoder settings reproduce the active flow rather than the earlier P4
research setting: quality/HQ, AQ, temporal AQ, 50 Mb/s ceiling, QVBR 29 for
ordinary content and QVBR 34 for animation.

| title | role | QVBR |
| --- | --- | ---: |
| Drag Race | labelled saturated-studio failure | 29 |
| Stormester | labelled bright-studio failure | 29 |
| Big Brother | non-grain/high-frequency studio structure | 29 |
| Supergirl | modern clean digital | 29 |
| Rick and Morty | 2D animation / clean edges | 34 |
| Silo | fine-grain positive control | 29 |

Artifacts and machine-readable results are retained at:

```text
/media/merged-storage/media/test-encodes/sourcefit-general-gate-20260803/
```

The candidate binary is the same pinned build used by the six-film gate:

```text
commit 603c2eeaf7323bbd48d7f4193359920abb4d7169
SHA-256 8bff5e6dbbfc2a66590a822bcefaa4d123ab7293361eaf4e8c83d8ef786f0ab0
```

## Integrity and a caught harness fault

- all 24 direct AV1 encodes completed;
- all 42 grain-enabled/disabled lossless outputs passed complete
  `libdav1d -xerror` decoding;
- every scored pair passed exact 600-frame and relative-PTS validation;
- BT.709 limited-range metadata matched on every pair; and
- decoded-pixel hashes and table/stream hashes are in `manifest.json`.

The first scoring attempt exposed that `review_score.vmaf_run()` inherited its
288-frame review default even when this gate prepared 600 frames. That attempt
was stopped after two pairs. Commit `278aab1e` added an explicit limit and a
regression test; every result below is the corrected 600-frame run. The Drag
Race plain VMAF reproduces the earlier baseline at 97.91, which is useful
independent evidence that the labelled segment was recovered.

## Base operator: source fitting does not introduce a separator regression

Finished synthesis is a new random texture and full-reference metrics penalise
it. The clean-base rows are therefore the first safety question. Relative to
the candidate-control base, enabling source fitting changes source-referenced
base quality as follows:

| title | VMAF | SSIMULACRA2 | Butteraugli 2-norm |
| --- | ---: | ---: | ---: |
| Drag Race | +0.0677 | +0.1030 | -0.0014 |
| Stormester | +0.0512 | -0.0210 | +0.0007 |
| Big Brother | +0.0113 | -0.0476 | +0.0024 |
| Supergirl | +0.0218 | +0.0377 | -0.0007 |
| Rick and Morty | +0.0356 | -0.0093 | +0.0007 |
| Silo | **+1.0095** | **+1.7872** | -0.0395 |

Five titles are effectively flat and Silo improves. This agrees with the code
architecture: `modelsrc` changes model/strength estimation, while bilateral
continues to produce the base. The decoded bases are not pixel-identical
because the signalled strength LUT drives the intentional one-code luma level
compensation before encoding.

The candidate-control arm was necessary. Only Silo is pixel-identical to
deployed r4069; later candidate commits move the other five streams slightly.
Against the source, however, candidate-control base VMAF differs from deployed
by only -0.016 to +0.017. None of the large finished-result movements below is
binary drift.

## The model change is large on every content class

Representative table entries imply the following synthesized luma lag-1
autocorrelation. This is amplitude-independent spatial scale:

| title | candidate-control | bilateral-source |
| --- | ---: | ---: |
| Drag Race | 0.368 | **0.761** |
| Stormester | 0.263 | **0.869** |
| Big Brother | 0.445 | **0.850** |
| Supergirl | 0.191 | **0.733** |
| Rick and Morty | 0.228 | **0.771** |
| Silo | 0.184 | **0.508** |

Every table applies grain over 100% of its clip. There is no semantic admission
step that asks whether the correlated high-frequency signal is film grain,
codec residue, moving graphics or line art. Source fitting correctly answers
"what spatial texture is in selected source blocks"; it cannot by itself
answer "should AV1 synthesize this texture at new pixel locations."

One adjacent-frame static-flat measurement was taken inside the longest table
entry for each title. Source-fit field lag-1/lag-2 follows the temporal
difference rather than merely copying static picture structure:

| title | temporal texture | source fit | static blocks |
| --- | ---: | ---: | ---: |
| Drag Race | 0.771 / 0.645 | 0.787 / 0.676 | 98 |
| Stormester | 0.740 / 0.571 | 0.731 / 0.543 | 8 |
| Big Brother | 0.859 / 0.733 | 0.837 / 0.696 | 28 |
| Supergirl | 0.508 / 0.283 | 0.408 / 0.142 | 92 |
| Rick and Morty | 0.878 / 0.700 | 0.886 / 0.743 | 9 |
| Silo | 0.374 / 0.113 | 0.384 / 0.108 | 34 |

This prevents an overclaim: the general-content result does **not** prove that
source fitting simply leaked static edges into the model. It sees genuinely
time-varying correlated texture. On compressed WEB-DLs and animation that can
still be codec residue or moving raster detail rather than film grain. The low
Stormester/Rick block counts also make those two measurements diagnostics, not
threshold calibration.

## Finished-output guard rails fail, but do not become a grain oracle

Source-fit minus candidate-control at identical settings:

| title | bytes | VMAF | VMAF p1 | SSIMU2 | SSIMU2 p5 | Butter p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Drag Race | +0.15% | -2.2156 | -8.1200 | -10.0128 | -10.8982 | +3.9925 |
| Stormester | -0.24% | -2.6758 | -7.6849 | -13.3373 | -21.0912 | +8.3811 |
| Big Brother | -0.38% | -6.6294 | -8.4544 | -25.9088 | -33.3913 | +0.3179 |
| Supergirl | +0.17% | -5.7919 | -10.9630 | -24.1359 | -44.1771 | +7.3699 |
| Rick and Morty | -0.08% | -3.3744 | -9.0820 | -19.1883 | -30.6260 | +3.6433 |
| Silo | **+26.13%** | +0.0334 | -3.6407 | -1.5286 | -12.0866 | +3.5080 |

These guard rails decisively say "not cleared." They do not prove that finer
production grain is perceptually better. The fixed-energy Shining experiment
demonstrated that VMAF prefers finer grain at equal energy. SSIMULACRA2 and
Butteraugli are also full-reference, position-sensitive guard rails here, but
their scale bias has not been isolated in the same factorial; do not promote
their direction to a perceptual ranking. A blind playback comparison remains
required before assigning perceptual meaning to the direction.

The Silo size movement is different and cannot be dismissed as metric bias.
The same separator/source clip grows from 5.797 MB to 7.311 MB while the other
five source-fit arms remain within 0.4% of control. Its source-fit base gains
1.01 VMAF, so the next localisation is the raw pre-encode base and the
strength-driven luma level compensation, not rate-control tuning.

## What this says about the deployed blanket FGS route

Plain versus deployed r4069 at the flow's same QVBR:

| title | bytes | base VMAF | finished VMAF | finished Butter p95 delta |
| --- | ---: | ---: | ---: | ---: |
| Drag Race | -4.5% | -0.86 | -1.04 | -0.60 |
| Stormester | -9.0% | -1.27 | -2.09 | **+7.35** |
| Big Brother | -14.3% | **-2.32** | -4.52 | **+16.03** |
| Supergirl | -11.5% | -0.92 | -1.13 | +0.50 |
| Rick and Morty | -4.2% | **-2.19** | -2.42 | +0.19 |
| Silo | **-29.7%** | -1.97 | -2.18 | +0.09 |

The Silo result is the expected useful case: substantial saving with the
separate grain-fidelity evidence already established elsewhere. Stormester and
Big Brother reproduce real negative tails. Animation is especially poor value:
only 4.2% saved while the grain-disabled base loses 2.19 VMAF. That is enough to
justify expanding the animation bypass experiment, not enough to modify the
live flow from a single episode.

## Next sequence

1. Keep production and `modelsrc` routing unchanged.
2. Fix the temporal report so every sampled frame pair selects and validates
   its own static-flat mask. Reusing the first pair's mask across fast-cut
   general content produced inflated intermediate values during this gate.
3. Build a per-table-entry admission report with three separate outputs:
   model fidelity to temporal texture, evidence that the texture is film-like
   rather than codec/graphics residue, and coverage/confidence. Do not collapse
   them into one fixture-derived threshold.
4. Expand the plain/deployed base gate to at least three original-source
   animation titles and three clean/studio titles. If animation repeats Rick
   and Morty's base loss and weak saving, bypass FGS for the existing Animation
   NFO route independently of `modelsrc`.
5. Isolate Silo's +26.13% transfer by comparing raw pre-encode bases with and
   without source fitting, then encoding those fixed bases. This distinguishes
   level compensation from model-dependent rate-control behaviour.
6. Keep the five-film blind playback review. On general content, explicitly
   judge whether source-fit texture looks like restored camera grain or newly
   synthesized compression/raster noise.

The architectural direction is therefore narrower but still intact:
source-fitting fixes film-grain texture; bilateral remains the safe base
operator; a content-admission layer is the missing boundary between them and a
universal production route.
