# Finite native fitting in the encoder

D52 qualifies diagnostic implementation `1c353dd7`. Its encoder is
`build-1c353dd7/nvencc`, SHA256
`4960cee155f08a54842e22ede451c485cc0d561d1d91cec62fca937e9135feee`.
This is not deployed. Production remains ordinary `cb903a17`, retention/FEL off.

## Implementation

The explicit `native_model_output` extension connects actual NVENC reconstructed
pictures to the finite native engine through eight private ABI functions.
Source plane length, SHA256, ordinal and timestamp are checked before fitting.
Native NV12/P010 reconstruction is normalized without modifying the input.
Shapes use the first eight training halves; bounded strengths/seed choices,
independent halves and sliding windows determine model readiness. The existing
owned-packet FIFO waits for both reconstruction and model readiness. Missing,
failed or incomplete decisions reject the experiment; they never silently use
the original encoded model after partial retention.

The private library hides its pinned AOM and FFmpeg utility symbols. Independent
contexts own their state. Ordinary mode performs no reference fitting.
See [configuration and lifecycle](MODEL-OUTPUT-TRIAL.md#native-fitting-extension).

## Qualification

- Ten positive GPU encodes and six expected failures complete. Both 16-picture
  live-fitted streams match the precomputed reference packet for packet: all
  32 models, seeds and readiness decisions are exact. Peak FIFO size is 13
  packets. Wrong source/hash/library/packet, insufficient budget and early end
  reject. Early end reaches a changed-packet hash first; the CPU bridge provides
  the independent missing-tail lifecycle check.
- Fresh AOM and dav1d checks cover 2,432 decoded observations, grain on and off.
  All 101 captured reconstructions match, covering 118,831,104 native samples.
  Fitted output matches 50,331,648 oracle samples. Clocks and colour metadata
  are exact. The NV12 reference/reordering controls and UHD HDR ordinary/capture
  controls preserve the earlier qualified outputs; no HDR model replacement
  is claimed.
- The exact encoder-facing CPU bridge passes both positive sequences and ten
  negative cases. Fourteen ABI failure controls and twelve invalid configuration
  controls pass. Four independent contexts, two concurrent, preserve 1,024 model
  queries and all 96 shared native plane allocations. Finish is idempotent;
  subsequent input fails closed.
- Full CPU suite: 214 Python tests in 30 suites plus 44 C++ programs.

Finite native fitting takes 5.75/5.74 seconds for the two 16-picture container
runs, versus 2.11 seconds with supplied models. These include container startup
and expensive reference synthesis; they are not production throughput estimates.

Exact commands, manifests, build/library pins, failure logs and independent
comparisons are in `roadmap-r3-live-fitting-20260923/` under the local evidence
root named in [the handoff](WORK-TO-PRODUCTION.md). Both owned Tdarr pauses were
released with current worker limits preserved. Reserved footage is unopened;
no experiment is scheduled or automatically restarted.

## Remaining integration

Original sources and pre-encode retained fractions are still explicitly
supplied. Next is original-source transport through the encoder, followed by
automatic pre-encode fraction selection and source-preserving failure behaviour.
Passing a moment/model diagnostic does not establish source eligibility. Native
engine dimensions are still divisible by 64; other borders need qualification.
R3 whole-picture support and R4–R8 quality, transitions, bytes, speed and canary
remain open. This checkpoint does not complete automatic retention.
