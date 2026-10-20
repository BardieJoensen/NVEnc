# R17 parent runner final preflight review

Disposition: **released for the one native q4 diagnostic**. I found no material blocker in the frozen parent runner. This is authorization for the bounded local diagnostic defined by the contract, not an outcome judgment.

Reviewed identities:

- `ROUND17_FIXED_Q4_CONTRACT.md` SHA256 `c207781f7fd77d488df17a9892988c78d660cf88c3ab8216209a91c73ab29f8c`
- `parent/psyex-q4-r17/experiment.py` SHA256 `cb0e9a59adfde606ec489095ba71874bf476f5775e5d4223a6cb477fb44f19a6`
- `parent/psyex-q4-r17/README.md` SHA256 `e67609e1a7106b5f5599036083671a70fd1b93b515258256a43fb600896914d1`
- DC v4 result/script/execution SHAs `beca735ea45536e43c6230efd12289d03d5a0c4502b1f23e0a895ec5416785f3`, `e1085f5817b3c7562f12e388d2dfd54a45876c3e7034edddd9c8fa02f6f9b7a8`, and `eac7cff03af51e340b7f14ce1263830b20d88db93e52bd1f8075ce9ddfa914ca`
- no-native outer/inner preflight SHAs `64b92b5cea8593310ef9c9c83dd3adbdd1168b31987e6caf999c73bc6887c427` and `9d6fad834fd3de0e9caeebc4786dd7247977b50f6b641cfce68c85e1f18807fb`

The corrected DC extraction is sound for this use. It reconstructs all 502 syntax events (336 coded and 166 show-existing), independently identifies event 314 / coded ordinal 210 / packet 209 event 1, binds the target OBU, and uses a zero-based half-open source interval with explicit one-based round trips. The target block begins at line 22319, the luma-DC syntax occurs at zero-based index 22348 (one-based line 22349), and the next frame-header marker is line 22414. The exact syntax is `delta_q_y_dc.delta_coded 0 = 0`, establishing frame-level luma DC delta zero without conflating it with block delta-Q.

The runner meets the scientific controls. Before q4 it reconstructs all 2870 joined tokens, separates 2169 invoked from 701 uninvoked owners (including 39 invoked zero-EOB tokens), binds original/coding input, predictor, admitted preloop, token payload offsets, native table inputs, and adjusted-64 coefficient packing. It requires exact captured-versus-direct-C-versus-runtime q/DQ/EOB/inverse and raw-inverse equality on every invoked token. Only FP table rows 0, 1 and 6 are replaced for q4; the other rows and every predictor, partition, transform, scan, QM input, and uninvoked predictor remain fixed. New direct/runtime equality is required per token.

The result remains independently inspectable: coefficient and pixel offsets are gap-free, baseline/q4 arrays and EOBs are retained, full mosaics and masks are saved, all three fixed ROIs require complete coverage, and invoked/uninvoked plus native-transform strata close exactly for additive SSE. HF/ACF/correlation use the established complete-neighborhood masked helper and are not treated as additive. Scope text correctly excludes coded-bit, filtering, feedback, full-window, deployability, repair, and playback claims.

The successful no-native preflight was run through the pinned outer wrapper on CPUs 8–11 with `native_loaded=false`; it validated the full input closure and the expected 2870/2169/701/2130/39 population counts without executing the intervention.

Two nonblocking cleanup observations:

1. `experiment.py:151` calls `matched_rate_sweep.py` the underlying high-pass source, but the loaded legacy helper actually resolves the already pinned `pantheon-rd/analyze.py` dependency chain (`investigate.py` and `texture.py`). The extra pin is harmless and unused; correct or remove that comment in later reporting so provenance wording names the files that actually supply the metric.
2. `receipt = ...` is duplicated at lines 229–230. Both assignments are identical and occur before any output, so this has no behavioral or evidentiary effect.

No native q4 result existed or was considered in this review.
