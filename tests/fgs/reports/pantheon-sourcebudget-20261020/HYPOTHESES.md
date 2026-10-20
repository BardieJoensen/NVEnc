# Current hypothesis ledger

Updated after admitted Round7. No candidate qualifies; no technical blocker or
playback observation exists. Practical ceiling remains original video payload
rate; all texture, clean-region, detail, banding and temporal gates are unchanged.

| Hypothesis | Support | Contradiction or limitation | Unknown | Cheapest next discriminator |
|---|---|---|---|---|
| Coding-source sample substitutions dominate loss | R4 finds sparse changes elsewhere and R5 changes reconstruction | Target input is already original; all-event neutralization fails at matched rate | Retained upstream analysis/reference policy | Defer this route; unchanged neutralization reruns add no information |
| Finer actual quantization can restore meaningful texture | R7 delivers shirtq32/backgroundq32–36 and substantially improves texture/detail | At4.01686×source it still fails shirt and background texture screens | Other precision/decision policies; no general quantization impossibility | Stop global qmax repeats; identify a distinct decision policy before another real arm |
| Later coefficient processing is independently important | R7 optimizer-only shirt stratum HF.544→.214; dropout is absent there | Initial quantization and skips also lose texture; mixed intra path remains unseparated | Native decision costs and whether a fixed alternative policy retains useful candidates at source budget | Existing policy source audit; otherwise one R3 native decision-margin capture |
| Selected skip/transform decisions constrain reconstruction | R7 removes reduced64 shirt support and raises exercised fraction46.88→67.84% |32.16% still unexercised; fixed raw mosaic itself misses whole-shirt amplitude | Whether available residual candidates lose mainly on rate/distortion cost or are already inadequate | Inspect coefficient, TU-skip and coding-block decision margins together; no final-only bypass |
| Legal grain can distinguish clean and textured areas at comparable inputs | Prior conditional inputs show a local quiet/texture conflict | Only specific white-model probes tested; no global nonrepresentability proof | Other legal model inputs/AR support/base reconstructions | Revisit representability only if a stronger measured base warrants it; never relax quiet protection |

R7 is an unconstrained end-to-end diagnostic, not a matched-rate causal isolation.
Its qmax setting bounds base rate-control selection; objective delta-Q is active
and actual TU quantizers must be measured. A failed qindex32 point would not
falsify all finer quantization. Local coefficient/coder costs remain proxies
until compared with actual legal-encode packet costs.

Independent design review favors an R3 decision-margin observation unless a
pinned existing texture-sensitive policy reaches coefficient optimization,
TU skip and mode decisions with a fixed setting. No original-rate redistribution
of R7 is justified because preservation failed. No gate has been relaxed.
