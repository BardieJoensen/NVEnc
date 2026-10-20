# R16 midpoint-refinement package review — rejected revision 1

Reviewed 2026-10-20, before any refinement encode. The reviewed files are:

- `encode_refine.py` SHA-256
  `0c467289ef6e1bddeb966665c406ac52383ae05d4bd132e1b361f6bb339df9f5`
- `replay_refine.py` SHA-256
  `c4eedb26873066a6c7e6b8c2045687c79aae050a7babafce18267e5271d0cfbc`
- `runner-diff.patch` SHA-256
  `3f00eacaee2a366fe8bbc06ea4da081b019860975f9fb773516763ef82cd5ab8`
- addendum `ROUND16_RATE_REFINEMENT.md` SHA-256
  `9ea9b3bd9dcf4c5a7f994e0eb12508448a93142ad9d7b7baec27f5ea21597d82`

The unchanged encoding body and initial arithmetic are correct: the old 10014
and 10070 receipts are fully passed through the frozen old validator, 10042 is
the floor midpoint, commands remain TF-off with no QP bounds, and each output
uses fresh statistics. The revision is nevertheless **not released** because
its admission and replay paths do not prove those facts for a completed node.

## Blocking defects

1. `validate_chain` at lines 90--133 is the inherited proportional-chain
   validator, but its live-script and contract constants now identify the new
   midpoint runner. It cannot validate either an old receipt or a valid new
   10042 receipt. A public validator used by replay/binding must validate new
   refinement nodes; old receipts should be delegated to the hash-pinned old
   module.
2. `validate_refine` at lines 135--172 verifies only a subset of a receipt and
   trusts its recorded bracket. It does not reconstruct the exact initial old
   endpoints, midpoint, later transition, endpoint replacement, formula,
   source/app/library/R8 identities, or pass TBR. Consequently a self-consistent
   hash does not establish the calibration state that selected the run.
3. The memo branch compares `memo[path]` (a `(receipt, paths)` tuple) directly
   with `expected_sha` (a string) at line 142. Store the SHA separately or store
   `(sha, receipt, paths)` and compare the SHA member.
4. The old runner is executed by `exec_module` at line 235 before its SHA is
   checked at line 236. Verify the file hash first.
5. The first invocation accepts any old receipts that validate and happen to
   report requests 10014 and 10070. Require the canonical old receipt paths and
   the known SHAs `02bc2093...` and `690beb60...`, then validate both old
   ancestries and recomputed packet rates.
6. `replay_refine.py` is still the old R8 replay. Lines 20--21 hard-code
   `psyex-1x1`; lines 73--75 bind R8 artifacts; and lines 87--94 replay R8's
   pass-two command. It neither imports the refinement validator nor accepts a
   selected refinement receipt. A corrected replay must take the selected
   refinement receipt and SHA, require matched/under-cap status through the
   complete public validator, use that run's fresh statistics/pass-two command,
   and compare its off/on outputs to the selected refinement IVF and
   reconstruction. Its identity set must retain the complete old and new
   calibration lineage.

## Minimum complete new-node validation

For attempt 1, validate the exact canonical low/high old receipts, their frozen
old lineage, their recomputed rates, the exact target interval and request
10042. For each later attempt, recursively validate the immediately preceding
new receipt, require it to be unmatched, derive the transition from its actual
rate, reconstruct the new endpoint dictionaries, and recompute the floor
midpoint. For every node, require a strictly interior request and a measured
rate in the **closed** endpoint-rate interval; endpoint equality is a valid
plateau. Also require the low endpoint below 9.579757176 and high endpoint above
9.6765224, attempt index 1--3, exact policy/source/input/app/library/R8 command,
pass-one/pass-two TBR, packet recomputation, and live before/after identities.

The independently reviewed header parser needs no lifecycle changes. Its
refinement adaptation is intentionally withheld until the corrected public
validator and runner SHA are frozen; otherwise it would pin a rejected script.
