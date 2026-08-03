# Temporal chroma closure gate, 2026-08-03

> Quality-first research only. Nothing here was deployed to Tdarr. Production
> remains r4069 with the bilateral separator, residual-derived model and no
> research environment variables. `modelsrc` remains default-off.

## Question

The bilateral source-fit gate fixed U/V grain texture but left title- and
plane-dependent chroma amplitude errors. This experiment asks whether the
same consecutive-frame source/base estimate used by the luma leak closure can
close chroma strength without a corpus gain.

Two test-only modes were added behind `NVENC_FGS_TEST_CHROMA_LEAK`:

- `global`: one temporal source/base leak fraction per chroma plane; and
- `local`: an independent temporal source/base leak fraction in each of the
  existing 20 source-luma bins.

Both require `modelsrc=on`, chroma analysis, `retain=0`, and QVBR 25--39. The
ordinary path does not launch the added chroma kernels.

Commits under test:

```text
b8639a96 feat(fgs): test temporal chroma leak closure
aff66181 tests(fgs): compare chroma closure models
d20acdc6 fix(fgs): isolate chroma experiment from luma
aa317a9d tests(fgs): exercise rate-aware KAT paths
```

The pinned candidate binary was:

```text
/home/bardie/.cache/fgs-gate/builds/pin-d20acdc6-1785770314/build-gate/nvencc
SHA-256 a7578c49e9f99f141112290283452e0eb8b207208469de99856a2d1d95c2e593
```

Artifacts and the resumable six-film manifest are under:

```text
/media/merged-storage/media/test-encodes/chroma-closure-quality-20260803/
```

## Isolation and safety controls

The original luma temporal kernel, launcher and collector were restored
source-for-source. U/V collection runs in separate opt-in kernels. The CPU
gate passed 114/114.

The environment-off table was not byte-identical to a retained historical
table, but repeating the retained old binary produced a third hash. All table
differences were redundant strength-point x positions whose adjacent y values
were equal. The decisive image control was exact:

```text
grain disabled MD5  02eaf1253b1a8b13c389c515e265b2af
grain enabled MD5   35e00d9a9f41a81a4897a8d5f2b704bf
```

Historical output, an old-binary rerun and the corrected environment-off
candidate produced both hashes exactly. The default image result is therefore
unchanged; container bytes and non-canonical redundant knots are not a valid
isolation oracle.

The labelled `chroma_corr` and `chroma_ind` KAT fixtures passed at QVBR 29 in
off, global and local modes. Their already-correct U/V delivery was unchanged.
All 12 real-film experimental streams passed complete `libdav1d -xerror`
decoding.

## Six-film aggregate result

Variance-weighted played-total amplitude on the fixed production-static mask:

| plane / arm | corpus mean | MAE to 1.000 | title range |
| --- | ---: | ---: | ---: |
| U baseline | 0.9714 | **0.0329** | 0.9298 .. 1.0130 |
| U global | 0.9781 | 0.0443 | 0.9393 .. 1.0566 |
| U local | 0.9754 | 0.0440 | 0.9354 .. 1.0487 |
| V baseline | 1.0073 | 0.0598 | 0.8707 .. 1.0922 |
| V global | 0.9853 | **0.0479** | 0.9327 .. 1.0914 |
| V local | 0.9649 | 0.0622 | 0.9092 .. 1.0761 |

Global closure modestly improves V but worsens U. Local closure does not clear
either aggregate plane.

Across 48 populated title/plane/source-luma bands with at least 100 blocks:

| arm | band MAE | maximum absolute error |
| --- | ---: | ---: |
| baseline | 0.1436 | 1.2599 |
| global | 0.1368 | 1.1926 |
| local | **0.1237** | **1.1494** |

The local estimate improves average shape but barely moves the labelled
failure. Taxi Driver V in the 0.000--0.125 source-luma band changes from
`2.260` to `2.149`. Its absolute source sigma is only `0.739` native 10-bit
codes, so this large ratio is a low-energy quantisation/response problem, not
a 2.15-times-visible-noise claim. Ratios and absolute sigma must remain side
by side in follow-up work.

Other worst populated local bands are Deer Hunter V 0.375--0.500 (`1.650`),
Interstellar V 0.250--0.375 (`0.717`), Interstellar U 0.000--0.125 (`1.261`),
and Deer Hunter V 0.000--0.125 (`1.254`). The error changes sign across titles,
planes and luma ranges, so a fixed chroma multiplier remains invalid.

## Compression result

The six baseline streams total 116,099,448 bytes. Global adds 7,959 bytes
(`+0.0069%`) and local adds 17,136 bytes (`+0.0148%`). There is no meaningful
compression effect.

## What the experiment rules out

Temporal clean-base leak is a real secondary term, but it is not the root
cause of chroma strength error. Replacing the complete spatial strength target
with a temporal target does not close real-film U/V delivery, even per luma
bin. Neither mode should be promoted, and no threshold tuning follows from
this result.

The apparent analyzer/decoder coordinate mismatch is also absent. AV1 decodes
the signalled `cb/cr_mult=128`, `cb/cr_luma_mult=192` and offset 256 to signed
weights 0, 64 and 0. The separate U/V scaling curves are therefore indexed by
clean luma only, matching the analyzer's source-luma domain.

## Next quality investigation

Audit the exact normative chroma emission path on the retained real-film
streams. The chroma template combines spatial AR recursion with a predicted
luma-grain term, while the current solver divides every strength bin by one
entry-wide template gain. The audit must reproduce dav1d pixel-for-pixel and
report, per source-luma band:

1. absolute source, target and synthesized sigma;
2. scaling-curve response and integer rounding/clipping;
3. realised chroma-template variance;
4. the contribution of the luma-grain predictor; and
5. the analyzer population represented by each emitted curve point.

Only a causal mismatch from that decomposition justifies another encoder
change. Source-fitted AR remains the leading quality architecture because its
luma and chroma texture result is independent of this rejected amplitude
closure.
