# R11 final build and validator review

## Cleared source, build, and replay

The corrected observer source is cleared. `pc_impl.c` and installed `source/Source/Lib/Codec/pc_impl.h` are byte-identical at SHA256 `3ae5418f7b4b34677267bce91b1a4ab140ec52919ac4dd181bc0c224c2ccd56e`. The final route check uses the actual child `pcs->pic_bypass_encdec`, while retaining child/parent/configured M4 and MD-bypass assertions. The only prior include correction is `coefficients.h`. The source manifest SHA256 is `c4a264dfa50cf24e5411c27719cf9e7ac118357ee8f0ee133e5a371854065b55`; all 1,790 paths independently matched size and SHA. The canonical R9-relative patch is SHA256 `60d3b8e08de72e960c838df1b83e01eacbd2d755247cca732f0efc852a3eddbb`.

Completed build pins SHA256 `f32ace44e5e449ce0898b6566cc9bb3195a8daa2fcb0b9d7f20b0e0d8b3c54d8` are internally live: every identity record matches, before/after source manifests equal the final source manifest, the build receipt has one successful terminal status, and the app resolves the pinned private library. The build log contains existing/general compiler warnings but no observer compile warning or error. Failed build 1 remains properly separate and carries no experimental observation.

Final replay SHA256 `f9023e688eeacbc0c1b42defe879c0a3d93be072ea8e77e5fb4f565a4bb96747` differs from reviewed v3 `c4eedb26...` in exactly one receipt string: “Coefficient and boundary observation neutrality.” The behavioral review therefore remains valid.

## Validator disposition

Validator SHA256 `28ea377264c0162fb2ae478c4a662ac4ac9ac844bd24811a79a390ac1a80b5d0` implements the substantive requested corrections:

- fixed replay and completed-build-pins hashes;
- independently reconstructed R8 pass-2 argv, exact environment, copied stats, loader result, and original receipt;
- duplicate JSON-key rejection;
- the source-correct stage branch machine;
- requested/begin and actual/committed qindex joins for every quantized token;
- positive-EOB final type and source block-coefficient checks, with block-level labeling retained for EOB0 controls;
- corrected target SHA/population and visible R9/R10 joins.

One small parser correction remains before this exact validator may be called final: `strict_json` rejects `NaN`/`Infinity` constants through `parse_constant`, but Python parses a legal exponent such as `1e999` as floating-point `inf`. I reproduced this against the same call. Add a `parse_float` function that converts the literal and requires `math.isfinite`, or recursively reject nonfinite floats after parsing. This does not affect the private source, build, replay, or generated trace and requires no encode rerun. It only makes the stated nonfinite rejection true for all JSON numeric spellings.

Subject to that parser-only correction and a newly pinned validator hash, the on-trace run and later admission are methodologically cleared. No numerical or causal result is inferred here.
