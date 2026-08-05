# Pre-registration: a quality-labelled negative for grain admission — 2026-08-05

> Frozen before the first measurement. Offline measurement only; no
> `NVEncCore/` change, nothing deployed, `modelsrc` stays default-off.

## Why

`FINDINGS-2026-08-04-SHADOW-ADMISSION.md` ends: "Until a known harmful
admission exists, this conjunction cannot be called a validated safety gate."
Every admission gate so far has been tested only on inputs where source fitting
helps, and the campaign's own pre-registered CG negatives turned out
quality-positive. There is no negative in the corpus.

`FINDINGS-2026-08-04-ADMISSION-GATE.md` shows why one is needed: the current
adjudication standard asks whether playback restores the *input's* stochastic
texture, and codec noise is temporally stochastic. Restoring H.264 mosquito
noise scores identically to restoring film grain.

## Construction

For a retained lossless original `O`:

```text
C       = O recompressed at a harsh rate      (grain crushed, artifact added)
C_plain = plain encode of C
C_fgs   = FGS encode of C, bilateral + source-static + guarded response
```

`C`'s noise is codec artifact by construction, because `O` holds the real grain
and the noise appeared during compression. `O` and `C` are the same frames at
the same resolution, so any separating signal cannot be a resolution or genre
effect — the confound that disqualified the block-count CV lead.

## Rate selection (probe, completed before freezing)

Taxi Driver recompressed by the production binary, measured against `O` on
frames `10,58,106,154,202`:

| rate | bytes | retained amplitude vs `O` | noise lag-1 | noise lag-2 |
| --- | ---: | ---: | ---: | ---: |
| `O` truth | — | 1.000 | **0.806** | **0.434** |
| qvbr 38 | 12,144,170 | 0.434 | 0.907 | 0.690 |
| **qvbr 44** | 4,175,733 | **0.238** | **0.919** | **0.749** |
| **qvbr 50** | 1,184,668 | **0.124** | **0.903** | **0.779** |

qvbr 38 is rejected: at 0.434 retained amplitude the label is muddy, since half
the real grain survives. **qvbr 44 and qvbr 50 are frozen** — both have grain
mostly gone and bracket the harshness range.

The probe already shows the axis that should discriminate: recompression noise
is markedly *more* correlated than the source grain (lag-2 `0.69`--`0.78`
against `0.434`), the codec-ringing signature this project has recorded before
on plain encodes.

## Frozen corpus

Negatives — four titles x two rates = eight specimens:

| specimen | `O` | domain |
| --- | --- | --- |
| Taxi Driver | `keep-original/clip_Taxi_Driver-ref288.mkv` | 4K, 10-bit |
| The Shining | `keep-original/clip_The_Shining-ref288.mkv` | 4K, 10-bit |
| Tuner | `admission-gate-20260804/Tuner-ref.mkv` | 1080p, 8-bit |
| Train to Busan | `admission-gate-20260804/TrainToBusan-ref.mkv` | 1080p, 8-bit |

Rates `qvbr 44` and `qvbr 50` for every title. Retained amplitude will differ
by title and domain; specimen validity is established by measurement, not by
the rate label.

Positives that any candidate discriminator must retain, from existing runs: the
six architecture films, held-out Ju-on and Coming to America, and the
Migration/Elio CG scenes shadow admission re-labelled quality-positive.

Frames: `10,58,106,154,202,250` — the repo's standing texture set.
Arms are reached with `modelsrc=on` + `NVENC_FGS_TEST_SOURCE_STATIC=on` +
`NVENC_FGS_TEST_TEXTURE_LEAK=response`, and the runner fails if the encoder
logs `ignoring`, per commit `9c37ab62`.

## The decisive measurement

All layers on **one** mask, selected from `O`. `temporal_grain_report.py` takes
its flat/static blocks from `--source`, so the ground-truth pass passes `O` and
carries `C` itself as an arm; that arm's `total` layer is `C`'s codec noise on
exactly the blocks used for `O`'s grain and for the synthesis.

```text
harm  if   |synth_axis − C_noise_axis| < |synth_axis − O_grain_axis|
```

A second pass with `--source C` reproduces the current standard on its own mask,
for the divergence column. No aggregate mixes the two references.

## Pass conditions

1. **The specimen is a valid negative** if, on a majority of the eight
   specimens, `C_fgs` synthesis is closer to `C`'s noise axis than to `O`'s
   grain axis, **and** `C_fgs` played total is no closer to `O`'s grain than
   `C_plain` is.
2. **A discriminator is a candidate** only if it separates every valid negative
   from *all* positives — film and CG — without threshold tuning on this
   corpus. Anything that rejects Migration or Elio is rejected, per shadow
   admission's correction.
3. **If (1) fails**, the architecture is safer on recompressed input than
   feared. Record that as a positive safety result and stop. It is not a failed
   experiment.

## Discriminators, evaluated as-is

No thresholds fitted on this corpus.

- `cross-frame correlation` and `anisotropy mismatch`, via
  `sourcefit_admission_compare.py`;
- block-count CV, confound now controlled;
- the shadow campaign's stochastic descriptors (excess kurtosis, abs/RMS,
  quadrant-energy variation, boundary-gradient ratios).

## Integrity requirements

- every generated stream passes complete `libdav1d -xerror` decoding;
- frame counts verified per specimen; no silent truncation;
- delivered synthesis amplitude only — never the emitted table's mean scaling
  point, which overstates strength roughly twofold
  (`FINDINGS-2026-08-04-ADMISSION-GATE.md`);
- the runner reports which reference every number used.

## Discard criteria

Abandon rather than iterate if the recompression does not produce a case where
synthesis tracks codec noise over source grain, or if no discriminator
separates the specimens without also rejecting Migration/Elio. Do not tune a
threshold on this corpus to manufacture a separation.
