# Reproduction

Use a fresh scratch root. Previous evidence archives are immutable. Production
binaries, configuration and library media are outside this work's authorization.
Original files are read only. The canonical measured run receipts, rather than
requested rates, establish each experiment.

The input is the established336-frame E05 window:96 preroll and240 scored frames,
1920x1080,24fps, limited BT709. Original8-bit samples lift exactly to10bits.
Source packet cap is9.6765224Mbps. Rate matching uses sorted presentation packet
positions96:336 of the scored MKV, with a99–100% gate and99.5% calibration aim.
IVF packet bytes are also retained; IVF adds2bytes/frame relative to this MKV.

```bash
export PANTHEON_SOURCEBUDGET_ROOT=/tmp/downloads/codex-work/pantheon-sourcebudget-replay
REPORT=/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020
mkdir -p "$PANTHEON_SOURCEBUDGET_ROOT"
uv venv "$PANTHEON_SOURCEBUDGET_ROOT/analysis-venv"
PYTHON="$PANTHEON_SOURCEBUDGET_ROOT/analysis-venv/bin/python"
uv pip install --python "$PYTHON" numpy==2.5.4 scipy==1.18.1 matplotlib==3.11.2 pillow==13.0.0
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/prepare.py" e05-1440
"$PYTHON" "$REPORT/encode_svt.py" e05-1440 preset0-1x0 10003
```

The initial measured extraction invoked the same prior `prepare.py` directly
with `PANTHEON_RD_ROOT` and then wrote the full-input historical binding.
The new wrapper codifies those exact checks for replay. It must not overwrite
an existing fixture. The full E05 Y4M SHA256 is
`232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4`.
Source stat, all240 scored-frame hashes, raw-source SHA256 and full336 Y4M identity
bind this extraction to the already verified untouched original.

The encoder is the preserved unmodified SVT4.2 binary, SHA256
`5bd538283d52958ffd1756400e4b7b49178bf7895c68904a4670f5ab3a5ba215`.
The runner derives its command from the preserved E05 B baseline and permits
only preset4→0, bitrate request and fresh scratch paths. Tune0, VBR, lp1,
FGS0/denoise0, default GOP/lookahead/transforms and all color flags remain.
Niceness10 and CPU affinity0–7 are retained. Runtime includes the encoder and
reconstruction output; it excludes subsequent validation and scoring. It is
a short-window observation, not a full-episode throughput forecast.

Each run directory is exclusive. If actual packets miss the gate, keep its
receipt, adjust only requested TBR and use a fresh tag. Do not interpret an
overshoot as a matched-rate repair. `command.json` includes the executed script
snapshot, argv, version, binary/input/output hashes, timestamps, wall time,
effective settings log, return code, cadence and both packet populations.

The first running script marked encoder success before post-encode validation.
Its preserved `measured-runner.py` identifies that exact revision. The final
runner instead marks `validating` until the checks complete. The strict scorer
requires completed packet receipts and live hashes in either case; a partial
receipt cannot be admitted. This correction does not alter encoding arguments.

For a matched run, serialize GPU scoring:

```bash
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/score_budget.py" e05-1440 TAG
"$PYTHON" "$REPORT/summarize_budget.py" e05-1440 TAG
PANTHEON_RD_ROOT="$PANTHEON_SOURCEBUDGET_ROOT" \
  "$PYTHON" "$REPORT/../pantheon-rd-20261019/visuals.py" e05-1440 TAG
```

The measured `preset0-1x0` run finished at9.5227592Mbps, below the99% matching
floor but within the practical cap. It was scored with the explicit command:

```bash
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/score_budget.py" \
  e05-1440 preset0-1x0 --under-cap-screen
```

This mode preserves every quality/identity requirement and labels the result
nonmatched in assessment and summary. It cannot support a matched preset-only
causal claim. The encoder runner's `rate_gate_failed` status is not an encode
failure when its complete receipt proves a valid under-cap stream.

The scorer checks all336 application/dav1d/NVDEC frame planes exactly, then
all240 scored decoded frames. It uses the established `campaign.py` adapter
with patched CUDA VMAF and GPU FFVship metrics, retaining pooled and frame-tail
scores, CAMBI, alignment and color receipts. It reuses the frozen12,870 source
tiles on15 frames, requiring exact source descriptors; the old outside-ROI mask
is retained only for comparability. This preset arm has no selected ROI.
E05 face controls and all240 texture/ACF/source-correlation/temporal traces are
retained. Temporal correlation at fixed coordinates is not motion compensated.

