# Completed post-encode integration trials — 2026-09-09

All three full-title candidate videos passed the normal Tdarr post-encode
pipeline in isolated scratch jobs. The admitted AV1 packet payload survived
assembly exactly, and every video timestamp passed the final-copy check.
Expected audio, subtitles and chapters
passed independent fixture checks and the existing production validator.
This completes the post-encode integration study; it is not a production
rollout or a claim of perfect perceptual quality.

## Full media results

| Retained source | Video frames | Audio tracks | Subtitle tracks | Chapters | Stream policy / Opus | Final validator |
|---|---:|---:|---:|---:|---:|---:|
| The Gentlemen S01E01 | 96,671 | 2 | 6 | 2 | 30.7 s | 34.3 s |
| South Park S23E01 | 32,176 | 3 | 1 | 5 | 15.8 s | 51.0 s |
| House of the Dragon S03E08 (4K HDR/DV) | 100,851 | 2 | 7 | 0 | 35.6 s | 142.9 s |

Each output has a new default English stereo Opus track. The Gentlemen and
House of the Dragon also retain the original English 5.1 E-AC-3/Atmos track;
South Park retains English TrueHD 5.1 and AC-3 5.1. South Park's English PGS
subtitles are preserved. The other titles retain the expected language tracks,
including German, Danish, Norwegian, Swedish, English and the unresolved
subtitle language where present. The final validator confirms retained-track
identity, generated-Opus provenance samples, metadata and timelines, a complete
FGS synthesis scan, visual provenance samples and its full-file packet screen.
The provenance samples are not full audio or perceptual-quality certification.

The measured validator times are single runs on the shared server with a
six-CPU container limit. They exclude the extra offline source hashes, initial
mux, video-copy proof and separate size decision. They are not isolated
throughput benchmarks or per-file runtime guarantees. No extra audit was added
to the live validator.

The final-video payload hashes match admission in all three cases, with zero
common timestamp shift. Complete HDR frame-metadata comparison was already
performed for the admitted House of the Dragon video; exact packet preservation
and the final container/metadata checks connect that evidence to this mux.
The previous full video-only size increases remain +1.60%, +2.38% and +0.47%
respectively, below the selected 10% trial budget. Final files also pass Tdarr's
separate source-relative size policy. Added audio and mux overhead do not turn
that video-only budget into a comparison against an old fully assembled file.

## Replay hardening and controls

The runner checks the admission receipt, source/video/report hashes, expected
candidate build, all 184 pinned plugin/dependency files and the audio-policy
configuration. It requires explicit expected audio/subtitle/chapter results,
complete final video packet identity, every video timestamp, headers and
color/geometry before calling the actual final validator. Any failure records
`keep_source` and cannot replace a library file.

The first harness passed a host path where the language policy expects its
node path. That selected the real preserve-everything fallback. Those runs are
retained as preservation-path evidence only; they do not count as Opus or
subtitle-selection coverage. The corrected runner translates the fixture path,
requires a resolved policy, and verifies the intended final tracks independently
of the plugins' own simulation. All three normal-path runs above use that
correction. No production plugin change was needed.

Real-container controls demonstrate:

- A 7 ms common video origin shift with identical payload is accepted.
- A 250 ms shift with identical payload is rejected.
- Substitution of the completed production-baseline video is rejected.
- Two authoritative chapters and one font attachment survive the real
  reattachment plugin, with exact extracted-font SHA-256 and video payload.

The substitution control uses complete files: the two South Park encodes have
identical initial 72 packets, so those opening packets cannot serve as a changed
video control. The original failed negative-control attempt remains archived
and is not counted as a passed test.

Eight Node tests pass, covering these decision rules, changed/missing evidence,
plugin/policy drift, fixture path resolution and explicit track expectations.
A replay-level rejection test writes only the failure receipt, creates no media,
and leaves the source unchanged. The Node tests are now required by the CPU CI
workflow. The unchanged C++/Python suite was not repeated for these JavaScript
and documentation changes; its completed prior run is in the preceding trials
findings.

## Pilot settings and limits

The saved offline pilot profile specifies the tested
`denoise=auto,chroma=auto,denoiser=bilateral,retain=auto,retain-max=0.1`
for both sampling and full encoding. Both agree with the three completed
candidate commands. The candidate was mounted read-only at `/usr/bin/nvencc`
in the pinned runtime and its SHA-256 and program startup verified there.
This is also the path used by sampling and preflight. That startup check
performed no additional GPU encode.

The profile is a reviewable settings artifact, not an importable or deployed
flow. The post-encode replay reuses completed video-only encodes, substitutes
explicit fixture language for Arr lookup, and does not test the complete Tdarr
scheduler. It does not exercise encoder-side audio/subtitle copying in the same
process as a fresh encode. A future live pilot must preserve the admission
contract: complete measured baseline, candidate within budget, final validation,
and keep-source on rejection. The current live flow does not implement the
additional measured-baseline 10% gate.

The unrelated FFprobe XML-printer investigation remains documented and stopped.
The earlier repeat-encode variability is still not attributed to a proven
specific driver/component; no speculative workaround was merged. These trials
do not extend real-footage coverage to HDR10+ or Dolby Vision enhancement-layer
sources. See [the preceding full trials](FINDINGS-2026-09-09-TRIALS.md) for those
limits and the full decode/metadata evidence.

Production binary, image, flow and checked validator/Opus plugin hashes remain
unchanged. The repair and watchability-audit user services remain active.
No new recovery downloads were scheduled and no library file was replaced by
these trials.

## Evidence

Local study root:
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/pilot-integration-20260909`

- `media-trials-v2.json`: runtime, commands, exit status and elapsed times.
- `snapshot.json`, `pilot-profile.json`, `runtime-path-check.json`: pinned
  plugins, matched encoder settings and isolated runtime identity.
- `v1-classification.json`: limited coverage of the original replays.
- `node-tests.log`, `production-verification.json`, `evidence-index.json`:
  tests, unchanged production state and report/script hashes.
- Full reports and final media are under
  `/tmp/downloads/fgs-pilot-integration-20260909/{gentlemen,south-park,house-of-the-dragon}-v2/`.
  Real media controls are under the same root's `controls-v2/`.
