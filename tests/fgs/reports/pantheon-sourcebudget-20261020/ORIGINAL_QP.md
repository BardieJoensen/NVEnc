# Original H264 state versus conventional re-encode state

This is a reference-stream diagnostic, not an original-file restoration or a
repair candidate. All values use H264 8-bit QP_Y conventions. QP from skipped
macroblocks is decoder state; it does not establish that a residual was quantized.
Prediction, transforms, filters, picture schedules and rates are not held fixed.

The original E05 window has higher QP state than the previously tested 2x and
4x x264 re-encodes, despite the original retaining the texture used as reference:

| Region, five prescribed midpoint frames | Original QP | x264 2x QP | x264 4x QP |
|---|---:|---:|---:|
| Shirt | 24.12592 | 22.44608 | 16.46656 |
| Background | 25.78171 | 24.28812 | 19.70448 |
| Face | 27.18723 | 25.84632 | 21.21053 |
| Whole visible picture | 25.35669 | 23.74368 | 18.57017 |
| Actual scored video Mbps | 9.6765224 | 19.3683368 | 38.6852184 |

Weights cover visible pixel area, including partial ROI macroblocks and only
the visible eight rows in the padded bottom macroblocks. The prescribed scored
frames are 116, 118, 120, 122 and 124, corresponding to input positions
212, 214, 216, 218 and 220. Complete 240-frame series are retained.

These state values do not establish “match the original QP number” as a
preservation solution. They do **not** prove why re-encoding costs more, nor that
the original texture was intentional grain, nor that a different encoder cannot
preserve it at source rate. The original has keyframes every 48 input frames;
the prior x264 arms have different scene-dependent keyframe positions. Decoder
QP state alone does not separate prediction, transform, rounding and filtering
contributions to the decoded texture. Coefficients, scaling matrices and actual
residual-quantization execution are not observed by this reader.

## Validity and reproduction

Scripts: [original_qp.py](original_qp.py) and
[original_qp_summary.py](original_qp_summary.py). Machine-readable values and
provenance: [original-qp.json](original-qp.json). Use Python with NumPy2.5.4
and the freshly verified fixtures prepared by the prior report's
[prepare.py](../pantheon-rd-20261019/prepare.py), setting `PANTHEON_RD_ROOT`
and `PANTHEON_SOURCEBUDGET_ROOT` to the same fresh root:

```bash
nice -n10 taskset -c8-11 "$PYTHON" "$REPORT/original_qp.py" e05-1440
"$PYTHON" "$REPORT/original_qp_summary.py"
```

Initial 336-packet copies using both system and fixture FFmpeg selected the
1434-second keyframe, although a keyframe exists at the intended 1436-second
boundary. Exact sample hashes rejected these copies before QP export. Merely
adjusting the requested seek by 0.125 seconds did not fix it. Their commands and
failed identity receipts are retained; none enters the comparison.

The accepted path retains 384 decoded frames starting with the earlier GOP.
All 336 established input frames match exactly at decoded positions 48:384.
The earlier complete-population reader and wrapper are generated with only their
literal expected count changed from 336 to 384. The exporter checks 3,133,440
unique macroblock states, full padded grids, decoder drain, side-data bounds,
frame PTS/cadence and input hashes. The selected 336-frame state array has its
own SHA256 and receipt. Source file size/mtime remain unchanged.

Fresh evidence is under
`parent/original-qp/e05-1440/preroll/`: `extract.json`,
`identity-check.json`, `tool-provenance.json`, generated tool sources,
`export/receipt.json`, `selection.json`, `fixture-qp-state.i8` and
`comparison.json`. Historical x264 map hashes bind to their original stream
hashes and verified actual-packet audits. No AV1 qindex is compared numerically
to these H264 QPs.

Independent review confirmed the unique frame mapping, complete grids, PTS,
visible-area weights and archived-map provenance. Parent added the requested
cross-links from the selected state to the extraction receipt and copied
stream. The reviewer initially described the requested boundary as a non-keyframe;
parent corrected that using original packet evidence. The problem was seek
selection, and no invalid copy was admitted.
