# Dolby Vision in retained-source repairs

The standalone repair worker is separate from the Tdarr container. Deploying
the new Tdarr image does not update workers already encoding on the host.

`repair_dovi_guard.py` and `repair-worker-dovi.patch` add source admission and
the shared Tdarr output guard to that worker. Profile 7 MEL requires the exact
independently qualified encoder SHA-256, in-stream RPU copy and profile 10.1.
FEL and unknown classifications retain the original library file and source.
The initial 120-picture classification matches Tdarr's policy; it is not a
claim to have classified every RPU in a full film. The normal output guard
checks 16 initial decoded frames, while full decoding, synthesis scanning,
timing, stream metadata and copied-payload checks remain in the repair worker.

The worker config supplies `dovi_tool`, `dovi_tool_sha256`,
`dovi_output_guard` and `dovi_output_guard_sha256`, alongside its existing
encoder/scanner identities. Install the Python helper beside the worker as
`fgs_repair_dovi_guard.py`. The installation-specific patch is based on the
recorded worker revision; review context if applying to a changed worker.

The same patch treats an omitted empty track title as an empty title. Named
titles, languages, dispositions, codec data, attachments and copied media
payloads keep their existing comparisons. A video-only file now has an empty
audio/subtitle hash set: optional FFmpeg maps must not fall back to hashing the
newly encoded video as though it were a copied nonvideo stream.

The real P7 MEL interval passed the complete worker workflow, including full
decode, metadata guard, mux, backup and atomic replacement of a disposable test
library copy. The real FEL source and historical unconverted P7 output were
both rejected. Existing source and library paths were retained during the
negative controls. See the readiness findings and `repair-deployment-v1` under
the local evidence directory.

The deployment uses the host binary path already recognized by the repair
coordinator's Emby-yield policy. New workers read the new config; safe SDR/P8
workers already in progress may finish on the preceding encoder. Do not change
the path without also accounting for that playback-yield policy. Historical
baseline binaries remain separately pinned in the evidence directory. A Tdarr
container rollback and a host repair-worker rollback are separate operations;
do not resume old P7 replay when rolling back a component.