The summarizer asserts fresh and historical source traces agree on every frame,
binds all input evidence by SHA256, and plots full traces. The native-pixel
visual script creates lossless10-bit synchronized crop clips with all240
panel hashes checked; RGB stills explicitly convert limited BT709 to full range.
No generated still or clip establishes actual playback.

## Round2 libaom arm

The independent implementation arm uses the installed system FFmpeg6.1.1 and
linked libaom3.8.2, both hashed in its receipt. It uses the exact same336-frame
Y4M input. Four threads, niceness10 and CPU affinity0–7 bound the CPU work.

```bash
"$PYTHON" "$REPORT/encode_aom.py" e05-1440 1x0 10003
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/score_aom.py" e05-1440 aom-1x0
"$PYTHON" "$REPORT/summarize_budget.py" e05-1440 aom-1x0
```

The runner prefixes tags with `aom-`, creates an exclusive directory, and exits
nonzero if the actual packet match fails. Preserve that receipt. A lower-rate
arm can be screened explicitly with `--under-cap-screen`; an overshoot must be
calibrated before it can be judged practical. Two-pass statistics, logs, exact
commands, script snapshot, input before/after SHA, binary/library/probe hashes,
stream color, zero PTS origins and both complete packet arrays are retained.
The runtime is the sum of the two encode passes, excluding remux/validation.

The same numerical/control gates apply. All336 frames/planes must match between
dav1d, native libaom and NVDEC. The raw `dav1d-decoded.yuv` is separately validated
against those hashes and is not an application reconstruction export. All240
scored frames must equal display positions96:336. Required CUDA/FFVship campaign
metrics and frozen whole-window controls reuse the established path. Native
comparison clips use the same `visuals.py` command with the `aom-` tag.

## Round3 direct tune-policy comparison

The pinned [source audit](AOM_TUNE_POLICY.md) identifies SSIM's extra normalized
source-variance RDMULT factor. The public PSNR tune omits that factor; the in-block
distortion metric stays unchanged. First-pass statistics must match exactly.

```bash
"$PYTHON" "$REPORT/encode_aom.py" e05-1440 psnr-1x0 11576 --tune psnr
```

The first PSNR request landed at9.5041536Mbps (98.22% of source), outside both
source and pairwise matching gates. Before quality inspection, calibrate only
TBR to11727 and preserve the first receipt:

```bash
"$PYTHON" "$REPORT/encode_aom.py" e05-1440 psnr-1x1 11727 --tune psnr
```

That calibration overshot the hard ceiling at9.7005904Mbps and was not scored.
A bracketed interpolation selected request11671, yielding9.639088Mbps
(99.613% of source,0.153% above SSIM). Only this matched arm was scored:

```bash
"$PYTHON" "$REPORT/encode_aom.py" e05-1440 psnr-1x2 11671 --tune psnr
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/score_aom.py" e05-1440 aom-psnr-1x2
"$PYTHON" "$REPORT/summarize_budget.py" e05-1440 aom-psnr-1x2
"$PYTHON" "$REPORT/compare_aom_tunes.py" e05-1440 aom-psnr-1x2
```

The last script directly pairs the two libaom arms and rejects undeclared
command differences, unmatched rates, changed sources/controls or unequal pass1
statistics. The older SSIM summary is bound to its committed machine result;
its unchanged metrics are not rerun just to add the newer tune-policy field.
Mode, partition, transform, reconstruction and later prediction choices are free
to change with the tested policy. Requested TBRs and actual packets are both
reported; this is a rate-calibrated contrast, not identical rate-control input.

## Round4 source-boundary instrumentation

`source_trace_input.py` binds the visible Y/U/V little-endian 16-bit serialization
of all 336 original 10-bit frames to the historical whole-frame hashes, and
exports all 1,008 plane hashes. The independent header parser is preserved at
`reviewer/round4-coverage/parse_trace_headers.py` under the experiment root.
It accounts for hidden frames and show-existing headers; 336 display packets
contain 363 coded events, so display count is not the expected hook population.

