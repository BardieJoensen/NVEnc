# R16: temporal filtering disabled at the original packet budget

Status: initial calibration completed; reviewed midpoint refinement running.
No R16 quality conclusion.

The [contract](ROUND16_TF0_BUDGET_CONTRACT.md) tests the admitted R8 policy with
only temporal filtering disabled and the bitrate request calibrated to
99–100% of the untouched original's 9.6765224 Mbps scored-window packet rate.
No public QP bounds or static QP change are used. TF-off changes the coding
input and reference/search policy together; this is not an isolated pixel
ablation.

The first request, 10313 kbps, produced **9.8804608 Mbps** over scored frames
96:336, exceeding the ceiling. Its full 336-frame rate was 10.2541509 Mbps.
Passes took 64.6435 and 311.1749 seconds, totaling **375.8184 seconds**.
This arm is ineligible for the decisive quality comparison. The prescribed
proportional corrections used fresh two-pass statistics:

| Request kbps | Scored Mbps | Full336 Mbps | Two-pass seconds | Eligibility |
|---:|---:|---:|---:|---|
| 10313 | 9.8804608 | 10.2541509 | 375.8184 | Above source |
| 10070 | 9.7013600 | 10.0236371 | 373.0344 | Above source |
| 10014 | 9.3933528 | 9.9653091 | 375.4678 | Under cap; outside matched interval |

The last request decrease produced a much larger scored-rate change per kbps
than the preceding decrease. The [method addendum](ROUND16_RATE_REFINEMENT.md)
therefore replaces proportional feedback with bounded midpoint refinement
between the measured 10014/10070 endpoints, starting at 10042. Only bitrate
request and fresh paths change. The source ceiling and matched-rate interval
remain fixed. Endpoint-equal rates are allowed as quantizer plateaus; they still
narrow the request bracket and do not by themselves imply nonmonotonicity.
The [completed calibration records](psyex-tf0/calibration-initial/manifest.json)
retain both later attempts and the reviewed method correction.

The [refinement preflight](psyex-tf0/refinement-preflight/manifest.json) freezes
the corrected runner/replay, independent binder, observation/scoring wrappers,
no-encode preview and synthetic validation controls. Review rejected an
incomplete lineage validator and a replay incorrectly based on the old R8
encode. The parent replaced them with explicit endpoint/predecessor validation
and replay of the selected refinement's own pass-two command and statistics.
Four valid synthetic states and five corrupted states behaved as prescribed;
these are software controls, not measured encodes. The first real midpoint
request is 10042. No quality gate was changed.

The [preflight manifest](psyex-tf0/preflight/manifest.json) preserves the exact
runner, provenance, packet records, commands, reviews and prepared validation
scripts. Preparation reviews required corrections to recursive calibration
lineage, live dependency hashes and recorded packet-rate checks. The final
runner and replay were released after those corrections. An outer execution
receipt retains failures even before the inner runner can create its receipt.
The early inline lineage smoke lacks preserved source; its limited provenance
is explicitly recorded and is not substituted for review of the actual runner.

Once a matched arm exists, it must pass all336 decoder identity, independent syntax
binding, encoder/decoder instrumentation neutrality and native coefficient
joins before quality interpretation. Unchanged GPU campaign metrics, frozen
texture/quiet/detail controls, full-window tails, banding and temporal evidence
remain required. Full-episode cost and actual playback qualification remain
unresolved; no production change is proposed.
