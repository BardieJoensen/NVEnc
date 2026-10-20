# Round 8 PSYEX observation v2 review

Reviewed unbuilt `observation.patch` SHA
`c698bb24a735f01ab099c812ecc1becddc43fc02b1d92277a801334bfd888118`.

**Disposition: rejected before build.** The intended hook locations are closer to
the minimal contract than v1, but v2 is neither buildable nor safe to admit.

1. `psy_observe.c:14` allocates/serializes a 524-byte picture payload as
   `12 + 4*16*8`, but lines 79–80 write four u32 fields (16 bytes) plus 512
   counter bytes. This overruns the buffer by four bytes and emits a truncated
   last counter. The payload and schema must say 528.
2. `emit()` returns the boolean result of `write_all(...) || write_all(...)`
   (`psy_observe.c:69–71`), hence 0 or 1. Both callers test `< 0`; write failures
   are never recognized. Return an actual error code and fail closed.
3. `PSY_OBS_OPT_COMPLETE` is at `full_loop.c:1599–1600`, the end of
   `svt_av1_perform_noise_normalization`, rather than at the ordinary completion
   of `svt_av1_optimize_b` (which ends at line 1343). It therefore cannot close
   the optimizer entry/early-exit population and is mislabeled.
4. Numerous `get_svt_psy_full_dist` calls now pass `pcs->picture_number`, while
   `psy_rd.h` and `psy_rd.c` retain the original ten-argument signature. This is
   a compile failure. Meanwhile the only implemented nonzero-psy hook is in the
   separate SSIM distortion helper; tune 0's principal AC-energy calls are not
   observed. The replacement must instrument the actual returned
   `get_svt_psy_full_dist` value on the intended decision paths.
5. `PSY_OBS_SKIP_CHOICE` combines coefficient/residual-zero choices and
   skip-mode choices. Keep their comparisons and selected outcomes separately;
   otherwise counts cannot show which policy decision occurred.
6. The route counters are not a symmetric census: quantize/inverse-quantize
   counts both spatial and transform flags for its invocations, while the UV
   hook adds spatial calls only. They may show reachability, but cannot be
   reported as relative spatial/transform coverage without hooks at the actual
   mutually exclusive decision branches.

Provenance is also stale: `provenance.json` and `artifact-hashes.txt` still bind
v1 hashes, `source-manifest-all.tsv` no longer matches its recorded hash, and
the patch's two new-file headers contain scratch-absolute `a/tmp/downloads/...`
paths instead of repository-relative paths. Regenerate all of these only after
the parent-owned replacement is stable.

The useful parts to retain are the real `rd_cost.c` residual-versus-zero and
skip-mode comparison hooks, final candidate-selection hooks, guarded sharp/RDOQ
hooks, atomic per-picture counters, and post-thread-shutdown flush. Counts remain
search invocations rather than pixels/final blocks, and stream identity in both
disabled/enabled observation modes remains required.
