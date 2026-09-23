# Full-picture spatial policy and independent vetoes

D56 qualifies the explicit `full_picture` diagnostic in `36897c38`. It keeps
the original spatial/cross-component bounds on every picture. Only the training
fold selects among at most four seeds; independent spatial or global-mean
failure rejects that choice without retry. The existing `frame_window` policy
remains explicit and byte-compatible. Neither policy establishes source eligibility.

## Evidence

- Full CPU: 214 Python tests in 30 suites plus 46 C++ programs. Four prior
  candidate replays preserve exact models/bytes. All four original strict
  candidates reject; three invalid-policy/old-library controls also reject.
- Five positive and three expected-negative GPU encodes. The consumer checks
  the engine's policy confirmation, preventing an older ABI-2 library from
  silently ignoring the requested strictness. Both legacy 8/10-bit outputs
  preserve all reference models, readiness and AV1 payloads exactly.
- Both decoders agree across 320 fresh observations. Independent checks verify
  62,914,560 samples each for original source, pre-encode candidate and NVENC
  reconstruction. A separate AOM oracle matches 62,914,560 synthesized samples.
- Constructed normative grain over a known clean constant base passes all 16
  full-spatial checks at both native depths, independently confirmed with NumPy.
  The actual NVENC 8-bit output also passes all 16 and nine sliding windows.
  These are constructed mechanism controls, not new real-source admission.
- The 10-bit actual reconstructed candidate is **rejected at picture 0**. Both
  spatial folds pass, but Cr mean error is 0.2279816 in 8-bit code units, exceeding
  the unchanged 0.125 bound. Its first spatially accepted seed cannot be retried
  based on a mean that includes independent pixels. No strict 10-bit output is
  published. The original legacy full-spatial results remain 0/32.

This rejection motivates separately measured training/check means. Such evidence
can inform a training-only seed choice without exposing independent pixels to
selection; the final independent and global vetoes must remain. It is not a
reason to relax thresholds or count a failed partial encode as source fallback.

## Reproduction and continuing work

Read `roadmap-r3-strict-candidate-policy-20260923/{cpu-report,known-source,encodes,
comparison,drain-pause}.json` in the private evidence root. `check.py` preserves
independent comparisons and hash receipts for retired oracle scratch. Native
library ABI 2 retains nine private exports, with no dynamic AOM/FFmpeg dependency.
Diagnostic binary SHA-256:
`fb07687265c3bc7d4c7ae079bd6f7a46664c716eac5f7ba73581d04a1c52d140`.

All owned Tdarr pauses are released and current limits preserved. Continue
training-only mean evidence, bounded automatic fractions, source/detail
eligibility and R4–R8. Production remains ordinary `cb903a17`, retention/FEL off;
reserved footage is unopened. Nothing is scheduled to restart automatically.