The portable [instrumentation patch](aom-source-boundary.patch) applies after
all seven Ubuntu patches. It was dry-run checked on a fresh reconstruction.
It observes samples only and is restricted to this exact 10-bit 1920x1080 4:2:0
fixture. It requires an inherited writable append descriptor when enabled.
Neither a library installation nor production replacement is involved.

A private rebuild uses the preserved archives and the following recipe. The
working directory must be fresh. Original configure/pristine-build stdout was
not retained; this is a reproduction recipe, not a claim about missing logs.
The final v3 rebuild has a captured command, exit code, timestamps and log in
`worker/aom-source-trace-preflight/build.json`.

```bash
TRACE_WORK="$PANTHEON_SOURCEBUDGET_ROOT/rebuild-source-boundary"
AOM_ARCHIVES="$PANTHEON_SOURCEBUDGET_ROOT/reviewer/aom-tune-source-v382"
mkdir "$TRACE_WORK" "$TRACE_WORK/pristine"
tar -xf "$AOM_ARCHIVES/aom-v3.8.2.tar.gz" -C "$TRACE_WORK/pristine"
tar -xf "$AOM_ARCHIVES/aom_3.8.2-2ubuntu0.2.debian.tar.xz" -C "$TRACE_WORK/pristine"
while IFS= read -r patch_name; do
  patch -p1 --batch -d "$TRACE_WORK/pristine" \
    -i "$TRACE_WORK/pristine/debian/patches/$patch_name"
done < "$TRACE_WORK/pristine/debian/patches/series"
cp -a "$TRACE_WORK/pristine" "$TRACE_WORK/trace"
patch -p1 --batch -d "$TRACE_WORK/trace" -i "$REPORT/aom-source-boundary.patch"
for mode in pristine trace; do
  cmake -S "$TRACE_WORK/$mode" -B "$TRACE_WORK/$mode/build" -G Ninja \
    -DBUILD_SHARED_LIBS=1 -DFORCE_HIGHBITDEPTH_DECODING=0 \
    -DCONFIG_LIBYUV=0 -DCONFIG_WEBM_IO=0 -DCONFIG_MULTITHREAD=1 \
    -DENABLE_TESTS=0 -DGIT_EXECUTABLE=/nonexistant-binary \
    -DAOM_TARGET_CPU=x86_64 -DCONFIG_BIG_ENDIAN=0 -DCMAKE_BUILD_TYPE=Release
  nice -n10 taskset -c 0-7 cmake --build "$TRACE_WORK/$mode/build" \
    --target aom --parallel 4
done
```

The two optional I/O/conversion dependencies were disabled because their
system development libraries were absent. Encoding-byte equality, not a claim
that those flags never matter, binds this private build to the installed arm.
The fresh source reconstruction and patch logs are preserved in
`worker/aom-source-verify-v3-20261020T100425Z/`. Its final
`source-domain-receipt.json` compares an initial 1,294-file subset. The later
`reviewer/round4-full-source-audit/` reconstruction covers all 1,344 official
regular paths, including upstream `build/cmake` and README files; see
[aom-full-source-audit.json](aom-full-source-audit.json). Never rebuild from the
1,294-file subset. Extract the complete archive as shown above. Debian packaging
and generated scratch/build output are additional files. Earlier receipts
and aggregate hashes are retained as historical attempts, not admitted proof.

Using the preserved reviewed private libraries and build receipt:

```bash
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/source_trace_input.py"
"$PYTHON" "$REPORT/replay_aom_trace.py" pristine pristine-v3
"$PYTHON" "$REPORT/replay_aom_trace.py" trace trace-v3
"$PYTHON" "$REPORT/validate_aom_trace.py" pristine-v3 trace-v3
```

These scripts require fresh output paths. The replay copies the admitted PSNR
pass-one statistics unchanged, clones its exact pass-two command except local
stats/output paths, binds the private library through loader output and its
reported configuration, and records input/stats/library hashes before and after.
The trace descriptor is passed only to the traced process. Runtime measures
only diagnostic pass two and must not replace the candidate's two-pass runtime.

