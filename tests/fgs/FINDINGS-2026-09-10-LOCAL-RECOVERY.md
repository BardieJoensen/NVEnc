# Local grain recovery and Tdarr acceptance

Status: **core 9c1664d4 passes exact-build short/full-source quality qualification,
ordinary and source-savings Tdarr acceptance, and rollback. All three full sources
exceed the unchanged 10% trial cap; coarse optimization remains failed**.
The faster HDR validator is deployed. Automatic-retention rollout still needs
a storage-policy decision. This report does not close the broader
[work through production](WORK-TO-PRODUCTION.md).

Evidence directory:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/auto-retention-production-20260910`.
Scratch and decoded controls:
`/tmp/downloads/fgs-auto-retention-production-20260910`.

## Demonstrated defects and recovery

The preceding `02a6c86b` iteration protected quiet regions at distinct
brightnesses, but averaging all patches at one brightness could still hide a
small quieter region. New source-labelled controls reproduced this in luma,
Cb and Cr, including motion, medium grain, PQ and HLG. These are demonstrated
optional-mode control failures, not additional identified library damage.

The local guard now keeps six source-strength populations within each fine
brightness bucket. Source/base variance and covariance describe the total
predicted played-out grain. A rejected model first gets an independent luma
strength refit, within AV1's 14-point limit. This keeps the AR coefficients,
shared scaling shift and colour curves unchanged. Failed attempts are
transactional. Quiet borders can use a narrow zero-strength plateau without
removing grain from unobserved brightnesses. Conflicting local strengths at
one brightness retain the source; one global curve cannot represent them.

Colour components get independent local energy checks. Approximately white
colour grain with sufficient current observations and negligible measured and
signalled luma coupling can preserve only its source component. All-zero
scalings preserve AV1's paired Cb/Cr point-count requirement. Coupled, spatially
correlated or insufficient colour evidence uses whole-frame source retention.
The original model stays in the temporal cache; source-component restoration
has its own stricter, three-frame recovery requirement.

A separate correlated-luma control exposed under-strength grain after the
quiet border was repaired. A retained noisy base and its removed residual are
correlated, so removed-residual variance alone is an incorrect independent
synthesis target. Source-flat 32x32 patches now require an adjacent source
picture with stable local level and independently changing noise. Their
source/base moments supply the synthesis target. Strength-population labels
use the independent previous sample so ordinary sampling variation does not
create artificial populations. The first correlated picture is preserved
while that temporal witness is unavailable.

The coarse check pools this evidence across its actual brightness interval.
Requiring four samples separately in every fine bucket had left some coarse
bins comparing against the old residual target and rejected otherwise valid
recovery. The corrected check still needs four independent observations in
the coarse interval. Fine population checks remain separate vetoes.

## Controlled evidence

Prototype 7 is pinned in `recovery-7-build.json`; its binary SHA-256 is
`e25e677942c28c042f10a740fe764e018783dcb12c878bb9032fdafcefe2e000`.
The cached build label is historical; identify this prototype by its binary
and source hashes. A separately identified final build is required for the
remaining acceptance stages.

The 19 picture controls, 23 local-grain controls, 16 controlled cases at both
retention ceilings and nine strength/transition controls passed their individual
checks. The claimed eight texture-residual passes were invalid: the prototype
runner still pointed those checks at `controlled-3`. Exact-build qualification
of core `f9d087ca` caught residual ratios of 1.273 and 1.219 in `detail_coarse`
and `woven_coarse`, exceeding the unchanged 1.10 limit. The earlier separate
cost pass combined mismatched evidence and did not qualify prototype 7.
`qualification-final.json` and `texture-final.json` retain the rejection.
The cost harness now requires the texture report's hash binding to match its
controlled report, with a regression test that rejects stale evidence. Every tested output is scanned
for synthesis stability; both grain-on and grain-off output are decoded.
The local controls include positive and negative luma-colour coupling and
uniform-grain controls around the strength-group boundaries.

The quiet/noisy brightness control drops from 2,909,640 bytes with the prior
whole-source fallback to 311,130 bytes, a reduction of 89.31%, at the same QP.
Quiet-region decoded checks still pass. Same-brightness conflicts continue to
preserve source rather than claiming this saving.

In the coarse directional control, the median decoded flat-grain sigma ratio
improves from about 0.778 to 0.871 without changing QP. The complete output is
1,191,873 bytes versus the preceding cost-study reference's 1,202,403 bytes
(-0.876%). The newly preserved startup picture adds 18,284 measured video
packet bytes. Excluding that one measured startup difference, the earlier
processing optimization still saves 2.396%.

A separately reviewed size calculation compared a two-second clip with
no protected startup picture and missed its 1% saving threshold by 1,494 bytes.
`startup-cost-accounting.json` records the resolution. The cost regression now
separately measures this first packet only when exactly frame zero is retained
and the reference has no source fallback. Full file sizes remain reported.
The rejected prototype with 47 fallback frames still fails this check. No
Tdarr size limit or picture-quality bound was relaxed. The original failed
qualification record remains intact. The startup byte calculation remains
valid, but it does not resolve the independently failed texture checks.

On the 150-second Gentlemen interval, ABBA means were 45.669 seconds for
`02a6c86b` and 45.569 seconds for prototype 7 on the shared server. Output grew
from a mean 47,338,406.5 bytes to 49,602,274 bytes (+4.782%). Whole-source
fallback increased from 98 to 1,162 of 3,600 frames. This is additional source
preservation with no measured slowdown in this bounded run, not a universal
performance guarantee. All real-clip grain-on/off decodes, timelines and
synthesis scans pass; fixed/default-mode decoded pixels remain unchanged.

## Coverage and limits

### Spatial texture and transient brightness follow-up

Correcting amplitude while retaining the old residual's AR shape increased
fine-grain energy in the coarse controls. New independently measured spatial
covariances describe the required synthesis after subtracting retained-base
energy. The matrix must be positive definite with a bounded sampling ridge;
sparse or inconsistent evidence preserves the source. The occupied strength
curve remains independently checked after fitting.

This exposed a second problem: some fitted coarse templates changed a band's
mean briefly, even though its steady-state grain amplitude passed. Prototype
9's coarse controls reached mean differences of 0.621 and 0.678 eight-bit code
units. Prototype 10 also failed the larger local correlated/border controls.
The lower-band check now covers every frame and all 12 brightness bands, with
the same 0.5-code limit used by the local controls. The texture test retains
its established steady-state bound and now checks transient HF excess too.
The local correlated controls also measure fine-grain energy, alongside mean
and total amplitude. These are source-labelled engineering checks, not HDR
perceptual scores or a promise of exact grain reproduction.

The recovered fit limits low-frequency amplification and normalizes strength
from the quantized AR transfer spectrum. Its high-frequency energy must also
agree with the independent source-minus-base target. A stronger constraint
alone was insufficient: prototype 12 fixed brightness but raised decoded
coarse HF residual medians to 1.445 and 1.362. Prototype 13 still had a transient
texture failure. Their failed results remain recorded. Prototype 14 passes
the joint decoded checks; it does not qualify the earlier coarse size saving.

`qualification-14.json` records 16 controlled cases at both retention caps,
eight texture cases, 23 local-grain controls, 19 picture controls, the real
clips and the quick ripple gate. Its `quality_passed` is true and its overall
`passed` remains false because the old coarse optimization check still fails.
The tested binary SHA-256 is
`da03108266b12639da74f4fb5ac2a88c762568fb7c76da23f69859ab74a3396f`.
All 48 frames of the three coarse controls at cap 0.1 preserve source.
`preserved-coarse-14/report.json` proves that their grain-on and grain-off
decoded pixels are identical to plain encodes with the same candidate and QP.
This is measured source preservation with its full byte cost, not successful
reproduction of the old coarse optimization.

On the 150-second Gentlemen interval, the new ABBA mean is 28.968 seconds,
versus 29.052 seconds for `02a6c86b` automatic retention on the shared host.
The new output is 51,759,133 bytes versus 47,351,720 (+9.308%), with 2,134 versus
98 source-fallback frames out of 3,600. These figures compare two automatic
modes, not the current production default, and do not establish full-title
admission. The other real clips also retain additional source information
and cost more bytes. Ordinary/default decoded pixels match in the bounded
real-clip comparisons. Production-setting measurements for the committed
replacement are recorded below.

AV1 synthesizes grain from a seeded finite template; its normative process
does not provide an encoder-controlled global mean correction.
See the [AV1 film-grain synthesis specification](https://aomediacodec.github.io/av1-spec/av1-spec.pdf).
The checked-in NVENC API also exposes no grain-seed input. The connection
between finite-template low-frequency amplification and the measured offsets
is an inference supported by the constrained-fit trials. It is not a new
diagnosis of damage in existing library files. Fits which cannot jointly meet
the measured fidelity constraints retain source pixels and can cost more
bytes. They must still meet the separate Tdarr admission budget before use.

The original coarse optimization check remains intact and continues to fail
when repeated source retention loses that saving. A texture or brightness
failure must not be excused by a byte saving, nor can the old optimization be
claimed from a model which fails the new decoded checks.

Full-frame metadata recording now uses bounded streaming FFprobe JSON. The
deferred XML-printer investigation remains deferred. JSON and legacy XML
trace digests have explicit format identities and cannot be mixed into a
false report of metadata loss. The trusted 736-frame dual-HDR reference was
recorded successfully with all expected metadata types.

### Colour grain appearing after a quiet interval

Core `ebad733e` passed the then-existing 23 local controls, but review found
that a fresh covariance fit could activate colour grain after the held model
had been quiet. Checking only the held model's independence missed coupling
in the new model. A 24th control, `chroma_coupling_entry`, reproduces the fault:
source Y/Cb correlation at frame 16 is 0.796; the same-QP plain encode is 0.741,
and the rejected candidate falls to 0.636. Its synthesis syntax scan passes,
so syntax stability alone does not establish colour-grain fidelity.

Eligibility is now checked again on the freshly fitted model before it can
replace the held parameters. The targeted prototype retains that source frame
and measures correlation 0.743, with no local amplitude, mean, texture or
coupling failures across all 48 frames. The rejected exact binary and the
targeted regression remain recorded in `ebad-followup-rejection.json` and
`coupling-entry-recheck/report.json`. This targeted pass does not qualify the
replacement build or complete the full-source/Tdarr acceptance stages.

### Committed transition fix and production settings

Core `9c1664d473926f2b93c93c1c04a8cc4f824fc0b4` contains the transition
postcondition. Its independently rebuilt binary SHA-256 is
`8dff824c8d7360adac294f05e7c6032770f8594cf1c3b63961f50a854e3b0fec`
(`r4252`). `exact-9c1664d4/qualification.json` records passing CPU tests,
16 controlled cases at both retention caps, all-frame texture/brightness
checks, the three same-candidate plain-encode preservation comparisons,
24 local controls, 19 picture controls, nine strength controls, 16 real
encodes and their complete grain-on/off decodes, the ripple gate, and both
complete short production-source comparisons. The unchanged coarse cost
optimization still fails and is explicitly separate from quality acceptance.

The 150-second Gentlemen ABBA means are 88.323 seconds for the preceding
automatic mode and 86.494 seconds for this candidate. Video-only outputs are
47,322,014 and 51,768,902 bytes respectively (+9.397%). Both new-candidate runs retain
2,134 of 3,600 source frames, versus 98 with the preceding automatic mode.
The server was running other repairs; the GPU encoder was later observed at
100% utilization with three concurrent encodes. These are shared-host timings,
not an isolated speed guarantee. Ordinary-mode decoded pictures remain equal
in all required comparisons.

Complete production-setting short clips cost substantially more than the
current live default: Bridge is +48.019%, and the dual-HDR Shining interval is
about +69.6%. A deterministic AVC weak-grain control is +243.5%, and a clean
motion control is +15.0%. They are recorded rejected admission examples,
not successful automatic-retention pilots. No quality bound or the 10% pilot
budget was changed to admit them. The controls do not establish the cost of
whole titles.

All six full-source encodes and all complete grain-on/off decodes,
source-property/timeline checks and synthesis scans have passed. The complete
HDR metadata comparison has also passed:

| Complete source | Frames | Live-default video-only bytes | Automatic video-only bytes | Increase |
|---|---:|---:|---:|---:|
| South Park S23E01 | 32,176 | 268,741,386 | 343,289,829 | 27.740% |
| The Gentlemen S01E01 | 96,671 | 992,177,278 | 1,190,807,948 | 20.020% |
| House of the Dragon S03E08 | 100,851 | 3,189,340,911 | 4,155,975,758 | 30.308% |

All three exceed the trial budget. Independent packet-byte admission has
also completed: primary-video growth is 27.763%, 20.033% and 30.315%, and all
three correctly select `keep_source` at 10%. `full-source-admission-9c1664d4.json`
binds these decisions to the completed qualification and independently counted
packets. Actual measured Tdarr jobs also reject the two short real candidates.
These are video-only figures;
retained audio and final media assembly have their own source-size policy.

`full-source-9c1664d4.json` is complete and passed. Both HDR outputs match
the source's timestamps, mastering display, content-light and Dolby Vision
metadata across all 100,851 frames, with zero differing frames and no stream
property failures. Each of the three metadata types is present on every
frame of all three traces. The source is HDR10/PQ plus Dolby Vision P8.1;
the separate complete 736-frame Shining controls cover HDR10+ as well.

`source-video-bytes-9c1664d4.json` independently counts the original primary
video with the unchanged Tdarr byte helper, verifies source identities and
matches complete packet counts. The original video totals are 3,330,259,090,
2,412,529,020 and 7,775,960,897 bytes respectively. Charging the candidate's
entire video-only container against those video bytes gives conservative
savings of 89.692%, 50.641% and 46.554%. These source-relative figures do not
satisfy or change the separate 10% old-encoder trial cap.

The full HDR automatic encode yielded to Emby for 303.660 seconds and resumed
successfully. Its 3,020.057-second wall time includes that pause; active time
is approximately 2,716.397 seconds against the baseline's 2,410.041 seconds.
Repairs shared the GPU during both runs. The other episodes were faster with
the candidate in this schedule, but these timings do not establish an
isolated encoder speed improvement or regression.

The full Gentlemen outputs also pass the jacket checks at 33:24, the user's
34:05 position, 34:06 and 34:24.5. Both arms remain within the established
source-error and grain-concentration bounds, and suppress grain at the two
required regression positions. Automatic mode preserves source picture at
all four checked positions before AV1 quantization. The source alignment
check confirms exact agreement with the pinned lossless regression clip.
`full-jacket-9c1664d4.json` records these eight output/position checks; they
do not certify every scene's perceptual quality.

`full-sdr-model-diagnostics-9c1664d4.json` distinguishes explicit fidelity
fallback from all unusable-model cases. The former occurs on 29,854 South
Park frames and 84,490 Gentlemen frames. Including frames with no reliable
model, source picture is preserved on 32,099/32,176 and 95,809/96,671 frames
respectively. A reliable synthesis model survives on less than 1% of each
complete episode. These measured coverage and storage limits
remain material even though the required quality checks pass. Diagnostic
events overlap; a recovered local curve alone is not a final accepted model.

The completed `full-model-diagnostics-9c1664d4.json` adds the HDR episode.
Its automatic mode explicitly falls back on 97,515 frames; including all
unusable-model cases, it preserves source picture on 99,841/100,851 frames.
Thus reliable synthesis survives on about 1% of this source too. There are
96,568 covariance attempts and 7,691 successful covariance fits, but later
quality checks still reject most of those fits. The earlier ordinary encoder
has 2,535 unusable-model frames on this episode. These are model/fallback
counts, not a classification of visibly damaged scenes.

`fallback-reasons-short-9c1664d4.json` records overlapping diagnostic events.
The colour-eligibility check vetoes all 735 covariance attempts in the Shining
interval and 1,699 in the Gentlemen interval. That check includes insufficient
evidence and correlated colour residuals as well as luma/colour coupling;
the compact event does not identify its failing subcondition. A veto is not
proof of damaged media, a particular source correlation, or impossibility of
a different grain model. Source retention remains the qualified behavior for
these currently unsupported fits.

These measurements establish the named controls and intervals. Sparse or
structured regions cannot certify the whole picture. The correlated-grain
check depends on source-flat, temporally independent evidence; the local
colour recovery eligibility is intentionally narrower. Existing syntax and
feedback guards remain in force. Encoding quantization still applies to
preserved source pixels. Ordinary fixed retention does not allocate the new
analysis buffers or run these additional checks.

Grain texture remains an approximation. An additional source/output spatial
correlation audit of prototype 6 (`correlated-texture-6.json`) found remaining
lag-four correlation of about 0.14 in the repaired Gaussian-grain border
controls, compared with approximately zero in the source. This difference
was also present in the preceding optional encoder; amplitude recovery does
not solve every covariance/texture difference. It is not evidence of another
unstable ripple or of additional damaged library titles. Aggregate amplitude
checks must not be described as complete grain-texture or perceptual fidelity.

## Completed Tdarr acceptance

Complete retained sources for The Gentlemen S01E01, South Park S23E01 and
House of the Dragon S03E08 are independently hashed in
`full-source-preflight.json`. The executed video arguments are pinned in
`full-source-trial-manifest-9c1664d4.json`. Complete candidate/baseline size,
metadata, timeline, decode qualification and independent admission have passed.
Actual measured and ordinary scheduler jobs have also passed their checks.

The Tdarr builders now support upgrading the already deployed source-size and
Dolby Vision guard layout. Both original and already-preserving FEL policies
are handled explicitly; unknown guard settings and routing are rejected.
The 12 routing tests and preparation from the actual current flow pass.
`prepared-flow-checks.json` pins that source flow. These prepared graphs have
not activated a candidate or changed the ordinary validation budget.

The exact 10% measured-baseline budget continues to need a complete matching
baseline. Rejected or unlisted pilot sources are retained; no hidden QP rise
or substitute lower-quality encode is introduced. The existing ordinary
flow keeps fixed retention and its source-relative saving rules. Final
runtime and canary evidence is recorded below. The source-savings alternative
has also completed accepted-output verification and restoration.
Background repair/audit services, their pause ownership,
Emby yielding and the hold on new recovery downloads remain in force.

Core remains pinned to `9c1664d4`; commit `87d10506` adds a separate
[source-savings review alternative](../../tools/fgs/TDARR-SOURCE-SAVINGS.md).
Both paths require 5% savings against original video plus identical retained
tracks, without an old-encoder baseline encode. Source/build checks span the
job using filesystem identities and one encoder hash pass. Four node
test groups and eight routing tests pass, and an immutable image and bundle
were prepared from the actual current flow. This alternative has passed
isolated accepted/rejected jobs, staged-output qualification and restoration
of the prior lab image, flow and plugin archive. It has not changed the live
flow or the measured pilot's 10% limit. It does not solve the remaining
grain-model coverage or coarse optimization limits.

`source-guard-overhead-9c1664d4.json` runs the actual preparation plugin six
times inside that pinned image. It hashes the 404,954,536-byte encoder and
checks real read-only source copies in 0.557–1.157 seconds per call. It does
not read media contents. Container startup and Tdarr scheduling are excluded;
these shared-host, normally cached measurements do not establish a universal
cold-start bound. Actual flow and validator timings follow below.

The isolated scheduler setup exposed two API assumptions in the private test
runner. Tdarr assigns library IDs on insertion, and connected-node controls
use a runtime ID while persistent node settings use the node name. The runner
now uses the assigned library ID and resolves the connected runtime ID before
each control call. The unsuccessful setups started no media jobs; their logs
and records remain preserved. The corrected acceptance controller also pins
the API helper. These setup corrections do not change encoder or plugin bytes.

### Completed measured and ordinary scheduler jobs

`canary-execution-9c1664d4.json` and `canary-result-9c1664d4.json` record the
real measured-policy jobs. Bridge and Shining encode successfully and exceed
the exact 10% packet-byte limits; both originals are retained. The unlisted
source skips candidate encoding. No accepted source was invented for this
policy. The actual encoder pause/resume exercise passes.

`ordinary-canary-result-9c1664d4.json` records two accepted staged outputs:
all 765 Bridge frames and 736 Shining frames pass full grain-on/off decodes,
stable synthesis scans, declared video properties and relative packet timing.
Both video payloads and decoded pixels are identical to the qualified offline
ordinary outputs. The true-interlace case encodes 600 frames and is rejected
at 127.25% of its retained-stream baseline. All original copies remain hashed
and unchanged; the lab review flow cannot replace library files.

The Shining remux changes video timestamp origin by exactly -125 ms. The
offline HDR comparator now has an explicit `--allow-common-origin-shift`
mode: it records the one offset and requires exact rational relative cadence,
all frame indices and counts, and every metadata value. Strict absolute
timestamps remain the default. Eleven CPU tests pass, including rejection of
cadence drift, changed metadata, missing timestamps, reordered frames and
truncation. This normalization does not verify audio synchronization; the
existing stream-alignment checks remain separate.
`ordinary-canary-hdr-origin-9c1664d4.json` passes every one of the 736 frames
against the trusted reference, including mastering display, content light,
HDR10+ and Dolby Vision. The earlier strict-origin failure remains preserved.

Routine validation takes 4.4 seconds on the SDR clip. On the 4K dual-HDR clip,
it takes 75.0 seconds: source HDR sampling 42.4, output HDR sampling 15.3,
and sampled visual provenance 17.1 seconds, with the remaining checks small.
These are actual timings from the unchanged validator in a four-CPU-limited
canary on the shared host, not universal per-file costs. Exhaustive offline
decodes and metadata comparison remain outside routine Tdarr validation.

`canary-rollback-9c1664d4.json` verifies restoration of the deployed encoder
image and original flow, then restoration of the candidate image and review
flow. All 148 plugin files match at both steps. The lab finishes paused with
library processing disabled. The complete base acceptance record binds eight
passed reports in `remaining-acceptance-complete-9c1664d4.json`.

### Alternative runtime installation correction

The initial alternative image was rejected before encoding: `COPY --chmod=0644`
also created the new plugin directories with mode 0644. Root hash verification
passed, but Tdarr's UID 1000 worker could not traverse the directories and
reported a missing plugin. Restarting the server did not solve it. The corrected
image sets both new directories to 0755, and preflight now reads all 150 plugin
files and loads the guard as UID/GID 1000:1000. Encoder and plugin contents are
unchanged. The image and revised flow bundle are pinned in
`source-savings-runtime-access-9c1664d4.json`. The unsuccessful installations
and the controller's transient file-record polling failure remain preserved;
the completed interlace encode is reused rather than repeated.

### Completed source-savings jobs and decoded comparisons

`source-savings-canary-execution-9c1664d4.json`,
`source-savings-canary-result-9c1664d4.json` and
`source-savings-canary-restore-9c1664d4.json` are complete and passed.
The corrected runtime is image
`sha256:cc7cc26f4717eeb92db5b91d70e7588ff1bd2fd14a2d9766519ccace2f9a6ed7`.
Bridge stages 7,544,454 bytes (9.928% of the source-relative baseline), and
Shining stages 45,960,109 bytes (17.531%). Both source/build checks pass.
The 600-frame interlace output is rejected at 131.57%; no substitute encode
or QVBR increase is used. Every input copy stays unchanged, and actual
encoder pause/resume is observed. The prior lab image, flow and 148 plugin
files are restored with processing disabled.

Both accepted videos pass full grain-on/off decodes, stable synthesis scans,
properties and exact relative timelines. All 736 HDR frames match the trusted
reference after one exactly measured origin shift, including all four HDR
metadata types. Their pixels and video payloads differ from the offline
automatic encodes, despite the same video settings. These results therefore
cannot inherit the ordinary-mode pixel-identity claim.

`staged-picture-9c1664d4.json` measures every native-resolution frame against
the original and the qualified offline encode. Grain-on source luma RMS error
is 1.104 versus 1.105 for Bridge and 1.242 versus 1.243 for Shining on an
eight-bit code scale. Offline/staged luma RMS differences are 0.429 and 0.559;
the largest whole-frame RMS differences are 0.790 and 0.650. All Y/Cb/Cr
per-frame traces are retained. Shining's grain-on/off pictures are identical
in both outputs, so its second metric decode is omitted with hash evidence.
These are bounded code-value measurements, not HDR perceptual scores or proof
that every localized difference is invisible. Repeat variation remains a
documented limitation of this encoding path.

### Faster HDR validation, with the same sampled evidence

The existing HDR metadata probe ran without an explicit decoder thread count.
The offline ABBA benchmark now exercises the installed sampling function with
four threads. It obtains exactly the same parsed frame metadata, frame counts
and validator result in every run: 590 sampled HEVC source frames and 600
sampled AV1 output frames. Source sampling improves from a mean 41.321 to
13.230 seconds (-67.98%); output sampling improves from 14.304 to 9.813 seconds
(-31.39%). The intervals, entries and parsing are unchanged. This uses up to
four decoder threads while sampling, rather than reducing the evidence checked.

The one-line [patch](../../tools/fgs/tdarr-hdr-sampling-threads.patch) passes
90 existing validator/plugin tests. The full validator passes both clips;
the paired HDR run improves from 88.7 to 48.9 seconds including process
startup. It also passes in the actual isolated node in 42.0 seconds. These
shared-host timings are bounded measurements, not universal runtime limits.
`hdr-sample-threads-9c1664d4.json` and `hdr-validator-threads4/validation.json`
bind the evidence.

The rollback rehearsal exposed Tdarr's automatic ZIP regeneration. It changed
the archive hash and UTF-8 flags while preserving all 440 members' contents,
names and permissions. The installer now accepts only a verified equivalent
repack of a hash-pinned old or new archive; changed bytes, names, permissions,
unknown flags, encryption and duplicate members still fail. Three archive
tests pass, including an exact original-byte rollback after a Tdarr-style
repack. The actual lab installation, execution and rollback pass too.

`hdr-validator-threads4/production-installation.json` records deployment of
the single validator change, SHA-256
`3a1e8ffed6c56039d8aacd1b06499d396aba5331d06bc27ce788b2c8cccb4313`.
All 148 live plugin files are verified as UID/GID 1000:1000. The encoder,
image, flow, size rules and worker limits retain their prior values. The
repair-owned node pause and both repair/audit services are preserved, and the
original startup setting is restored. Exhaustive development tests have not
been added to routine Tdarr jobs.
