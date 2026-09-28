# FGS encoder and library repair: current work and handoff

**September 28 active:** [D78 exact constant-source check](FINDINGS-2026-09-28-CONSTANT-SOURCE.md) completes CPU/native/GPU qualification at `c6c53646`: six successful encodes, two expected rejections, 320 independent decoded observations and exact ordinary SDR/HDR controls. [D76 reconstructed source veto](FINDINGS-2026-09-28-SOURCE-ENERGY.md) and [D77 ordinary recovery](FINDINGS-2026-09-28-ORDINARY-RECOVERY.md) are complete. Deployed/branch ordinary output is identical on six controls, but an existing compressed-grain loss during recovery needs source-bound natural development measurements next. All owned pauses are released. Full CPU: 267 Python / 37 suites plus 54 C++ programs. R3–R8 remain open; production `cb903a17`, retention/FEL off, reserved footage unopened. Continue through checkpoints.

**September 28 current:** [D73 source-bound preserved colour](FINDINGS-2026-09-28-PRESERVED-SCHEDULE.md) passes four modeled/twelve clean-negative GPU encodes and 256 independent decoded observations. [D74 native component evidence](FINDINGS-2026-09-28-COMPONENT-EVIDENCE.md) improves structured luma estimates, but every occupied brightness code still includes unsupported pixels in the two HDR frames; no new whole-picture source rule is admitted. Full CPU: 267 Python / 37 suites plus 53 C++ programs. Next qualify copied-colour full-resolution and source/model transitions, then continue bounded source/runtime work and R3–R8. Tdarr is unpaused; production `cb903a17`, retention/FEL off, reserved footage unopened. Nothing starts automatically. Continue through checkpoints.

**September 27 current:** [D71 textured-colour fitting](FINDINGS-2026-09-27-PRESERVED-CHROMA.md) and [D72 actual source-copy integration](FINDINGS-2026-09-27-PRESERVED-TRANSPORT.md) are qualified. D72 passes eight positive/ten clean-negative encodes, 416 independent decoded observations and unchanged ordinary SDR/HDR output. Latest GPU-qualified diagnostic: `524a98f6`, SHA `35dcffc13b8100e3961455cdcbea7fa862823971ccd102747382d4e41de7a275`. Next bind source-preserved colour to measured automatic selector plans; real source eligibility, bounded runtime and R3–R8 remain open. All owned pauses are released. Production `cb903a17`, retention/FEL off, reserved footage unopened; no automatic experiment. Earlier dated entries are historical.

