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
