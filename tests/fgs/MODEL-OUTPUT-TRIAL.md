# Finite encoder model-output trial

`--film-grain-recon-probe manifest.json` is capture-only by default. An explicit
`model_output` object enables the finite reconstructed-model output experiment.
It is disabled unless supplied and is not an automatic-retention setting.

The outer reconstruction manifest must capture every ordinal from zero through
N−1, where N is 1–16, and meet the existing native layout/device/host budgets.
Its `model_output` object has:

| Field | Contract |
| --- | --- |
| `schema` | Integer 1 |
| `library` | Absolute path to the private ABI-1 complete-model library with packet-identity/SHA reporting |
| `packets` | N entries in actual receive order, each with signed integer encoder `pts` and `sha256` array of one or two exact accepted original packet hashes |
| `models` | N entries by encoded-input/display ordinal: a complete [model](MODEL-OVERRIDE.md) or explicit `null` to preserve the original encoded grain state |
| `ready_after` | Optional receive ordinal 0–N−1 before which no decisions are released; default 0 |
| `max_pending_packets` | Optional bound 1–64, default 64 |
| `max_pending_bytes` | Optional compressed-payload bound 1–268435456, default 268435456 |

Clocks must strictly increase and cannot use the missing-timestamp sentinel.
Two hashes allow a separately proven container-copy temporal delimiter variant;
both hashes are explicit. No hash wildcard, unbound model or missing picture is
accepted. The trial cannot be combined with the seed-correction option.

Models are precomputed from the pinned encoded base. Their source, fitting,
quality and oracle evidence must be retained with the manifest. Successful
parsing or output alone does not qualify them. Keeping an original encoded grain
model is not a source fallback after the input has already been partially
retained and compressed.

The hook receives only owned bitstreams after reconstruction has matched its
submitted ordinal and PTS. It holds original packet/metadata ownership until
both future reconstructions and model decisions are available, serializes in
order, and verifies completion at the common encoder completion boundary.
Failures can leave an incomplete diagnostic output file; treat any nonzero exit
or incomplete status as a rejected experiment. Nothing replaces a library input.

The capture directory's `model-output.json` records completion, failure, pending
and peak payload counts, and parser/writer counts. Payload limits exclude parser
state, independent bitstream tokens, returned packets and reconstruction surfaces;
they are not a total-process RAM claim. Qualify actual peak memory separately.

The [current qualification findings](FINDINGS-2026-09-23-CONTINUOUS-OUTPUT.md)
record completed CPU controls and the qualified finite live encoder trial.

## Native fitting extension

An alternative `native_model_output` object connects the bounded reference
engine to actual reconstruction callbacks. It is mutually exclusive with
`model_output`, requires 8–16 complete consecutive captures, and is diagnostic
only. Reference CPU synthesis remains outside ordinary production analysis.

It retains `schema`, `library`, `packets` and the two pending-buffer limits from
the table above. It rejects supplied `models` and `ready_after`. Instead provide
an absolute `engine_library` and an `engine` object:

- `schema: 1`; exact `width`, `height`, `depth`, `matrix`, `frame_count`;
  dimensions divisible by 64, native depth 8/10, matrix 1/9.
- `shift` 6–9, `grain_shift` 0–3, and 1–32 distinct nondegenerate
  `training_seeds` for finite template-power calibration.
- `sources`: one entry per ordinal, containing `ordinal`, matching encoder
  `pts`, and three `planes` in Y/Cb/Cr order. Each plane has an absolute `path`
  and exact lowercase `sha256`; files contain unpacked native uint16 codes.
- Optional `max_native_bytes`, at most 512 MiB, covering eight source/base
  pairs. This counts those buffers, not all engine/AOM/process memory.

The engine verifies source length/hash before fitting against the live native
reconstruction. Shapes use the first eight training halves; strengths and seeds
are selected with the bounded diagnostic policy. Independent halves and sliding
windows can reject the entire output. Model readiness delays packet release,
including hidden references; no missing decision becomes an original model.
Status is written to `native-model-output.json` beside the reconstruction report.
Source identity/provenance remains the experiment author's responsibility;
matching a supplied hash is not evidence that a region contains only grain.

This still uses explicitly supplied original-source planes and pre-encode
retained fractions. It does not establish automatic retention, whole-picture
eligibility, HDR/perceptual quality or production speed. The private native ABI
and its completed finite CPU/GPU qualification are tracked by
`roadmap-r3-live-fitting-20260923` and the
[live-fitting findings](FINDINGS-2026-09-23-LIVE-FITTING.md).

## Direct original-source transport

The outer reconstruction manifest can request `capture_source: true` with
`--film-grain auto`. For the same explicit ordinals, the filter carries immutable
native Y/Cb/Cr originals alongside its per-picture result. This is the input to
the FGS filter, after any preceding crop/resize/filter operations. It is not the
partially retained output or the older luma-only history. Ordinal, source ID,
timestamp, timebase and layout must match the encoder submission exactly.
Missing or mismatched sources reject the diagnostic.

`max_source_bytes` bounds live native source allocations (default/maximum
512 MiB). It excludes transient per-plane download staging, the native fitting
engine's separately bounded clones, encoder surfaces and other process memory.
The existing `max_output_bytes` must also cover three native uint16 source planes
per requested picture. Source captures have `frame-N-source.json` and three
`frame-N-source-C.raw` files. Ordinary mode does not allocate or download sources.

To feed those originals directly into fitting, use `engine.source_mode: "memory"`
and ABI 2. Source records keep ordinal/PTS but omit `planes`; file and direct modes
cannot be mixed. Capture-only mode supports even 1080p/UHD dimensions; fitting
still requires tile-aligned dimensions. The source-transport qualification is
tracked in `roadmap-r3-source-transport-20260923`. Pre-encode fractions and source
eligibility remain separate work.
