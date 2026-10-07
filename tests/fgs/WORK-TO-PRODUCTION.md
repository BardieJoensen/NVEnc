# AV1 film-grain (FGS) encoder: where things stand (2026-10-07)

This is the single entry point. FGS encoder development is paused. The release below is qualified and ready for the user to deploy. Everything else that was tried is parked, with its measured result and the condition that would reopen it. Older entry points (the fidelity worktree's `WORK-TO-PRODUCTION.md`, `/opt/docker-apps/docs/fgs-open-questions.md`) are history and point here.

## The release

- **Branch** `fix/fgs-clean-source-20261006` (this branch). Runtime commit `e78e97f2`; later commits change only tests, fixture pins and documents.
- **Binary** `nvencc` SHA256 `46d6781cab9995de227ebe668765cb91869706bd8399f0c57a86ae4a6fcfdfb8`, a from-scratch build in `nvenc-fgs-build:cuda13.3`, kept at `/tmp/downloads/codex-work/fgs-submission-20261005/bin/nvencc-release-46d6781c`.
- **Contents:** (1) the qualified filter-kernel speedup (about 0.12 ms less GPU work per 1080p frame, identical output); (2) the clean-source fix, "variant D": no synthesized grain on exactly flat luma at any level (letterbox bars, black frames, flat fills) or on flat mid-level colour. Legitimate grain and file sizes are unchanged within about 1%.
- **Release note, deploy steps and rollback:** [RELEASE-NOTE-2026-10-07-BUNDLE.md](RELEASE-NOTE-2026-10-07-BUNDLE.md). Rollback is the current production image `nvenc-fidelity/tdarr-node:2.94.02-aeb14263-20261004` (nvencc `c6cbd528…`, copy at `/tmp/downloads/codex-work/fgs-clean-source-20261006/bin/nvencc-prod-c6cbd528`), redeployed with `scripts/tdarr-node-safe-redeploy.py`. Throughput is to be read from production Tdarr job reports before and after deployment (procedure in the release note).
- **Deployment:** not deployed by this work; the user deploys. No Tdarr flow change is needed.

## The gate

`tests/fgs/run_cpu_tests.sh` (119 Python tests plus the C++ programs) and `tests/fgs/local_gate.sh --full`, run from a clean pinned clone. The full gate has 17 stages: tools, known-answer fixtures, table export, synthetic and real-film libaom oracles, the texture-model and texture-detector negatives, the base-fidelity canaries, **chroma base detail** (new), the periodic-grain regression, grain-header syntax, grain-flash regression, mixed-source, the Play Dirty amplitude regression and the source-variance and training support checks. Each detector carries a labelled negative it must reject.

- **New: `chroma_base_detail`** (`chroma_base_detail.py`). The other base checks look only at luma, so they missed duller colour. This stage encodes the pinned Gentlemen clip, decodes it with grain off, and compares the most colour-structured tenth of chroma patches with the lossless source (amplitude and peak saturation per plane). The floor is the reviewed release output; the candidate may not fall more than 0.002 below it. The parked option-on encode is its labelled negative.
- **Running it:** `DOCKER_APPS=<path view> FGS_GATE_CACHE=<cache> FGS_GATE_REPORTS=<dir> FGS_GATE_HARNESS_COMMIT=<sha> bash tests/fgs/local_gate.sh --full --candidate-nvencc <binary> --amplitude-manifest <manifest>`. The private path view and cache are `/tmp/downloads/codex-work/fgs-submission-20261005/gate-path-view/docker-apps` and `…/gate-cache` (which resolves to `~/.cache/fgs-gate`). The amplitude manifest comes from a full Play Dirty history bound to the binary (about an hour; the manifest is `<output>/amplitude-manifest.json`):

  ```
  cd /tmp/downloads/codex-work/fgs-submission-20261005 && python3 resume_amplitude_history.py candidate \
    --source original-fixtures/play-dirty-source.mkv \
    --negative-report amplitude-histories-resumed/negative/report.json \
    --reference-report amplitude-histories-resumed/reference/report.json \
    --candidate <binary> --candidate-sha256 <sha256> --candidate-core <runtime commit> --output amplitude-final-<name>
  ```

  Pinned fixtures live in `/media/merged-storage/validation-fixtures/nvenc-fgs/v1/`.
- **Latest result with the release binary:** CPU tests pass (119 Python, all C++), and `local_gate.sh --full` passes **24 of 24 checks, 0 failed** (2026-10-07), with harness commit `0b2db87e` from a clean pinned clone and an amplitude manifest from a complete 183,661-frame Play Dirty history bound to `46d6781c` (`/tmp/downloads/codex-work/fgs-submission-20261005/amplitude-final-release-46d6781c`). Reports: `…/reports/full-gate-release-46d6781c-0b2db87e/`.

## Parked

| Idea (branch) | Measured result | Reopen if |
|---|---|---|
| Codec-flat chroma option (`fix/fgs-chroma-codec-flat-20261007`, build `725585b8`; flow patch v43 untracked in docker-apps) | Grain change 0.02-0.2 code values, invisible in a blind TV review. Visibly duller red lips (structured colour Cr 0.905 vs 0.968). Files 1-3% smaller | A chroma separator that passes `chroma_base_detail`, followed by a blind review that prefers it |
| Coarse-band separator (`research/fgs-separator-20261007`, offline prototype) | 2-5% smaller files at fixed QVBR on grainy 1080p, no texture gain (output amplitude flat), structured detail -0.1%, edge error +10-13% | Storage gets tight; budget about 6-7.5 days for a CUDA build and qualification |
| Chroma range threshold from the chroma noise model | No headroom: the release hands NVENC 0.995-1.000 of the source's structured colour in 17 of 19 windows. The colour loss (0.89-0.995) happens in NVENC's coding at QVBR 30; chroma QP offset does not help | A change that submits separator chroma at more brightness levels |
| AR-model rejection of coarse grain | 53-88% of frames on synthetic coarse PQ grain only; never on real footage (Play Dirty, Taxi, Alien) | Real footage shows `rejected` frames in an analyzer trace |
| Knightfall same-shot strength jump | A single event | The same jump in a second title |
| Residual retention | Parked by decision | User decision |
| 4K HDR-specific work | Real evidence is two 24-frame clips (Taxi, Alien) plus synthetic PQ | Before any 4K-specific change: add several-minute 4K HDR windows, frozen before results, outside the reserved corpus |

Evidence: `FINDINGS-2026-10-07-GRAIN-ATTRIBUTION.md` (`research/fgs-fidelity-attribution-20261007`), `FINDINGS-2026-10-07-CHROMA-OPTION-QUALIFICATION.md` (option branch), and `FINDINGS-2026-10-07-CHROMA-DETAIL.md`, `FINDINGS-2026-10-07-COARSE-BAND-PROTOTYPE.md`, `PLAN-2026-10-07-SEPARATOR.md` (separator branch).

## Lesson

In the blind TV review, grain-statistic changes this small were invisible, while a small loss of base detail (duller lips) was obvious. Judge future work first on base detail (luma and colour, grain off, against the lossless source) and on file size at fixed QVBR. Grain statistics come second. Measure before building: the chroma-threshold plan rested on a premise that one stage-by-stage measurement disproved.

## Housekeeping

Proposed branch, worktree and scratch cleanup (nothing deleted yet): [CLEANUP-PROPOSAL-2026-10-07.md](CLEANUP-PROPOSAL-2026-10-07.md).
