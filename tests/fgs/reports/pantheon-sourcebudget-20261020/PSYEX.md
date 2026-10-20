# Fixed PSYEX policy at the original packet budget

Status: encode and decoder admission complete; runtime policy observation and
quality assessment pending. No candidate or playback claim.

The frozen [Round8 policy](ROUND8_POLICY_CONTRACT.md) requested10313kbps after
one rate-only calibration. Actual scored-window video packets are9.6279048Mbps,
99.49757% of the original9.6765224Mbps and99.88398% of R3's9.639088Mbps.
The full336-frame stream averages10.25718343Mbps; the240-frame scored window
is the defined comparison, not the full14s input. Both passes took370.33577s
for336frames. This is observed execution cost, not a controlled speed ranking
or a full-episode prediction.

The original legal encode receipt is
`worker/psyex-r8/runs/e05-1440/psyex-1x1/command.json` beneath the scratch root
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`.
Its SHA256 is
`ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`.
IVF SHA256:
`26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca`.
Application reconstruction SHA256:
`162c2eb85dc9d036912aa5c3a20e613d4ce0fe2ecbc0505ea96bd6d0288d7099`.

[Decoder admission](psyex-decoder-result.json) verifies application
reconstruction, dav1d, libaom and NVDEC agree on every Y/U/V sample of all336
frames. Frame cadence, timestamps, dimensions, limited BT709 and10-bit format
also pass. This validates samples, not preservation quality.
[Independent review](psyex-decoder-review.md) required binding the actual
resource-wrapper executables; the corrected validator was accepted and run.

Reproduce the admitted decoder check in a fresh run directory with
`validate_psyex_decoders.py psyex-1x1 ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`.
The script intentionally refuses to overwrite its existing validation directory.
Do not rerun this unchanged check merely to recover its result.
