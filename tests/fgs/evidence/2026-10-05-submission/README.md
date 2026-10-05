# Submission identity evidence, 2026-10-05

The supported trace shows identical repeated NVENC inputs between production and the kernel candidate on five original-source fixtures and all 21 KAT fixtures. Production's Lost Tapes and Gentlemen runs can produce different IVFs from those identical inputs. The user-authorized candidate identity rule therefore uses the traces, with IVF hashes informational.

`trace-evidence.tar.gz` (1,104,245 bytes, SHA256 `9e0154f8ac842c805a7d4a7d57c23b4e85ab56a45c9dc214a82bab1e4bf08b00`) contains all 113 exact schema-2 trace files, compact complete run receipts with exact commands/pins/output hashes, build receipts, parser controls and the pooled instrumentation comparison. `MANIFEST.json` binds every archived file by size and SHA256. The original full-report hashes are retained; only redundant inline copies of trace rows were removed from the compact reports. No source, raw media or encoded video is embedded.

Extract into a fresh SSD scratch directory, verify the manifest, and use `tests/fgs/compare_submission_traces.py` with the expected fixture geometry/frame count and at least two production/candidate traces. Encode/decode completion is recorded in the run receipts. The initial three-repeat instrumentation batch retains its strict Gentlemen finite-subset failure; the already-required extra production repeats supply both known states in the pooled deployed-versus-traced comparison. No new state-hunting runs or rewritten failure receipts were used.

Runtime pins: production diagnostic `1184bcb5` / binary `94301bda…`; candidate `a1ac278a` / binary `d1de4e49…`; deployed comparator `aeb14263` / binary `c6cbd528…`. Full release-gate and throughput qualification are separate evidence, not implied by this archive.
