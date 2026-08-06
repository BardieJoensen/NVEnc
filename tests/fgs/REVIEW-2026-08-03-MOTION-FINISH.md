# Detail-aware motion-finish playback gate, 2026-08-03

## Status

> **Reviewed 2026-08-06. Verdict: no visible difference between arms.** See `FINDINGS-2026-08-06-PLAYBACK-VERDICT.md`. The review used the distilled clips from `minimal_review.py` rather than this full package.

**Blind playback judgement pending. Research only; nothing here has been
deployed to Tdarr.** Production remains on r4069 with the bilateral separator,
and `modelsrc` remains default-off.

The current review set is at:

```text
/media/merged-storage/media/test-encodes/sourcefit-motion-finish-review-20260803/blind/
```

It compares production bilateral against balanced-centred motion with source
fitting and the detail-aware spatial finishing pass. Scarface, Taxi Driver,
The Deer Hunter and The Shining are included. The A/B mapping is sealed until
observations are recorded and is held constant between each title's
grain-disabled `base` and grain-enabled `finished` pair.

The older `sourcefit-balanced-review-20260803` package is superseded because
it contains the uniform finishing arm rather than the current candidate.

## Why this remains a shipping gate

The detail-aware finish improves labelled fine-detail transfer from 0.786 to
0.937, reduces systematic edge RMSE from 1.61 to 1.27, improves six-film base
VMAF by 1.94 on all 6/6 titles, and reduces symmetric temporal projection on
all six while leaving source-fit grain texture intact.

It still does not beat production on every base guard rail. Production wins
SSIMULACRA2 and Butteraugli on all six titles even though the candidate wins
VMAF on all six. These metrics disagree about whether the additional
grain-like structure retained in the base is useful detail or residue. Only
motion playback can decide whether the candidate's remaining absolute error
is visible ghosting, smearing or benign grain.

## Review method

Review each `base` pair first. Grain synthesis is disabled there, exposing
separator damage directly. Use the same playback speed and display settings.
Look for trailing contours, texture at an object's old position, doubled hair
or facial detail, displaced hands or rifle edges, and smearing as a detailed
background is uncovered.

Then review the matching `finished` pair. Record whether any base defect is
visible in normal grain-enabled playback and whether one arm's grain scale,
strength, temporal stability or interaction with picture detail looks more
faithful. Independent AV1 grain positions are expected and must not be scored
as a pixel mismatch.

Record title, A/B, approximate timestamp and the observation before opening
the reveal file. The files are lossless 1920x1080 10-bit FFV1 centre crops;
their byte sizes are not part of the comparison.

## What playback can and cannot settle

A clean playback result would clear the base-operator direction for broader
testing; it would not clear deployment. The remaining per-luma amplitude
errors are independent and still require analyser work, especially Deer
Hunter's roughly 0.91--1.25 populated-band slope.

If the candidate shows visible motion damage, work stays on separator
admission/refinement. If it passes, the next code target is the per-luma
strength population/curve estimator, not a global gain and not a speed pass.

