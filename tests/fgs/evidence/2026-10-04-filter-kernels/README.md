# Filter-kernel evidence, 2026-10-04

Runtime pin: `6e8fa1fb1a2b06e64b8c4a19af392bc5adfe5c5e` on the production line. Later branch commits add documentation only. Binary SHA256: `be7a50a1681fc5aa9a7133533f081d4e3253b2c74bc639605358f69d591ababe`.

The candidate is not qualified. CPU tests and all 21 KAT identity cases pass. The 26-case aggregate still lacks two known production IVF/decoded states; no candidate-only state was observed. All 26 comparisons have plain controls verified against every compatible known FGS state rate; see `plain-control-summary.md`. The selected fifteen release stages pass 22 checks, while the actual `--full` command stops at missing-input preflight. Timing receipts report CUDA work, not whole-job throughput. These are separate requirements: matching a fresh campaign or passing the partial gate cannot override the missing known states or full-history gate.

`index.json` records source paths and hashes for compact evidence copied from `/tmp/downloads/codex-work/fgs-improvement-20261004/`. Full logs, per-frame/packet hashes, preserved encodes and Nsight SQLite traces remain there. Raw diagnostic media was deleted only after its whole-file and per-frame MD5s were recorded; the original fixture media was never changed. Temporary storage is not a backup and must be retained through review or verified archive transfer.

The helper scripts reproduce the bounded comparisons from pinned binaries and explicit source manifests. They are evidence tools, not production encoder changes. Run the encoder gates from the pinned clone using the recorded harness commit; never build a moving worktree.

The exact temporary-path patch is stored as `scratch-path-only.diff.json`; its `diff` field decodes byte-for-byte to the original unified diff, including significant blank-line context prefixes.
