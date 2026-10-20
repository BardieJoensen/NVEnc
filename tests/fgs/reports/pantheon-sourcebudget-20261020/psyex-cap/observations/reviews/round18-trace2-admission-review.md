# Round 18 corrected-trace admission review

## Identities

- `trace_provenance2.py`:
  `1111b50a7b8272e280ca326207ac4ba314cc639910d861d5e83bab856e08b037`
- `cap_semantics2.py`:
  `c94327149138fb95d347ae409c8deed29d75566d2381795e5f806f7a93341acb`
- `admit_cap_trace2.py`:
  `0782ee6a4b4f44f49bb807dc95432a7b690a6306482d9a02f832e4bc478bb553`
- Reviewed nominal admission:
  `b5a9c506e58fc897b695ea2a87e06c8b07d0dd4e798190fc752a0a0f1c004645`

No trace result existed or was inspected for this review.

## Semantic factorization

The factored semantic body retains the nominal admission gates. The only input
rewrite is deliberate: the old main loop iterated
`read_records(trace["path"])`; `evaluate` iterates the already parsed
`records` argument supplied by the new main. From construction of
`groups`/`sequences` through the final population assertions, the picture,
generation, ordering, cap application, selected-SB geometry, lambda,
accepted-generation, final-block, TU, q/EOB/skip, transform-dimension,
coverage, offset, and algebraic closure checks are unchanged.

`SELECTED`, `TX_DIMS`, and `lambda_check` are imported from the exact
reviewed nominal script, whose SHA is pinned before use. The new return merely
packages the previously computed values; `decode_orders` and `order_hints`
are additional transparent output fields, not new or weakened gates. Trace,
receipt, provenance-index and script before/after checks remain in the new
main around the pure evaluation.

## Two-domain provenance

`trace_provenance2.validate` correctly joins:

1. the immutable policy index through the reviewed
   `policy_provenance.policy` validation of baseline/pass1/cap and build 1;
2. the exact observer-build index through
   `policy_provenance.build(..., "observer")`;
3. the corrected replay's inner receipt and successful outer launch.

It reconstructs the exact replay command from cap-1, substituting only the
observer executable and fresh stats/IVF/reconstruction paths. It requires the
exact observer build pins, old cap parent/control links, cap settings/source/
request/contract, correction addendum, exact loader plus cap and three
distinct FD environment, and the reviewed replay producer. The outer command
is reconstructed as `replay_observer2.py <tag>`, so preview mode cannot be
admitted.

The completed replay must expose exactly the seven expected outputs. All are
live-rehashed. IVF, the complete 336-frame reconstruction, and pass statistics
must match immutable cap-1 in both size and SHA. Trace files are bounded, all
input identities remain unchanged, and the resource gates are retained.
Consequently the semantic trace is attached to the corrected observer build
without moving the policy/rate/quality facts out of the original build domain.

## Output and circularity

The admission result retains the exact replay receipt, R18 trace, provenance
index, reader and all scripts used. The pure evaluator does not consume its own
output or any later quality result. Native coefficient/decoder admission
remains explicitly separate.

The new admission script records and rechecks its own identity but does not
hardcode its own SHA. Therefore its actual launch must be retained under the
standard outer wrapper (or its result must be consumed with the reviewed SHA
above). This is an execution-provenance condition, not a semantic blocker in
the reviewed source.

## Disposition

**Released for nominal corrected-trace admission and bounded corruption
controls after the observer replay completes successfully.** No quantizer,
coverage, lambda, native-decoder, or policy outcome is established by this
preflight review.
