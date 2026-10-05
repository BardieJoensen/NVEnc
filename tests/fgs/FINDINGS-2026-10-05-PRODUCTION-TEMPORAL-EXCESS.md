# Production grain excess and abrupt tracking

Production adds about 47% and 35% more grain than the source estimate on two frames of the held-out 1080p Knightfall animation, then reduces that grain by 57% in one frame while the source falls by 7%. The event survives an encode starting at the beginning of the title. This establishes a production defect relevant to the library: grain can overshoot a changing shot and then jump in strength. The wider content census and fix ranking are still in progress.

## Evidence

The deployed binary is SHA256 `c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b` (production `aeb14263`). This uses the flow's hardware decode, bilateral FGS and animation QVBR 34. The verified private original is SHA256 `26b6f448e1481bc75583fd3a6013c281b85a5ea406ea09ad47dbaea0a10aae16`; the source-only selection was fixed at 10/40/70% of duration before viewing encoder errors. A bounded search of the current project evidence found no earlier tuning use of this title; that does not establish the absence of every private historical experiment.

The initial census retains 288 consecutive evaluation frames after 288 context frames. The confirmation encodes the first 11,760 frames from time zero and checks the same source timestamps. On/off grain decodes come from the same IVF. Source timestamps, counts and independent source/base pixel-offset controls pass; the source masks exactly match the original census subset.

| Source time (seconds) | Source luma strength | Added grain strength, full history | Excess |
|---|---:|---:|---:|
|477.519|0.6253|0.9167|46.6%|
|477.560|0.6613|0.8914|34.8%|
|477.602|0.6159|0.3806|below source|

Strength is affine-detrended sigma in native 8-bit-equivalent code units. The source estimate includes remaining scene texture, so it is a conservative noise-plus-detail comparator, not a pure grain oracle. These values cover the source-only core patches in luma codes 0–31: 351/358 patches on the two initial witness frames. This brightness band occupies about 71–73% of those frames; that occupancy is **not** a claim that every pixel in the band was measured or over-delivered. Both chroma planes, HF energy and lag-1/2 correlations are retained separately in the per-frame evidence.

The reviewed source neighbors remain in the same animated hallway shot. Smooth walls, gradients and clothing fills are real source content; no letterbox bars are selected. The expanded mask includes more drawing/scene structure and produces different incidence, which remains visible in the census rather than being excluded.

The seek-window event measured added sigma 0.9344/0.9428 against source 0.6253/0.6613. Paired resampling of its selected patches gives excess ranges 0.3046–0.3132 and 0.2761–0.2871 at the 2.5/97.5 percentiles; this describes the finite spatial sample and is not a library confidence interval. Full-history values differ, but the excess and abrupt drop remain. Source-self controls return zero excess, and known tiny-addition/strength-change controls verify the measurement ruler.

## Receipts and limits

Scratch root: `/tmp/downloads/codex-work/fgs-submission-20261005/task4/`.

- `heldout-windows-capture2/knightfall-p10/`: first census, exact commands/alignment/masks/per-frame metrics and retained native event frames 145–160.
- `knightfall-full-history-confirmation/`: encode command, IVF/table and 16-frame confirmation with actual source-mask review and metrics.
- `knightfall-p10-census.json`, `knightfall-full-history-census.json`: machine-readable incidence and full grain axes.
- `heldout-window-plan.json`: frozen source-only title/window selection.
- `census-controls-receipt.json` and `frame-safety-*-controls.json`: source-self and quantity controls.

The two witness frames establish a case, not whole-title or whole-library prevalence. The initial three Knightfall windows contain 864 evaluated frames; smaller excesses and temporal changes also occur and will be reported with their sizes and denominators. A 0.25-code reporting bin separates sizes descriptively; smaller additions remain reported and are not declared acceptable. No production quality code has changed. A fix proposal follows the wider census, with matched-bitrate plain controls and explicit kill criteria.

- Auto: confirm the first source-relative excess using all preceding production encode history before ranking it as a library defect.
