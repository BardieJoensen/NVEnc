# Finer source protection — September 12

Status: **qualified narrow core ef5c61fe deployed**. The full library audit
continues independently. Start at [WORK-TO-PRODUCTION.md](WORK-TO-PRODUCTION.md)
for the current runtime, repair state and deferred broader branch work.

## Demonstrated problem and fix

The preceding `273723b7` guard could miss clean artwork contained within a
textured 32x32 source-analysis block. In Steven Universe S1E23 at 01:47.441,
a 16x16 source patch had standard deviation 0.25 while the containing detrended
32x32 block measured 5.294. Synthesized noise in the clean patch reached about
10.7 native eight-bit-normalized code levels. The larger block correctly saw
texture but could not protect its clean subregion.

Core `ef5c61fe62232e6917d3d2a7adc248bac06d5ae4` adds four finer source samples
per existing analysis region: 16x16 Y and 8x8 U/V. Model fitting still uses its
existing region. Fine samples require deviation at most 0.3; coarse evidence
retains 0.5. Four native eight-bit code levels of reconstructed brightness
headroom prevent a small base-reconstruction level change from escaping the
protected source range. Temporal recovery, model rejection, partial-edge,
constant-colour, ripple and syntax protection remain in force.

Samples use pixels already cached in the CUDA block. There are no extra global
pixel reads, kernel launches or host synchronization. Integer sums and squared
sums fit 32 bits for the supported 8/10-bit inputs, with a 64-bit variance
numerator. P010 is normalized to ten bits before analysis. Empty partial regions
still participate in the required lane reduction and are not divided by zero.
This review covers accepted NV12/YV12/YV12_10/P010 inputs, not arbitrary 16-bit
formats.

## Qualification and retained failures

Local evidence below is relative to
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912`.
[qualification.json](/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/qualification.json)
pins the artifacts used for deployment.

| Evidence | Result and scope |
| --- | --- |
| `strict-full-gate/result.json` | Original full gate: 16 passes and one periodic sequence-change alert; original limits/results retained |
| Mixed-source gate cases | All ten 8/10-bit cases pass; the previous deployed build fails the four fine-region CQP/QVBR negatives |
| `strict-periodic-source-review.json`, `strict-periodic-visual-review.json` | All 3,600 source frames numerically compared, selected source/old/new frames inspected, intentional change explicitly reviewed |
| `strict-periodic-baseline-receipt.json`, `strict-periodic-final/result.json` | Separately named reviewed positive; fresh complete regression passes at unchanged numeric limits |
| Real-film oracle and base-fidelity canary | Taxi/Silo/Alien controls and original quality limits pass |
| `strict-source-container-smoke.json` | Five actual runtime-image source cases pass: Amphibia, Lost Tapes 8/10-bit, South Park and opening colour |
| `strict-hdr-runtime-check.json` | Actual runtime HDR10 encode: 24 independently decoded frames, native metadata, timing and synthesis checks pass |
| `fine-source-strict-steven-trials/` | 48 original-source windows pass; complete chosen-region checks span 33,305 frames, old strong counts 76/207 become zero |
| `strict-amphibia18-trial/`, `strict-amphibia18-recurrence/` | 23 original-source windows pass; three chosen regions followed through 17,193 frames, old strong count 818 becomes zero |
| `strict-amphibia11-trial/`, `strict-amphibia11-recurrence/` | 21 original-source windows pass; three chosen regions followed through 17,194 frames, old strong count 874 becomes zero; earlier flash witness still passes |
| `strict-steven-old-witnesses/`, `strict-amphibia18-old-witnesses/` | Nine Steven and one Amphibia earlier flash witnesses remain passing |
| `routine-monitor-final/` | Actual installed-image canary and supported monitor health pass; unchanged Tdarr validation policy |

The HDR metadata assertion initially demanded literal equality between container
rationals and AV1 fixed-point fields. Independent examination found the encoder
had written the correct nearest representable values. The completed check
compares each representation correctly and rejects one-code corruption,
missing mastering data and wrong content-light values. The original failed
measurement is retained; this did not require an encoder metadata change.
The 24-frame check does not qualify Dolby Vision or physical TV playback.

Two preliminary candidates remain rejected. `2558962b` exposed reconstructed
brightness leaving the protected range. `b702a30f` passed the small-region
controls but failed the real-film oracle and periodic gate. Stronger quiet
source evidence was implemented before the final qualification. The oracle
measurement also had a separate range-conversion problem: grain curves need
native Y occupancy, not display-expanded gray. Seven CPU regressions and
independent full-YUV real-fixture histograms verify that correction. Correcting
the measurement alone did not qualify the rejected candidate.

The periodic source review found the same 1,671 grain-on frames and 29 on/off
transitions as `273723b7`; no extra grain-on frames appeared. Mean source RMS
improved in all planes and source low-pass errors improved. Fine grain is a
tradeoff: mean quiet-region high-frequency energy was 0.2914 in the source,
0.3135 in the older output and 0.2500 in the new output. One reviewed window
was 0.252 / 0.277 / 0.149 respectively. Protecting clean regions at shared
brightness can attenuate genuine fine texture. The separately named positive
records acceptance of this demonstrated tradeoff; it does not erase the old
alert, replace earlier controls or assert pixel-perfect source preservation.

## Deployment and installed files

The immutable production binary is
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/bin/nvencc-ef5c61fe`, SHA-256
`d8127dfa63011160dc222a41516452c269c2438269866b3da74f95e5ba4fd47b`.
The image is `nvenc-fidelity/tdarr-node:2.87.01-ef5c61fe-20260912`, ID
`sha256:218540effe6149030631445914c8f35c6e81090326a8e4bbca55d0b57c3f50e4`.
`rollout-record.json` and `rollout-before/` pin the new runtime and the prior
273723b7 rollback. Flow hash remains
`6cebd7cb63d540f61d9c142a9728ed4fbf0edaeaa3312eacae9ae7503126c7fe`.
All four runtime tools, 25 plugins and worker limits were checked.

