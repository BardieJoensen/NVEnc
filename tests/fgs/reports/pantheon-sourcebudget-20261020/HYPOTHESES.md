# Current hypothesis ledger

Updated after admitted and independently reviewed Round12 scalar-rule/precision diagnostic. No candidate qualifies; no technical blocker or
playback observation exists. Practical ceiling remains original video payload
rate; all texture, clean-region, detail, banding and temporal gates are unchanged.

| Hypothesis | Support | Contradiction or limitation | Unknown | Cheapest next discriminator |
|---|---|---|---|---|
| Libaom coding-source sample substitutions dominate loss | R4 finds sparse changes elsewhere and R5 changes reconstruction | Libaom target input is already original; all-event neutralization fails at matched rate | Retained upstream analysis/reference policy | Defer this libaom route; unchanged neutralization reruns add no information |
| PSYEX upstream sample processing explains texture loss | R9 shirt HF .6063→.4413 before EncDec | Background input nearly unchanged; shirt falls further to .0937 before filters | Which upstream component and feedback effects matter | Source audit now; retain TF-off as a separate policy intervention after final coding map |
| Finer actual quantization can restore meaningful texture | R7 delivers shirtq32/backgroundq32–36 and substantially improves texture/detail | At4.01686×source it still fails shirt and background texture screens | Other precision/decision policies; no general quantization impossibility | Stop global qmax repeats; identify a distinct decision policy before another real arm |
| Later coefficient processing is independently important | Libaom R7 optimizer-only shirt stratum HF.544→.214; dropout is absent there | PSYEX R11 later optimizer changes no shirt units and only six of2151 positives across allROIs; noise changes none | Encoder/policy-specific decision costs; cannot transfer libaom attribution to PSYEX | Defer optimizer bypass on PSYEX; its initial scalar stage is the observed loss boundary |
| Selected skip/transform decisions constrain reconstruction | R7 removes reduced64 shirt support and raises exercised fraction46.88→67.84% |32.16% still unexercised; fixed raw mosaic itself misses whole-shirt amplitude | Whether available residual candidates lose mainly on rate/distortion cost or are already inadequate | Inspect coefficient, TU-skip and coding-block decision margins together; no final-only bypass |
| Native scalar choice/precision accounts for remaining PSYEX texture loss | R11 isolates large initial scalar loss; R12 q32 restores much background/face structure | Same-q B worsens allROIs; q32 shirtHF only41.39%source and ACFerror.393; rawshirt itself misses source | Remaining scalar floor versus upstream/selected-decision loss | One q1 replay with distances to raw, then stop scalar sweep; real budget feasibility remains open |
| In-loop filtering alone causes the PSYEX loss | R9 filters further reduce shirt/background/face HF | Pre-loop shirt already loses84.55% of source HF; postloop improves MSE and shirt ACF | Individual filters and feedback on later frames | Do not infer a repair from unfiltered stills or run a filter-only sweep |
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

Round8 supplied and tested that distinct policy. Its fixed bundle failed both
texture gates at99.4976%source,370.336s for336frames despite admitted runtime
delivery. R9 now admits the exact pre/post boundaries of frame120, including
source-processing loss on shirt and additional coding/filter losses with mixed
error tradeoffs. There are no quiet tiles in this single-frame population.

R10 completed accepted final ownership and residual-state observation with exact
preloop identity. Stored qindex and reused/stale buffers still cannot establish
actual forward quantization. R11 must prove coefficient producer lineage through
normal EncDec or MD reuse/bypass before interpreting scalar versus later losses.

R10 rejects predictor-only syntax as the dominant target coverage explanation.
Shirt predictorHF.09038→preloop.09367 versus.60632source; background.36803→1.28050
versus1.67639source. Residuals improve MSE, but shirt source-HF correlation stays
nearzero. Exact decoderq71shirt is normative, not actualforwardq. Next discriminate
initialquantization versus laterremoval on finalcommitted encoder owners, requiring
explicit MDreuse/bypass provenance and exact decoderjoin. See DECODER_MAP.md.

R11 completes that producer lineage: all510 pre-dispatch route assertions prove
normal finalEncDec, all2907 tokens join committed owners, all2151positiveDQ/EOB/
IQM agree with R10 after exact independently proven storage permutation.
Actualforwardq is now established (shirt71/background79–87/face71–115).
Initial scalarFP accounts for the decisive observed coefficient-stage loss on
exercised support; face34.37% never invokes finalquantization and remains separate.
The raw local diagnostic itself does not fully match original shirt, so a
quantizer-only success cannot be assumed. Next: same-q nativeB vsFP and a lower-q
FP control, exact baseline first. No real encode or bitrate claim yet.

R12 accepts exact native delivery on all2187 invoked TUs,720 unchanged owners.
Independent full-ROI recalculation agrees within1e-12. B is a negative result;
q32 improves background/face locally but fails joint shirt preservation. No rate
or full-window/quiet/playback inference. R13 predeclares one q1 point to measure
the residual distance to raw, then moves upstream/decision policy. This is a
diagnostic closure, not a relaxed repair gate. See PSYEX_SCALAR.md.
