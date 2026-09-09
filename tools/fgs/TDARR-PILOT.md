# Measured Tdarr fidelity pilot

This is part of the [unfinished production work](../../tests/fgs/WORK-TO-PRODUCTION.md).
It prepares a separate flow; it does not install or activate anything. The first
bundle is an integration prototype. The newly demonstrated Dolby Vision P7 RPU
conversion issue must be resolved and the generated flow exercised before rollout.

`tdarr_size_budget.js` has three phases. `select` exits early for unlisted
sources. `prepare` verifies the complete source hash, candidate binary hash,
QVBR setting and measured reference. `check` counts every final primary-video
packet and byte, verifies file identities again, and applies the exact byte cap.
Source aliases are explicit paths for identical copies/imports; they still need
the same full source hash. A title or file size alone never identifies a source.

Rejection returns the original library object on output 2. The generated flow
sends this to a terminal original-file branch. It does not raise QVBR, disable
detail guards, encode a fallback, replace the source, or send a notification.
The usual source-relative 95%/120% size gate and final validator still apply.

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
`pilot-promote.json` retains promotion only after verified preparation, successful
NVEnc completion, both size gates and the final validator. Graph checks reject
bypasses, ambiguous routes and cycles. Both reject FEL conversion and fallback
video encodes. The bundle includes the plugin, reference, original flow and a
hash manifest. Runtime deployment and server/node plugin synchronization remain
separate operations.

An exact old-encoder cap requires its complete measured output. Existing
references avoid a second encode for the same source; unlisted inputs skip the
pilot. The trial's 10% setting is not a blanket production storage policy. Do not
replace the ordinary whole-library flow with this small-source manifest.

Tests:

```sh
node --test tests/fgs/test_tdarr_size_budget.js
python3 tests/fgs/test_tdarr_pilot.py
```

The recorded real full-episode trial accepted a 1,007,395,242-byte video against
its 991,509,444-byte baseline and 1,090,660,388-byte limit. The same real candidate
was rejected with a zero-extra-byte control. The fresh full encode and subsequent
audio/subtitle/chapter processing preserved the previously validated candidate's
complete video payload, codec private data and timeline. Neither test replaced
a library file.
