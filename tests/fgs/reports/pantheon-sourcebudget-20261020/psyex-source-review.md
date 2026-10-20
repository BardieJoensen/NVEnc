# R8 PSYEX source review

## Provenance

The fetched tree is clean at master commit `59d1a025698f2ca7b4c4b0e833937dd15e382494`, with no tag pointing at HEAD. It is therefore distinct from the advertised `v3.0.2-B` tag commit `3beb4aee471c686ecb05089b29b0e676026aea1b`. The receipt records 1,217 tracked files and manifest SHA-256 `8cf0314d5ee329b662c32021020c8299ef47bb87681d87508328c1b28eeb5c69`; the pointer scan found no LFS placeholders, submodules, or symlinks. Reports must call this pinned master, not v3.0.2-B.

The README/parameter documentation is not sufficient to establish effective defaults: `Docs/Parameters.md` lists `PsyRd` default 0, while code initializes `psy_rd = 1.0` (`Source/Lib/Globals/enc_settings.c:1108`). The runner should set and verify all policy options explicitly, with code/runtime evidence authoritative.

## What the fixed policy changes

Code defaults include tune 0, random-access prediction, CRF rate control, AQ mode 2, preset M8, QM on, variance boost on, temporal filtering strength 1, sharpness 1, `psy_rd=1.0`, `sharp_tx=1`, `complex_hvs=0`, and noise-adaptive filtering off (`enc_settings.c:957-1115`). A two-pass VBR experiment necessarily replaces the CRF/default target-rate portion. Tune 0 is allowed with VBR; low-delay would silently force tune 1, so the arm must explicitly retain random access (`enc_settings.c:800-805`). Ten-bit 4:2:0 input is supported (`enc_settings.c:435-448`).

Preset is consequential. Automatic HBD mode decision uses full high-bit-depth search through M4 when psy-rd is at least 0.6, hybrid behavior at M5/M6, and mostly 8-bit decisions at faster presets (`Source/Lib/Codec/enc_mode_config.c:1815-1842`). Thus a 10-bit input alone does not establish 10-bit mode-decision precision. Preset must be fixed and reported as part of the bundled policy.

The psy term is an AC-energy mismatch penalty, not a direct measurement of the campaign HF/ACF descriptors. For 8-bit and high-bit-depth paths it compares source and reconstruction block energy using SA8D minus a DC-like SAD component (`Source/Lib/Codec/psy_rd.c:135-165,241-270`), then scales by psy-rd (`:277-292`). Effective strength also varies by frame temporal layer (`:295-306`). It can favor matching source AC energy, but it does not distinguish wanted texture from other source energy.

## Reach into actual decisions

### Coefficient and transform selection

The ordinary transform/quantize path runs before the later coefficient optimization (`Source/Lib/Codec/product_coding_loop.c:5705-5736`). In `full_loop.c:1153-1184`, fast/EOB exits precede the PSYEX sharp-transform branch. Only when `use_sharpness`, `delta_q_present`, and luma are all true does `sharp_tx=1` force the RDOQ rate weight to zero. Initial FP/B quantization is unchanged by this branch. This is a direct, potentially useful mechanism for retaining coefficients, but it is guarded and cannot be described as universal until runtime counters prove it was exercised.

Transform-type search constructs source/prediction/reconstruction distortion with `get_svt_psy_full_dist`, then uses the resulting RD costs to select transforms (`product_coding_loop.c:4848-4899,4941-5039`). However, the main full-loop psy additions are conditional on `ctx->mds_spatial_sse` (`:5743,5808-5855`). The alternate transform-domain facade at `:5872-5885` does not obtain the same psy term with default `spy_rd=0` (`Source/Lib/Codec/pic_operators.c:236-285`). Some fast-stage branches also omit psy when variance distortion is selected. Runtime evidence must therefore report spatial-SSE/fast-stage coverage and surviving candidate coverage.

### TU zeroing and coding-block skip

When the spatial path is active, the residual reconstruction distortion and predictor-only distortion each include their corresponding psy term (`product_coding_loop.c:5808-5855`). `svt_aom_full_cost` compares those two alternatives: residual cost uses the reconstruction entry, skip/zero cost uses the predictor entry, and choosing skip clears coefficient state (`Source/Lib/Codec/rd_cost.c:1521-1558`). The same routine compares regular coding against skip mode using predictor distortion (`:1596-1630`). This establishes that the psy term can reach TU coefficient removal and coding-block skip decisions; state-copy sites alone would not establish that.

### Mode and partition policy

The mode cost is assembled from plane distortions and rate into `full_cost` (`rd_cost.c:1589-1595`). Full mode decision then selects the lowest-cost candidate and records that cost for subsequent block/partition selection (`Source/Lib/Codec/mode_decision.c:4311-4353`). Psy-influenced distortion can therefore affect modes and downstream block structure. Candidate pruning and the spatial-SSE guards mean it need not affect every candidate or every stage.

This is consequently an integrated decision-policy test: AC-energy distortion, guarded zero-rate RDOQ, fork defaults, candidate pruning, filtering, QM, AQ, and search precision can all matter. It cannot isolate psy-rd, sharp-tx, or a common RD multiplier.

## Scientific disposition

One fixed, source-budget arm is justified after build and runtime-delivery admission. It tests a genuinely distinct policy family from prior stock SVT, libaom PSNR/qmax, ROI allocation, and final-stage coefficient retention. Exact equivalence to another encoder's RD multiplier is unnecessary for that feasibility question.

A passing arm would show that this pinned bundled policy can satisfy the unchanged E05 screen under the source cap, subject to full controls and later transfer. A failure would reject only this tested commit/configuration/rate. Neither result establishes a pure psy-rd effect, an AV1 limit, or superiority over a matched implementation.

Minimum admission should include:

- Explicit random-access, tune 0, psy-rd 1.0, sharp-tx 1, preset, 10-bit 4:2:0, two-pass VBR, AQ/variance-boost/QM/filter/noise-normalization settings.
- Exact 336-frame input, color/cadence, binary/library/source identity, fresh pass-1 stats, and actual packet-rate gate of 99-100% of source and no more than 9.6765224 Mbps.
- Runtime proof of coefficient-optimizer calls; luma/delta-Q/sharp-tx zero-weight calls; spatial-SSE versus transform-domain paths; nonzero psy terms; and coverage of residual-versus-zero, skip-mode, mode, and partition comparisons. Source reachability alone is insufficient.
- The unchanged decoder identity, texture, quiet/detail/tail/face/banding/temporal controls. No result-based parameter selection; E04 transfer only after E05 qualifies.

## Build disposition

The current `build-plan.md` is not releasable because it uses `-DENABLE_TESTS=0`, while this tree exposes `BUILD_TESTING` and `BUILD_APPS` (`CMakeLists.txt:229,263,716`). Use `-DBUILD_TESTING=OFF -DBUILD_APPS=ON` explicitly. Before approval, the forthcoming runner should use a fresh out-of-tree build, fatal error/status handling, bounded resources, source-manifest before/after equality, exact compiler/CMake/Ninja/config provenance, binary and resolved-library hashes, and a help/version smoke test without installing anything. The fixed configuration and linked library must be captured in the receipt.

The build disposition above records the initial plan. The corrected runner was independently accepted and built successfully; see `psyex-build-review.md` and `ROUND8_POLICY_CONTRACT.md`.
