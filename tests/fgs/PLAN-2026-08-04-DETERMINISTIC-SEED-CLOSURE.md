# Pre-registered deterministic-seed two-pass closure

Date: 2026-08-04 UTC  
Branch: `fgs/test-automation`  
Authority: research only; no production, Tdarr, routing, or public-option change

## New evidence after the expectation gate failed

The four-seed post-encode solve failed its independent eight-seed expectation
gate: internal maximum luma-band error `0.0145`, external maximum `0.0423`.
Because both evaluations used every block on the same decoded base, the miss
is seed/template expectation rather than response population.

A read-only check of retained fixed-base/table experiments then found that the
actual NVENC seed sequence is deterministic across table-only changes:

- Interstellar original versus centred strength-grid table: 0 mismatches in
  288 frames;
- Interstellar fractional-global versus fractional-local table: 0/288; and
- today's pinned 9.29 fixed-table encode versus the older causal and
  strength-grid encodes: 0/288 in both comparisons.

This supports a distinct hypothesis: a two-pass workflow can solve the second
table against the actual first-pass seeds instead of estimating an average
over seeds.  Determinism must be verified on the resulting pass, not assumed.

## Frozen sequence

Reuse the already completed Interstellar pass 1 and its measured post-encode
targets from `PLAN-2026-08-04-POSTENCODE-STRENGTH-CLOSURE.md`.

1. Run the unchanged full-population quantized response Jacobian with the
   **actual pass-1 side-data seed for each frame**, one seed per frame, and at
   most two iterations.  Source/static population, damping, step bound,
   quantisation and exact post-encode targets stay unchanged.
2. Replay the proposed table on the pass-1 decoded base with those same actual
   seeds.  Every populated luma band must be within `0.020` of its synthesis
   target.
3. Only if step 2 passes, encode the same original clean Y4M with the proposed
   table and otherwise byte-for-byte identical arguments.
4. Require the actual pass-2 seed to equal pass 1 on all 288 frames.  One seed
   mismatch fails the deterministic architecture.
5. Require the grain-disabled pass-1 and pass-2 decoded video MD5 to match.
   If they differ, record the movement but do not re-fit a third table.
6. Require a complete `libdav1d -xerror` decode and exact table/stream model
   match.
7. On the original seven frozen frame pairs, require every populated luma
   band's played-total ratio to be within `0.0442` of 1.000.  Report aggregate
   amplitude, bytes and elapsed encode time without using them to waive a
   band failure.

No extra response iteration, seed averaging, amplitude multiplier, or
threshold change follows a failure.  Taxi Driver and Deer Hunter run only if
Interstellar passes unchanged.

## Interpretation

A pass establishes a technically closed two-encode luma path for this clip:
the same clean input, same coded base, same decoder seeds, corrected metadata.
It still does not approve production; full-title storage/throughput, chroma,
failure recovery, semantic admission and playback remain.

A seed or base mismatch rejects the premise immediately.  A played-amplitude
failure with both identities intact localises the remaining fault to the table
solve or measurement rather than NVENC nondeterminism.

## Resolution

Failed at step 2 and stopped.  The internal actual-seed replay reached a
maximum luma-band error of `0.020699`; the independent per-block replay found
`0.039354`, both above the frozen `0.020000` bound.  No pass-2 encode or
downstream identity test was allowed.

The pre-registration's attribution of the prior disagreement solely to seed
expectation was too strong.  The solver visits every block but collapses its
response to a 20-bin mean before reconstructing the fixed luma bands.  The
independent audit retains per-block response, exposing a large split inside
the analyser bin that straddles luma `0.125`.  See
`FINDINGS-2026-08-04-DETERMINISTIC-SEED-CLOSURE.md`.
