# R16: temporal filtering disabled at the original packet budget

Status: rate calibration in progress; no R16 quality conclusion.

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
proportional correction selects request 10070 with fresh two-pass statistics.

The [preflight manifest](psyex-tf0/preflight/manifest.json) preserves the exact
runner, provenance, packet records, commands, reviews and prepared validation
scripts. Preparation reviews required corrections to recursive calibration
lineage, live dependency hashes and recorded packet-rate checks. The final
runner and replay were released after those corrections. An outer execution
receipt retains failures even before the inner runner can create its receipt.
The early inline lineage smoke lacks preserved source; its limited provenance
is explicitly recorded and is not substituted for review of the actual runner.

The selected arm must still pass all336 decoder identity, independent syntax
binding, encoder/decoder instrumentation neutrality and native coefficient
joins before quality interpretation. Unchanged GPU campaign metrics, frozen
texture/quiet/detail controls, full-window tails, banding and temporal evidence
remain required. Full-episode cost and actual playback qualification remain
unresolved; no production change is proposed.
