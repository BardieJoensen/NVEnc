# Prepared FEL encoding tools

This is a deliberately narrow, staged integration. The current qualification,
runtime pins, source scope and live-job links are in
[the production qualification report](../../tests/fgs/FEL-PRODUCTION-20260914.md).
It is not installed in the ordinary Tdarr flow.

`fel_prepare.py` is a command-line preparation tool. Give it one retained source,
a fresh scratch directory, the qualified dependency runtime and pinned dovi_tool:

```sh
python3 tools/fgs/fel_prepare.py \
  --source /retained/source.mkv \
  --output-dir /scratch/new-fel-source \
  --runtime /qualified/felbaker-runtime \
  --dovi-tool /qualified/bin/dovi_tool
```

Run preparation under a CPU/memory cap. It reserves space, verifies the complete
original video clock, demultiplexes into BL/EL without a combined-video scratch
copy, verifies all converted metadata and checks independent layer ordering.
It rejects unsupported input instead of discarding the residual. A partial
preparation cannot be reused as a successful result.

`fel_bundle_runtime.py` packages previously qualified artifacts into a Docker
build context. Its receipt records every copied file, matching Python runtime
packages and the immutable base image. It does not build those dependencies
from source. A changed dependency requires a new qualification.

`fel_encode_prepared.encode(...)` and `fel_validate_staged.validate(...)` are
Python library functions called by the site controller, not unattended queue
daemons. The controller owns admission, playback yielding and restart/stop
cleanup. The exact manually started controller is linked in the report.

The encode function requires verified metadata, arithmetic ranges, complete
source picture continuity and immutable tool identities. It uses a FIFO between
bounded reconstruction and encoder containers. Both exits must succeed. The
result remains `encoded_unvalidated` in scratch. Validation preserves tracks,
checks complete metadata/clock/payloads and decodes the final staged container.
Neither function installs a library replacement.

TrueHD tracks use their exported native Matroska frame starts explicitly during
the staged mux. The validator checks them against every known FFprobe packet
timestamp, fills an omitted access-unit timestamp only from its stored clock,
and compares the complete timeline, durations and codec trimming. The trailing
inferred end in an `mkvextract timestamps_v2` file is not a frame. The report
records the actual mux regression, successful fixture and shifted-audio controls.

For a library repair, give `validate(...)` both `retained_library` and its
previously captured `library_signature`. The mux then retains that file's
current tracks, attachments and chapters. Before muxing, it checks every library
video timestamp against the reconstructed source clock and runs the existing
source/content alignment checks. It rechecks both file identities at completion.
Omitting both arguments qualifies the original source's tracks, as in the
complete-film canary. A canary retaining original tracks is not permission to
replace a library file with a different track selection.

`fel_input.vpy` loads the reconstruction manifest. `fel_reconstruct.py` performs
the bounded graph and per-frame BL/RPU checks. `fel_metadata.py`,
`fel_parameter_bounds.py` and `fel_layer_order.py` enforce the qualified input
contract. `fel_process.py` supervises both sides and provides cleanup hooks.

Do not construct qualified excerpts with an arbitrary compressed-stream end
cut: future reference pictures can survive while intervening pictures are
missing. Use complete groups or a frame-accurate view of a fully verified
source. The source-continuity check deliberately rejects unsupported POC wraps.
Historical diagnostic clips are not all valid complete-source preparations.

Run CPU tests with `bash tests/fgs/run_cpu_tests.sh`. The additional
`python3 tests/fgs/test_fel_staged.py` integration test needs FFmpeg/FFprobe and
demonstrates that unchanged audio samples can still have incorrect timestamps.
The optional `fel_rpu_roundtrip.cpp` checker needs the pinned libdovi; its build
command and real-stream controls are recorded in the qualification ledger.