**September 27 current:** [aligned source-history estimates](FINDINGS-2026-09-27-ALIGNED-POPULATIONS.md) complete D67 after [D66 native moving-detail vetoes](FINDINGS-2026-09-27-MOTION-DETAIL.md), [D65 quiet/range checks](FINDINGS-2026-09-27-QUIET-EVIDENCE.md) and [D64's numerical correction](FINDINGS-2026-09-27-MEASURED-EVIDENCE.md). Controlled estimates improve, but 0/4,080 real HDR regions pass all conditions; no new source rule is admitted. Full CPU: 259 Python / 36 suites plus 51 C++ programs. Next implement the finite fitter's copied-chroma case, initially exact constant colour, preserving all missing source/compatibility requirements. Broader classification, bounded runtime R3 and R4–R8 remain open. Production `cb903a17` is unchanged; no GPU trial or owned pause is active. The dated entries below are historical.

**September 27 recovery:** [exact checkpoint and remaining work](FINDINGS-2026-09-27-RETENTION-RESUME.md). D64's 64 measured candidate replays finished and all preserve the source because detail/quiet and regional evidence remain incomplete. The experimental numerical false-rejection fix passes 516 independent matrix controls; its code and measurement tools are still uncommitted. Final fitter/library comparison, stage closeout and R3–R8 work remain. Production `cb903a17` is unchanged; no retention experiment is running. This entry supersedes older next-step pointers below.

**Active continuous roadmap work:** [bounded selector plans and exact source association](FINDINGS-2026-09-24-SELECTOR-PLAN.md) completes D63. Source-bound plans, preservation decisions and both independent decoders pass, including real SDR/HDR missing-evidence fallback. Next derive candidate proofs from actual source/base/model measurements and bind their full association. Accepted D63 plans used labelled unit evidence; they do not qualify real partial retention. R3–R8 remain open. Continue without stopping at checkpoints.

Latest GPU-qualified diagnostic is `build-033cd83b/nvencc`, SHA `9a91e94e65498656ce24717e12fcacd179a28a4c3007c9f01b11cbf7d33ce2b2`. Full CPU: 214 Python / 30 suites plus 49 C++ programs. D63: 18 positive/10 expected-negative GPU encodes, 1,056 fresh decoded observations, 710,866,944 exact source/reconstruction samples per role. One extra HDR reference-domain failure was diagnosed and corrected in the trial manifest; final metadata remains exact. All pauses released, current limits preserved. Production `cb903a17`, retention/FEL off; reserved footage unopened; nothing starts automatically.

The dated entries below preserve earlier checkpoints; their then-current builds and next steps are historical.

**September 23 current:** the [full-episode seed-guard comparison](FINDINGS-2026-09-23-SEED-INTEGRATION.md#complete-episode-encoder-cost)
is complete: four SDR encodes, identical packet payloads/clocks and size,
34,626 independent decoded observations. Mean time changes by +0.25%, within
the observed repeat variation. This qualifies one cost control, not retention
quality or broad throughput. Tdarr is unpaused with current limits preserved;
completed trial scratch has cleanup receipts. No experiment is scheduled.

The [frozen motion/correlation study](FINDINGS-2026-09-23-STATIONARITY-CONTROLS.md)
measures 1,024 known-source controls and replays 3,960 real HDR development tiles.
Fast zero-grain motion and persistent grain evade its necessary checks, so it
does not establish a new safe population classifier. Its
[disjoint-frame-pair improvement](FINDINGS-2026-09-23-MOTION-HOLDOUT.md) removes
the flat-grain false motion conflicts on development controls, while preserving
the unresolved counterexamples. No source classification or output policy
changed. Full CPU: 208 Python tests in 29 suites plus 29 C++.
R3–R8 remain open; production stays ordinary `cb903a17`, retention/FEL off.
Next model work needs independent motion evidence and explicit preservation of
temporally persistent residual before a new population can be admitted.

**September 23 latest:** the [optional retention colour-range and recovery guard](FINDINGS-2026-09-23-RUNTIME-RANGE.md)
is qualified as `53d3ff3f`, binary SHA
`a0d760f57bbb2ff7b423ed3c117e6a09535b1e04941e80430182045df89bcaf2`.
It fixes active-zero-curve clamping of copied chroma and prevents unsafe frames
from counting toward recovery. Both decoders agree on the declared QVBR30
controls; 84 native captures and 7,584 decoded observations pass. Ordinary
SDR/HDR, neutral and full-range outputs remain unchanged. Full CPU: 185 Python
in 26 suites plus 29 C++ programs. Read
`roadmap-r3-runtime-range-20260923/report.json` in the evidence root.

The [bounded AV1 compatibility investigation](FINDINGS-2026-09-23-AV1-LEVELS.md)
now reproduces QVBR 16/20 level 23 with the deployed binary and independent
FFmpeg NVENC, including ordinary dimensions and real development sources.
Both AOM 3.8.2 and 3.14.1 reject that undefined level. All 39 emitted controls decode
with dav1d; 17 also pass AOM with exact pictures/clocks, 20 fail on level 23 and
two isolate FFmpeg timecode forwarding. A new optional header-policy check
catches every level 23 control and a later sequence change. Production's current
QVBR 29/30/34/37 map is unchanged. The underlying NVIDIA-path/configuration
compatibility defect remains unresolved; no equivalent-quality workaround or
broad library scope is claimed. Read `roadmap-r3-level-signalling-20260923/report.json`.

The [complete-file seed parser pass](FINDINGS-2026-09-23-SEED-INTEGRATION.md#complete-existing-stream-compatibility-and-parser-cost)
is also complete: 521,260 AV1 video packets across four existing files, all
idempotent with unchanged inputs. Seed candidates are not confirmed visible
damage. No media repair, download or source protection changed.

Automatic retention is still unfinished: R3's whole-picture model/selection
and R4–R8 remain open. Production remains ordinary `cb903a17`, retention/FEL
off. All owned pauses are released and current worker limits preserved. The
reserved corpus is unopened; no experiment or restart job is scheduled.

**September 23 active work after reboot:** automatic retention is **not finished**.
The [optional emitted-seed correction](FINDINGS-2026-09-23-SEED-INTEGRATION.md)
now has a private isolated parser and actual Linux encoder/container qualification.
The latest built encoder is `b2a6daeb`, SHA
`d779c46b21b74e75c698158531bc605b3c7a067a1c5d591bf31c507ade90f260`.
It passes 68,264 decoded observations, a complete seed cycle, SDR/HDR,
Matroska/MP4 and ten configuration/failure controls. It is **not deployed**.
The explicit seed option is off by default; full-title/release/canary checks and
library visibility/scope remain separate. The prior final-model and native
source/base diagnostics are qualified; Meson/CUDA dependency tracking is fixed.

R3's new [native population preflight](FINDINGS-2026-09-23-POPULATION-ENVELOPE.md)
passes independent pixel-oracle and 36 real census replays. For those fixed
lookup equations every occupied code also contains unsupported pixels, so no
positive whole-picture curve passes the current coverage rule. Fitting the same
patches again cannot resolve that conflict. Per-seed fidelity also remains open.
The new helpers have no output selection call sites. The full CPU suite passes
185 Python tests in 26 suites and 28 C++ programs.

Read `roadmap-r3-seed-integration-20260923/report.json` and
`roadmap-r3-population-envelope-20260923/summary.json` in the evidence root.
The bounded alternative-lookup study is also complete: 324 legal projections
isolate at most one eligible pixel per UHD colour component; even an unrestricted
native 2D lookup isolates at most 37. The missing work is a qualified regional
safety model or explicit source-preserving fallback, followed by actual automatic
selection and temporal/quality/bytes/speed qualification. R3–R8 remain open;
the reserved corpus is unopened. Production remains ordinary `cb903a17`,
retention and FEL off. Both owned pauses are released; current Tdarr limits
(two GPU transcodes/two CPU healthchecks) were preserved. No experiment is
scheduled. Preserve the user's existing September 12 maintenance note.

**Current retention task list:** [ordered implementation and qualification roadmap](RETENTION-ROADMAP.md).
It tracks R1–R8 with dependencies, completion criteria and the working method.
R1's [decision contract](RETENTION-CONTRACT.md) and separate qualification corpus
are complete. R2's [GPU collector, complete colour history and encoder integration](FINDINGS-2026-09-22-JOINT-COLLECTION.md)
are qualified against independent CPU/source references. Sixteen encodes (2,432
frames) preserve control pixels in both grain modes, clocks, metadata and grain
decisions; 393 native source/history plane comparisons are exact. The explicit
bounded diagnostic is disabled by default and does not select retention or
change output. R3 is next: automatic selection, whole-picture coverage and
complete model integration. R3–R8 remain open. The stage report is
`roadmap-r1-r2-20260922/report.json` in the local evidence root. Ordinary Tdarr
configuration is unchanged; retention and FEL remain off. No experiment is scheduled.

**R3 first stage:** [coverage feasibility and safe model reuse](FINDINGS-2026-09-22-RETENTION-SELECTION.md)
records 18 candidate measurements and commit `2000f767`. Whole-picture colour
coverage is still insufficient; the bounded selector is not integrated. The new
hold guard rejects a changed grain scale, with an independently measured negative
and full CPU pass. This is preparation for the future prototype; it changes no
deployed runtime or library-repair scope. Read `roadmap-r3-20260922/report.json`.
The next work is population-aware coverage/fallback and consistent model gains.

**R3 current stage:** [native GPU blending, grain-scale units and exact brightness lookup](FINDINGS-2026-09-22-GRAIN-SCALE.md)
are qualified prerequisites. The 31-case GPU blend matches 141,191,039 valid
native samples exactly and rejects all 434 invalid calls. Commit `5826421d`
corrects nonzero-scale strength/refit/DC units and makes finite luma gains
explicit; independent AOM comparisons cover 576 templates and 144 strength
calculations. The separate integer lookup matches 2,580,480 native values across
1,440 curves. Separate common-colour cohort accumulation also passes 20 native
CPU/GPU controls; the three real frames still have no adequately populated
joint-grain group. The bounded host selector/coverage and common-colour guards
remain CPU-qualified, with no encoder output selection call sites. Read the local
`roadmap-r3-scale-20260922/report.json` and `roadmap-r3-native-scaling-20260922/`.
The completed blend's commands in `roadmap-r3-selector-20260922/` are historical;
do not rerun its create-new output paths.

At the earlier September 22 checkpoint, the ordinary-output-compared encoder was
`5826421d`, SHA `0ddbb547ac0f81192c8808ae4694ab8d73fa52eaed8a53eba9fbf0182890e281`.
Four fresh SDR/HDR encodes preserve all 1,920 decoded observations in both grain
modes, clocks, metadata and 960 grain/training records versus `da9ce557`.
The owned pauses are released; the node is unpaused with its preexisting
all-zero worker limits preserved. No experiment is scheduled. Production stays
ordinary `cb903a17`, retention and FEL off, source protections unchanged.

Next: complete whole-picture population/model evidence, finite colour gains
and actual bounded encoder selection, then temporal and quality/bytes/speed
qualification. Smooth sigma and linear DC estimates cannot replace exact
native synthesis evidence. R3–R8 remain open; the reserved corpus is unopened.

**September 22 latest development:** [brightness-aware fitting and partial colour retention](FINDINGS-2026-09-22-BRIGHTNESS-FIT.md)
adds bounded minimax fitting and an independent synthesis-covariance check.
Actual decoder pixels reject the first shared-shape candidate despite its good
regression scores. A later prototype retains 25% of the removed Cb residual,
measures the native rounded base, and passes eight tested source-patch groups
(513 held-out blocks; worst variance error 4.99%, normalized covariance 0.07344).
This reuses development holdouts and is not production qualification. Twenty
parameter sets round-trip exactly between AOM and dav1d across 140 pictures,
including deliberate grain transitions and quiet Cr. The new helpers remain
offline, with no encoder call sites. Whole-picture support, both colour planes,
native rounded-base integration, moving NVENC output and size/speed remain open.
Read `brightness-fit-20260922/report.json` in the evidence root below. Its capture
pause is released; ordinary Tdarr continues. Automatic retention and FEL stay off.

**September 22 earlier finite-template follow-up:** [finite-template and intensity work](FINDINGS-2026-09-22-FINITE-TEMPLATE.md)
adds an offline luma-template reference with exact independent AOM verification
across 768 templates. Internal template clipping explains most of the previous
stationary-power discrepancy; separate real calibration/holdout seed sets agree
within 0.32%. Brightness-specific checks still reject five of fourteen supported
groups. A balanced fit improves the worst dark-region error from about 20% to
9.27%, which still fails the 8% bound. Keep that alternative rejected. No encoder
call site, production policy, amplitude limit or source protection changed.
Read `finite-template-20260922/` in the evidence root below. Ordinary Tdarr
continues; this follow-up needed no new pause. Per-intensity eligibility, stronger
coupling and integrated transitions remain the next model work, before full-title
cost/optimization. The finite GPU comparison is complete.

**September 22 current state:** [colour recovery and native HDR work](FINDINGS-2026-09-22-COLOUR-RECOVERY.md)
has completed the finite matched-size comparison, including VBR/CRF SVT
references, native PQ measurements, tighter ordinary size points and inspected
source-paired stills. Ordinary/automatic SDR and HDR sizes now differ by only
0.211% and 0.085% in the tighter controls. Automatic improves the sampled
source-fidelity scores modestly and resembles plain NVENC in these selected
fallback windows. This does not establish a whole-title/library benefit.

The user **authorizes pausing and unpausing Tdarr as needed** for this work.
The owned study pause drained existing jobs and has been released; two ordinary
workers resumed. Emby's playback watchdog retains its independent ownership.
Production remains ordinary `cb903a17` in Tdarr 2.89.01; retention and FEL stay
off. The flow, routine validation, worker limits, source protections and
restored FEL originals are unchanged. No private experiment is left running
or scheduled to restart automatically.

The proposed colour model remains offline, with no encoder call sites. Its
initial zero-real-support result was invalidated: the private diagnostic read
unused chroma from a luma-only reference cache. Corrected analysis uses
independently decoded previous colour and verifies all planes of 20 current
pictures plus 20 cached previous luma pictures. Eight real frame/component
groups support joint source/base fits; four meet the exploratory holdout
bounds. Actual AOM confirms their chroma transfer closely, while finite luma
transfer still needs calibration. Intensity coverage, causal stability and
integrated transitions remain unfinished. Longer-title cost and optimization
follow a useful qualified recovery candidate; they have not been run or waived.

The latest full CPU suite passes 185 Python tests in 26 suites plus C++ checks.
No new production defect or additional library repair was established by this
study. The evidence root is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/colour-recovery-20260922/`.
Read `README.md`, `handoff.json`, `work-plan.json`, `evidence-index.json` and
`resume-authorized/`. The completed `matched/` reports cover size, quality,
source clocks and explicit software-reference metadata limitations. Do not
reuse the historical `pixels/moment-report.json` zero-support conclusion.
Completed media and dependent source/base captures are hash-verified on storage;
disposable calibration and raw witness buffers have cleanup receipts.

**September 21 current state:** Tdarr is now 2.89.01, image
`nvenc-fidelity/tdarr-node:2.89.01-cb903a17-20260919`; the deployed encoder hash
and production flow still match the qualified ordinary core below. A fresh
check finds ordinary Tdarr unpaused and idle; the playback watchdog retains
ownership of playback pauses. This work did not change its pause state.
The [bounded retention pilot](FINDINGS-2026-09-21-RETENTION-PILOT.md) completed
15 encodes with full frame/clock/metadata checks, source-paired quality samples
and inspected stills. Diagnostic-only correction `c84dbb1f` passes the CPU suite
and exact before/after pixel comparisons across 2,160 pictures in both grain
modes. Retention changes video bytes by -0.86% / +2.65% / +19.04% across these
animation / SDR / HDR windows; this is neither matched-size nor full-title
qualification. Correlated colour-grain recovery remains a specific model
limitation. Production retention remains off, FEL remains disabled, and future
studies remain manual. Completed controls are archived on storage; raw scratch
and the duplicate build cache are retired. The evidence entry is
`retention-prep-20260910/manual-pilot-20260921/closeout.json` in the repair ledger.

**September 16 rollout snapshot:** ordinary core `cb903a17` is qualified and
**deployed**. Its four selected full-source repairs are installed and fully
validated. Ordinary Tdarr is resumed, with two workers active in the final
snapshot. The retired repair coordinator is stopped and disabled at startup. FEL remains
disabled; all four original HEVC films remain restored in Movies and excluded.
Optional automatic-retention studies remain off/manual-start only.

Runtime: `nvenc-fidelity/tdarr-node:2.87.01-cb903a17-20260916`, encoder SHA-256
`06dd65fc00773536f76d09eaf49b1d18032808742e8e13d8037262475c73af7c`.
The combined fidelity implementation is committed as `c1d3c356`; the independent
source-supported grain regression is integrated in `ae852b1c`. The isolated
ordinary core is `cb903a179f8bdb7631410c6fb5674f4ab17fee81`.

The correction bounds gross synthesis against native source variance and excludes
repeating picture texture from both grain training and denoising estimates.
Bounded startup lookahead preserves picture order and source history. Read
[SOURCE-VARIANCE-20260916.md](SOURCE-VARIANCE-20260916.md) and the
[live September 16 ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/README.md).
Current receipts are under `source-variance/training-v7/`:
`qualification.json`, `rollout/report.json`, `repairs/status.json`,
`tdarr-resume.json` and `final-health.json`. The qualification pins 449 evidence files.

Completed qualification includes the unchanged Taxi base-detail canary, native
frame-paired libaom comparison, 19 broad regression checks, a fresh 3,600-frame
jacket/mesh repeat, ten complete short-sequence comparisons, actual source-matched
witness review, two real HDR10 metadata/source-window trials, full strict decode
of five outputs (509,315 pictures), exact runtime reproduction of 768 displayed
frames, and combined-branch CPU/GPU checks. The four episode clocks match source,
prior library and candidate on every presentation timestamp.

Two initial alerts remain evidence. The periodic schedule changed; all source
pictures were compared and worst/anchor stills reviewed before a separately
pinned positive passed a fresh encode. A synthesis-off source-detail check rejects
the V6 jacket-blur negative. The movie dialogue's original pixelwise grain-on
error also rose while source-supported fine grain was restored. Independent
random-noise controls establish why phase must be separated from picture loss;
unchanged base/coarse-error and synthesis caps plus source texture energy pass.
The original failed results and modest displayed-metric tradeoff remain recorded
in `amplitude-review.json`; no claim of losslessness or whole-library clearance.

Three paired timing runs per arm: SDR median 216.18 -> 203.68 fps (-5.78%),
HDR 44.95 -> 46.58 fps (+3.63%). Their sizes change -3.56% / -5.49%; full
Play Dirty video changes +0.2595%. These finite results do not predict all media.
Routine Tdarr validation settings, flow, all 25 plugins and worker limits are
unchanged. The owned qualification pause is released; the independent Emby
watchdog remains responsible for playback pauses. The retired repair coordinator's
automatic startup is disabled so it cannot pause the ordinary queue at reboot.

The four confirmed repairs are Severance S02E02, The Chestnut Man S01E02 and
Taskmaster DK S10E01/S10E05. Final installed files passed complete video-payload
and presentation-timestamp identity with the qualified trials, plus normal worker
decode, metadata, nonvideo-payload and chapter preservation. File-size changes
are +0.24%, +0.73%, -0.05% and +0.16%, respectively.
Other audit flags remain review candidates. Existing
343 source protections remain: season packs still have unresolved dependencies,
the regression movie retains its source, and restored FEL originals stay protected.
Do not infer damage, schedule downloads or discard originals from build age alone.

The user authorized cleanup once dependencies finish. **325,922,254,848 allocated
bytes** have been removed, including obsolete FEL AV1 backups, completed
FEL layers/muxes/raw references, the two completed no-FGS Girl-film backups and
reproducible trial buffers, twelve completed timing encodes and eight obsolete
AV1 predecessors of the four new repairs. Exact plans/results are indexed in
`source-variance/cleanup-authorization.json`. Current sources, compact regressions,
unfinished review evidence and operational rollback remain. Historical raw/timing
outputs need regeneration for new analysis. Per-file `retired-backups-20260916.json`
receipts explain removed historical backup paths. The final snapshot reports
about 50 GiB free on `/`; no source hold or FEL-original protection was released.

The later [encoder review](ENCODER-REVIEW-20260916.md) closes two release-harness
gaps: diagonal-only texture measurement missed axial stripes, and a single
failed stage was misreported as “nothing ran”. Nine directional/scale bands now
retain the existing quality limits; the deployed output passes both pinned movie
witnesses and the retained bad encodes fail. The full CPU suite passes. This
changes offline release testing only; ordinary Tdarr continues on the same
qualified binary. Supplemental evidence is in `encoder-review-20260916/` beside
the live September 16 ledger; original qualification remains unchanged.
No additional ordinary-mode encoder defect was found in that review. Optional
retention's matched-size quality/fallback trials remain manual work, with the
current ordinary baseline required before interpreting historical cost results.

## Historical record before the V7 rollout

The following snapshots retain earlier findings, counts and decisions. Their
runtime names and pause states are historical; the current state is above.

September 16 source/repair reconciliation: 1,882 installed repair receipts resolve
to 1,874 unchanged outputs, five later changes at the same path and three newer
movie releases. Of the unchanged outputs, 1,872 predate the latest amplitude
build; age alone does not establish damage. The diagnostic review queue includes
509 repaired paths. The two completed Girl-film sources have returned to ordinary
`radarr-longterm` handling and 30-day total-seeding limits. The other 343 audit
tags remain: 340 have outstanding dependency review, one retains the Play Dirty
regression source, and two protect FEL originals. The other two FEL originals
already have non-cleanup NordicBits policy. Seeding was never paused by these tags.

The user confirmed deliberately resuming ordinary Tdarr before the restoration
preflight. The assistant's subsequent re-pause incorrectly overrode that choice
and has been reversed. The two running jobs (Neagley S01E01 and Reacher S04E08)
finished successfully and need current-version audit. At that stage the old
ordinary-worker pause did not apply. This operational correction was not
encoder quality clearance or evidence that the user accepted the remaining
quality defect; they subsequently asked whether any issues remained and were
told that excess synthesis is still confirmed in the deployed build.
After excluding the four restored HEVC films, the current Tdarr AV1 index has
5,481 paths, including those two new versions beyond the finite audit snapshot.
The later user-authorized qualification pause above now applies; the existing
Emby playback watchdog remains independent.
Read
[repair lineage, source releases and original restoration](SOURCE-RELEASE-20260916.md)
and its live receipts before releasing further sources or resuming FEL work.

Read `amplitude-qualification.json`, `amplitude-rollout/report.json`,
`amplitude-repairs/status.json` and `amplitude-repair-verification/status.json`
in the [live September 16 ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/README.md).
The deployed build is from `/home/bardie/git-repos/NVEnc-fgs-amplitude`, branch
`fix/fgs-held-amplitude-20260916`, commit
`2fa6cfd09dadd4705d08da07ddea90fb72be56c0`. Binary SHA-256 is
`ef4799f6e7110e1057d8f728586d45e382b1ce3aa75c035403da35f05ca4b946`;
image `nvenc-fidelity/tdarr-node:2.87.01-2fa6cfd0-20260916`, ID
`sha256:f37f59c608bbfc74ed0bfdae43c31db4ce6698ca4be99d3a41275fe2972d5907`.
The prior `ef5c61fe` image, binary and configuration are retained for rollback.
All four runtime tool hashes, current 25 plugin files, flow and worker limits
were checked. Routine validation and optional-retention settings are unchanged.

The broader Play Dirty source comparison exposed excessive grain that the
flat-source-only diagnostic could not assess. Ordinary encoding skipped the
existing current-picture model-strength fit/recovery because its entry condition
required optional retention. The two-condition correction makes that protection
mandatory using existing statistics; no GPU analysis pass was added. Both
widely separated movie witnesses and the Eric Andre story witness improve in
actual source/old/candidate comparisons. Full strict decodes, selected source
windows, prior GPU/reference/ripple/flicker/source controls, real HDR10 pairs
and a fresh exact-runtime 720-frame reproduction qualify the isolated release.
The complete Play Dirty video grows 0.2002% versus the previous image's trial;
single-run encode timing is not a speed guarantee.

Two initial checks intentionally remain as evidence. The periodic fixture
changed on 263 of 3,600 pictures; all-frame source errors improved, no new grain
pictures appeared, worst changes were visually reviewed and a fresh repeat
passes a separate new positive fixture. The initial city source-RMS limit of
4.0 also rejects ordinary no-FGS NVENC at the same settings. A separate
same-settings reference establishes ordinary compression loss there; the new
structured-scene check bounds added synthesis and error above that reference,
and rejects both retained bad witnesses. See
[the amplitude regression and limits](AMPLITUDE-GUARD-20260916.md).
Do not reinterpret sampled passes as whole-library perceptual clearance.

The separately owned `fgs-current-city-fidelity-20260916` hold remains scoped to
further repair-worker admission and experimental deployment qualification for
the new source-support failure. The later user-authorized qualification work
also temporarily owns the ordinary Tdarr pause, with a separate receipt above.
Do not release the repair/deployment gate on nine-repair or scan completion.
`amplitude-scope-pilot-review.json` records ten new source/pilot comparisons:
five improved witnesses, four conspicuous remaining mismatches (Severance
S02E02, Taskmaster DK S10E01/S10E05, Chestnut Man S01E02) and a further Sugar
S02E07 mismatch awaiting severity/recurrence review. No extra replacements or
downloads are selected from these stills. Six initial short-clip extraction
failures have successful diagnostic retries with explicit timestamp passthrough;
the initial failures are retained.

The Severance 2232.439-second light-panel source sigma is 0.977 codes versus
13.865 codes of added synthesis. Native 12-frame measurements and actual
source/on/off images are in its `amplitude-scope-pilots/` evidence. The new
`/home/bardie/git-repos/NVEnc-fgs-source-variance` worktree, branch
`fix/fgs-source-variance-20260916`, tests an 8x8 luma total-variance ceiling,
including thin near-white regions excluded by the quiet-source guard. Read its
`tests/fgs/SOURCE-VARIANCE-20260916.md` and live `source-variance/` receipts.
CPU checks and all four targeted synthetic GPU cases pass; the same cases reject
the deployed encoder as expected, while retaining synthesis in the constructed
genuine-grain region. All ten real 32-second trial encodes and diagnostic
extractions completed. Their visual review, broader grain/regression/HDR checks,
whole-source behavior and performance remain unqualified. Two local build setup failures (missing
untracked cargo-c cache and uninitialized pinned submodules) remain recorded.
The retry uses the existing cache read-only and local exact submodule revisions;
networking remains disabled. Sources/backups remain protected.

The fourteen later display/source pairing errors are restored using the
already-qualified ten-second source preroll, preserving every original output
picture and four unchanged positive controls. They cover Flame and Citron plus
one window each in Scrubs S04E21/S03E15. `source-window-retry/` retains the
original failures, restored measurements and fork qualification. This recovery
is now in the fork's display source helper, with 18 source-review and 13 native
controls passing. It changes audit recovery only. Current follow-up reports
contain 5,945 source-compared windows, 96 grain-absent windows and 308 unpaired
windows; the separate two native Scrubs source-decoder gaps remain open. Integration commit `5f197758` in the broader fidelity branch passes the full
CPU suite (`amplitude-branch-integration.json`). That does not qualify or deploy
the combined GPU binary, and
future FEL qualification must include this ordinary-core correction.


September 16: the user approved recovery/retranscode of the two extended Girl
films with confirmed multi-second story-scene gaps, completion of current-version
coverage and review of remaining diagnostic candidates. Both exact originals
(77.26 GB total) were recovered; both films passed full worker checks, installed
and passed fresh installed-version measurements with the ordinary qualified core.
This is a narrow two-release exception; the general recovery hold remains intact.
The immutable follow-up covers 611 current AV1 versions: 482 qualified display
measurements and 129 native-source checks for SD files lacking colour tags.
Source discovery adds 202 retained originals: 585 of 611 now have candidates
for per-window source alignment, and 23 additional torrents are held against
cleanup. The 515 diagnostic candidates remain a review queue, not a damaged-file
list. Forty distinct files have actual visual observations. Owl House
S02E08 and Adventure Time S07E25 are repaired from retained originals, with zero
strong source-flat frames in the previously affected measured regions and fresh
installed-version checks. All 611 header scans pass. Native measurements cover
127 of 129 versions; two early-picture source-pairing gaps remain explicit.
Operational pause timeouts have qualified retries. All finite scans/retries
finished at 09:04 UTC; source/display gaps remain explicit in `reconciliation/`.

Whole-image amplitude now complements quiet-source area in review ordering.
The older Gentlemen S01E01 repair has a severe pattern around 38:45 despite a
tiny quiet-source flag. An unchanged deployed-image trial passes 25 source
windows and improves five visual witnesses; the repeat repair is installed and
passes full worker gates plus 15 fresh windows. Weaker grain-estimation differences
remain documented. Steven Universe S02E27 and Regular Show S02E06 pass 24
source windows each; full-duration selected-region stronger events fall from
670/1,055 to zero, with improved source/old/current visual witnesses. Their
retained-source replacements are installed and pass fresh 12/13-window checks.
All nine completions, sizes and rollback paths are recorded in the live ledger
`nine-repairs-completed.json`, including Play Dirty and Eric Andre S05E10
with `2fa6cfd0`. Their installed containers grow 9.5771% / 1.3377% versus
their prior installed files; these are different baselines from video trial deltas.
The additional full-image-ranked witnesses include genuine added grain and
intentional source effects; neither priority list is a damaged-file list.
The remaining recurrence and contextual review work stays open.
Read the [follow-up and qualification record](FINDINGS-2026-09-16-AUDIT-FOLLOWUP.md)
and [live job health and coverage](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/status.json).

September 15 Tdarr errors: MobLand S01E01–S01E10 were rejected because the
post-encode FFmpeg remux automatically marked the first subtitle as default.
Horns was rejected because the validator treated German `deu`/`ger` aliases as
different languages. Both are corrected in two local plugins; the ordinary
encoder binary, flow, quality settings and validation decode workload remain
unchanged. The 105-test suite, deployed-node checks and actual-file remux
controls pass. All eleven full retries completed successfully, with no failed
retries. Read
[the diagnosis and patch record](TDARR-SUBTITLE-ERRORS-20260915.md) and
[live retry status](/opt/docker-apps/logs/tdarr-errors-20260915/retry-status.json)
for completion. All eleven originals were preserved by the rejecting validator.

September 15 FEL results: the complete Beasts candidate passed the corrected
current-library mux validator, including all 182,867 output pictures, full strict
libdav1d decoding, every RPU/static-HDR check, retained track bytes, chapters and
native TrueHD clocks. Both complete source-layer decodes also passed. Source-
matched comparisons finished; these two measured windows are not whole-film
perceptual approval. The earlier frozen canary's TrueHD timing failure remains
recorded; the corrected qualification reused the same completed video. Complete
Bumblebee preparation passed (163,840 frames), without another GPU encode.
No FEL replacement or new encoder was installed, and all four originals remain
held. On September 16 the user reported that the Apple TV/Infuse test clips
looked good, with no mistakes noticed, but only UHD was indicated. Actual HDR
output remains unconfirmed; the TV does not support Dolby Vision and Match
Dynamic Range was not reported. The eight temporary Movies copies and their
Tdarr exclusion were removed as requested, and Emby's index was verified clear.
Original test clips and qualification evidence remain available. The
[feedback and cleanup receipt](/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914/emby-playback-pack-20260916/cleanup-20260916.json)
records the exact observation; it does not release the remaining FEL gates.
The user subsequently requested the untouched HEVC originals in Movies and
disabled FEL encoding. All four are restored through hardlinks, with the old
AV1 versions backed up, exact source-inode identity verified, Emby/Radarr
metadata refreshed and the four folders excluded from Tdarr. The historical
FEL candidate's library-track qualification no longer describes these restored
library track selections. Future FEL work requires an explicit new user decision.

Read [the FEL production report](FEL-PRODUCTION-20260914.md) and
[live work ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/fel-production-20260914/work-plan.json)
for exact pins and remaining release gates. The focused checkout is
`/home/bardie/git-repos/NVEnc-fgs-fel`; candidate `a72f589e` starts at ordinary
`ef5c61fe` and adds verified scene boundaries plus fatal pipeline-error
propagation. The combined branch includes these changes, but its compiled
`296993f9` is not the isolated GPU-qualified candidate. Prepared metadata,
source correspondence, bounded reconstruction and current-library preservation
checks are implemented. Runtime v3 adds graph-entry evidence requirements;
exact native TrueHD clocks and shifted-audio rejection controls pass.
The [initial FEL trial report](FEL-RECONSTRUCTION-20260914.md) retains its
historical scope. Actual player/HDR approval, other complete-film qualifications
and guarded FEL installation remain pending. Deferred retention trials remain
manual-start only.

September 14 audit: the primary decoded pass finished successfully at 10:57 UTC
with 4,896 measured and 264 superseded versions. Current-version catch-up and
review remain pending; this is not whole-library clearance.

September 14 held-repair work: all ten non-FEL holds are installed and verified,
using source-clock qualification and narrow chapter/SubRip preservation checks
with the same deployed encoder. The queue now records 1,880 installed, four
FEL holds and zero ready. Tdarr resumed automatically at 12:49 UTC with both GPU
workers processing the backlog. The qualified Daniel Sloss timestamp correction
is separately installed with rollback. The earlier DV fix normalized MEL
metadata and did not reconstruct FEL. See
[held repairs and FEL scope](FINDINGS-2026-09-14-HELD-REPAIRS.md),
`implementation/final-verification.json` and `final-operational-state.json`
in its linked ledger for the exact completion and retained-source evidence.

September 13 operations: the decoded audit now runs two files concurrently
through the unchanged, qualified v5 measurement tools, ordered by the sources'
original cleanup deadlines. A scoped qbitmanager hold protects 320 source
torrents while review is pending. The repair coordinator already resumes the
two ordinary Tdarr transcode workers after its ready queue and active workers
remain empty for five minutes, subject to playback ownership.
See [audit acceleration and source retention](FINDINGS-2026-09-13-AUDIT-THROUGHPUT.md)
for service names, qualification, release policy and the live evidence ledger.

The September 12 deployment used isolated core `ef5c61fe`, binary
SHA-256 `d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.
That historical image is `nvenc-fidelity/tdarr-node:2.87.01-ef5c61fe-20260912`, image ID
`sha256:218540effe6149030631445914c8f35c6e81090326a8e4bbca55d0b57c3f50e4`.
The prior `273723b7` deployment is retained for rollback. At that encoder deployment, the production flow,
25 local plugins, worker limits and routine validation were unchanged; the
September 15 subtitle-only plugin corrections are recorded above. All four
custom runtime tools were verified. Both routine monitors passed for the installed binary, and two
ordinary repair workers were observed after releasing the audit-owned hold.
Pause ownership and Emby playback yield remain in place.

The audit demonstrated a gap in `273723b7`: a small clean source patch inside
a larger textured analysis block could still receive strong grain. That
fix adds finer 16x16 luma / 8x8 colour source evidence while preserving the
existing model-fitting region, ripple/syntax guards and temporal recovery.
It adds no extra pixel reads from GPU global memory, kernel launches or host
synchronization. Both bit depths pass all ten mixed-source controls, including
the four small-region cases that reject the previous deployed build.

[The finer-source qualification](FINE-SOURCE-GUARD-20260912.md) records the
source controls, full-frame periodic review, unchanged quality canary, five
exact-image cases, HDR10 signalling check, installed repairs and limitations.
[The full audit](FULL-AUDIT-20260912.md) records scope, evidence-based repair
priorities, tools and outstanding coverage. The local
[qualification](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/qualification.json),
[rollout](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/rollout-record.json)
and [operational restoration](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/final-additional-amphibia-operational-state.json)
pin the exact tested and installed artifacts.

Five files were repaired from retained originals during this audit: Regular
Show S1E2 with then-current `273723b7`, plus Steven Universe S3E22/S1E23 and
Amphibia S1E18/S1E11 with `ef5c61fe`. The latter four are repeated repairs of existing
selections. The [37 distinct selected-file results](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/current-selected-repairs.csv)
now total +1.620% versus their recorded pre-flicker-repair containers. This
selection history is neither a complete damaged-file count nor whole-file
perceptual clearance. All original and superseded files remain available.

The two Steven source trials add 0.136% and 0.147% video-only bytes versus the
previous `273723b7` trials; single-run encode times rose 0.83% and 0.64%.
The actual installed containers are +13.24 MB and +4.87 MB versus the older
`3778447e` repairs. Amphibia S1E18 grows 40.85 MB (+20.89%) versus its older
repair; S1E11 grows 49.48 MB (+25.96%) versus its earlier partial-fix build.
These comparisons use different baselines and must not be conflated
or extrapolated across the library. Heavy audit tests were not added to Tdarr's
per-file validation.

There is no universal fidelity certificate. Source review shows a fine-texture
tradeoff at shared brightness levels: protecting clean artwork can also reduce
some genuine fine grain elsewhere. The periodic regression was separately
reviewed against all 3,600 source frames; the original change alert, old
positives and failing negatives remain. No numeric detector limit was relaxed.
Lossy base texture, very thin source regions, optional retention cost and actual
Apple TV/Infuse playback remain distinct limitations or deferred work.

The combined fidelity branch includes the new core at `704a8f8f`; its exact
`03eb4796` build compiled and passed the CPU suite. That broader binary is
**not deployed**. Later `e4ed723f` changes only audit tools: low storage now
pauses the finite run without consuming pending files as media errors, and
whole-movie timestamp matching avoids a quadratic scan. Twenty-eight audit CPU
tests and retained real-movie alignment checks pass. Audit-only `708ae7ca`
adds qualified explicit BT.601 mapping and fixes rounded window boundaries.
The active helpers are pinned in `tools-v5/`; 31 Python tests, eight native CLI
tests, display controls and real BT.601/unchanged SDR/PQ comparisons pass.
Missing SD colour metadata remains a coverage limit. The finite v5 continuation
reuses 86 completed results, queues 5,160 original versions and freshly pins 17
replacements. Earlier results remain immutable and keep their method identities.

Read the [active audit ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/work-plan.json)
and [published coverage](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/published/status.json)
for current jobs and timestamps. The original inventory has 5,578 videos,
including 5,263 AV1. The finite catch-up queues cover replacements observed
at their recorded times. Header and sampled decoded/source coverage remain
unfinished. No diagnostic flag authorizes mass downloads.

The earlier [source-guard report](SOURCE-GUARD-20260912.md),
[flicker report](FLICKER-20260912.md) and `grain-recovery-followup-20260912/`
describe their named older builds and dated qualifications. Their 36-file counts
and earlier production pins are historical. The general recovery download hold
remains in force; the September 16 two-release approval above is the only new
recovery exception. No optional retention campaign was started.

This is the canonical entry point for resuming this project. Read the current
state and next steps here before using an older findings report or work ledger.
Older reports describe their named builds and dates; a historical `complete`
status does not close the present goal. Live queues, binaries and file
identities must be checked again when work resumes. No chat history is required
to find the working state, evidence and remaining tasks from this document.

The working checkout is `/home/bardie/git-repos/NVEnc-fgs-fidelity`, branch
`feat/fgs-detail-fidelity-20260908`. Other NVEnc worktrees under `git-repos` are
not necessarily on this branch. The separate deferred-retention preparation ledger is
[/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/work-plan.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/work-plan.json).

The goal is to finish the encoder improvements, resolve measured quality,
reliability, speed and storage costs, and integrate the validated result into
Tdarr. The evidence-based library audit and approved repairs continue alongside
that work. A completed experiment is evidence toward this goal; it does not
close the overall task.

The user's original aim is fast, space-efficient CUDA/NVENC AV1 with grain
preservation comparable in intent to an SVT-AV1 grain workflow, for both UHD/HDR
and ordinary 1080p SDR. Preserving source detail and avoiding ripple, banding,
colour loss and unstable grain matter as much as throughput and size. Higher
average VMAF alone does not justify a storage increase. Demonstrate visible
benefit and compare at similar actual video-byte budgets before choosing an
automatic-retention allowance.

Core `9c1664d4` completes the subsequent local/chroma recovery iteration,
exact-build quality checks, full-source measurements, actual measured and
source-savings Tdarr trials, staged artifact checks and rollback. Automatic
outputs still exceed the unchanged 10% cap on all three full sources, and
the coarse optimization still misses its target. The tested alternative
requires savings versus originals and allows more bytes than the ordinary
encoder. The storage-policy decision follows evidence of visible benefit and
quality per byte against the current production encoder.
The qualification ledger for that optional build
is `/opt/docker-apps/logs/fgs-ripple-repair-20260906/auto-retention-production-20260910/work-plan.json`.

The [repair-period preparation](FINDINGS-2026-09-10-RETENTION-PREPARATION.md)
adds precise fallback diagnostics, prepares skipping unused covariance work,
retains source/output references without copying payloads, and prepares
matched-size comparisons. CPU tests pass. The integrated branch now compiles with the source-guard work. These optional
covariance/model changes still need deferred GPU output-preservation and quality
qualification; compilation does not make them the ordinary production build.

The [September 11 evidence inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md)
recovers the July measurement campaign, Silo retention operating points,
SVT/settings studies, whole-title metrics and additional reference candidates.
Use those records to refine the next comparisons before repeating old sweeps.
Historical scores remain attached to their original runs; newly found media
requires provenance checks before entering the current comparison manifest.

The [CPU model-reuse correction](FINDINGS-2026-09-11-MODEL-HOLD.md) replaces a
sparse brightness-grid comparison that could miss narrow strength-curve
changes. The full CPU suite and an archived Ju-on curve reproduction pass.
The combined branch still needs GPU qualification, including temporal update
stability; this intentional model-decision change is separate from the
covariance optimization's output-preservation checks.

The [joint fallback analysis](FINDINGS-2026-09-11-FALLBACK-PROFILES.md) joins
checks on the same frame across six saved full-episode logs. It distinguishes
overlapping colour/local failures from source preservation after successful
covariance recovery, and selects six short diagnostic targets plus the existing
jacket regression. The report tests pass; new media work remains deferred.

## Build and deployment state

| Revision | Role | State at this handoff |
| --- | --- | --- |
| `e2c3a99d` | First 24-fit recovery hold | Superseded; retained partial-fix baseline and rollback |
| `3778447e` | Prior recovery-ramp hotfix | Superseded ordinary baseline and rollback; residual limits retained in historical reports |
| `273723b7` | Coarse source-quiet and constant-colour protection | Superseded; retained qualified baseline and rollback |
| `ef5c61fe` | Finer independent source protection | Superseded ordinary baseline; structured-source amplitude defect documented |
| `2fa6cfd0` | Mandatory ordinary-mode current-picture amplitude support | Qualified and deployed; runtime/full-file/HDR/source regression evidence pinned in September 16 ledger |
| `a72f589e` | Isolated FEL scene schedule and fatal drain correction | Short controls passed; full canary running; not deployed |
| `296993f9` | FEL tools/core changes integrated with broader work branch | CPU suite and compilation pass; not the isolated candidate and not deployed |
| `2d72d779` | Later graph and native TrueHD timing qualification | Host-only additions; real staged mux and negative controls pass; full library qualification remains in progress |
| `e4ed723f` | Audit storage and alignment hardening | 28 CPU tests and full retained-movie timestamp check pass; no encoder change |
| `708ae7ca` | Audit BT.601 and window-boundary corrections | 31 Python tests, eight native CLI controls, display controls and real-file comparisons pass; diagnostic only |
| `497caa64` | Earlier ordinary encoder, `retain=0`, bilateral | Retained comparison/rollback baseline; superseded in production |
| `9c1664d4` | Optional automatic retention | Quality/operational qualification recorded; not broadly enabled; all three complete-source outputs exceed the unchanged 10% trial cap |
| `5450a4fc` | Precise fallback traces and skipping unused covariance work | CPU checks and integrated CUDA compilation passed; separate output-preservation checks deferred |
| `3ac80ceb` | Exact strength-curve comparison for model reuse | Full CPU suite and archived curve reproduction passed; intentional model decisions need GPU/temporal qualification |
| `57c0e8ae` | Joined diagnostic reports and focused target selection | 13 diagnostic and seven tradeoff tests passed; six saved logs reanalyzed; no encoder code changed in this step |

Subsequent documentation commits do not constitute a new encoder qualification.
The preparation ledger records current source hashes and completed CPU commits;
the rollout and qualification records retain the baseline revisions. The two
measured baseline binaries are pinned in
[comparison-manifest.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/comparison-manifest.json):

- Ordinary `497caa64`: SHA-256
  `bb7e75cbcb9097f1f1c7ac3347e7193c74caa6c7d57db1c3c77348cc27daf144`.
  Its retained artifact is `production-readiness-20260909/bin/nvencc-fidelity-497caa64`
  under the repair log root. The host build input now contains `2fa6cfd0`;
  do not use that mutable path as the old comparison baseline.
- Optional `9c1664d4`: SHA-256
  `8dff824c8d7360adac294f05e7c6032770f8594cf1c3b63961f50a854e3b0fec`.
  Its retained path is under `auto-retention-production-20260910/bin/` in
  the repair log root.
- Ordinary flow `/opt/docker-apps/configs/tdarr-flow/flows/AV1NVENCflow1.json`:
  SHA-256 `6cebd7cb63d540f61d9c142a9728ed4fbf0edaeaa3312eacae9ae7503126c7fe`,
  verified again on September 12. Hashes are recorded identities, not a promise
  that a future installation is unchanged.

The faster four-thread HDR validator is already deployed. Its 90 checks and
measured sample timing are recorded in the September 10 ledger; this does not
add the expensive development studies to routine Tdarr validation. FEL encoding
is disabled and the four original-film folders are excluded. Ordinary Tdarr is
temporarily paused for the newly authorized qualification; playback yielding
remains active.

The September 12 application upgrade preceded this encoder rollout; its initial
encoder image is historical. The current runtime is pinned above.

## Historical next-step plan (superseded by the current roadmap)

The immediate ordinary-core work is the remaining source-support failure above.
Finish the `source-variance/` experiments and preserve all failing controls.
The finite audit scan is complete; source-window gap review and watchability
classification remain open. Further repairs and experimental deployment still
require qualification; ordinary Tdarr is temporarily paused for the user's
newly authorized correction. Keep the repair coordinator stopped while this separate
work remains held. The retention plan below is still deferred.

**Retention GPU trials are prepared, not running or scheduled to start automatically.**
The user explicitly confirmed manual start only: wait for the repair to finish
and resume the trials when requested. Do not install a timer or trigger that
starts them when the repair completes.
The user's resource decision is to finish the current ripple repair before the
optional retention studies. The later authorization permits focused defect
comparisons and this full audit during the repair; it does not start that
deferred campaign. The
ordinary repair queue completed on September 14 with four FEL holds remaining;
the focused FEL work described above is separately authorized. Use the live
status when resuming, not an old countdown. A failed or stalled service does not
establish repair completion.

1. Read this document and the current preparation ledger. Check the working
   branch/changes, live repair queue, worker state and pause ownership. Preserve
   the running repair/audit work and playback yield. Resolve the resource
   condition before starting the deferred media work.
2. Recheck retained source identities and hashes; build and pin the exact
   candidate binaries in isolated build directories. Use `5450a4fc` separately
   from `3ac80ceb` to distinguish the covariance optimization from intentional
   temporal model changes. The existing comparison manifest still pins
   `497caa64` and `9c1664d4`; preserve those arms and add qualified current
   ordinary `2fa6cfd0` explicitly, retaining `ef5c61fe` as the prior arm. It must not silently represent a newer build.
3. Start with the six targets in
   [pilot-selection.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/retention-prep-20260910/fallback-profiles-20260911/pilot-selection.json)
   plus the existing jacket regression, about 270 seconds of source per arm.
   Verify source-frame alignment and reproduce the historical target with the
   qualified baseline. The initial context is at least ten nominal seconds;
   extend it if a cold excerpt does not reproduce the full-run model state.
4. Use precise source-reason masks and joined checks to identify the useful
   model improvements. South Park's held-colour rejections overlap heavily
   with local mismatch; the HDR episode often preserves source even after a
   successful covariance fit. Legacy logs cannot identify every later reason.
   Improving model coverage must continue to satisfy the picture checks.
5. Qualify actual encoded output with the existing full GPU gate and relevant
   fidelity, local/chroma, temporal, gradient and HDR regressions. Output
   preservation for the speed change and temporal stability for the model-hold
   correction are separate claims. Check labelled negatives as well as passing
   controls. Do not regenerate a positive baseline merely to accept a candidate.
6. Execute the prepared seven-window/70-command quality/size comparison,
   refining operating points until actual video sizes are comparable. Compare
   ordinary FGS, auto and plain AV1; calibrate bounded SVT controls. Pin metric
   definitions, inspect worst scenes, and review grain/detail at playback speed.
   Old campaigns narrow this work; they do not qualify the current build.
7. Measure speed under controlled conditions with pause time accounted for.
   Use the measured quality/byte/time results to resolve retention policy, then
   qualify the chosen build in the isolated real Tdarr flow with staged output
   and rollback checks before production integration. Existing ordinary
   retention and source-savings rules remain the live policy meanwhile.

The overall task remains open while required qualification, retention-cost
resolution or approved library repairs remain outstanding. A clean CPU suite,
completed pilot, or a deployed ordinary encoder is only one part of that goal.

## Where the local state and evidence live

The repair log root is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906`. Paths in this table are
relative to that root unless shown as absolute. These are local records and
private media references; they are not all stored in Git. Additional filenames
in a row share the directory of that row's first path.

| Path | What it answers |
| --- | --- |
| `full-temporal-audit-20260912/work-plan.json`, `OPERATIONS.md`, `published/status.json` | Current full-audit jobs, exact file versions, confirmed findings versus candidate measurements, trial holds and required finish |
| `full-temporal-audit-20260912/inventory.json`, `headers/status.json`, `decoded-v5/status.json`, `resume-v5-20260912/plan.json` | Explicit current-file snapshot, full displayed-header stage and bounded full-image/frame source review |
| `full-temporal-audit-20260912/current-selected-repairs.json`, `installed-vc1-verification.json`, `strict-installed-steven-verification.json`, `strict-installed-amphibia18-verification.json`, `strict-installed-amphibia11-verification.json` | 37-file selection history and all five audit installations, including independent decode, video-packet and retained-stream/source proofs |
| `full-temporal-audit-20260912/qualification.json`, `rollout-record.json`, `final-additional-amphibia-operational-state.json` | Qualified ef5c61fe core, deployed image/runtime identities, monitors and restored repair admission |
| `full-temporal-audit-20260912/resume-v5-20260912/plan.json`, `audit-tools-v5-qualification.json`, `storage-pause-20260912/evidence-relocation.json` | Reused completed evidence, qualified diagnostic corrections, pending checks, replacement catch-up and byte-verified evidence relocation |
| `full-temporal-audit-20260912/published/repair-priorities.csv` | Preliminary human-reviewed repair priorities and source availability, separate from unreviewed diagnostic ranks |
| `retention-prep-20260910/work-plan.json` | Current unfinished encoder objective, constraints, source hashes, completed CPU work and deferred steps |
| `retention-prep-20260910/comparison-manifest.json`, `comparison-plan.json` | Original-source and binary pins, seven quality/size windows and 70 planned commands; none executed by this preparation |
| `retention-prep-20260910/fallback-profiles-20260911/` | Six-log joins, 459,396 decisions, exact diagnostic target profiles, source/log hashes and verification |
| `retention-prep-20260910/model-hold-audit-20260911/` | CPU suite, old-code failing reproduction and archived Ju-on/curve evidence |
| `retention-prep-20260910/existing-log-analysis.json`, `chroma-equivalence.json`, `cpu-suite.json` | Original six-log analysis and prior 40,000-decision colour equivalence/CPU checks |
| `retention-prep-20260910/existing-campaign-inventory-20260911.json` | Older campaign/report inventory and 42 media candidate files; candidates have not been admitted as current references |
| `retention-prep-20260910/reference-retention.json` | The 25 retained artifacts, recorded hashes/identities and hard-link storage accounting |
| `auto-retention-production-20260910/work-plan.json`, `qualified-candidate-9c1664d4.json` | Optional-build quality, full-source costs, actual Tdarr acceptance, unresolved storage cost and pointer to current preparation |
| `auto-retention-production-20260910/foreground-final-state-9c1664d4.json` | Recorded live-state restoration, paused ordinary node and stopped trial containers |
| `production-readiness-20260909/work-plan.json`, `production-rollout-result.json`, `production-rollback-preflight.json` | Ordinary rollout, exact runtime/flow, real scheduler evidence and rollback |
| `status.json`, `progress.md`, `ready-manifest.json` | Current approved repair progress and retained-source work; do not sum unrelated counters into a damage estimate |
| `tdarr-pause-ownership.json`, `source-recovery-hold.json`, `watchability-policy.json` | Pause owner, download hold and recorded review policy |
| `evidence/watchability/`, `reports/watchability-measurements.csv` | Contextual recurrence/severity audit; measurements need their coverage and viewing limits |
| `evidence/grain-syntax/` | Syntax findings, current scans, unresolved entries and repair receipts; syntax accounting is separate from watchability |
| `evidence/jacket-34m05/`, `evidence/movie-extent/`, `evidence/decoded-scenes/` | Original defect and scene/extent review evidence |

Read-only operational checks can start with:

```sh
git -C /home/bardie/git-repos/NVEnc-fgs-fidelity status --short --branch
systemctl --user status fgs-ripple-repair.service fgs-ripple-watchability-audit.service
```

The coordinator and audit scripts are under `/opt/docker-apps/scripts/`:
`fgs-ripple-coordinator.py`, `fgs-ripple-repair.py`, and
`fgs-ripple-watchability-audit.py`. The separate syntax-audit service/timer is
documented in
[the operations guide](/opt/docker-apps/docs/fgs-repair-and-audit.md).
That September 8 guide's encoder revision and numerical counts are historical;
use this handoff and live state for current deployment and queue decisions.

### Retained media, archives and scratch space

The user explicitly requested space care and authorized moving completed work
to cold storage or cleaning it up. Check `/`, `/opt/docker-apps`, `/home` and
`/tmp/downloads` separately; they are different filesystems. Put large new
scratch outputs on `/tmp/downloads`, and retained experiment payloads on
`/media/storage1/tdarr-audit-evidence`. Keep small ledgers and indexes in the
application log tree. Archive completed work after checking active references,
verify copied bytes, and preserve evidence paths and regression controls.
The September 12 cleanup is recorded in
[the storage ledger](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/storage-cleanup-20260912/README.md).
Its receipt identifies original and archive paths, file hashes, metadata and
any ownership changes. Consult it before removing an archive or treating a
relocated artifact's new inode as evidence of changed media content.

- `/media/merged-storage/validation-fixtures/nvenc-fgs/v1` holds the pinned
  source clips and labelled positive/negative controls in
  [FIXTURES.md](FIXTURES.md) and [fixtures.json](fixtures.json).
- `/media/merged-storage/validation-fixtures/nvenc-fgs/retention-20260910`
  and `/tmp/downloads/fgs-retention-prep-20260910/retained` hold the recent
  references. Hard links share data: never modify these media in place. The
  five primary originals keep 15,126,585,999 bytes alive without copying their
  payloads. Unlinking an old name does not release those blocks while another
  link remains. Recorded hashes need rechecking before new experiments.
- `/tmp/downloads/fgs-retention-prep-20260910` holds preparation/reproduction
  scripts. `/tmp/downloads/fgs-auto-retention-production-20260910` holds recent
  full-source outputs and logs. The ledgers bind their exact identities; a
  path's continued existence alone does not establish validity.
- `/media/merged-storage/media/test-encodes` and
  `/tmp/downloads/tdarr-temp` contain older campaign artifacts. Use the
  [campaign inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md) for the Silo,
  SVT, settings, HDR and whole-title reports rather than guessing from filenames.
  Some old sources are missing or have changed at the same path. The
  uncorrected Planet Earth timing sample is excluded.
- Persistent gate tools/builds are under `${FGS_GATE_CACHE:-~/.cache/fgs-gate}`;
  [TIERS.md](TIERS.md) explains exact-commit builds and pinned dependencies.
  Git stores code and findings, not the private media or all raw results.
  Preserve the referenced artifacts when cleaning scratch or test directories.

## Quality requirements for further encoder work

The user's priority is source-picture fidelity and prevention of artifacts,
including ripple and banding, alongside speed and storage efficiency. Evaluate
quality independently: a size or speed improvement does not qualify a change
that introduces artifacts or fails the agreed source-detail checks. Compare
against both the source and the qualified encoder, and retain rejected
examples as regression controls.

The September 10 automatic-retention iteration addresses these questions:

- Smooth gradients, near-black detail and fades in SDR, PQ and HLG now have
  source-labelled, per-frame grain-on/off checks. No new gradient regression
  was found. SDR CAMBI evidence also records existing source/base contours;
  the results do not establish freedom from banding on arbitrary footage.
- Confirmed colour-only detail loss is fixed with independent colour noise
  and direction measurements in bilateral auto, plus restoration of source
  colour components that have no synthesized grain. Clean, noisy, asymmetric
  and moving-colour controls compare with ordinary compression at the same QP.
- Confirmed local grain overshoot is caught by finer independent source
  evidence, including quiet and weak regions excluded from coefficient
  fitting. Cuts and fades check source-fallback entry and recovery. Existing
  sharp-curve, woven-texture, synthesis and jacket regressions remain required.

The [picture findings](FINDINGS-2026-09-10-PICTURE.md) retain the demonstrated
failures, rejected prototypes, decoded comparisons, storage costs and final
qualification. Subsequent local recovery adds independent colour checks and
constrained spatial covariance fitting. Unsupported, coupled or insufficient
evidence preserves source picture before encoding. The existing model checks
still apply. These controlled optional-mode faults
do not establish additional damaged library titles or justify new downloads.

Aggregate quality scores alone do not qualify a candidate. Future local
retention changes must preserve grain balance across regions and time.
Output-preserving speed changes require decoded-pixel comparisons; the
saturated-edge shortcut has those comparisons and a separate bounded timing
study. These results complete this development iteration, not a promise of
lossless encoding or complete perceptual coverage.

The expensive qualification work stays in offline development and bounded
pilots; the existing routine Tdarr validation budget remains unchanged.

The [local recovery findings](FINDINGS-2026-09-10-LOCAL-RECOVERY.md) record the
subsequent source-population, correlated-energy and component-restoration
work, its cost measurements, rejected prototypes, completed acceptance and
the remaining storage-policy and grain-model limits.

## Established

- The intermittent ripple originated in the transcode. The corrected encoder
  is deployed in Tdarr and the repair workers.
- The fidelity branch contains the optional detail-preservation, current-model
  recovery and directional-filter changes. Controlled cases, real footage,
  full episodes, decoded HDR metadata and post-encode media assembly have
  completed their documented checks.
- The offline measured-baseline admission rejects oversized candidates while
  preserving the source. This admission is not yet an active Tdarr policy.
- The exact source/bitstream/track checks and the limitations of sampled or
  conservative measurements are recorded in the linked findings.

## Acceptance and remaining background work

| Work | Required outcome |
|---|---|
| Production integration | Qualified narrow core ef5c61fe deployed; runtime, source/periodic/HDR10 checks, installed repairs and rollback verified |
| Storage policy | Ordinary retain=0 and existing savings rules; the size-policy decision follows matched-size quality and playback evidence |
| Repeat variability | Bounded qualification complete; picture impact measured, operating policy recorded, no unsupported deterministic-output claim |
| Format coverage | Available HDR10+/P7 MEL and true-interlace paths pass; FEL/uncertain source video is preserved |
| Speed and overhead | Byte-accounting optimization and bounded DV guard retained; four-thread HDR sampling deployed after identical-metadata checks, 90 unit tests and actual-node validation/rollback |
| Further automatic-retention quality | Controlled colour/local-grain faults fixed and full-source/Tdarr acceptance complete; source preservation still costs 20–30% more bytes on measured episodes and leaves about 1% usable synthesis coverage |
| Library remediation | Running in background; repair-worker DV guards and metadata fixes installed, evidence-based later recovery remains under the download hold |

The active operational ledger is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/work-plan.json`.
It distinguishes completed foreground engineering from ongoing background
repairs and explicitly deferred investigations.

## Persistent constraints

The existing ripple protection and repair/audit services stay active. The hold
on new recovery downloads remains in force; a conservative header flag does
not justify a blanket redownload. Oversized or uncertain outputs retain their
input. Exhaustive development audits do not become routine per-file Tdarr
validation by accident. The unrelated FFprobe XML-printer investigation is
documented and deferred.

The user explicitly chose to continue encoder work without the FFprobe
XML/AddressSanitizer investigation. Keep its findings documented; it is not a
prerequisite for the next retention trial. The JSON metadata path and its
qualification are recorded in the later integration/local-recovery reports.

The earlier 1,981-file/9.5-TB figure described a conservative repair scope,
not individually confirmed visible damage. Subsequent title/source identities
and audit coverage matter. Review recurrence, severity and watchability before
new recovery selections; prior source searches do not establish that no
original can exist at another path or later date. The separate September 4
import move-versus-copy/seeding incident was fixed and is not an open encoder
task. Keep those histories distinct when resuming library recovery.

The 10% measured-baseline limit remains a trial setting requiring a complete
matching baseline. The ordinary production flow keeps default retention and
its existing source-relative savings policy, so it gains neither a second
encode nor a source-hash pass. Optional automatic detail retention remains
outside broad production activation. The separate source-savings review
alternative has passed actual accepted/rejected jobs and restoration without
changing the 10% trial rule.

## Evidence and implementation index

Use the relevant report for exact commands, build identities, rejected
prototypes, numerical results and limitations. Dates indicate historical
context, not continuing deployment. In particular, July hypotheses and initial
coarse-grain limits are not conclusions about today's corrected encoder.

| Topic | Entry points |
| --- | --- |
| Tests, coverage and retained controls | [Test README](README.md), [tiers](TIERS.md), [fixtures](FIXTURES.md), [fixture manifest](fixtures.json), [full local gate](local_gate.sh) |
| Grain inspection, HDR/display assumptions and visual review | [Review tools](../../tools/fgs/README.md), [display qualification](FINDINGS-2026-09-07-DISPLAY.md) |
| Original analyzer work and historical limits | [July 17](FINDINGS-2026-07-17.md) |
| Sampling correction, quality/size and texture-substitution history | [July 29 performance](FINDINGS-2026-07-29-PERFORMANCE.md), [July 30 texture](FINDINGS-2026-07-30-TEXTURE.md), [July 31 model statistics](FINDINGS-2026-07-31-MODEL-STATS.md) |
| Recovered historical campaigns | [September 11 inventory](FINDINGS-2026-09-11-EXISTING-CAMPAIGNS.md), [July campaign plan](/opt/docker-apps/docs/fgs-measurement-campaign.md), [historical open questions](/opt/docker-apps/docs/fgs-open-questions.md) |
| Reliability and source/detail behavior | [September 7 hardening](FINDINGS-2026-09-07-HARDENING.md), [September 8 fidelity](FINDINGS-2026-09-08-FIDELITY.md) |
| Initial retention cost and repeat variability | [Cost](FINDINGS-2026-09-08-COST.md), [repeatability](FINDINGS-2026-09-08-REPEATABILITY.md) |
| Full-source checks, admission, repeats and deferred XML issue | [September 9 trials](FINDINGS-2026-09-09-TRIALS.md) |
| Post-encode assembly and validator time | [Integration](FINDINGS-2026-09-09-INTEGRATION.md) |
| Ordinary production, DV, byte accounting and real scheduler | [Readiness evidence](FINDINGS-2026-09-09-READINESS.md), [rollout/rollback guide](../../tools/fgs/TDARR-ROLLOUT.md), [repair DV handling](../../tools/fgs/REPAIR-DOVI.md) |
| Initial automatic-retention recovery and edge protection | [September 9 auto retention](FINDINGS-2026-09-09-AUTO-RETENTION.md) |
| Colour detail, local grain, gradients, cuts and fades | [September 10 picture](FINDINGS-2026-09-10-PICTURE.md) |
| Current optional recovery, coupled colour, costs and qualification | [Local recovery](FINDINGS-2026-09-10-LOCAL-RECOVERY.md) |
| Measured size limit and separately tested source-savings alternative | [Measured pilot](../../tools/fgs/TDARR-PILOT.md), [source-savings review](../../tools/fgs/TDARR-SOURCE-SAVINGS.md) |
| Retained references, precise traces and prepared comparisons | [Preparation](FINDINGS-2026-09-10-RETENTION-PREPARATION.md), [diagnosis/planning/comparison usage](../../tools/fgs/RETENTION-TRADEOFFS.md) |
| CPU model-reuse correction and archived reproduction | [Model hold](FINDINGS-2026-09-11-MODEL-HOLD.md), [CPU regression](model_hold_test.cpp) |
| Overlapping fallback checks and six diagnostic targets | [Fallback profiles](FINDINGS-2026-09-11-FALLBACK-PROFILES.md), [analyzer](retention_diagnostics.py) |
| Repair/source matching, syntax audit and review limitations | [Operations guide](/opt/docker-apps/docs/fgs-repair-and-audit.md), live state/evidence map above |

Those reports retain their completed-study status. This broader production
work does not inherit that status. When another stage completes, update this
handoff and the current ledger with the exact revision/binary, validation,
remaining work and any deployment change; keep the underlying reports intact.
