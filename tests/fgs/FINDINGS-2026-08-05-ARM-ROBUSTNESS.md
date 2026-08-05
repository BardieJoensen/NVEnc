# The guarded response holds in aggregate, not per title — 2026-08-05

> Offline measurement only. Nothing deployed, `modelsrc` default-off.

`FINDINGS-2026-08-05-QVBR-MARGIN.md` established that absolute texture-error
figures in this project swing up to `4.5x` on identical media purely from which
frames are sampled. `FINDINGS-2026-08-04-TEXTURE-RESPONSE-SELECTOR.md` reports
the guarded response arm improving on static source fitting **12/12**, measured
on "six frozen frame pairs" whose identity is not recorded. A 4.5x spread is
more than enough to flip a per-title comparison, so the claim needed re-testing
on an independent frame set.

## Result

Both arms, six architecture films, sixteen frame pairs at `6,23,...,261` —
the set used throughout this session and independent of whatever produced the
original table.

| title | recorded static | recorded response | my static | my response | response wins |
| --- | ---: | ---: | ---: | ---: | :--: |
| Casino | 0.06292 | 0.02103 | 0.03883 | 0.02670 | yes |
| Interstellar | 0.06214 | 0.00575 | 0.06340 | 0.02327 | yes |
| Scarface | 0.01026 | 0.00736 | 0.03430 | 0.02091 | yes |
| Taxi Driver | 0.05455 | 0.02221 | 0.03356 | 0.02405 | yes |
| **The Deer Hunter** | 0.04494 | 0.03086 | **0.01832** | **0.04084** | **no** |
| The Shining | 0.01371 | 0.01252 | 0.05735 | 0.02332 | yes |

**5 of 6, not 6 of 6.** Mean static `0.04096`, mean response `0.02652` — a
**35.3%** aggregate improvement against roughly 60% on the recorded frames.

## What holds and what does not

**Holds:** the direction and the aggregate. Guarded response is better on the
corpus by a third, on frames it was never tuned or measured on. That is the
substantive claim and it survives.

**Does not hold:** the per-title sweep. The Deer Hunter reverses, and the
response arm is `2.2x` worse than static there on this frame set. That title
was already the weakest case in the original write-up, which noted Deer
"improved over baseline, but less than the unguarded arm (`0.03086` versus
`0.01847`), confirming that a fixed margin is conservative rather than free."
On an independent sample the conservatism costs more than it saves there.

**Absolute magnitudes are not comparable at all.** The Shining static reads
`0.05735` here against `0.01371` recorded, Scarface static `0.03430` against
`0.01026`. Same media, same binaries, different frames. Only the within-set
ordering means anything.

## Consequence

Quote the guarded response as a **corpus-level ~35% improvement with one known
per-title reversal**, not as 12/12. Deer Hunter should be the labelled case for
any future margin work, exactly as Interstellar is for the deadzone and
Scarface V is for chroma.

This does not weaken the covariance closure result underneath it: that was
established by exact normative replay against a frozen oracle
(`FINDINGS-2026-08-04-TEXTURE-LEAK-CLOSURE.md`), not by frame-sampled played
error, and the `-76.6%` there is unaffected by this class of error.
