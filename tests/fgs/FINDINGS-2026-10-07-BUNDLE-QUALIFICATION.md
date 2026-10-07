# Bundle qualification: 22 of 23 gate checks, one intended change awaiting review

The kernel speedup plus clean-source fix (variant D, runtime `e78e97f2`, binary `5cb5a80a…`) passes CPU tests, 22 of 23 full-gate checks, and the trace check: nothing changes outside the grain curves. The one failing check is the periodic-grain stage's whole-sequence change detector. By its own description it fails on any intentional model change until a reviewed baseline is updated. On the 150-second Gentlemen fixture, a few short runs of low-amplitude chroma patches change their correlation pattern, all on frames where the clean-source rule changed the chroma curve. The kernel-only candidate passes the same stage. Updating the stage's pinned baseline is the user's decision; nothing was changed in the gate or its fixtures.

## Candidate

- Branch `fix/fgs-clean-source-20261006`, runtime commit `e78e97f223f3cececc29ddcd47504e2dd828c4b7`, on the qualified kernel candidate `a1ac278a`.
- Binary SHA256 `5cb5a80ac98694aff71dfb9d7843d594a54bcc65d1cd9bf84baeeaa58e05f86c`. Built incrementally from a pinned clone in `nvenc-fgs-build:cuda13.3` reusing the qualified candidate's cache; only `NVEncFilterFilmGrain.cu` recompiled. Staged at `/tmp/downloads/codex-work/fgs-submission-20261005/bin/nvencc-bundle-5cb5a80a`.
- Clean-source results: [clean-source findings](FINDINGS-2026-10-06-CLEAN-SOURCE-FIX.md).

## Checks

| Check | Result |
|---|---|
| `run_cpu_tests.sh` (pinned clone) | pass: 119 Python tests, all C++ programs, exit 0 |
| Submission trace vs kernel candidate, same run | 21 KAT + Silo identical; Amphibia, Gentlemen, Lost Tapes, Taxi differ only in scaling-curve fields (pictures change only alongside them); no other field or picture-only change |
| Play Dirty full history (`amplitude-final-bundle-e78e97f2`) | 183,661 frames encoded and strictly decoded; bound to the candidate SHA |
| `local_gate.sh --full`, unchanged, pinned harness `e78e97f2` | **22 passed, 1 failed** (periodic grain regression) |

The gate ran with the existing private path view (`DOCKER_APPS` → `gate-path-view/docker-apps`, which differs from the live canary helper only in temp-dir literals) and cache `fgs-submission-20261005/gate-cache`. Reports and console log: `fgs-submission-20261005/reports/full-gate-bundle-e78e97f2[-console.log]`. Amplitude regression, mixed source, source variance, source training, canaries, flash/colour and grain-syntax stages all pass.

## Review of the periodic-stage failure

The stage's encode and scan pass: stable 3,600-packet grain scan, mesh negative rejected, source-detail check passed. What fails is `decoded_sequence.compare` against the pinned training positive: "signed correlation vector changed" on red (8 frames, 3 runs) and blue (36 frames, 10 runs). There are no texture, amplitude, temporal or grain-scheduling failures, and luma is clean. Peak score, RMS p95 and maximum adjacent change match the positive to within 0.006.

Re-encoding the same command with a grain table on both binaries (`scratch periodic/`) shows:

- The kernel candidate passes the comparison; the bundle reproduces the gate's flags (red 8, blue 35).
- The bundle's curves differ from the kernel candidate's on 2,190 of 3,600 frames: Y 2,148 (the letterbox-bar notch), Cb 1,460, Cr 946 (mid-level constant chroma, now with no 0.25 tolerance).
- All 43 flagged frames lie on curve-changed frames, 41 on the same plane's curve (Cb 34/35, Cr 7/8). They cluster at 23.8–29.0 s, 119.2 s and 138.9–141.4 s.
- The largest correlation change is 0.13 (red) and 0.21 (blue) against the 0.10 limit, on patches whose chroma RMS is 0.21–0.33 code. Bundle RMS there is 12–16% below the kernel's: the reduced synthesis on those low-amplitude chroma patches.

This is the intended clean-source change measured by a detector that requires review for any change. Making the gate green needs either acceptance of this review and a baseline update for that stage by the user, or a change to the candidate.

## Follow-up: review accepted, baseline updated, clean release build

The user accepted this review. Commit `733a4fe0` points the periodic stage at a new fixture: the unmodified reviewed `candidate.mkv`, stored as `gentlemen-clean-source-positive-33m-150s.mkv` (SHA256 `da7f25e4…`). No existing fixture changed. Run from a pinned clone of `733a4fe0`, the stage passes with the release binary (no failures) and still rejects the mesh negative (13 failures).

The release binary is a from-scratch build of `e78e97f2`, SHA256 `46d6781c…`, version `r4389, Oct 7 2026`. A same-run submission trace shows all 1,496 frames identical to `5cb5a80a` on 21 KAT and 5 real fixtures (`fgs-submission-20261005/release-trace-46d6781c`).

