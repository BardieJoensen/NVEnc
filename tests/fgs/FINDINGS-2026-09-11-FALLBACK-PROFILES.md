# Joint fallback decisions and focused diagnostic targets

The next retention experiment must distinguish frequently rejected checks from
the combinations of checks that actually occur on a frame. The diagnostic
report now makes those joins, and six completed full-episode logs have been
reanalyzed. No encoder, decoder, media metric or GPU workload was run. Encoder
code, thresholds, production settings and the running repair remain unchanged.

## Report changes

`retention_diagnostics.py` schema 2 retains the existing marginal counters and
adds two views:

- `source_reason_overlap` partitions source-preserved frames by their exact
  recorded reason masks, separating single/multiple reasons and unknown legacy
  reasons. It does not assign absent masks from indirect events.
- `decision_profiles` joins final outcomes with covariance blockers, available
  held/fresh colour reasons, logged local mismatch, and component-restoration
  decisions/reasons. Counts, first/last frames and the longest uninterrupted
  run of each profile support choosing short diagnostic excerpts.

Local-refit messages and later mismatch messages can coexist on a frame. A
refit alone does not count as a mismatch. Missing frame IDs and intervening
decisions break profile runs. Absent events do not establish that a check ran
and passed. Component eligibility is kept distinct from an unattempted check.

These are observed combinations, not counterfactual results. Changing a model
can change later checks and temporal state. Even a frame with one recorded
reason does not prove that removing that check would recover it, or quantify
any byte saving. The report is not a visible-damage classifier.

## Findings from the existing qualified-build logs

All six log hashes still match the previous analysis. All 459,396 ordered
frame decisions are accounted for, and every existing counter, blocker count,
source-reason count and longest source-preservation run remains identical.
The final streaming analysis took 26.44 seconds under a 50% CPU quota, with
low CPU/I/O priority. This is analysis time, not an encoder speed measurement.

The automatic arms show substantially different combinations:

| Full episode | Held-colour rejections | Also logged a local mismatch | Share |
| --- | ---: | ---: | ---: |
| South Park S23E01 | 21,106 | 17,717 | 83.94% |
| The Gentlemen S01E01 | 68,479 | 10,643 | 15.54% |
| House of the Dragon S03E08 | 83,692 | 554 | 0.66% |

This supports separate diagnostic targets for animation and the two live-action
sources. In particular, the South Park colour-rejection count alone hides a
large overlap with local grain-amplitude mismatch. It does not prove that the
two conditions need independent fixes: a better fit could affect both.

Successful covariance recovery also does not imply final synthesis acceptance:

| Full episode | Successful covariance recoveries | Final source preservation | Those with a logged local mismatch |
| --- | ---: | ---: | ---: |
| South Park S23E01 | 48 | 48 | 34 |
| The Gentlemen S01E01 | 684 | 604 | 2 |
| House of the Dragon S03E08 | 7,691 | 7,307 | 64 |

The remaining reasons cannot be assigned from these legacy logs. In particular,
the HDR episode's 7,243 recovered-but-source frames without a logged local
mismatch do not establish whether coarse strength, DC, recovery history or
another recorded-only-in-new-traces condition was decisive. Its 4,113
`model_or_fresh_colour_unknown` events likewise remain ambiguous. The prepared
version-1 encoder traces are needed to resolve those questions.

## Initial diagnostic excerpts

The selection uses a common profile's longest recorded run, with at least ten
nominal seconds of preceding context. Each new excerpt requests 720 frames,
about 30 seconds. Times below are planning coordinates derived from full-run
frame IDs and nominal frame rate; source alignment has not been rechecked.

| Source / purpose | Nominal seek | Historical target frame |
| --- | --- | ---: |
| South Park: colour rejection with local mismatch | 00:01:18 | 2,127 |
| The Gentlemen: common held-colour rejection | 00:40:12 | 58,149 |
| House of the Dragon: common held-colour rejection | 00:27:04 | 39,191 |
| House of the Dragon: failed fit or fresh-colour check | 00:30:00 | 43,410 |
| House of the Dragon: recovered fit rejected later | 00:06:30 | 9,607 |
| House of the Dragon: accepted recovery control | 00:04:38 | 6,922 |

The existing 90-second Gentlemen jacket window at 00:33:24 remains a regression.
Combined nominal source duration is 270.15 seconds per encoder variant. These
targets precede the broader quality/size matrix; they do not replace its seven
windows, metadata controls, synthetic regressions or matched-size review.

After repair, verify source hashes/alignment and reproduce each target with the
qualified `9c1664d4` baseline. A short excerpt resets temporal history. If a
target does not recur, extend context before interpreting a different outcome.
Keep the diagnostics/covariance-skip source at `5450a4fc` separate from the
intentional model-hold correction at `3ac80ceb`: the former requires checks for
preserved output, while the latter requires temporal and picture qualification.
Neither new build has been produced or GPU-qualified. No automatic execution
has been scheduled.

## Verification and artifacts

Thirteen diagnostic tests pass, including equal marginal counts with different
overlap, precise/legacy mixtures, colour subcondition joins, local refits,
missing-frame boundaries and interrupted runs. The seven tradeoff tests also
pass. The encoder's C++/CUDA files did not change in this report iteration; its
previous CPU qualification remains separate from pending GPU qualification.

Private artifacts are under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/fallback-profiles-20260911/`:
`existing-profiles.json` binds all six original log hashes and the analyzer
hash; `pilot-selection.json` binds the analysis and retained-source manifest,
records exact profiles and source hashes, and preserves the baseline binary
pin. Sources were matched to the prior full-source manifest without reading
media payloads. The original comparison manifest and 70-command plan are
unchanged. The shortlisting and analysis scripts remain alongside the private
preparation workspace.
