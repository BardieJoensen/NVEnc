# Production baseline evidence — 2026-10-04

Compact receipts for the production-core rebuild and development-fixture measurements. Full build logs, reports, binary copies, commands, per-frame and per-packet hashes, IVF outputs and profiler traces remain under `/tmp/downloads/codex-work/fgs-improvement-20261004/`; keep that workspace through review. It is temporary storage, not a backup. These receipts contain no source media.

`identity.json` combines completed results from three immutable reports: the three KAT cases completed before the first raw-metadata harness failure, all four real-source cases, and seven additional Lost Tapes runs per arm. It requires exactly five repeats per arm/stage except Lost Tapes, which requires twelve, and compares whole raw-file/pixel/table and IVF/table/decoded-pixel state sets. It retains hashes and original report paths. The failed report remains preserved and is not relabelled successful.

`repeat_identity.py` records exact encoder commands, binary/input SHA256, raw MD5, filmgrn1 MD5, IVF packet/file MD5 and grain-off decoded MD5. It deletes only its own raw intermediate after recording hashes. Raw output is a separate run, not captured encoder input. The earlier three KAT runs used the preserved v1 script (hash in the report); the raw-metadata correction does not alter KAT commands. The fixed script is retained here for reproduction.

`profile_summary.py` parses Nsight SQLite data. Grouped `profile-*.json` files omit verbose schema and individual kernel names from the original reports; sums are unchanged. Host synchronization and device work overlap and cannot be added together. One baseline trace per source is only a speed-target measurement, not a before/after win.

Reproduce the build with the pinned-clone recipe in `tests/fgs/local_gate.sh`, at `aeb14263`, using the Docker image and dependency identities in `pins.json`. The recorded package versions are libass-dev `1:0.17.1-2build1`, libx11-dev `2:1.8.7-1build1`, and libplacebo-dev `6.338.2-2build1`; release mode disables VMAF/libvship. The source tree was cloned locally with tags, detached and checked clean. CPU and quick checks used that immutable clone; production head differs only by the merge report.

The unchanged full gate is not covered by these quick receipts. Its exact Play Dirty original and full-history artifacts remain a separate prerequisite; see the bounded cold-storage search receipt. No release is qualified by this directory.
