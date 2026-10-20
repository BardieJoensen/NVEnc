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
nice -n10 taskset -c8-11 "$PYTHON" "$REPORT/prepare.py" e05-1440
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
nice -n10 taskset -c8-11 "$PYTHON" "$REPORT/score_budget.py" e05-1440 TAG
"$PYTHON" "$REPORT/summarize_budget.py" e05-1440 TAG
PANTHEON_RD_ROOT="$PANTHEON_SOURCEBUDGET_ROOT" \
  "$PYTHON" "$REPORT/../pantheon-rd-20261019/visuals.py" e05-1440 TAG
```

The measured `preset0-1x0` run finished at9.5227592Mbps, below the99% matching
floor but within the practical cap. It was scored with the explicit command:

```bash
nice -n10 taskset -c8-11 "$PYTHON" "$REPORT/score_budget.py" \
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
