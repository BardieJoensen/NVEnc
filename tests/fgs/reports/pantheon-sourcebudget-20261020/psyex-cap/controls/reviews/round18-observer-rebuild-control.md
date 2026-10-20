# R18 observer-only rebuild control decision

## Conclusion

Yes. A fresh observer-only build can be admitted without repeating the new build's baseline, pass1 and unobserved cap runs **if** its completed trace replay produces IVF and all 336 app-reconstruction frames byte-identical to the frozen old-build `cap-1`, uses the exact frozen pass1 statistics, and the source/build review proves the correction is confined to observer code. This is the most direct neutrality control for the evidence actually used.

The failed `trace-1` is an observer failure, not a cap-policy or quality result. It aborted after 4.199 seconds at the coefficient observer's commit-offset assertion; `cap-1` had already completed without observation and remains immutable evidence.

## Why the reduced control set is sufficient

The old build already supplies three distinct controls:

1. baseline reproduces admitted R16 IVF, all 336 reconstructions and stats;
2. fresh pass1 reproduces the admitted statistics route with the cap and observers disabled;
3. unobserved `cap-1` is the policy output to be scored and interpreted.

The scientific question for the replacement build is only whether corrected observation changes that frozen policy output. A complete corrected trace replay with exact `cap-1` IVF proves every coded byte is unchanged, and exact all-frame app reconstruction proves the observed sample output is unchanged. Repeating baseline or cap-off on the corrected build tests disabled code that is not used to derive the trace evidence. Repeating pass1 is likewise redundant because the actual corrected replay must consume the exact frozen pass1 stats; the contract forbids observer/policy execution during pass1.

A separate unobserved cap on the new build is also redundant: trace-on exact equality to old `cap-1` is stronger for observer neutrality than trace-off equality. If trace-on equality fails, no trace evidence is admitted; only then would a new-build trace-off cap be useful to distinguish build/codegen drift from observer effects.

## Required revised admission chain

The current provenance helper assumes all four modes share one build and should not be relaxed silently. Create an explicit trace-v2 ancestry with two named build domains:

- **policy domain:** old accepted build-1, baseline, pass1 and immutable `cap-1` receipts/outer receipts;
- **observer domain:** fresh source freeze, review, build and corrected trace replay only.

Require all of the following:

1. Preserve failed trace-1 source, build, inner/outer receipts, partial logs/streams and the exact failure reason as rejected evidence.
2. Reconstruct the corrected source from the exact old 1,790-file source manifest. Bind a complete new manifest and literal path-level diff. Every changed hunk must be observer-only, guarded by the observation FD/active state, with no policy, RC, lambda, quantizer, search, filter, input or output mutation. Retain the reviewed correction rationale for the offset convention.
3. Use the identical configuration, toolchain and bounded build procedure; bind fresh app/library/loader identities and complete before/after source manifests. A binary hash change is expected and is not itself policy evidence.
4. Derive trace-v2 pass2 argv from frozen `cap-1`: change only app/library binding, output/stats paths and the three inherited observation FDs. Keep settings, input, request, cap environment and every codec argument exact.
5. Copy and verify the exact frozen pass1 stats SHA. Do not run a new pass1 or describe trace-v2 runtime as two-pass policy cost.
6. Require successful completion of all observation streams and exact equality of trace-v2 versus `cap-1` IVF SHA/size, reconstruction SHA/size, and stats SHA/size before parsing delivery evidence. Re-run all-frame decoder/media identity on the immutable `cap-1` policy output; a separate decode of trace-v2 is unnecessary once both IVF and app recon are exact, though its native observer joins must use the exact trace-v2 bitstream identity.
7. Update provenance/admission schemas to state this cross-build lineage explicitly. Do not make the old one-build invariant accept both structures ambiguously.

## Interpretation boundary

On success, delivery records from corrected trace-v2 may be joined to `cap-1` because their complete coded and reconstructed outputs are identical. Quality, packet rate and normal two-pass runtime come from unobserved `cap-1`; trace-v2 wall time is diagnostic observer overhead only. The correction supplies no speed result and cannot change the cap intervention or acceptance gates.

If corrected trace-v2 differs in IVF or reconstruction, stop the join. Then the smallest isolation is one corrected-build cap replay with all observation FDs absent: equality there would localize the difference to active observation; inequality would expose build/source drift and require restoring the full control chain before interpretation.
