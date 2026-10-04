# Filter-kernel evidence, 2026-10-04

Runtime pin: `6e8fa1fb1a2b06e64b8c4a19af392bc5adfe5c5e` on the production line. Later branch commits add documentation only. Binary SHA256: `be7a50a1681fc5aa9a7133533f081d4e3253b2c74bc639605358f69d591ababe`.

Qualification is pending. The CPU and KAT receipts are completed results; timing receipts report CUDA work, not whole-job throughput. Full historical-state identity, matched controls and the full gate have separate requirements. An individual matching campaign cannot override a missing known production state.

`index.json` records source paths and hashes for compact evidence copied from `/tmp/downloads/codex-work/fgs-improvement-20261004/`. Full logs, per-frame/packet hashes, preserved encodes and Nsight SQLite traces remain there. Raw diagnostic media was deleted only after its whole-file and per-frame MD5s were recorded; the original fixture media was never changed. Temporary storage is not a backup and must be retained through review or verified archive transfer.

The helper scripts reproduce the bounded comparisons from pinned binaries and explicit source manifests. They are evidence tools, not production encoder changes. Run the encoder gates from the pinned clone using the recorded harness commit; never build a moving worktree.

The exact temporary-path patch is stored as `scratch-path-only.diff.json`; its `diff` field decodes byte-for-byte to the original unified diff, including significant blank-line context prefixes.
