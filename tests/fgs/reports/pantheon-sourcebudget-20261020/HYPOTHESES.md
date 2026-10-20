# Current hypothesis ledger

Updated after admitted Round6. No candidate qualifies; no technical blocker or
playback observation exists. Practical ceiling remains original video payload
rate; all texture, clean-region, detail, banding and temporal gates are unchanged.

| Hypothesis | Support | Contradiction or limitation | Unknown | Cheapest next discriminator |
|---|---|---|---|---|
| Coding-source sample substitutions dominate loss | R4 finds sparse changes elsewhere and R5 changes reconstruction | Target input is already original; all-event neutralization fails at matched rate | Retained upstream analysis/reference policy | Defer this route; unchanged neutralization reruns add no information |
| Finer actual quantization can restore meaningful texture | R6≤32 raw reconstruction closely matches source; initial FPq65 removes most shirt texture | Later optimization, skips and reduced64 support also lose detail | Whether real finer quantization changes decisions enough, and at what rate | R7 one qmax8 real arm with actual TU delivery and full-window quality checks |
| Later coefficient processing is independently important | Initial→final loses substantial background amplitude and further shirt detail | Initial background structure already differs; q32 alone not yet observed | Optimizer versus dropout; persistence at finer q | If R7 still fails after delivered precision, fixed-decision initial/post-optimization q32 diagnostic |
| Selected skip/transform decisions constrain reconstruction |53.12% shirt skipped;17.28% reduced64 support; raw fails there | Exercised≤32 raw succeeds, so no general transform limitation | Whether alternate real decisions improve within source budget | Compare R7 realized coverage/transform populations; then targeted decision intervention if warranted |
| Legal grain can distinguish clean and textured areas at comparable inputs | Prior conditional inputs show a local quiet/texture conflict | Only specific white-model probes tested; no global nonrepresentability proof | Other legal model inputs/AR support/base reconstructions | Revisit representability only if a stronger measured base warrants it; never relax quiet protection |

R7 is an unconstrained end-to-end diagnostic, not a matched-rate causal isolation.
Its qmax setting bounds base rate-control selection; objective delta-Q is active
and actual TU quantizers must be measured. A failed qindex32 point would not
falsify all finer quantization. Local coefficient/coder costs remain proxies
until compared with actual legal-encode packet costs.
