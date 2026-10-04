# Plain-control calibration correction — 2026-10-04

The first synthetic control campaign accidentally introduced NVENC's default VBR maximum when replacing canonical CQP. Most 1080p trials reported an 8,000 kbps maximum, and the 4K trial reported 20,000 kbps. They could not reach the intended payload rates. The replacement harness fixes only control calibration; candidate code, canonical FGS commands and the 3% acceptance limit remain unchanged. All earlier attempts and the original harness are retained.

## Evidence and cause

Production `NVEncCore.cpp:2494` clears maximum bitrate in CQP mode; lines 2497–2518 derive a level-based maximum for other modes when no maximum was supplied. Canonical CQP KAT commands omit this option. The old VBR controls therefore acquired a cap that their FGS comparators did not use.

`const_10bit` stayed at 13,047.774 kbps despite increasing its requested VBR through 486,326, versus a 20,397.798 target. Its logs consistently say `Max: 8000 kbps`. The 4K control plateaued at 27,355.160 kbps with `Max: 20000 kbps`, versus 79,148.352 target. Short-clip actual payloads can exceed those nominal rate-control maxima; their bytes alone do not reveal the configured cap.

The old unbounded ratio updates also exceeded CLI arithmetic bounds. For example, ramp_luma requested 5,669,698 kbps but logged 1,374,730 kbps. `NVEncCmd.cpp:904` parses maximum bitrate as signed `int`, then multiplies by 1000; all version-two requests are bounded well below this arithmetic limit. The old capped/wrapped attempts remain failed calibration evidence, not matched controls.

## Version two

`match_plain_controls_v2.py` preserves the complete-receipt SHA requirement, deployed/source/FFmpeg pins, exact non-rate arguments, all failed outputs, frame/IVF checks and strict accepted-output libdav1d decode.

For KAT VBR controls only it adds `--max-bitrate ceil(2*max(requested_vbr,target_fgs_payload))`, and records the exact added arguments and rationale in each trial. Requested VBR is limited to 500,000 kbps and KAT maximum to 1,000,000 kbps. These are experimental bounds below signed kbps-to-bps overflow, not a claim that every NVENC device or AV1 level supports them. A requested or effective-rate violation is preserved as unresolved rather than silently clamped. Real-source commands retain their existing `--max-bitrate 50000` unchanged.

The log must show the requested VBR and at least the explicit KAT maximum. The clean KAT first gets a separate canonical CQP20 plain control in its own `clean-cqp20` directory, removing only FGS/table/output arguments from the original sequence. If it matches the same 3% payload band and passes strict decode, no VBR tuning is needed. Otherwise it proceeds to at most eight VBR trials. The separate CQP probe is explicit in the receipt.

Tuning uses ratio adjustment while observations lie on only one side of the accepted payload band. Once both sides exist, it chooses the integer midpoint of the tightest monotonic requested-rate bracket. Silo's preserved low/high observations at 2092/2155 kbps imply midpoint 2123. A fresh eight-trial campaign can establish its own bracket; no earlier artifact is overwritten or silently reused. Adjacent integer endpoints without a match, reversed/nonmonotonic endpoints, repeated targets, and the eight-trial bound leave the case unresolved. The tolerance stays exactly ±3%.

## Validation

No GPU process was launched by the author. Syntax and `--help` pass. No-GPU validation pinned all 21 KAT cases and Silo; receipts are `reports/plain-controls-v2-kat-validation/report.json` and `reports/plain-controls-v2-silo-validation/report.json`. `reports/plain-control-v2-review.json` verifies the max arguments, unchanged Silo max50000, clean CQP20 command, ratio/midpoint choices, and rejection of adjacent/reversed brackets. V1 remains SHA256 `86da8fa74732df1a25cd70f8ce5b4a5fdfc3e24c7810c4c851c20c98a88c83f0`; V2 is `9a3e6b4ce395b1e2801494325a5c6a982c7dbe8ffab0d94dc29174cc10eb3777`.

Ready report pins: KAT `52572083f29e37fef57d0b5030c5d8d7a9a34dd49c79499ee2ef749f9bc0758b`; complete real `06c83ff1ae5bd1f58436de51994b5b5839a45d5ce42ef2484983e92f9f961abf`. Use a fresh output directory and `--cases silo_partial` for the real retune. Root schedules actual encodes serially with the other GPU work.