Admission requires private pristine = installed = traced IVF bytes, all 336
original frame/plane bindings, and exact equality to the independently parsed
363 coded-event keys. The validator pins the reviewed build and reconstruction
receipts. A newly rebuilt binary or revised trace requires refreshed provenance
and review before updating those pins; equality and coverage gates remain.


## Round5 controlled source-pixel contrast

The complete source/build is `worker/aom-neutralize-r5b`, constructed from all
1344 official regular archive paths plus the seven pinned Ubuntu patches.
Apply [aom-source-neutralize.patch](aom-source-neutralize.patch) to that patched
baseline. It includes dual-stage trace instrumentation and the source-pointer
contrast; do not apply the Round4 trace patch first. Keep generated build output
outside source. The preserved `build_runner.sh` captures exact configure/build
commands and requires reviewed-source equality before/after, the R4 generated
configuration hash and the versioned library. Failed preparation `r5` is kept
separately; its1294-file subset is insufficient to build.

The reviewed successful build receipt is SHA256
`4ce837abcd6ffc55a1e8a17520dfb2c6079732899d035266a01955d0e21d0a8d`;
private library SHA256
`1f800a96318b7bcd5e824e923eb01e55f2ddfa89a7995da81bef2ac4beea8b25`.
Both arms use this same library. The environment switch is process-local;
no system library or production binary is replaced. Replay uses the preserved
installed first-pass stats and reports only actual instrumented pass-two time.
The full two-pass production cost is not inferred from this replay.

Using the preserved build/receipt and fresh unused run tags:

```bash
python3 "$REPORT/replay_aom_neutralize.py" off off-1
python3 "$REPORT/validate_aom_neutralize.py" off-1 \
  "$PANTHEON_SOURCEBUDGET_ROOT/parent/source-neutralize/parser-control"
python3 "$REPORT/replay_aom_neutralize.py" on on-1
python3 "$REPORT/parse_aom_headers.py" \
  "$PANTHEON_SOURCEBUDGET_ROOT/parent/source-neutralize/runs/on-1/command.json" \
  "$PANTHEON_SOURCEBUDGET_ROOT/parent/source-neutralize/coverage-on-1"
python3 "$REPORT/validate_aom_neutralize.py" on-1 \
  "$PANTHEON_SOURCEBUDGET_ROOT/parent/source-neutralize/coverage-on-1" off-1
```

`parser-control` was generated with the reviewed generic parser against the
byte-identical Round4 stream; all336 packet identities and490 semantic header
records match the independent original parse. The validator requires off stream
identity before reusing that population. On coverage is freshly bound to its
own run receipt. The initial contrast requires unchanged request11671. A later
rate-calibrated arm would need separately labeled admission; current validation
does not silently permit a different TBR.

The disabled control completed and passed all363 coded-event/source bindings.
The enabled arm passes source/header admission but fails the unchanged texture
gates at matched original rate; see AOM_SOURCE_NEUTRALIZATION.md.


For the admitted changed stream, run the reviewed GPU campaign and paired
summary, then the existing native-clip generator. Each output tag must be fresh:

```bash
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/score_aom_neutralize.py" on-1
nice -n10 taskset -c 8-11 "$PYTHON" "$REPORT/summarize_aom_neutralize.py" on-1
PANTHEON_RD_ROOT="$PANTHEON_SOURCEBUDGET_ROOT" \
PANTHEON_INDEPENDENT_DIR="$PANTHEON_SOURCEBUDGET_ROOT/parent/scores" \
  nice -n10 taskset -c 8-11 "$PYTHON" \
  tests/fgs/reports/pantheon-rd-20261019/visuals.py e05-1440 aom-neutralize-on-1
```


Round6 hidden-frame binding (no new encode or quality scoring):

```sh
nice -n 10 taskset -c 8-11 python3 tests/fgs/reports/pantheon-sourcebudget-20261020/aom_tu_binding.py /tmp/downloads/codex-work/pantheon-sourcebudget-20261020/parent/tu-observation/binding-v2
```

Use a fresh output directory on reproduction. The script binds complete IVF/OBU
framing, original whole/per-plane samples, the preserved all-event reference
history, R3 command/remux/decoder receipts and extracted display216 Y.
`aom-tu-binding.json` is the accepted compact receipt. Full Round6 trace and
analysis scripts are not yet admitted experimental evidence.
