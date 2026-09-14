# Dated FEL reconstruction harness

These scripts reproduce the local September 14 diagnostic work described in
[the report](../FEL-RECONSTRUCTION-20260914.md). They are an experiment snapshot,
not a production dependency or a general-purpose public encoder integration.
Nothing here is scheduled or invoked by CI. Do not invoke GPU/operational
scripts merely to read the results.

The ledger is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-reconstruction-trial-20260914`.
Its `scratch` link locates the prepared inputs, dependency sources/builds,
outputs and full logs. Scripts deliberately refer to this dated ledger and
refuse many existing output paths. For a new experiment, create a new scratch
directory/ledger and update the dated constants deliberately; do not overwrite
the evidence. Do not run `prepare_clips.py` against replaced source identities.

## Dependencies and build provenance

The disposable CPU container used image
`nvenc-fgs-build:cuda13.3-deps`, ID
`sha256:4a1674c2522b5f9c675e1f0a50080b9023379cdf17ea8a7d3bbdeb5a571c6616`,
four CPUs, 6 GiB memory, no swap, no GPU, and no library mounts. Trial scratch
was `/trial`; host `/usr/local` was mounted read-only for the existing static
FFmpeg development installation. System packages were installed only in this
disposable container. It has been stopped and removed.

Pinned source checkouts under `scratch/src`:

| Dependency | Commit |
|---|---|
| FelBaker | `cae66302433578ec62afa8c5c5809e93d0405b2f` |
| FelBaker's dovi_tool submodule | `82384bc7652c6f88cb63f7f11e0315b624003fc3` |
| VapourSynth R73 | `76762f6a07d5169c21903972f67827fc108020ba` |
| FFMS2 | `3af2ef2ae47bc30b64597c9e419e5b19c4bda7d8` |

The cloned zimg checkout was **not built**; Ubuntu's `libzimg-dev` 3.0.5 was
used. `scratch/results/runtime-provenance.json` records actual package/Python
versions, native binary SHA values and container resource limits. FFmpeg was
the existing `/usr/local` build `2026-03-26-5dfe661f03`.

`bootstrap.sh` is the historical initial invocation. It stopped at the FFMS2
shared link against static FFmpeg; **it is not a successful one-command build**.
`finish_build.sh` contains the successful continuation using
`LDFLAGS=-Wl,-Bsymbolic` for FFMS2. A clean replay must apply that flag to FFMS2's
initial make/install as well. Keep the FFmpeg linkage private to the plugin;
neither script installs anything into the production encoder/image.

`build_variants.py` copies the pinned FelBaker source and builds separately
named no-residual and compatibility plugins. Generated patches, compilation
commands and hashes are retained in the corresponding `scratch/build` folders.
These controls must never silently substitute for the default plugin.

## Measurement and qualification order

1. `prepare_clips.py`: verify source signatures, extract eight short combined
   HEVC clips, demultiplex BL/EL, extract RPU, record component hashes.
2. Run the upstream fixtures using `upstream-test-resource-limits.patch` and
   `vspipe-limited`; expected test checksums remain unchanged. The original
   unbounded failures and bounded successful logs are retained.
3. `build_variants.py`, `probe_clips.py`, `compat_fixture.vpy`,
   `final_graph_fixture.vpy` and `missing_rpu_control.py`: reference checks and
   required-data rejection. `fel_clip.py` sets explicit node caches and colour
   semantics. Its optional `FEL_TRIAL_ROOT` only relocates dependency paths.
4. `measure_reconstruction.py`: every-frame reconstruction comparisons,
   declared spatial sampling, native RGB witnesses and fixed SDR previews.
5. `run_encoder_trials.py` and `run_baselines.py`: finite manually admitted GPU
   comparisons. They require an already drained node/playback inactivity;
   `run_encoder_trials.py` does not acquire or restore a Tdarr pause itself.
   The source clock is explicit for raw HEVC inputs in the corrected baseline
   script. `correct_baseline_clock.py` records the one-time supersession of
   invalid 25 fps controls; it is historical, not a normal replay step.
6. `validate_outputs.py`, `verify_hdr_metadata.py`: complete decode, grain
   syntax, clocks, fields, numerical error and deterministic payload checks.
   The validator reuses qualified output receipts only after verifying that
   the media still match their recorded encoder SHA-256 identities.
7. `decode_review_stills.py` + `review_outputs.py`: explicitly decode AV1 with
   host libdav1d, then apply the same preview mapping as the references.
   The isolated FFMS2 AV1 reader failed and is not used for validation.
8. `inspect_output_grain.py`: every-frame HDR grain measurements for the four
   full-FEL outputs, with no automatic damage threshold.

`beasts_source_transition.py` adds source witnesses around a selected temporal
transition. `beasts_grain_followup.py` is a finite, manually started GPU
diagnosis: it acquires its own Tdarr admission pause when necessary, leaves
active jobs to finish, regenerates an exact-hash input, runs two controls and
restores its pause in `finally`. It has a ten-minute drain deadline and yields
to Emby playback. The diagnostic encodes and follow-up validation completed; their receipts
take precedence over dated prose. `validate_beasts_followup.py` verifies the
exact repeated payload and no-FGS control. `beasts_texture_compare.py` compares
all 165 frames at 50 fixed native luma patches, including grain-disabled
decoding as a distinct coded-base observation.

The host follow-up used the retained trial prefix/venv with explicit
`FEL_TRIAL_ROOT`, `PYTHONPATH` and `LD_LIBRARY_PATH` under a disposable user
systemd unit limited to four CPUs and 6 GiB, no swap. It matched a previously
saved full-resolution container reference and regenerated the full Beasts
Y4M SHA before use. No system-wide Python packages were installed.

Initial raw Y4M/review-YUV scratch was removed after qualification and hash
verification. Regenerate it from preserved inputs and recorded commands if
repeating metrics. Keep the original source movies and their holds; this
harness does not authorize full movie replacement, Dolby metadata conversion,
downloads or release of retained originals.

Completed evidence is archived on cold storage with all original path links
preserved. Both raw-reference cleanup receipts and the file-by-file archive
verification are in the ledger. No trial containers, scheduled trials or
owned Tdarr pause remain after completion.
