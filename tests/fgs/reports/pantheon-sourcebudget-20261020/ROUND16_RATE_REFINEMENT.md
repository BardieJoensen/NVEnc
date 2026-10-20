# R16 calibration-method addendum

The original contract permits the supervising investigator to reassess calibration
after three requests. Those completed requests were:

| Requested kbps | Scored actual Mbps | Source-rate status |
|---:|---:|---|
| 10313 | 9.8804608 | Above ceiling |
| 10070 | 9.70136 | Above ceiling |
| 10014 | 9.3933528 | Below matched interval |

The last 56 kbps request reduction changed scored output by 0.3080072 Mbps.
Proportional feedback has not reached the required interval. Replace it with
bounded midpoint refinement using the observed under/over bracket. This changes
the calibration method only; retain the same source, encoder policy, source cap,
99–100% matched interval and all quality gates.

Freeze the old runner, all three runs and their receipts. Use a new runner and
fresh output/statistics directories. Initial bracket endpoints are the completed
10014 and 10070 requests, with their exact receipt hashes bound. The next request
is the integer midpoint `floor((low.request + high.request) / 2)`, initially
10042 kbps. The low endpoint must measure below 9.579757176 Mbps; the high
endpoint must measure above 9.6765224 Mbps. Both must use the same policy, source,
encoder and packet accounting. Bind every ancestral endpoint receipt.

After each fresh two-pass run, stop calibration if its measured scored rate is
in [9.579757176, 9.6765224] Mbps. Otherwise replace the low or high endpoint
according to its measured rate and choose the next midpoint. Permit at most
three additional requests in this refinement phase. Retain all attempts,
including failures. If a result falls outside the measured endpoint rate range,
or no unused integer request lies between the endpoints, return to the parent
for assessment; do not assume monotonicity or call the rate target impossible.
Do not select based on quality measurements.

No below-interval output substitutes for the decisive matched comparison.
No above-source tolerance is allowed. Full-window damage checks and eventual
full-episode rate/runtime/playback qualification remain unchanged.

Worker owns fresh `worker/psyex-r16-calibration-refine`; parent owns fresh
`parent/psyex-tf0-r16-refine`, integration and Git index. Reviewer remains
independent. No production, unrelated edits or recursive delegation.
CPU affinity/thread policy is unchanged; GPU work remains serialized.
Allow up to 30GB additional R16 evidence including calibration outputs and
observation duplicates, with staging free space remaining above 120GB.
Existing evidence and live dependencies remain in place.
