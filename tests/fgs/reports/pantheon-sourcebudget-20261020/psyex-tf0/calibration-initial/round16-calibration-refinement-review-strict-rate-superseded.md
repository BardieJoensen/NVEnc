# R16 TBR calibration-refinement design review

Reviewed 2026-10-20. This is a method review only; no encode or quality result
was produced or inspected.

## Evidence fixed before the refinement

The base contract is `ROUND16_TF0_BUDGET_CONTRACT.md`, SHA-256
`5ed81849c12af6daeb206e2184fa7ad0ddacb4b6d7d3ec35fab3b845c9901c71`.
The frozen runner's three completed receipts are:

| request (kbps) | measured scored MKV rate (Mbps) | receipt SHA-256 |
|---:|---:|---|
| 10313 | 9.880460800000002 | `90b6df06c93ae6e048ee37f0584f17b658f38c674af81fb03ccc785c34271a33` |
| 10070 | 9.70136 | `690beb605f882ddb9748f4e23f4aabc604cca1027f019b5ad09004b9b31b442a` |
| 10014 | 9.3933528 | `02bc209310beb0c88d72c9ca40deb621ce07b2694dfd52bc9ddc5db5219deadd` |

The unchanged acceptance interval is
`[0.99 * 9.6765224, 9.6765224] = [9.579757176, 9.6765224] Mbps`.
Thus `(request=10014, rate=9.3933528)` is a valid low endpoint and
`(request=10070, rate=9.70136)` is a valid high endpoint. The first integer
midpoint is exactly 10042.

The measured slopes are materially different: approximately 0.000737 Mbps per
requested kbps between 10070 and 10313, versus 0.005500 Mbps per requested kbps
between 10014 and 10070. These three observations therefore do not support a
stable proportional or local-linear response model. Bracketed bisection is a
defensible, cheaper continuation; there is no evidence-grounded reason to
change another encoder setting or add a quality discriminator during rate
calibration.

## Minimal state machine and chain checks

1. The addendum must leave the policy, source ceiling, 99--100% comparison
   interval, input, binary/library, two-pass command and quality gates
   unchanged. Only integer TBR and fresh output/log/statistics paths may vary.
   Each trial must use fresh pass-one statistics.
2. The first refinement must hard-bind and validate the frozen three-receipt
   lineage with the frozen old runner's `validate_chain`; it must not reinterpret
   attempt 3 as a matched result. It then binds the exact low receipt (10014)
   and high receipt (10070), including live path, SHA, request and recomputed
   packet rate.
3. Each new receipt records a refinement index 1--3, exact predecessor receipt,
   exact low/high endpoint receipt identities and values, and the addendum and
   new runner identities. Recursively validating the predecessor is sufficient;
   duplicating the entire history into every receipt is unnecessary.
4. Compute the request as integer floor midpoint
   `candidate = (low_request + high_request) // 2`. Require
   `low_request < candidate < high_request`; if the integer bracket is
   exhausted, stop for parent assessment. This fixes 10042 for refinement 1 and
   avoids rounding ambiguity.
5. Before updating the bracket, recompute the candidate's scored MKV packet
   rate using the unchanged `[96:336]` window. Require it to be strictly between
   the currently bound endpoint rates. A result outside that measured-rate
   interval, or one that reverses the request/rate ordering, is a nonmonotonic
   or out-of-bracket response and must stop the refinement for parent review.
6. If the rate is inside `[9.579757176, 9.6765224]`, select it and stop. If it is
   below the interval, replace only the low endpoint; if above, replace only the
   high endpoint. Validate that the retained opposite endpoint is unchanged and
   that the new bracket still straddles the full acceptance interval.
7. Permit at most three additional requests (refinement indices 1--3). An
   unmatched third refinement is reported rather than silently selected or
   extended. `encoded`, `within_source_ceiling`, and
   `matched_rate_comparable` remain separate fields.

The new runner should also reuse the existing live provenance and packet-rate
checks rather than merely trusting values copied into the old receipts. The
scientifically necessary new checks are limited to the frozen old-lineage
admission, endpoint identities, midpoint formula, monotonic interior response,
endpoint update and three-request limit.

## Disposition

The refinement is methodologically sound with the state machine above. The
10042 midpoint is a rate-calibration request only. No quality inference is
available from these rates, and the under-cap but unmatched 10014 result cannot
be substituted for a matched R16 arm.
