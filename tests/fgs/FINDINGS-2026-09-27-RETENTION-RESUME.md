# Retention work recovered after the usage limit

The goal remains fast, space-efficient AV1 with preserved detail and grain on
1080p SDR and UHD HDR. Automatic retention is unfinished. R1/R2 are complete;
R3 implementation and R4–R8 qualification remain open.

## Exact checkpoint

The active worktree is `NVEnc-fgs-fidelity`, branch
`feat/fgs-detail-fidelity-20260908`, last committed HEAD `4b7fd526`.
D63's finite source-bound selector schedules are committed and GPU-qualified.
D64's measured candidate evidence and numerical fix are still uncommitted.
The existing nine-line September 12 maintenance note in WORK-TO-PRODUCTION is
the user's change; preserve it separately when staging our work.

No retention experiment is running. Old tool session IDs no longer exist,
but the final `measured-plan-report.json` confirms the last job completed.
The live Tdarr node image remains ordinary `cb903a17`; this work has not
deployed a replacement. Retention/FEL remain disabled in the recorded policy.
No owned pause, automatic experiment, library replacement or new download was
started during recovery. Current free space is about 54 GiB on `/` and 295 GiB
on `/tmp/downloads`. Other sessions have active containers; do not treat them
as abandoned trial containers or stop them.

## Completed local work

- All 64 existing constructed candidate frames have exact source, rounded
  input, reconstruction, model and decoded-output associations. The new
  pixel tool verifies 50,331,648 native rounding samples and reuses independently
  verified AOM evidence alongside 64 fresh dav1d observations.
- The original two 10-bit single-picture spatial failures remain recorded;
  all 36 eight-frame spatial windows pass. These different checks are not
  interchangeable, and their results do not establish full source eligibility.
- Current source/reconstruction missing-noise targets agree independently on
  both spatial folds for every component of all 64 frames. Twenty syntax and
  feedback controls behave as expected.
- A fixed-order PSD calculation rejected a valid, nearly singular colour
  source/base pair. The local fix eliminates the largest diagonal first and
  checks the entire trailing block at numerical rank. It changes neither input
  targets nor the existing tolerance. All 516 independent matrix controls
  agree, including 96 deliberately indefinite matrices. This repairs a false
  rejection in the experimental fitter, not a newly demonstrated picture defect.
- The measured evidence join keeps detail and quiet-region checks unknown;
  it rejects mismatched content, frame clocks, fractions, models and proof
  files. All four measured 16-frame selector replays consequently preserve
  the source. Regional coverage does not acquire approval from a whole-frame fit.
- The complete CPU run passed 227 Python tests in 32 suites plus 49 C++
  programs. The subsequently added five evidence-join tests also pass. A final
  consolidated run after completing the remaining edits is still pending.

The numerical approach was checked against
[LAPACK's complete-pivoting Cholesky documentation](https://www.netlib.org/lapack/explore-html/de/de0/group__pstrf_ga27d24f9a4af47099060aafcb15fbd296.html).
That factorization does not itself establish PSD; our independent target
checks and trailing-block rejection remain necessary.

## Resume in this order

1. Compare the newly built `native_fitting_reference-v3` against the exact
   retained 8/10-bit fitting inputs and prior coefficients. Rebuild the
   experimental native library with the numerical fix and check its existing
   model decisions before using it in further encoder trials. Finish the
   consolidated tests, D64 report and commit; preserve the user's note.
2. Complete measured detail, quiet-region and whole-picture population checks.
   Keep source/history coordinates fixed across candidates. Native Y still
   lacks an established source classifier; unsupported colour regions remain
   unsupported. Passing statistics on flat constructed grain do not qualify
   arbitrary moving detail. Do not invent the missing check bits.
3. Connect admissible measured candidates to full runtime automatic selection.
   The current finite 8–16-frame diagnostic schedules do not implement a
   production streaming retention policy. Qualify transitions and reference
   state, including grain dropout/excess and preservation boundaries (R3/R4).
4. Freeze a useful candidate before opening reserved footage. Qualify actual
   compressed SDR/HDR output, detail, ripple, banding, grain stability, clocks
   and metadata, then compare quality at matched size and measure full-title
   size/time (R5/R6). Optimize measured costs and settle size/failure behaviour
   before any Tdarr canary (R7/R8). FEL stays off.

These are implementation and evidence gaps, not merely a final test run.
All 64 fallback decisions demonstrate safe rejection, not useful partial
retention or production readiness. Do not repeat GPU fallback encodes solely
to reproduce already-qualified mechanics; first establish the missing proofs.

## Evidence

The stage directory is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/roadmap-r3-measured-candidates-20260924/`.
Start with `recovery-checkpoint-20260927.json`, `pixel-report.json`,
`refit-report.json`, `model-target-report.json`, `psd-control-report.json` and
`measured-plan-report.json`. The initial numerical disagreement and partial
run are retained separately; do not confuse them with the corrected results.
There is no completed D64 `report.json` yet. Scripts with create-new output
directories must not be rerun over existing evidence.

The previous evidence index covers D63 and the initial D64 plan, not all new
D64 files. Refresh it after closing this stage, including ignored `.log` files.
Latest GPU-qualified diagnostic remains `build-033cd83b/nvencc`, SHA
`9a91e94e65498656ce24717e12fcacd179a28a4c3007c9f01b11cbf7d33ce2b2`.
