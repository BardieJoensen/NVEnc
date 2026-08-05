# Pre-registration: does covariance closure discount codec artifact? — 2026-08-05

> Frozen before measurement. Offline only; no `NVEncCore/` change, nothing
> deployed, `modelsrc` default-off.

## The hypothesis under test

`FINDINGS-2026-08-05-NEGATIVE-SPECIMEN.md` raised, and explicitly declined to
claim, one explanation for why the candidate sometimes reconstructs an
original's grain character from a source that no longer contains it:

> the guarded covariance response subtracts the encoded base's covariance from
> the AR fit, and codec artifact lives largely in that base, so the closure may
> discount it structurally.

This tests it directly.

## Correction to the previous construction

The negative-specimen run built `C` by recompressing to **AV1** and then
encoding to AV1 again. That path does not occur in production: real inputs are
H.264/HEVC remuxes and WEB-DLs, and AV1 is only ever the output. Those results
stand as measured but are not representative of the artifact the analyser will
actually meet.

`C` is therefore now **x264**, calibrated against a real distributor encode.
The retained `Tuner 2025 AMZN WEB-DL` runs 5.37 GB over 6470.7 s (~6.6 Mbit/s
total, 1920x1040 letterbox-cropped) against its 27.5 GB remux. Cropping breaks
pixel alignment with the 1080-line original, so the real WEB-DL is used to set
the *rate*, not as the specimen. Frozen rates: **5000 kbit/s** (WEB-DL-like)
and **2000 kbit/s** (harsh).

## Corpus

Lossless 288-frame `O` clips cut at 00:35:00 from 1080p AVC remuxes in
`long-term-seeding`, chosen to span the behaviours the previous run separated:

| title | why |
| --- | --- |
| Train to Busan | one of the two titles whose synthesis tracked codec artifact |
| Tuner | the title that tracked the original's grain instead, and has a real WEB-DL |
| Quiz Show | grain-bearing 35 mm film positive, already a project validation scene |

## Arms

All `modelsrc=on`, bilateral, QVBR 29, same pinned candidate
`40b987ff` / `042cb34e…`. Only the closure strength changes:

| arm | environment |
| --- | --- |
| `A0_sourcefit` | `NVENC_FGS_TEST_SOURCE_STATIC=on` |
| `A1_response` | `+ NVENC_FGS_TEST_TEXTURE_LEAK=response` (guarded, current candidate) |
| `A2_dynamic` | `+ NVENC_FGS_TEST_TEXTURE_LEAK=dynamic` (full subtraction) |

The runner aborts if the encoder logs `ignoring`, per commit `9c37ab62`.

## Measurement

One `temporal_grain_report.py` pass per (title, rate) with `--source O` and
arms `C, A0, A1, A2`, so every layer is measured on a single `O`-derived mask.
`C`'s `total` layer is the codec artifact; `truth` is `O`'s real grain.

For each arm: `synth_to_o` and `synth_to_c`, mean absolute distance over the
four texture axes.

## Frozen prediction

If the hypothesis holds, strengthening covariance closure moves synthesis
**away** from the artifact and **toward** the original's grain:

```text
synth_to_c :  A0 < A1 <= A2      (further from artifact)
synth_to_o :  A0 > A1 >= A2      (closer to real grain)
```

**Supported** if the ordering holds on a majority of the six (title, rate)
cells, and the A0 to A2 movement is larger than the between-rate noise on the
same title.

**Rejected** if there is no consistent ordering, or the ordering is reversed.
A reversal would mean covariance closure *increases* artifact tracking, which
would matter more than the original hypothesis.

## Discard criteria

If A0 and A2 differ by less than the same-title between-rate spread, the effect
is not resolvable at this corpus size and no mechanism claim is made. Do not
add titles or rates after seeing the result to manufacture an ordering.
