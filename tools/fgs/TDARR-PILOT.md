# Measured Tdarr fidelity pilot

This is part of the [unfinished production work](../../tests/fgs/WORK-TO-PRODUCTION.md).
It prepares a separate flow; it does not install or activate anything. The first
bundle was an integration prototype. The Dolby Vision P7 RPU conversion fix now
passes an independent complete-clip regression. The measured real scheduler
trial has passed; the ordinary production rollout is tracked in the readiness findings.

The [ordinary rollout](TDARR-ROLLOUT.md) deliberately keeps the existing default
retention setting while this optional mode remains limited to measured sources.

`tdarr_size_budget.js` has three phases. `select` exits early for unlisted
sources. `prepare` verifies the complete source hash, candidate binary hash,
QVBR setting and measured reference. `check` counts every final primary-video
packet and byte, verifies file identities again, and applies the exact byte cap.
Source aliases are explicit paths for identical copies/imports; they still need
the same full source hash. A title or file size alone never identifies a source.

Rejection returns the original library object on output 2. The generated flow
sends this to a terminal original-file branch. It does not raise QVBR, disable
detail guards, encode a fallback, replace the source, or send a notification.
The usual source-relative 95%/120% rules and final validator still apply. The
source-size plugin uses the shared `tdarr_video_bytes.js` helper, which avoids
unnecessary codec parsing only for the exercised Matroska H.264/HEVC/AV1 cases.
Other containers/codecs keep parsers. This shortcut is never used for timing,
decoded-picture or HDR correspondence checks.

The reference budget covers **primary-video packet bytes**. This excludes audio,
subtitles and container overhead so track pruning cannot mask video growth.
The older offline admission instead compares whole video-only container bytes;
the two measurements are intentionally named separately.

Build a reference using complete paired-comparison reports:

```sh
python3 tests/fgs/build_tdarr_budget_reference.py \
  --config reference-config.json --output measured-reference.json
```

The config contains `expected_candidate_sha256`, decimal-string
`maximum_extra_percent` (the trial uses `"10"`), and `cases`, each containing
`report`, `case`, and optional `source_aliases`. The report must pass the existing
complete paired-trial checks. The original full baseline artifact must still
match its recorded hash, frame count and size.

Prepare an immutable bundle:

```sh
python3 tools/fgs/build_tdarr_pilot.py \
  --flow current-flow.json --expected-flow-sha256 REVIEWED_FLOW_SHA256 \
  --reference measured-reference.json \
  --candidate-image sha256:IMMUTABLE_LOCAL_IMAGE_ID --output new-bundle
```

`pilot-review.json` has no reachable library replacement or notification nodes.
Its terminal stages the accepted candidate and a hash-verified receipt under
`/fgs-review`, then returns the original library object. Mount a dedicated review
volume there, outside both the media library and Tdarr transcode cache. Tdarr
rejects jobs that end on a working file left in that cache.
`pilot-promote.json` retains promotion only after verified preparation, successful
NVEnc completion, both size gates, the DV normalization guard and final validator. Graph checks reject
bypasses, ambiguous routes and cycles. Both reject FEL conversion and fallback
video encodes. The bundle includes the plugin, reference, original flow and a
hash manifest. Install the complete plugin directories, including shared helper
files, on both the server and the node. The runtime image also carries these
plugins: a server-side copy alone did not supply them through the observed node
plugin download. Verify hashes after node startup. Runtime deployment and
server/node synchronization remain separate operations.

An exact old-encoder cap requires its complete measured output. Existing
references avoid a second encode for the same source; unlisted inputs skip the
pilot. The trial's 10% setting is not a blanket production storage policy. Do not
replace the ordinary whole-library flow with this small-source manifest.

Tests:

```sh
node --test tests/fgs/test_tdarr_size_budget.js
node --test tests/fgs/test_tdarr_dovi_guard.js tests/fgs/test_tdarr_video_bytes.js tests/fgs/test_tdarr_stage_review.js
python3 tests/fgs/test_tdarr_pilot.py
```

The recorded real full-episode trial accepted a 1,007,395,242-byte video against
its 991,509,444-byte baseline and 1,090,660,388-byte limit. The same real candidate
was rejected with a zero-extra-byte control. The fresh full encode and subsequent
audio/subtitle/chapter processing preserved the previously validated candidate's
complete video payload, codec private data and timeline. Neither test replaced
a library file.