| File installed with ef5c61fe | Previous complete file | New complete file | Change |
| --- | ---: | ---: | ---: |
| Steven Universe S3E22, Earthlings | 223,776,032 B | 237,020,007 B | +5.918% / 13.244 MB |
| Steven Universe S1E23, Monster Buddies | 174,720,966 B | 179,591,797 B | +2.788% / 4.871 MB |
| Amphibia S1E18, Plantar's Last Stand | 195,520,274 B | 236,368,140 B | +20.892% / 40.848 MB |
| Amphibia S1E11, Sprig Vs. Hop Pop | 190,579,631 B | 240,059,167 B | +25.963% / 49.480 MB |

The previous Steven and S1E18 files used the older recovery-ramp encoder;
S1E11 used an earlier partial fix, binary SHA beginning `ee72bd946e`.
None of these complete-file baselines used `273723b7`.
The Steven video-only trial comparison against `273723b7` is instead +0.136%
and +0.147% bytes, with single-run encode times +0.83% and +0.64%. This is not
a general library throughput or storage forecast.

Installed-file verification includes complete independent libdav1d decoding,
original and superseded-file SHA-256 checks, synthesis scans, prior flash
witnesses, candidate/installed video-packet identity, and audio/subtitle/chapter/
video-signalling preservation. See `strict-installed-steven-verification.json`,
`strict-installed-amphibia18-verification.json` and
`strict-installed-amphibia11-verification.json`. Original and superseded
library files remain retained. No new downloads were needed.

The owned admission hold was released only after installation and runtime
checks. The latest `final-additional-amphibia-operational-state.json` records
two ordinary repair workers on
the new binary, healthy monitors, active coordinator, Tdarr pause ownership and
minute playback watchdog. No audit hold remains merely for long CPU work.

## Broader branch and remaining limits

The hotfix worktree is `NVEnc-fgs-flicker`, branch
`fix/fgs-rejection-flicker-20260912`. Its core and test changes were integrated
into `NVEnc-fgs-fidelity`, branch `feat/fgs-detail-fidelity-20260908`; the exact
combined `03eb4796` build compiled and passed the CPU suite. Its binary SHA-256
is `f9a89a4d7b4083423c9f5eb65f3d4e52d303b4277830fac288a68a2cc6c5d566`.
That broader binary is not deployed and still needs the explicitly deferred,
manual-start retention/quality-per-byte campaign.

The full library audit remains open. Sampled source windows and all-frame
checks of chosen regions cannot clear every source pixel, scene or decoder.
Very thin regions, fine texture at shared brightness, lossy base compression
and device-specific rendering remain practical limits. New confirmed cases
require their own recurrence and current-build/source checks before repair.
