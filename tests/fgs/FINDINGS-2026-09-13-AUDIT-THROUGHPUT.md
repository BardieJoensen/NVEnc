# Audit throughput and source retention — September 13

The user requested ordinary Tdarr workers after the existing repair queue,
and a faster library audit before qbitmanager removes needed originals.
Production encoder `ef5c61fe` is unchanged by this work. Optional retention
trials remain deferred; this change starts no encoder experiment or download.

## Tdarr handoff

The existing repair coordinator already resumes `NVENC_Node` after the ready
queue and active repair slots have remained empty for 300 seconds. Emby
playback ownership still takes precedence. Verified worker limits are two
GPU transcodes and two CPU health checks; the repair currently owns the node
pause. The library audit does not own that pause.

The live flow and its current export agree: an existing AV1 video routes to
the audio/subtitle policy check. Compliant files end without encoding; files
requiring stream policy changes take the stream-copy path. Clearing already
compliant queue entries itself creates little disk space. Space recovery
comes from remaining eligible conversions and releasing retained originals
and backups when their dependent reviews are resolved.

The flow export had already changed at 07:00 UTC, before this task, from the
September 12 handoff hash. That pre-existing state is recorded separately in
`tdarr-flow-observation.json`; this work does not change the flow or silently
replace the historical qualification pin.

## Faster audit, same measurements

[`parallel_library_audit.py`](../../tools/fgs/parallel_library_audit.py) is a
finite scheduler around a separately pinned measurement directory. It uses
the original `inspect_file` function and its original binary/wrapper/source
hashes, so valid completed measurements remain reusable. It preserves the
same output directory and every selected frame/pixel check.

- Two independent files at a time; duplicate keys/versions are rejected.
- Original source cleanup deadlines determine order after completed-result
  revalidation. Library identities and installation timestamps are preserved.
- The coordinator alone publishes status. Resource or scheduler failures keep
  unmeasured files pending. A stop drains active files before leaving the rest
  pending. A completed measurement remains distinct from a quality verdict.
- CPU quota is 600% (six logical CPU equivalents on the 20-thread host),
  memory limit 7000 MiB, CPU nice 15, disk best-effort priority 7.
- All decoding and measurements remain on the CPU. No new GPU load or routine
  Tdarr validation stage is introduced.

The new manually started unit is
`fgs-full-decoded-audit-parallel-20260913.service`. It replaces
`fgs-full-decoded-audit-v5-20260912.service` and continues writing
`decoded-v5/status.json`. The original header unit remains
`fgs-full-temporal-audit-20260912.service`. Later replacements still require
the documented catch-up checks against their final installed identities.

Eight scheduler tests pass: bounded parallel execution, exactly-once file
admission, storage pause, unexpected worker error, wrong result identity,
draining stop, missing header coverage, and ordering/duplicate rejection.
Two real parallel source windows produce byte-identical measurement CSVs and
identical decoded/source summaries compared with the saved sequential
results. Repeating that run reuses the results without changing report bytes.
The qualified v5 decoder and measurement helpers were not modified.

An initial one-worker priority trial shortened a nearby file measurement to
about two minutes from the earlier four-to-five-minute examples. File mix
varies, and scheduler startup rechecks cached results; use the saved timing
observations for a fresh ETA rather than extrapolating cached or superseded
results as newly measured files.

## Scoped original retention

The current source inventory found 2,138 matching source paths in 378
torrents, covering 1,912 library keys. Normal cleanup applied to 320 of these
torrents, with an earliest recorded deadline approximately 28 hours away.
The remaining 58 have no matching cleanup rule. Four older recorded source
paths are missing and eight existing source paths are outside the matched
torrent set; these remain explicit coverage distinctions.

Only those 320 torrents received `fgs-audit-hold-20260913`. The new qbitmanager
share-limit group `fgs-audit-hold` has priority 4.5, that required tag,
`cleanup: false`, unlimited ratio/seeding duration and native action `Stop`.
The live per-torrent ratio, seeding and inactive-seeding limits were cleared,
and all 320 tags/limits were read back and verified. qbitmanager loads config
again for scheduled runs. Its installed rule classifier verified all 620
torrents: the 320 targets enter the hold, while the other 300 retain their
previous rule assignment. Normal seeding and unrelated cleanup continue.

The held torrents list about 5.71 TiB of logical payload, including any
cross-seed duplicates; this is not a unique physical-storage estimate. The
hold makes no media copies, but it delays reclaiming originals through expiry.
This specifically protects against seeding/activity share-limit cleanup;
it is not a guarantee against every possible deletion mechanism.

Release holds in reviewed batches. For each torrent, account for every
dependent library key, use the final installed file version, finish any
required repeat repair and preserve unresolved source witnesses. Remove only
the tag this task added when those dependencies are resolved; the next normal
manager run restores current ordinary policy. Do not equate `measured` or a
raw threshold with permission to release an original. No automatic expiry or
blanket release was installed.

## Local evidence and resumption

All paths below are relative to
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/acceleration-20260913`.

| Record | Purpose |
| --- | --- |
| `README.md` | Current operation, source hold and release instructions |
| `source-retention-inventory.json`, `source-retention-plan.json` | Exact source/torrent mapping, original policies and finite hold list |
| `source-retention-applied.json` | Applied batches and verified live tags/limits |
| `source-coverage-gaps.json` | Missing and untracked source distinctions |
| `audit-priorities.json` | Original cleanup deadlines, without changing source provenance |
| `parallel-qualification.json`, `parallel-smoke/` | Independent equality and real completed-result reuse |
| `parallel-rollout.json`, `decoded-v5-before-parallel.json` | Frozen scheduler/measurement pins, command and prior checkpoint |
| `audit-rate-before.json`, `priority-trial-applied.json` | Original rate and reversible one-worker priority trial |
| `runtime-verification.json`, `tdarr-flow-observation.json` | Deployed tools, handoff and pre-existing flow state |

The private before/candidate qbitmanager config copies are mode 0600 and
remain local. Preserve unrelated flow exports, maintenance notes and other
working-tree changes. The full library audit and visual review remain open.
