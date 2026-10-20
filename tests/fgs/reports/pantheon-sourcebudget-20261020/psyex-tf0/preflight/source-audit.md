# R16 source/settings audit

The contract SHA is `5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71`. The runner loads the preserved R8 command receipt and compares both normalized pass commands. It asserts the R8 `--enable-tf` value is `1`, R16 is `0`, and no min/max-QP flags occur. Only `--tbr`, fresh stats/output paths, and the TF value are normalized differences; all other options, source, app, library, threads and GOP must match.

The runner does not infer effective QP from requested settings. It records encoder log settings and leaves realized TU quantizers to later R16 trace/admission. The updated contract interpretation requires sufficient realized residual support before attributing a failure to coarse scalar quantization; coarse q alone is insufficient, and skip or missing support selects a decision trace.

The preserved R8 command receipt is hard-pinned to SHA `ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`. Initial execution requires request 10313 with calibration attempt 1. A later request must provide `--previous-receipt` and its SHA, validate a successful same-policy R16 receipt recursively back to attempt 1, be at most attempt 3, and equal `round(previous.request_kbps * (0.997 * source_mbps) / previous.actual_mbps)` only when the prior scored rate is outside 99–100% of source. The prior receipt and R8 command receipt are included in live identity bindings.

The final preflight also rejects optimized Python (`python3 -O`) before creating a run directory. Positive preview `preview-lineage-final` completed with no encoder invocation; optimized negative probe exited 1 with `optimized Python is rejected` and created no run directory.

Lineage validation also rehashes every identity_before/identity_after path, recomputes the MKV scored packet rate from packet sizes at positions 96:336, and checks each stored source/validity identity. Replay binds the encoder source, selected receipt, complete ancestry, and all identity paths before launching.

The final lineage smoke also exercised a synthetic 336-packet window: the validator recomputed 9.5 Mbps from packet sizes and rejected altered policy and cyclic predecessor receipts. No media or encoder was used for this check.
