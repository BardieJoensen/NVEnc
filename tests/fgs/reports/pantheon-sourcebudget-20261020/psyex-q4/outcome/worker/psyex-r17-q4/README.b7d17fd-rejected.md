# R17 fixed-decision q4 preparation

Preparation only; this runner has not been executed. It is a one-point native FP qindex-4 fixed-decision diagnostic for the admitted R16 TF-off token population. It does not encode, rate-control, entropy-code, update references, or claim a deployable repair.

The runner binds `ROUND17_FIXED_Q4_CONTRACT.md` SHA `c6ce21643dde4213ade5cb666771dcf3259b6934c620d61d57e59aae0a9af619`, R16 command `00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497`, R16 admission `a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab`, and P16R producer `fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb`. It imports the existing R12 native helper and R15 parser by exact hash; it does not rebuild or copy their library.

Before q4, every invoked token must pass controls: dynamic coded ordinal and exact token joins; gap-free coefficient/pixel offsets; captured native table rows reproduced by `rp_fp_tables(actual_q, captured_dc_delta)`; direct-C/runtime baseline q,DQ,EOB and inverse equal captured scalar stage; and raw inverse direct-C/runtime equal captured raw inverse. Only after those controls pass does q4 replace rows `[0,1,6]`; rows `[2,3,4,5]`, predictor, raw residual, TX/type, scan/iscan, QM/IQM, dimensions and log_scale remain unchanged. Uninvoked owners are retained only as a separately labelled predictor mosaic. 64x64 uses the captured packed `n`/scan/layout; no 1024-to-4096 expansion is permitted.

The future admission path and SHA are CLI inputs because the R16 admission output is produced after the active run. No numerical or q4 result exists yet.
