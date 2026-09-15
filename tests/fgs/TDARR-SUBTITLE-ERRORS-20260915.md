# Tdarr subtitle metadata errors, September 15

The eleven errors reported on September 15 are MobLand S01E01–S01E10 and
Horns (2013). All failed the final subtitle metadata comparison. Replacement
was refused and all eleven original files still matched their recorded size
and modification time before retry. No redownload is required.

## Causes and correction

| Scope | Observed change | Correction |
| --- | --- | --- |
| Ten MobLand episodes | First English PGS subtitle changed from default=0 to default=1 | Explicitly preserve each retained subtitle's default flag in the FFmpeg command |
| Horns | Two German PGS tracks were tagged `deu` before the mux and `ger` afterwards | Compare language aliases using the same normalization as the frozen selection policy |

The MobLand job report contains default=0 in the intermediate NVEncC stream
inventory. Its following FFmpeg stream-copy command supplies no disposition
options because the audio policy preserves both soundtracks. FFmpeg then
[automatically selects a default track](https://www.ffmpeg.org/ffmpeg.html#Main-options)
when multiple tracks of a type exist without one. This is a flow remux issue;
the encoded picture does not need a different quality setting.

`applySubtitlePolicy` now writes relative `+default` or `-default` for each
retained subtitle using Tdarr's final output-index placeholder. Relative flags
preserve forced, accessibility and other dispositions. Pruned tracks are not
addressed, and restating these flags does not itself request an extra remux.

`validateTranscodeOutput` now normalizes ISO aliases in audio, video and
subtitle semantic signatures. Distinct languages, missing tracks, codecs,
titles, default/forced/accessibility flags and copied-payload checks remain
distinct. Mandarin and Cantonese are not merged.

The two-file patch is [versioned in this fork](../../tools/fgs/tdarr-subtitle-metadata.patch).
Its paths are relative to the deployed Tdarr `Plugins` directory. The live
deployment remains in `/opt/docker-apps`, whose unrelated working changes were
preserved. This update changes no encoder binary, production flow, quality
settings, worker limits, decode checks, timing tolerances or grain thresholds.

## Qualification and deployment

- 105 checks passed across the existing plugin, language-policy and grain
  suites plus [four focused regressions](tdarr_subtitle_metadata.test.js).
- The focused suite fails on the previous plugins for default preservation and
  language aliases; its distinct-language/metadata negative controls still pass.
- Thirty-second samples from both actual titles went through the deployed
  FFmpeg and MKVToolNix binaries. Both corrected outputs match the expected
  subtitle signatures. All 1,788 compared video/subtitle packets have identical
  payload hashes, sizes, PTS, DTS and durations between old and corrected muxes.
- Server and node plugin hashes were verified after restarting the idle Tdarr
  containers. The existing archive and plugin bytes are available for rollback.
  Production encoder remains `ef5c61fe`, SHA-256
  `d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.
- MobLand S01E07 and Horns were requeued at 09:00 UTC. These full jobs must pass
  the remaining normal validation stages before being called successful.

The old failed job caches had already been removed by Tdarr. Retries therefore
encode from the retained library originals. The finite, manually started
`tdarr-subtitle-retries-20260915.service` admits the other nine MobLand episodes
only after S01E07 completes successfully, and records each completed retry.
It never automatically retries a second failure. It does not enable the
deferred retention campaign or release FEL/source-audit holds.

Read the [live retry status](/opt/docker-apps/logs/tdarr-errors-20260915/retry-status.json)
for completion; a queued or active job is not a successful repair.

## Evidence and rollback

All local evidence is under `/opt/docker-apps/logs/tdarr-errors-20260915`:

| Evidence | File |
| --- | --- |
| Original eleven records, job identities and reports | `errors-before.json`, copied job reports |
| Exact per-track differences | `diagnosis.json` |
| Old/corrected plugin trees | `baseline/`, `candidate/` |
| Regression results | `candidate-tests.log`, `baseline-regression-controls.log` |
| Real media mux controls and observations | `qualify_subtitle_mux.py`, `real-mux-qualification.json`, `*-probe.json` |
| Installation identities and unchanged encoder/flow | `deployment-before.json`, `deployment-install.json`, `deployment-verified.json` |
| Exact plugin and archive rollback artifacts | `plugin-update/` |
| Narrow retry admissions, status and completed reports | `canary-retries.json`, `sibling-retries.json` when admitted, `retry-status.json`, `retry-reports/` |

Rollback uses `tools/fgs/install_tdarr_plugin_update.py --prepared <ledger>/plugin-update
--server-container tdarr --node-container tdarr-node --rollback` after current
jobs drain and both containers stop. Preserve pause ownership and verify node
plugin hashes when restarting. Rollback is available, not requested or performed.

The initial test invocation lacked the staged FlowHelpers link; its log is
retained separately. An initial observer misread active job rows (`end=0`) as
terminal records; that observer exited without admitting siblings. The corrected
observer requires a completed job timestamp. Neither harness issue was a media
or encoder failure.
