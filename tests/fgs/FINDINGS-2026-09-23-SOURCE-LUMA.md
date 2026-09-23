# Source-luma retention and actual NVENC output

R3 remains open. This work adds an explicitly separate colour-only policy and
checks its first complete synthetic candidates through actual NVENC output.
It does not change the existing R1 selector or deployed ordinary FGS.

## Construction and decisions

D29's complete Y/C model fails individual-seed fidelity even on constructive
independent-grain controls. A fixed 50% Y proposal still fails averaged-Y checks
on 2–4 of 48 held-out seeds per positive control. Neither an ensemble mean nor
a successful native-Y fit qualifies these candidates.

D30 instead preserves every source Y sample and fits the marginal 25-variable
colour target, without a synthesized-Y driver. The full source/base covariance
must remain valid and consistent with copied Y. An indefinite missing joint
Y/C target is not relabelled PSD: actual reconstructed Y/C and spatial Cb/Cr
checks remain independent vetoes.

`film_grain_select_with_source_luma` tries at most five fractions per colour,
then one final combined check. It requires native source/base counts, exact
frame/model identity and decoder-clamp proof for **every copied component**,
including copied Cr when only Cb is changed. Missing, stale or failed evidence
preserves the complete source frame. The existing R1 terminal Y fallback stays
unchanged; this policy is never an implicit retry after it.

Complete native census and seven-frame persistent-detail replays accept two
1024x512 constructive controls: independent 8-bit and 10-bit SDR grain retain
75% of each colour residual and all source Y. Both pass all 48 individual
held-out seeds. Y-coupled, quiet and persistent controls fall back.

An additional direct-Cb/Cr negative isolates the final joint veto. One Cr tile
fails source classification, so that entire component stays original. Cb alone
passes at 75%; the combined output loses colour correlation on all 48 seeds
(worst normalized spatial error 0.221), and the selector preserves the frame.
The initial whole-source-support rejection and the later explicit mixed-copy
test are both retained. No source classification or threshold was relaxed.

Known constant clean fixtures supply independent detail truth here. These
results do not establish a classifier for arbitrary real footage. The
source-luma constructors and selector have no automatic encoder call sites.

Full CPU: 214 Python tests in 30 suites and 35 C++ programs. Additional mixed-copy
tests cover changed pixels, clipping, positive curves and stale/incomplete
proof. Refactoring the shared spatial fitter preserves all 80 recorded D28
constructor results exactly.

## Actual encoded output and the remaining limitation

D31 sends the selected native base and filmgrn1 parameters through diagnostic
encoder `04bd03aa` at QVBR30. Only frame 15 of each positive control uses the
measured candidate; earlier frames remain distinct original pictures, with
grain disabled. Four negative controls stay source-preserving throughout.
This is an external measured plan through the existing table path, not automatic
runtime model integration.

All 14 encodes (224 frames) pass both independent decoders in both grain modes:
896 decoded observations. Timing, colour metadata, active-frame identity,
quantized parameters and zero-Y synthesis agree. Native AOM synthesis matches
the emitted frame exactly using NVENC's actual seed: 1,572,864 samples. Every
fallback and every selected grain-off base matches its plain encoder control.

Compression nevertheless removes stochastic grain that the input-base model
expects retention to preserve. In the two selected frames, held-out native-Y
variance is approximately 51–57% below source; colour variance remains 53–88%
below source after synthesis. Plain NVENC also loses substantial grain on these
controls. These percentages describe detrended grain statistics, not VMAF,
detail loss, a library estimate or a new diagnosis of production corruption.
Pre-compression source preservation never promised lossless NVENC output.

The next finite diagnostic fits against the actual decoded base to distinguish
amplitude under-compensation from an unrepresentable covariance target. A useful
solution still needs automatic integration, stable moving decisions, independent
real/HDR qualification and measured storage/throughput cost. R3–R8 stay open.

## Evidence and operations

Local evidence root: `/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.
Reports are `roadmap-r3-selection-controls-20260923/report.json`,
`roadmap-r3-source-luma-20260923/report.json` and
`roadmap-r3-source-luma-output-20260923/report.json`. The direct-colour negative
is under the source-luma report's `direct-cbcr/` directory.

Disposable synthesis/decoding buffers have hash/byte cleanup receipts. Required
sources, controls and compact evidence remain. The finite GPU pause was released,
current Tdarr worker limits were preserved, and no automatic job was installed.
Production remains ordinary `cb903a17`, with retention and FEL off. Reserved
qualification footage remains unopened.
