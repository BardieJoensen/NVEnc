# Continuous models and bounded output integration

D42 is complete. On two 16-picture constructive controls (native 10-bit and
8-bit SDR promoted to 10-bit), all 32 pictures selected a model within four
declared seeds. The shape was fitted once on the first eight training frames;
per-picture strength and mean protections and all eighteen sliding eight-frame
comparisons passed. Selection took 19.83 seconds of offline CPU work. These are
development controls, not unseen-title qualification or an encoder speed claim.

Actual serialized output agrees exactly with the independently synthesized
oracle on 25,165,824 native samples. AOM and dav1d agree in both grain modes;
all underlying decoded base pictures, colour metadata and clocks are preserved.
This adds 128 fresh decoded observations to the preceding 128 capture/control
observations. The output grows by 1,426 bytes per control from complete model
headers; it does not measure source-to-retained-base compression cost.

The probe build `c0c20d79` independently validates every receive ordinal, input
identity and reconstruction. Its packet payloads, clocks and metadata match the
previous qualified build. Replaying that actual callback order binds 46
coded/displayed headers; up to six packets await future reconstructions. The
offline eight-frame fit has additional readiness requirements, so six packets
is not a complete model-selection memory estimate. Tdarr's owned pause was
released with the current worker limits preserved.

The single-picture full-spatial score remains recorded as failing on these
selections. This trial uses the explicit D40/D41 measurement investigation:
individual protections plus pooled colour shape. It neither replaces R1's
contract nor admits previously unsupported real populations.

## Bounded runtime output

`NVEncFilmGrainModelBuffer.h` separates reconstruction availability from model
readiness. Independent parser contexts observe the original stream and write
the delayed stream. The FIFO owns original packet bytes and caller metadata;
only the front packet can be released, after every needed reconstruction and
policy decision is available. Pending decisions cannot silently become original
models. A policy rejection or unfinished decision fails the experiment.

The buffer binds each write to its original packet SHA-256, timestamp, coded
picture, order hint and original grain state. The writer maintains original and
changed reference state, including materializing an unselected model whose
original reference was modified. Limits cover packets, bytes and pending model
requests. Independent instances own independent parser/reference state.

D45's CPU integration passes 29 positive modes on nine existing independently
decoded goldens, including no-op, eight-picture delayed decisions, a sixteen-
picture delay and exact original packet hashes. Packet bytes and metadata
tokens match; a provider called before its reconstruction would fail the test.
Sixteen negative controls fail without publishing completed output: missing
decisions, callback/clock errors, rejected/invalid models, packet/byte budgets,
missing future reconstruction, incompatible observation reports, wrong source
packet and calls after finish. These reuse qualified golden bytes and add no
decoder counts. Manifest tests reject 24 invalid finite-trial configurations.

An explicit `model_output` extension to the reconstruction-probe manifest now
connects the FIFO to the encoder output path. It supplies at most sixteen models,
all picture captures, expected original packet hashes and exact encoder PTS.
This is a finite integration trial with precomputed models. It is not automatic
model admission, and ordinary capture-only/option-off paths do not invoke it.
Seed correction cannot be combined with this trial. Decoder-reconstruction,
stream, completion and owned packet lifetime checks fail the complete encode
on error; the original input is not overwritten.

The pipeline packet pool must not outlive its owner through a deferred shared
pointer. The hook transfers the complete bitstream POD (including side data)
into independently owned storage before buffering. Payload replacement leaves
the packet's clocks, flags, index, duration and other metadata intact.

The new live hook still requires a pinned encoder build, actual positive and
failure runs, and independent decoded comparisons. Automatic source selection,
coverage, live fitting, temporal qualification and R4–R8 remain open. Production
stays ordinary `cb903a17`, retention/FEL off; reserved footage remains unopened.

Local evidence under the current handoff root:

- `roadmap-r3-continuous-model-20260923`: manifests, capture comparisons,
  selection, actual serialization and pause receipt. An initial serialization
  harness field-name mistake is retained separately; corrected results above.
- `roadmap-r3-model-buffer-20260923/v2/report.json`: final buffer integration.
- `roadmap-r3-model-buffer-20260923`: builds, configuration tests and CPU log.
