# Pantheon S02E04 repair proposal — 2026-10-19

**Recommendation: restore the untouched original video for Episode 4, keeping its existing audio and subtitle streams, and add Pantheon to Tdarr's existing keep-original allowlist.** The replacement is prepared and verified outside the live library. Neither action has been applied; both await user approval.

The original audit found visible texture loss around 20:49. The successful October 9 Tdarr job records QVBR 34 with bilateral automatic film-grain synthesis. Testing the current production binary at the same settings reproduces that weak scene closely (84.78 VMAF vs 84.50 in the library copy). This is not merely an obsolete encoder artifact.

## Controlled sample comparisons

Current production binary: `/opt/docker-apps/build/tdarr-node/nvencc`, version 9.38; SHA and original/library probes in `inputs.json`. The live node image was `nvenc-fidelity/tdarr-node:3.01.00-f1327e14-20261016`. Production settings are held constant apart from QVBR/rate control and whether FGS is enabled. A 96-frame preroll precedes the same 240 scored source frames at 1243.493 seconds. All pairs pass multi-frame zero-offset alignment and exact metric frame-count checks. CUDA metric helpers are from the installed campaign and library-fidelity harnesses.

| Variant | VMAF | VMAF p1 | SSIMULACRA2 | Scored-window Mbps |
|---|---:|---:|---:|---:|
| library | 84.50 | 66.33 | 46.55 | — |
| q34-fgs | 84.78 | 68.45 | 47.59 | 3.309 |
| q30-fgs | 87.50 | 74.38 | 52.94 | 5.312 |
| q26-fgs | 89.74 | 79.62 | 58.50 | 8.321 |
| q22-fgs | 91.53 | 83.54 | 64.01 | 12.620 |
| q30-plain | 88.94 | 75.46 | 54.76 | 5.743 |
| q26-plain | 91.39 | 81.25 | 60.81 | 9.274 |
| q22-plain | 93.36 | 85.32 | 66.91 | 14.102 |
| window-matched-q30fgs-plain | 87.76 | 72.55 | 52.81 | 5.324 |

The original H.264 scored window is **10.029 Mbps**. Even plain AV1 at QVBR 22 uses **14.102 Mbps** in that window and retains only about 70% of the measured background high-frequency amplitude. QVBR 30 is an improvement, but does not recover the scene's source texture. None of the tested settings makes a compelling replacement for the available original.

The final matched-rate comparison is `q30-fgs` vs `window-matched-q30fgs-plain`: **5.312 vs 5.324 Mbps**, a **0.24%** difference. VMAF **87.50 vs 87.76** and SSIMULACRA2 **52.94 vs 52.81** are close. Disabling synthesis alone does not fix this scene at the same bit budget. The first `matched-q30fgs-plain` run was a rate-calibration attempt and is not the final matched control.

`comparison.json` also includes PSNR, SSIM, CIEDE2000, CAMBI, Butteraugli, and paired HF sigma / residual autocorrelation at lags 1–3. Grain statistics use the same five frames and background ROI as the initial audit. Full-reference scores alone are not interpreted as a measure of synthesized grain correctness. Findings apply to this difficult ten-second scene; the candidates were not validated over the whole episode or other shows.

## Ready replacement

`/media/merged-storage/cold-storage/docker-apps/pantheon-fix-20261019/S02E04-original-video-restored.mkv`

- **3.161 GB**, replacing a **0.731 GB** library file (about **2.43 GB** more).
- Original H.264 video payload hash matches exactly; no video re-encoding.
- Both existing audio streams and the embedded subtitle payload hashes match exactly. Default Opus stereo and non-default E-AC-3 5.1 are preserved.
- All 59,628 video, 202,065 audio and 614 subtitle packet PTS/DTS, sizes and skip/discard side data match their compared streams. Video timing is checked against the first verified original-video remux; audio/subtitles against the library.
- Lacing is disabled to preserve Opus timestamps. The final Opus packet reports its trimmed duration (11 ms vs 20 ms), with identical 456-sample discard padding; the entire decoded Opus PCM SHA256 is identical. This is a container-duration representation difference, not changed audio samples.
- Resolution, frame rate, duration, stream order and defaults verified. Receipt includes the library's inode/size/mtime snapshot and the candidate's complete file SHA256.

The filename in the receipt's `candidate` field records the staging location; `archived_candidate` records its durable location. Raw metrics, encoder logs and sample encodes are retained beside the candidate. Lossless intermediate clips were removed after scoring.

## Prevention proposal and installation boundary

The live flow reads `/flow-config/keep-original-allowlist.txt` on each job, backed by `/opt/docker-apps/configs/tdarr-flow/keep-original-allowlist.txt`. A read-only API check confirmed the live detection function matches the inspected source. Proposed addition:

```text
# Pantheon: preserve source texture; quality audit 2026-10-19
/cartoon-anime/Pantheon (2022)/
```

The existing detector matches all 16 inventoried Pantheon library paths with that entry; unrelated test paths behave unchanged. `keep-original-allowlist.patch` is a proposal only and includes the existing context; the base hash is recorded in `allowlist-proposal.json`. This leaves the global animation preset unchanged. It prevents future re-encoding; it does not repair other existing episodes.

After user approval: recheck current playback/queued work and the saved library signature; reconcile and install the allowlist entry with a local config commit; copy the verified candidate to a temporary file on the media filesystem, verify it, retain the existing library file as rollback material, atomically replace the episode, and refresh its media metadata. Existing external subtitles remain alongside it. Do not requeue an unprotected original through QVBR 34. Season 1 restoration still requires finding or obtaining its originals, a separate action.

Authorization: diagnostic tests and reversible candidate preparation followed the user's “how do we fix it?” request. Global AGENTS.md requires approval for “any torrent or live-library action,” so installation is the remaining approval boundary. No production code or configuration was edited.

Auto decisions: use current production binary; reproduce the actual weak scene with preroll; vary QVBR and synthesis independently; calibrate plain VBR against scored-window bytes; recommend original preservation after higher-bitrate candidates still lose texture; prepare an existing-allowlist entry rather than proposing a global preset change from one scene.
