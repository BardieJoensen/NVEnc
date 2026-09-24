# Bounded selector plans and exact source association

D63 is complete in `033cd83b`. The finite manual adapter invokes the existing
R1 selector, records its decisions and creates a complete pre-encode schedule.
Missing evidence preserves source. Unsupported component mixtures preserve the
whole frame; an epoch boundary breaks model history, and partial intervals
shorter than eight frames become source intervals before encoding starts.
Original proposals, evaluation counts and preservation reasons remain visible.
This is a mechanism qualification, not automatic real-source admission.

An optional `pre_encode_source_binding` pins layout, timebase, ordinal, source
ID, PTS and each native source plane's SHA256. The encoder verifies its existing
original-source snapshot before returning that frame to NVENC. Hashes use
canonical uint16 little-endian samples at both depths and FFmpeg's existing
SHA implementation. No extra GPU download is needed. Ordinary mode allocates
and hashes nothing new. Earlier unbound explicit diagnostics retain their
behaviour; the new schedule adapter requires a binding.

`retention_schedule_reference.cpp` verifies the supplied original planes and
runs bounded candidate/joint callbacks. It does not infer missing proof from a
successful fit. Accepted constructed plans in this stage explicitly label their
candidate evidence `unit_mechanism_fixture`. The real SDR/HDR development cases
measure source identity but leave unmeasured model/population/detail checks
unmeasured; all 32 pictures preserve source with no fitting context. Neither
the source hashes nor those successful fallbacks prove partial retention quality.

The full CPU suite passes 214 Python tests in 30 suites and 49 C++ programs.
Schedule controls cover all 65,536 binary patterns, 36 component searches,
15 epoch boundaries and terminal identity/evidence failures. Native hashing
matches 24 independent Python hashlib controls plus four invalid-input cases.
The manual adapter passes 14 positive plans and seven negative controls,
including two incomplete-evidence cases that preserve the whole sequence.

Actual qualification includes 18 positive and ten expected-negative GPU runs,
1,056 fresh AOM/dav1d decoded observations and 710,866,944 exact source and
reconstruction samples per role. All 192 constructed model/readiness records
match the previously independently qualified references, including their
recorded strict per-picture failures. Their earlier synthesis-oracle evidence
is reused by exact model, packet and decoded-pixel identity; no fresh oracle
sample count is claimed. Both ordinary development controls remain exact.
Late stale-source failures correctly reject incomplete outputs.

One additional HDR run exposed a trial-reference error: expected hashes came
from muxed packets containing static HDR/HDR10+/DV metadata, while the model
hook receives earlier NVENC packets. The corrected live manifest pins exact
pre-mux packets; CPU replay retains the muxed reference. Runtime hash checking
was not relaxed, no metadata is stripped from encoder output, and final HDR
packet payloads, clocks and metadata remain identical. The rejected attempt
and the boundary mapping are retained. An initial wrong-directory build attempt
was also detected before any trial used it and is marked invalid in the ledger.

Latest diagnostic `build-033cd83b/nvencc`, SHA256
`9a91e94e65498656ce24717e12fcacd179a28a4c3007c9f01b11cbf7d33ce2b2`.
Native engine v7 and model writer v5 are unchanged. Commands, inputs, complete
reports, original failures, pause and cleanup receipts are under
`roadmap-r3-selector-plan-20260923/` in the evidence root from
[the handoff](WORK-TO-PRODUCTION.md). All three owned pauses were released with
current Tdarr limits preserved. Rejected raw witnesses totaling 132,341,760
bytes were retired after recording their hashes; useful positive captures stay.

Continue deriving the candidate proofs from actual source/base/model evidence,
including their exact association and regional/detail vetoes. The schedule
adapter's unit fixtures cannot substitute for that work. R3–R8 remain open;
production stays ordinary `cb903a17`, retention/FEL off, reserved footage
unopened, and no trial starts automatically.
