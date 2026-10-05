# Submitted pictures and repeat variability — 2026-10-05

Production produced two different AV1 outputs from exactly the same 240 submitted pictures and grain-parameter records on both Lost Tapes and Gentlemen. The difference is downstream of the FGS input boundary, inside NVENC or its driver. This gives future FGS comparisons a useful identity test: compare stable picture/grain traces; treat IVF and decoded hashes as information, not as the candidate admission rule. No encoder-output correction is proposed, and the driver investigation stops here.

Production trace core is `1184bcb5`, built from a pinned clone; binary SHA256 is `94301bda67d0594cacbcb4546890757be896018a0a4c5000a23702a379983d50`. The deployed comparator remains `aeb14263`, binary `c6cbd528…`. Candidate runtime is `a1ac278a`, binary `d1de4e49…`; the only production-trace/candidate runtime difference is the film-grain CUDA kernel file.

| Lost Tapes repeat | IVF MD5 | Decoded-pixel MD5 | Full submitted sequence SHA256 |
| --- | --- | --- | --- |
| 1 | `234dbaecbf54c26b0b361abae33abfbb` | `d0246b24d4fbbdebdfc416d5fb9fdefe` | `b3ea430b88473dba524c6eb1dff1d3f47cec54dbbafc93f1b5521cdbc0c68408` |
| 2 | `ce0413d0300f5a9775d6352c56d76aa6` | `a0af3be3237f0395e31d6f6496266d80` | Same |
| 3 | Same as repeat 1 | Same as repeat 1 | Same |

The trace records full pitch, visible Y/UV and padding separately, exact SDK grain-object bytes, all grain fields and picture flags. Metadata is copied before submission; the same immutable owned input allocation is read after successful output completion and unmap, before reuse. Pairing uses buffer identity rather than reordered packet timestamps. Schema 2 distinguishes these capture points; see [the contract](SUBMISSION-TRACE-20261005.md).

Raw-base and filmgrn1 hashes match on Lost Tapes, Gentlemen and 4K PQ Taxi. Across the three instrumentation repeats plus two production repeats already required for candidate identity, production tracing reproduces both known IVF states on Lost Tapes and Gentlemen, and Taxi's same observed state, matching deployed production. All five production trace sequences per title are stable. These are the same commands, source pins and production trace binary; no additional state-hunting runs were made.

The initial three-arm instrumentation batch remains recorded with a failed strict state-set verdict for Gentlemen: its first three enabled captures showed only the common state, as did the supplemental capture-off build. The next two production captures exposed both states. The pooled deployed-versus-enabled comparison meets the requested observed-set check without changing the initial receipt or making an exhaustive-state/frequency claim; the capture-off build's finite subset is reported separately.

The kernel candidate also passes the new identity rule on all five real-source fixtures (Lost Tapes, Gentlemen, Amphibia, partial-width Silo and 4K PQ Taxi), and all 21 KAT fixtures, with two repeats per binary. Full-pitch pixels and exact grain objects match in every frame. Candidate IVF sets may differ from the finite production sample and are informational, exactly as the user specified.
The first two diagnostic revisions accessed a mapped surface, contrary to the SDK contract, and are excluded from supported qualification. Their receipts remain preserved. The corrected trace adds no capture, allocation, synchronization or hashing with its environment variable unset; there are two disabled pointer checks per picture. Capture-enabled timing is not a throughput measurement.

Evidence: `/tmp/downloads/codex-work/fgs-submission-20261005/reports/nvenc-variation-traced-pair.json` , `reports/instrumentation-unmapped-pooled.json` and `reports/unmapped-identity-summary.json`, including exact commands, counts, binary/source pins and per-frame receipts. Full-gate qualification and throughput remain separate checks.

The portable [trace comparator](compare_submission_traces.py) and [compressed evidence archive](evidence/2026-10-05-submission/README.md) are committed with this branch, so the identity receipts do not depend solely on temporary scratch.
