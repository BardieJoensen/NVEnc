# Ordinary Tdarr rollout and rollback

The ordinary flow uses the qualified branch binary at the existing `retain=0`
default. It adds the Dolby Vision normalization guard, preserves P7 FEL video,
and uses the tested packet-byte accounting helper for the existing 95%/120%
source-relative savings rules. Its QVBR buckets, sampler, final validator and
audio/subtitle/chapter policy remain unchanged.

Optional bilateral `retain=auto,retain-max=0.1` remains in the separate
[measured pilot](TDARR-PILOT.md). It cannot silently become the ordinary default.
That pilot has an exact measured old-output budget; ordinary jobs do not gain
a second full encode or a source-hash pass. The current 10% pilot budget is
not a blanket policy. Ordinary source-relative saving still does not promise
a maximum increase relative to a hypothetical old-encoder output.

## Build the deployment artifacts

```sh
python3 tools/fgs/build_tdarr_rollout.py \
  --flow current-flow.json --expected-flow-sha256 REVIEWED_FLOW_SHA256 \
  --candidate-image sha256:CANDIDATE_LOCAL_IMAGE_ID \
  --candidate-sha256 CANDIDATE_BINARY_SHA256 \
  --baseline-image sha256:CURRENT_LOCAL_IMAGE_ID --output ordinary-bundle

python3 tools/fgs/prepare_tdarr_plugin_update.py \
  --bundle ordinary-bundle --plugins /path/to/server/Tdarr/Plugins \
  --archive /path/to/server/Tdarr/nodePlugins.Zip --output prepared-plugins
```

Preparation does not change the running installation. The ordinary bundle
contains a production flow retaining the current flow ID, a separate review
flow, the exact old flow, image overrides and all plugin/helper files. The
archive preparation preserves unrelated archived files and backs up every
existing plugin it replaces. A retry or rollback refuses unrelated later edits.

Use the actual flow ID returned by the Tdarr API when inserting a new review
flow: this server's insert operation generates its own ID. Read the document
back and compare the complete flow before assigning it to the isolated library.
Update the existing production flow by its existing document ID.

## Verify before activation

Run the review flow in an isolated real Tdarr server/node with copied short
sources mounted read-only, a separate database, and a dedicated `/fgs-review`
volume. Accepted candidates are copied and hashed outside the transcode cache;
the flow then returns its original library file. Skipped/rejected video returns
the original directly. This review flow does not exercise stream-policy-only
replacement; that policy remains identical to the separately tested original.

Verify the qualified encoder hash, all pinned existing plugins, every new
plugin/helper file, real scheduler completion, the accepted staged artifacts,
and at least one source-retention decision. Preserve failed attempts as evidence.
Rehearse the image, flow and plugin rollback on the isolated stack.

## Activation and rollback

Preserve the existing node pause and worker limits. In this installation the
repair coordinator owns the pause until approved repairs drain; deployment must
not resume ordinary Tdarr work ahead of that coordinator. Wait for no assigned
workers and no active node encoders before stopping the node and server. Keep
the independent repair/audit services and Emby running.

Install the prepared plugin files and archive only with the target containers
stopped:

```sh
python3 tools/fgs/install_tdarr_plugin_update.py \
  --prepared prepared-plugins --server-container tdarr --node-container tdarr-node
```

Apply the candidate image to the **node only**, retaining the pinned server
image, existing mounts, resource limits and other Compose services. Start the
server and node with node assignment held, update the existing flow document,
read it back, and verify the live binary/plugin hashes before restoring the
previous pause state. Persist the image selection in the installation's normal
Compose configuration so a later routine recreate cannot undo the rollout.

For rollback, drain/hold the node again, restore `rollback-flow.json`, stop the
target server/node, install `prepared-plugins` with `--rollback`, and recreate
the node using `rollback-compose.json`. Restore the ordinary Compose image
selection as well. Restart, read back the old flow, verify old binary/plugin
hashes, and preserve the previous pause state. Existing completed library
replacements are not undone by changing the encoder/flow; their repair backups
and receipts remain separate.

Local installation-specific commands and results live under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/production-readiness-20260909`.
Do not treat an artifact's presence as proof it has been activated; consult
the rollout result and the live image/flow hashes.
