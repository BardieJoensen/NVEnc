# Lookahead, and the qvbr retune it forced — 2026-08-07

> **Deployed to the production Tdarr flow.** Unlike everything else in this
> directory, this changed a live pipeline. Backups:
> `AV1NVENCflow1.backup-20260807-072315-pre-lookahead.json` and
> `...-074900-pre-qvbr-retune.json`.

## What was missing

The flow ran `--preset quality --tune hq --aq --aq-temporal` with no lookahead
and no multipass. A July note recorded the tuned settings as a win but had
measured them in a different configuration, so this re-measured them as
deployed.

**`--lookahead-level` is the entire effect.** On Casino at qvbr 29:

| arm | bytes | vs current |
| --- | ---: | ---: |
| current flow | 26,693,388 | — |
| `+lookahead 32 +lookahead-level 3` | 12,935,164 | **-52%** |
| `+multipass +lookahead 32 +lookahead-level 3` | 12,430,580 | -53% |
| `+multipass +lookahead 32`, **no level** | 26,771,702 | +0.3% |

`--lookahead 32` alone does nothing. The option reads as "enable lookahead and
set depth" and is inert without `--lookahead-level`, which is easy to have and
not benefit from. No warning is emitted either way.

**Multipass was dropped.** 3.9% smaller for marginally *worse* quality (VMAF
93.22 vs 93.27, SSIMULACRA2 46.64 vs 46.96) and an extra pass. A wash that
costs encode speed.

## The 53% is not free, and the iso-size test is what justified deploying

At fixed qvbr the saving comes with a quality cost: VMAF `93.96` -> `93.22`,
SSIMULACRA2 `54.71` -> `46.64`, Butteraugli worse on both norms. Byte count
alone cannot separate "found redundancy" from "targeted lower quality".

Matched to size instead:

| arm | bytes | VMAF | VMAF neg | VMAF min | SSIMU2 | Butter max p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lookahead, qvbr 29 | 12.43 MB | **93.22** | **92.67** | **90.60** | 46.64 | **9.90** |
| no lookahead, qvbr 34 | 12.05 MB | 92.73 | 92.15 | 90.14 | 46.65 | 11.16 |
| no lookahead, qvbr 33 | 14.40 MB | 93.00 | 92.45 | 90.53 | **48.25** | 10.60 |

The no-lookahead arm needs **16% more bytes and still scores lower** on VMAF,
VMAF-neg, VMAF-min and the Butteraugli artifact tail. That tail matters most:
`9.90` vs `11.16` means lookahead *reduces* starved frames rather than creating
them, which was the failure mode to watch for in a rate-control change.
SSIMULACRA2 dissents, favouring the larger no-lookahead arm — three metrics to
one, not unanimous.

## The retune, and why it was mandatory

Lookahead changes what qvbr means, so the flow's 29/34/38 buckets no longer
select the quality they were chosen for. Leaving them would have moved the
whole library to a lower quality point nobody picked.

`bucket_calibration.py` measures, per title, the qvbr under the new settings
that reproduces each bucket's **old VMAF-neg**. Neg is the target because every
arm has FGS enabled and the default model pays an enhancement bonus for
synthesized grain. Three 4K films, 288 frames, lossless references.

| bucket | measured | per-title | saving at equal quality |
| ---: | ---: | --- | ---: |
| 29 -> **28** | 27.9 | 26.5 / 28.4 / 28.9 | 21--32% |
| 34 -> **33** | 32.6 | 31.3 / 33.4 / 33.2 | 19--22% |
| 38 -> **37** | 36.8 | 35.9 / 37.6 / 36.8 | 16--25% |

Bucket 38 initially returned `off-range` on two titles because the first sweep
stopped at qvbr 36 and their targets sat below it; extending to 38/40/42 closed
it. Reporting the Casino-only value would have set a library-wide bucket from
n=1.

**15--32% at equal quality, not 53%.** The two numbers reconcile: 53% is at
fixed qvbr with quality given up, 15--32% is at matched quality. It also agrees
with the independent iso-size estimate of 16--30% bitrate equivalent.

## Deployed

- encode args gain `--lookahead 32 --lookahead-level 3` (no multipass);
- `mapQvbr_001` maps cq 29/34/38 to qvbr **28/33/37**.

The bucket router is untouched — content still routes to the same three
buckets, they simply resolve to different qvbr. The node's `jobLog` line prints
the resolved mapping, so this is visible per job.

## Limits, and what is deliberately not covered

Three grain-heavy 4K films. **The same buckets serve animation and clean
digital content, which were not measured**: their rate-quality curves differ,
and the production analyser additionally over-synthesizes grain on them at
~1.9x (`FINDINGS-2026-08-06-ANIMATION-GATE.md`). Those buckets are now
carrying a film-derived calibration and should get their own pass.

Per-title spread is real. Bucket 29 wants 26.5 on Casino and 28.9 on Taxi, so a
single value slightly over-delivers on one and under-delivers on the other —
inherent to one bucket serving several titles, not a measurement fault.

A conservative alternative, if any quality loss versus today is unacceptable:
27/32/36, which gives up a few percent of the saving.

## Next

The FGS content gate is now the outstanding production item. `--av1-film-grain`
is applied unconditionally by a single encode template, so grain-free content
receives synthesized grain it never had. That is independent of this work and
of the measurement fix.
