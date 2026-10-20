# R17 preparation review — rejected before execution

Reviewed read-only on 2026-10-20:

- requested revision: `experiment.py.1879f4-rejected`, SHA-256 `1879f4caeb62ee825fb678bb9f9d3ac91ccc5261708894917d75753a7e71237b`;
- current v3: `experiment.py`, SHA-256 `1a0903beb82688631fbf2459b7b4b3dedf2cf139b0e8a6eff847efa11613bda3`;
- current README: SHA-256 `0c46d0faf366ef38c7cc88dcfdccec368bd2f2d6f438196e60802fc793075412`;
- current source audit: SHA-256 `ce09c968c773e4e4c39d9b86512ea1a89d45b07cd2c2366fca2b6da29c1e4682`.

**Disposition: reject.** The requested revision has direct numerical and API failures. V3 fixes several of them but still does not satisfy the contract and must not run yet.

## Requested revision `1879f4ca…`

1. Lines 81–85 divide `load_luma()` results by four a second time. The pinned helper already returns native luma divided by four. Predictor, preloop and original comparisons therefore use incompatible scales.
2. Line 85 calls the line-33 `desc(metric, helper, h, ref, z)` wrapper with four arguments, so it raises `TypeError` before producing metrics.
3. Line 82 equates the initial FP scalar mosaic with final preloop. R16 has later optimizer changes; the valid controls are native baseline against captured `scalar_fp`, and captured final against admitted preloop.
4. Line 72 records a trace payload byte offset as the concatenated coefficient offset and records no pixel offset. Arrays are not independently indexable as claimed.

## Remaining blockers in current v3 `1a0903be…`

1. **The contract is not bound.** The live contract SHA is `c207781f7fd77d488df17a9892988c78d660cf88c3ab8216209a91c73ab29f8c`; v3, README and audit pin `c6ce21643…`. Line 48 will fail. Restore the intended immutable contract or repin all three artifacts to the finalized file.
2. **DC-delta evidence is circular.** The admitted token `info` schema has `seg_delta` but no `dc_delta` or `y_dc_delta`, so line 68 necessarily infers a delta solely by matching the same captured FP rows that it later claims to explain. A unique table match is a useful consistency control, but it is not the contract's independent syntax/native evidence. Bind an authoritative encoder field/config/source derivation of luma DC delta, require every token to agree with it, then retain the table search only as a cross-check.
3. **Build provenance is under-validated.** Lines 55–56 check only receipt status and library SHA. The accepted R12 control also requires every build command/log, equal `inputs_before`/`inputs_after`, and every source identity. Reuse that validation before `CDLL`.
4. **The advertised before/after check is not actually before/after.** `deps` and `deps_after` are both created after all native work (lines 100–102). Snapshot all dependencies and the script before module/library loading, then rehash them after output; also bind the metric helper and its transitive helper rather than only `analyze.py`.
5. **The token join is partial.** Line 63 compares only `begin`; the admitted manifest also binds `info`, `end`, `commit`, stages and payload offsets. Require exact join fields for all 2870 tokens before using arrays.
6. **Reported strata do not meet the contract.** V3 emits whole-ROI descriptors and invoked/uninvoked SSE, but transform-size strata contain only pixel counts (lines 90–93). The contract asks for the declared descriptors by invoked/uninvoked and transform-size strata. Emit predeclared, support-aware stratum measurements, and assert exact nonoverlap/coverage and `all SSE = invoked SSE + uninvoked SSE` for every ROI/stage.
7. **Result reconstruction controls remain incomplete.** Assert final cumulative coefficient/pixel offsets equal each stored concatenated array, persist or bind the exact per-token tables/raw/scan inputs used by q4, and record explicit all-token direct/runtime, raw-inverse and baseline-control pass counts. The trace can be the authoritative payload source if its exact token offsets are kept under separately named fields.

V3 correctly fixes the double scaling, metric call, scalar/final distinction, cumulative offsets, raw-inverse persistence and final-to-preloop comparison. Those fixes do not resolve the blockers above. No diagnostic was executed and no numerical outcome was reviewed.
