# Round 8 PSYEX scoring review

Reviewed unexecuted `score_psyex.py` SHA
`d57da6e7771e87ed0b012e4cb68db05fc4af342364c697fe256d737e30846561`
against accepted R7 scorer SHA
`c95ee5246bcee2aaf4167620879edf7c8d3f4b7ef31a88f7789d1443a6734e29`.

## Admission bindings required before execution

1. Pin the accepted PSYEX decoder validator SHA
   `a32f685a4040cb10f7028ef8280920c2eb6d85225c26f78e24217f9e5c686d2f`
   and require `decoder.source_script.sha256` to equal it. Lines 67–71 prove
   only that the validator currently on disk matches the receipt; a different
   self-consistent validator could otherwise be admitted.
2. Once the runtime-delivery validator is stable, require its reviewed script
   identity explicitly, not merely arbitrary identities supplied in
   `validation.artifacts`. The future admission schema should bind exact
   case/tag, original receipt, unmodified installed IVF, observation-off/on
   streams, and the validator script. The existing checks at lines 38–42 are
   appropriate after that named script binding is added.

These are narrow provenance corrections; metric logic need not change.

## Verified unchanged acceptance

- The completed encoder receipt, live input/binary identity chain, IVF/MKV/app
  reconstruction, runtime-delivery admission, and fresh assessment are checked
  before scoring (`:28–45`).
- Packet positions 96:336 are freshly measured. Admission requires 99–100% of
  the original 9.6765224 Mbps ceiling and within 1% of the immutable R3 arm;
  the retained runner packet receipt must independently say the decisive gate
  passed (`:46–60`). Thus the scorer cannot reinterpret an unconstrained or
  lower-rate calibration as the matched practical result.
- The corrected decoder receipt binds the exact encode and requires all 336
  app/dav1d/libaom/NVDEC full-frame hashes. The newly decoded scored stream must
  equal hashes 96:336 for all 240 full YUV420P10 frames (`:61–79`).
- The GPU campaign and texture calls are inherited unchanged from R7. They use
  the established fixture reference, not a prior encode. The source raw is
  freshly bound to the archived original (`:76–89`).
- All 12,870 frozen tiles across the predeclared 15 frames are required, their
  source descriptors are recomputed exactly, and candidate mean/p95, signed-HF,
  face, quiet/edge/flat/other, and legacy-outside-mask controls are retained
  (`:80–124`). No PSYEX ROI is implied.
- Both prescribed five-frame midpoint regions retain HF ±10%, ACF1 error ≤.05,
  and source-HF correlation reporting (`:125–129`). Full temporal, full-reference
  metric/tail, and CAMBI artifacts remain products of the unchanged shared
  campaign/texture path; no threshold is loosened.

The final label should continue to describe this as a matched-rate bundled-policy
feasibility screen. Even with runtime delivery, it is not isolated psy-rd,
sharp-tx, or noise-normalization causality, and `playback_observed=False` is
correct.

**Status: conditionally accepted after the two explicit validator-SHA bindings.**

## Final disposition after focused correction

Reviewed scorer SHA `b9c3b2a6145504f1dbe2137503bd892963195b791b10f6308838d9995885ec89`.

**Accepted for execution, conditional only on a successfully produced admission receipt.** Lines 38–54 require both `status=admitted` and `policy_delivery_pass`, pin final admission-validator SHA `c0cf3c...`, live-check that validator source, bind case/tag and the original encode/IVF, bind both neutral off/on replay receipts and their IVF/reconstruction identities, and live-rehash every admitted artifact. Lines 73–86 pin accepted decoder-validator SHA `a32f68...`, bind it to the exact run/MKV/reconstruction, recheck its before/after identities and all command outputs, and retain all-336 decoder agreement. These resolve both prior conditional findings; the quality campaign and thresholds remain unchanged.
