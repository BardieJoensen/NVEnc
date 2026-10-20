# R15 paired-control comparison preflight

Reviewed unexecuted `parent/psyex-real-r15/compare_controls.py` SHA256 `3654b7340f18e219f2107bb9e8372ff7ac6df9ddf2b4ff61f627b6646e2976ba`.

## Disposition

One small admission correction is required before execution. The script pins and loads `assessment.json` and `controls.json` from each run, but never proves that each controls file is the one summarized by its paired assessment. A stale or cross-run `controls.json` under the same run directory could therefore pass the source/baseline and 12,870-key checks while rates, runtime, texture status, and tiles describe different candidate outputs. The existing R8 artifacts provide a direct binding: `pa["controls"] == previous["summary"]` and `pa["face"] == previous["face"]`. Require those equalities for R8 and the analogous `ca/current` equalities for R15 before producing output. This is the smallest correction and requires no recomputation.

Everything else in the requested delta is sound:

- `(frame,x,y)` dictionaries plus equality of key sets and equality of dictionary/list lengths reject duplicates and require the same complete 12,870-tile population. Per-key source, kind, legacy outside-target flag, and baseline descriptors must match exactly; the R8 source/control identities are hard-pinned.
- `hf_signed_excess` remains the signed `candidate.hf_sigma - source.hf_sigma`. Its mean, p95, maximum, and direction counts do not silently become absolute errors. The scope correctly warns that an increase between two negative values is not automatically degradation. `hf_abs_error` is separately absolute-valued.
- All, quiet, edge, flat-texture, and other populations retain mean, p95, maximum, and paired direction counts. ACF pairs with undefined source/candidate values are explicitly excluded and counted. The preserved `outside_target` labels are validated even though no separate legacy-outside subgroup table is emitted; that is adequate for this global policy comparison unless the final report claims an outside-only result.
- Actual Mbps and measured two-pass seconds are shown separately for R8 and R15. The scope explicitly calls the rates different and disclaims matched-rate causality or an acceptance decision. The script defines no threshold, aggregate pass/fail, or single-score optimization.

After the assessment-to-controls equality checks are added, this is a valid descriptive comparison of the frozen controls. It remains correlated repeated sampling from 15 frames and should not be presented as formal significance testing.

## Final delta clearance

Cleared final `compare_controls.py` SHA256 `1e0956de13835bdcd961ef4ec021c0743dcac8e728775b1cbcf990a3ae1357d9`. Its exact diff from preserved `compare_controls-pre-review.py` SHA256 `3654b7340f18e219f2107bb9e8372ff7ac6df9ddf2b4ff61f627b6646e2976ba` adds only the required R8 and R15 assessment-to-controls-summary/face equality assertions. The identified cross-binding gap is resolved without changing comparisons, metrics, or scope.
