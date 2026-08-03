# Robust three-sample temporal median gate — 2026-08-03

> Rejected research arm. Nothing here is enabled by default or deployed to
> Tdarr. Production remains on the conservative bilateral/residual analyser;
> `modelsrc` and every motion experiment remain default-off.

## Question

The paired centred motion separator rejects a one-sided reference at block
level, but the motion-cycle investigation showed that some wrong matches have
low SAD in both directions. The next proposed defence was a robust pixel
operator over the current, aligned-previous and aligned-next samples.

The test arm keeps the accepted balanced scheduler and its total reference
exposure:

```text
current=4, previous=1, next=1
```

When both paired references are admitted, it replaces the weighted mean of the
two reference samples with `median(current, previous, next)`. The combined
reference weight is unchanged. One outlying aligned reference can therefore no
longer pull the output, while the ordinary path is untouched.

This is selected only by:

```text
NVENC_FGS_TEST_MOTION_CENTERED=paired-balanced-median
```

The flag is explicit through the host and CUDA render path; it is not encoded
in an existing weight or exposed as a public option.

## Isolation and build

Implementation commit: `603c2eea`. The pinned build completed all 223 targets
and linked successfully:

```text
/home/bardie/.cache/fgs-gate/builds/pin-603c2eea-1785764448/build-gate/nvencc
SHA-256 8bff5e6dbbfc2a66590a822bcefaa4d123ab7293361eaf4e8c83d8ef786f0ab0
```

The complete Python gate passes 112 tests. Source files retain their original
UTF-8-BOM/CRLF format.

Before selecting the new arm, the pinned binary was run on the retained
`coarse_detail_occl` source with the existing balanced scheduler. It exactly
reproduced the r4165 control:

| payload | retained r4165 | commit `603c2eea` |
| --- | --- | --- |
| grain-table SHA-256 | `32e044f4a751207e1b1f5f8bbc541eb44d070be4d8da32a9d40b92a141842141` | identical |
| decoded raw-video MD5 | `b7b9199f2342f35d2683822432007df2` | identical |

The new source therefore changes no existing or default arm.

Artifacts are retained under:

```text
/media/merged-storage/media/test-encodes/robust-median-20260803/
```

## Mandatory labelled-fixture gate

Both arms used the same pinned binary and deterministic 32-frame
`coarse_detail_occl` input, with `modelsrc=on`, one motion reference in each
direction, paired confidence, matched one-third temporal exposure,
`thsad=640`, and the detail-aware luma finish. The only changed variable was
the robust median.

| measurement | balanced detail | robust median detail | direction |
| --- | ---: | ---: | --- |
| coarse-grain capture | **64%** | 58% | worse |
| fine-detail transfer | **0.936736** | 0.936551 | flat/slightly worse |
| systematic edge bias RMSE | **1.26933** | 1.26958 | flat/slightly worse |
| plain edge RMSE | **5.66893** | 5.76692 | worse |
| whole clean-base RMSE | **4.87194** | 5.04354 | worse |
| extracted residual sigma | **2.05751** | 1.88066 | less grain captured |
| encoded bytes | **6,976,832** | 7,144,659 | 2.41% larger |

Both direct streams passed a complete `libdav1d -xerror` decode. The control
reproduced the earlier `64% / 0.937 / 1.27` result exactly, so this is not a
fixture or harness drift.

## Interpretation

The median does not detect the labelled damage. Its systematic edge result is
effectively unchanged, while it gives back grain capture and increases base
error and encoded size.

The likely mechanism is visible in the operator itself: whenever the current
sample lies between the two independently grained references, the median is
the current sample and the temporal contribution becomes a no-op. That occurs
on valid grain as well as at occlusions. At the low-SAD wrong matches that
survive paired admission, the bad sample is evidently not a sufficiently
distinct one-pixel intensity outlier for the median to improve the labelled
edge statistic. This mechanism is an inference from the measured response;
the gate proves the result, not the frequency of each ordering case.

## Decision

Reject the robust temporal median and do not spend a six-film encode on it.
It fails the known-negative fixture that was the prerequisite for corpus work.
The code remains a test-only, default-inert reproduction arm on the research
branch; it must not be merged into the production branch as a candidate
feature.

The next separator investigation should be measurement-first: test whether a
soft per-pixel photometric confidence, normalised by the known local grain
scale, separates paired-SAD-admitted occlusions from valid references. Unlike
the hard median, that can retain ordinary temporal averaging for differences
consistent with random grain and fade only references whose aligned-pixel
error is implausible. It should be rejected offline if the labelled and control
distributions do not separate, before another CUDA implementation is written.
