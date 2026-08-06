# Where the low-signal floor comes from — 2026-08-06

> Diagnosis only. No default changed, nothing deployed, `modelsrc` still
> default-off.

`FINDINGS-2026-08-06-ONE-DEFECT.md` consolidated four separately-tracked
problems into one relationship: where the source's true grain signal is weak,
the analyser over-delivers — ratio `1.47`--`5.18` below true signal `1.0`,
`0.83`--`1.24` above `3.0`, log-log corr `-0.802`, slope `-0.414`, n=19. This
locates the code responsible.

## Two floors, both on master since the first FGS commit

`NVEncFilterFilmGrain.cu` contains exactly four references to `minSigma`, and
`minNoiseLevel` is hardcoded `0.5f` in 8-bit units (`:1701`) with
`depthScale = 1 << (bitDepth - 8)` (`:2357`) — so on 10-bit content **both
floors sit at sigma 2.0**, directly on top of the region where over-delivery
was measured.

| | line | what it does |
| --- | --- | --- |
| selection floor | `:2391` | blocks below `minSigma` never enter the flat mask, so the strength curve is fit on a sample censored from below |
| denoise floor | `:2449` | `clamp(metrics[i].sigma, minSigma, maxSigma)` sets per-block *denoise* strength, so a quiet block is denoised at 2.0 rather than its true level; the base is over-smoothed and the curve is then fit on an inflated `V_source - V_base` |

Neither is branch work. Both entered in `2e164d0e`, the first FGS commit. The
branch rewrites 1390 lines of that file and touches neither. Neither is
reachable from any command line — no parser anywhere sets `minNoiseLevel`, so
`0.5` is not a default but the only value. **The deployed production encoder
has both.**

An earlier note in this session said the `:2449` clamp floors synthesized
amplitude. It does not — it floors *denoise* strength, and reaches the curve
only through the over-smoothed base. That distinction is what the measurement
below tests.

## The denoise floor is real but far too weak

`adaptiveSigma` is `denoiseLevel <= 0`, so an explicit `denoise` bypasses the
`:2449` clamp entirely while leaving `:2391` active. `NVEncCmd.cpp:1181` then
rejects anything outside `[1.0, 50.0]` — the smallest requestable sigma is
already twice the floor, so the downward test is impossible from the CLI and
the test was inverted: if over-denoising inflates the curve, the curve must
rise with denoise.

Three grain-free animation titles, QVBR 25, `modelsrc=on`, bilateral, emitted
curve RMS (luma) — the analyser's own estimate, read without playback variance
in the way:

| title | auto | 1.0 | 2.0 | 4.0 | rises | 4.0/1.0 |
| --- | --- | --- | --- | --- | --- | --- |
| LongHalloween | 0.01982 | 0.01826 | 0.01952 | 0.01991 | yes | **1.09x** |
| PoppyHill | 0.02356 | 0.02173 | 0.02309 | 0.02400 | yes | **1.10x** |
| Kiki | 0.04152 | 0.03675 | 0.04025 | 0.04202 | yes | **1.14x** |

The mechanism is confirmed — monotone 3/3, and the direction is the predicted
one. But the **sensitivity is about `1.1x` per fourfold change in denoise
sigma**. Nothing in that response curve can produce `1.47`--`5.18x`
over-delivery; it would take a denoise ratio in the hundreds. The `:2449` clamp
contributes, and it is not the cause.

## What that leaves

The **selection floor at `:2391`** is now the leading candidate, and the
censored-sample account fits the shape of the defect in a way the denoise path
does not. A hard clamp would give a log-log slope of `-1.0` in the affected
region; selection acting on only part of the population gives something
shallower, and the measured slope is `-0.414`.

Two supporting observations, neither decisive:

- `auto` sits at or above every uniform arm on 3/3 titles despite its effective
  sigma being far lower — adaptive-with-floor behaves like much stronger
  uniform denoising. Consistent with quiet blocks being pushed up.
- The comparison of `auto` against the uniform arms is confounded: adaptive and
  uniform differ structurally, not only in magnitude. Only the within-uniform
  trend (`1.0`→`4.0`) is a clean read of sensitivity, and that is the number
  quoted above.

## Limits

Three titles, one QVBR, one content class. Animation was chosen because
grain-free content gives the floor the most room to act, which makes it the
best place to see the effect and the worst place to generalise from. The
emitted curve overstates delivered strength roughly twofold
(`FINDINGS-2026-08-04-ADMISSION-GATE.md`), so these numbers are not quality
claims — they are analyser estimates, which is what the floors act on.

## Next

Separating the two floors requires probing below sigma 2.0, which no interface
allows. That needs a build with `minNoiseLevel` lowered — an `NVEncCore/`
change, test-only or not, so it gets a plan before it gets a commit. Queued as
item 2 in `QUEUE-2026-08-05.md`.
