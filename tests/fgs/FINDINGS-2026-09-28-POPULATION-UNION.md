# Complementary source tests do not resolve whole-picture coverage

D83 measures the union of D82's source-history diagnostic and the original
flat/noise hypothesis on the same two fixed HDR development pictures. Every
native luma pixel and visible border is included. Original source, clocks,
candidate rounding and the earlier measurements are checked before comparison.
No new encoder output, source admission or production change is made.

The flat/noise arm applies R1's numerical tests to native 64-pixel luma regions.
This is an optimistic feasibility bound, not qualification of R1's averaged-luma
joint population: it also omits minimum independent population counts. A second
arm requires all seven adjacent source pairs, and a third retains the prior
detail and history-model vetoes.

| Picture | Pixels supported by the optimistic union | Occupied native brightness codes | Codes with no unsupported pixels | Pixels at those codes |
| --- | ---: | ---: | ---: | ---: |
| 30 | 3,667,968 / 8,294,400 | 499 | 1 | 3 |
| 210 | 3,575,808 / 8,294,400 | 513 | 1 | 1 |

Even the optimistic union separates only four pixels in 16,588,800. Requiring
all source pairs and the existing vetoes leaves zero pixels in picture 30 and
one in picture 210. These counts precede legal-curve interpolation, population
counts, joint-colour and compressed-output checks. They cannot supply a useful
whole-picture grain curve. This is a result for two fixed development pictures,
not a proof that every source is unrepresentable.

Temporal correlation, directional structure, unsupported motion and disagreement
between stationary and linear predictions remain substantive conflicts. Combining
the same tests or refitting their supported patches does not remove them. Missing
evidence remains unknown; none of these results justifies relaxing the guards.

The next bounded feasibility check uses already captured source and actual NVENC
reconstructions to ask whether grain lost during compression of a fully retained
source can be recovered. It does not authorize attaching grain to an ordinary
fallback, change the source-copy grain-off contract, or resolve unknown real
source eligibility. A useful finite result is required before adding a runtime
path. Automatic retention, temporal qualification and quality/bytes evidence
remain unfinished.

Evidence: `roadmap-r3-population-union-20260928/plan.json`, `study.py`,
`measurements.jsonl`, per-picture lookup censuses and `report.json` under the
[local handoff root](WORK-TO-PRODUCTION.md). Reserved qualification footage
remains unopened. The CPU study took 5.47 seconds; this is not a throughput
measurement of an encoder feature.
