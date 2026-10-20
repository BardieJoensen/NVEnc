# R11 hook correction clearance

The corrected observer is cleared for the private build.

Reviewed `pc_impl.c` and installed `source/Source/Lib/Codec/pc_impl.h`, both SHA256 `f053401126c3472c27a8b86d1ccbc14284ffcd30a6e4396c0266c52122e1d9f3`; they are byte-identical. `pc_route` now requires child, parent, and configured mode M4 and records all three (`pc_impl.c:81-87`). `pc_commit` now requires copied `EcBlkStruct.mds_idx` equality and records it, while correctly naming the unavailable destination facts `source_block_has_coeff` and `source_skip_mode` (`206-224`). The bottom-edge guard admits native TUs through padded row 1088, retains their full arrays, and records `visible_h=min(h,1080-y)` (`98-115`). Admission must use the visible extent for R9/R10 pixel joins while retaining the full extent for native inverse and coefficient checks.

The regenerated source manifest SHA256 is `128df5ff616347db501f99b4ea17d811ccc79c094d0e6992c09137022b886042`; all 1,790 listed paths were independently rehashed with zero missing, size, or SHA mismatches. The R9-relative patch is `coeff-r9-relative.patch` SHA256 `f9f6c0ed2726cc745b170cbb220da6a463a8c0cd36fbc398831160a18634b191`. The older `coeff.patch` remains a prior intermediate and must not be cited as the canonical final patch.

This clears the three blockers in `round11-hook-review.md`. Build and run admission still require the planned compilation, exact off/on output identity, complete trace parsing, accepted-generation coverage, and R9/R10 joins.
