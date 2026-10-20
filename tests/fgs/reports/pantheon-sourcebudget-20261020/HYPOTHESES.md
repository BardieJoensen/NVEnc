# Current hypothesis ledger

Updated after admitted and independently reviewed Round16 matched-rate result. No practical candidate qualifies; no technical blocker or
playback observation exists. Practical ceiling remains original video payload
rate; all texture, clean-region, detail, banding and temporal gates are unchanged.

| Hypothesis | Support | Contradiction or limitation | Unknown | Cheapest next discriminator |
|---|---|---|---|---|
| Libaom coding-source sample substitutions dominate loss | R4 finds sparse changes elsewhere and R5 changes reconstruction | Libaom target input is already original; all-event neutralization fails at matched rate | Retained upstream analysis/reference policy | Defer this libaom route; unchanged neutralization reruns add no information |
| PSYEX upstream sample processing explains texture loss | R14 original samples raise fixed-q1 shirt HF62.79→86.50%source; R15 bundle passes both screens | R16 TF-off fails both screens at99.9310%source; original coding input is verified only on observed frame120 | Interaction with precision and decisions | Hold new R16 choices fixed for one q4 diagnostic |
| Finer actual quantization can restore meaningful texture | R15 delivers actualq4 over all traced support and passes five-frame screens; R16 localizes major shirt loss to scalarq71 | R7q32 failed; R15 costs19.6777xsource and is not quantizer-only isolation | Sufficient precision, affordable redistribution and practical feedback | R17 q4 native replay measures remaining fixed-choice deficit; actual packet cost requires a later real encode |
| Later coefficient processing is independently important | Libaom R7 optimizer-only shirt stratum HF.544→.214; dropout is absent there | PSYEX R11 later optimizer changes no shirt units and only six of2151 positives across allROIs; noise changes none | Encoder/policy-specific decision costs; cannot transfer libaom attribution to PSYEX | Defer optimizer bypass on PSYEX; its initial scalar stage is the observed loss boundary |
| Selected skip/transform decisions constrain reconstruction | R14 original raw misses shirt HF; R16 raw shirt retains86.74% with23.12%64x64 coverage; R15 smaller transforms approach original | R16 all shirt pixels have positive EOB, so missing residual activation is not the dominant shirt explanation | Affordable decision/precision changes and role of large transforms | R17 one q4 point and additive transform strata; do not infer a real-policy limit from fixed choices |
| Native scalar choice/precision accounts for remaining PSYEX texture loss | R16 frame120 original-input shirt rawHF.5259→scalar.1274 at actualq71; later shirt stages unchanged | Raw already misses amplitude; face33.95%uninvoked; filtering adds loss; same-q B previously worsened | Remaining fine-precision deficit on current support | R17 exact nativeq4 fixed-choice replay, not a sweep or bitrate claim |
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

R13 q1 reaches shirtHF62.79%source versus raw64.82%, still failingACF(.0821).
Invoked q32→raw MSE falls to3.78%shirt/1.77%background/2.42%face of its prior
value; q1 remains nonlossless. Uninvoked support dominates background/face q1
squared error. Independent arrays/metrics agree<1e-12. Close scalar sweep and
select R14 original-source nativeforward replay with fixeddecisions/q1. No rate
or candidate inference. See PSYEX_FINE.md and ROUND14_SOURCE_CONTRACT.md.

R14 controls and independent reconstruction pass. Original-source q1 reaches
86.50%shirt HF and ACFerror.04132; raw88.89% still misses amplitude. Source
processing is material, not sufficient under fixed decisions. The next real
bundle lets decisions and feedback change while measuring actual precision,
packets and runtime. It is an unconstrained preservation diagnostic, not an
original-rate repair or isolated TF experiment. See PSYEX_SOURCE.md.

R15 closes that feasibility gap: a legal encode preserves both predeclared E05
texture screens at190.41154Mbps,19.6777xsource,692.477s. All4809 traced owners
are positive-EOB actualq4; input is original and local raw reconstruction is
near-exact. Full controls improve strongly with small regressions retained.
This does not establish affordable precision or a minimum rate. R16 fills the
missing normal-allocation TFoff arm at the original packet budget before
implementing a spatial allocator. See PSYEX_REAL.md and the R16 contract.

R16's initial three requests bracket, but do not hit, the original matched-rate
interval:9.88046/9.70136/9.39335Mbps. No texture hypothesis changes from these
rate-only observations. The cheapest next discriminator remains the same policy
at the original budget; bounded midpoint calibration replaces unstable
proportional feedback. No unmatched result is substituted. See
ROUND16_RATE_REFINEMENT.md.
