# Original source pixels carried through the encoder

D53 qualifies `552d0e7b`, diagnostic binary SHA256
`5f5403da02d918af56068d449f8c660847d28c99b2b4ac87ba6107e7498cac9f`.
Original FGS input now travels directly with its picture to the native fitting
engine. No source-plane files are required in memory mode. This remains a finite
diagnostic; production stays ordinary `cb903a17`, retention and FEL off.

## Implementation and limits

The explicit source-capture option carries immutable unpacked native Y/Cb/Cr
through delayed filter output and NVENC reconstruction. Ordinal, source ID,
timestamp, timebase and geometry must match. Shared ownership prevents source
reuse before consumption. Live source allocations have a separate 512 MiB
maximum; source bytes also count toward the diagnostic output allowance.
Transient download staging, engine-owned clones and other process memory are
outside that live-source budget. Ordinary mode performs no source download.

ABI 2 adds a read-only source/base pair operation. Its memory-source mode rejects
file-source records and mixed push operations; the file path remains supported,
including ABI 1 libraries. Actual reconstructed pixels determine fitted grain.
Read [the configuration contract](MODEL-OUTPUT-TRIAL.md#direct-original-source-transport).

## Qualification

- Fourteen capture/control encodes cover native 8/10-bit sources, scene cuts,
  reordering, motion filtering, 1080p SDR input and UHD HDR. All 4,480 independent
  AOM/dav1d observations match, with grain enabled and disabled. Packet payloads,
  clocks and colour/HDR metadata match the qualified baseline exactly.
- All 89 original and 89 reconstructed captures match independent decoding:
  117,993,984 native samples in each role. The 1080p library derivative is only
  an input-provenance control, not original-media quality evidence. Five GPU
  failure cases reject missing tails, missing FGS and inadequate source/output
  budgets. The initially malformed 1080p test command and its correction are
  retained separately; no completed encode was repeated to hide that error.
- Two further GPU runs fit directly from original 8/10-bit input and live
  reconstruction. Their 32 models, readiness decisions and AV1 payloads match
  the CPU reference. Another 128 independent decoded observations and
  25,165,824 separately synthesized AOM samples are exact. All 96 direct-source
  planes match the independently verified input; four clock/buffer failures
  reject cleanly.
- Independent NumPy measurements pass all 32 declared frame guards and 18
  eight-picture windows. The stricter original full-spatial per-picture test
  still passes **0/32**; these failures are retained. This uses the explicitly
  recorded D42 frame/window policy, not a new relaxation of source admission.
- Eight GPU layout controls match 101,376 samples across planar/interleaved,
  padded 8/10-bit storage. Twelve invalid-code/ownership-budget controls reject.
  The CPU layout test matches 25,740 samples; memory-mode failure controls,
  immutable input/lifetime checks and ABI 1 compatibility also pass.
- Full CPU suite: 214 Python tests in 30 suites and 45 C++ programs.

Finite live fitting takes 5.75/5.21 seconds for the 16-picture 10/8-bit runs,
versus about 2.1 seconds for their capture controls, including container startup.
This expensive reference implementation does not establish production throughput.
All owned pauses were released with the current Tdarr worker limits preserved.
Completed oracle raw data has cleanup receipts; needed source evidence is retained
off root. No experiment is scheduled; reserved qualification footage is unopened.

Exact manifests, source/library/build pins, failed attempts, CPU/GPU commands,
oracle receipts and independent results are in
`roadmap-r3-source-transport-20260923/` under the local evidence root identified
by [the handoff](WORK-TO-PRODUCTION.md). Main reports are `comparison.json`,
`direct-comparison.json`, `direct-sources.json`, `memory-report.json`,
`cpu-report.json` and `direct-encodes.json`.

## Next work

The encoder now has real source and reconstructed-base inputs throughout the
finite model path. It still needs automatic pre-encode fraction selection,
whole-picture source/detail eligibility and source-preserving fallback. A late
model failure rejects the complete experiment; it cannot make an already
compressed partial base into the original source. R3 and R4–R8 remain open.
