# Optional detail retention with source-relative savings

This is a separate, unactivated alternative to the
[10% measured-baseline pilot](TDARR-PILOT.md). The measured pilot remains
unchanged. This alternative is being qualified in an isolated review flow;
it is not yet the live library policy.

Complete episode candidates for core `9c1664d4` cost about 20–30% more video
bytes than the current encoder, while still saving at least 46% against their
retained source video. An exact cap relative to the preceding encoder requires
its complete matching encode. The source-savings alternative removes that
baseline requirement and permits larger outputs than the preceding encoder,
provided that the strict source-relative saving and existing validation pass.
It does not solve the grain-model coverage or storage-cost limitations.

Both size paths require at least 5% savings. The comparison baseline is:

```
original primary-video bytes + (candidate file bytes - candidate primary-video bytes)
```

This holds the retained audio, subtitles and container contribution constant;
discarding source tracks cannot disguise video growth. Both paths use 95%,
including the path which formerly permitted 120%. The existing lower bound
also rejects outputs at or below 5% of this baseline. The comparison counts
complete primary-video packets, without an old-encoder encode or source hash
scan. It is a size decision, not a picture-quality score.

The flow uses the qualified `retain=auto,retain-max=0.1` settings in both the
sample and full encode. It keeps the source when an encode fails, a size check
rejects the output, or Dolby Vision FEL cannot be preserved. It does not raise
QVBR or encode a substitute video to satisfy the size limit.

`fgsSourceGuard` checks the source's device, inode, size, modification time and
change time before sampling and again after encoding and the size check. It
hashes `/usr/bin/nvencc` once at preparation, requires the configured qualified
SHA-256, and checks that its filesystem identity remains unchanged. The final
check ties the earlier source identity to the size measurement and verifies the
candidate's identity. Missing preparation, a different build or changed media
returns the original object on the terminal rejection path. These are ordinary
filesystem change checks, not a full source-content hash guarantee.

The existing Dolby Vision guard and final validator follow these checks.
Routine validation retains its existing work budget; exhaustive offline
decodes and HDR correspondence tests are not added to every Tdarr job.

Prepare a new bundle with immutable local image IDs:

```sh
python3 tools/fgs/build_tdarr_source_savings.py \
  --flow current-flow.json --expected-flow-sha256 REVIEWED_FLOW_SHA256 \
  --candidate-image sha256:QUALIFIED_IMAGE_ID \
  --candidate-sha256 QUALIFIED_ENCODER_SHA256 \
  --baseline-image sha256:ROLLBACK_IMAGE_ID \
  --output new-source-savings-bundle
```

The builder writes new files only. `source-savings-review.json` stages a
verified candidate and receipt in the dedicated `/fgs-review` volume and
retains the original. It has no reachable library replacement or notification
nodes. `source-savings-promote.json` includes replacement only after the same
checks; generating it does not activate it. The original flow, image rollback
override and hashes are included.

Install and verify the bundled plugins on both the server and the node image,
including each shared helper. The source guard adds two files to the existing
seven-file fidelity plugin bundle. Verify the actual node files after startup;
placing plugins only on the server is insufficient for the observed runtime.
Before activation, exercise accepted staging, oversized-source retention,
metadata preservation, playback yielding and rollback in the isolated review
flow. Keep the source copies read-only and the review directory outside the
library and transcode cache. The guard evidence remains in job state and logs;
the staging receipt records the accepted source-size measurement.

Tests:

```sh
node --test tests/fgs/test_tdarr_source_guard.js
python3 tests/fgs/test_tdarr_source_savings.py
```

The node tests exercise real temporary-file edits and replacements, changed
encoders, missing preparation, stale measurements and successful completion.
Routing tests reject bypassed guards, inconsistent encoder settings, disabled
checks, failed paths reaching acceptance, and a reintroduced 120% allowance.
