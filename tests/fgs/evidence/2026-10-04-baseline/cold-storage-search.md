# Play Dirty amplitude-gate archive search — 2026-10-04

No recovery candidate was found. The newer HDD offload exists, and the old scratch path already resolves into it, but the three pinned videos remain absent there and in the separate evidence archive. This is a bounded search result, not proof that no copy exists elsewhere.

The exact required identities are:

| Role / filename | Bytes | Expected SHA-256 |
| --- | ---: | --- |
| Original: `Play.Dirty.2025.REPACK.1080p.AMZN.WEB-DL.DDP5.1.Atmos.H.264-FLUX.mkv` | 8,667,928,469 | `d4a348ec7afc3dd22a66a492f2c804a49392ba8de1afc5aa244c548f4e15934d` |
| Negative: `city-trial/31f295cbb640d53811d6/video.mkv` | 2,172,225,990 | `6ce321ee4f2f5c5a746fb1fa58f8abcc4e9636eb60e921a31a33be8b3483819d` |
| Plain reference: `city-plain-reference/video.mkv` | 2,431,217,088 | `f52864a2b19de2b221babf465c2a5437437552066c408a208f7e17d07b965a6b` |
| Historical candidate: `source-variance/training-v7/extended/full/play-dirty/video.mkv` | 2,182,221,927 | `2a7c1f11efb27f387dcda4593de1d830f2e9bfdb86abfcbb16c8ffc7890b3802` |

Sizes and hashes come from surviving historical JSON reports; no media was read to derive them.

`/tmp/downloads/fgs-full-temporal-audit-20260912` points to `/media/merged-storage/work-archive/nvme-offload-20261004/fgs-full-temporal-audit-20260912`. Beneath `followup-20260916`, the negative directory contains runtime JSON, the plain-reference directory is empty, and the old-candidate directory contains runtime JSON. Their `video.mkv` files are absent. The corresponding `/media/storage1/tdarr-audit-evidence/full-temporal-audit-20260912/followup-20260916/` paths also lack the videos. The mounted mergerfs pool joins `/media/storage` and `/media/storage1`; these are not dangling paths caused by an absent pool mount.

The completed October 4 offload scan checked **244,557 files in 19,100 directories** for all four exact byte sizes: zero matches, zero errors, and no compressed archive larger than 1 GiB. It excluded Git metadata, LLM models and reserved/corpus names; no reserved/corpus directory was encountered. The September 28 docker-apps and home migration inventories also contain no matching media. Those archives are directory copies that preserved symlinks to separate evidence storage, not hidden compressed copies of their targets.

A separate physical evidence filename search stopped at its 180-second bound after **175,459 file entries and 34,566 directories**, before finishing `/media/storage1/tdarr-audit-evidence`; it is explicitly incomplete. Formal cold-storage filenames and recorded migration inventories were checked separately. Full paths, exclusion rules and provenance are in [the JSON receipt](cold-storage-search.json). Raw shell logs were not persisted; the receipt records the returned command results without claiming otherwise.

This work read metadata and existing reports only. No media hash, probe, decode, extraction, archive change, torrent operation or library action occurred. The exact-source prerequisite remains unresolved.
