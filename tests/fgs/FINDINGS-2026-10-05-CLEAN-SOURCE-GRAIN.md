# Production adds grain to some clean picture regions

The current production encoder adds noise to exactly constant parts of four of the five held-out originals tested. The strongest confirmed case is inside a dark shot in *Insidious*: a black source patch gains about 0.83 code values of noise, with individual changes up to four values on an 8-bit scale. A full encode from the beginning reproduces it. The affected areas are small, but this directly violates the requested priority of preserving clean regions and takes precedence over making heavy grain more faithful. No quality-changing code has been written.

## What was measured

Production is deployed core `aeb14263`, binary SHA256 `c6cbd5280440c62b51c3b43ced4570dad40295748d42f562a867ac6a525be72b`. Five independently copied original H.264 sources were tested with the production hardware-decode, bilateral, 10-bit AV1 command: QVBR34 for animation and 30 for live action. Source hashes, exact commands, native timestamps and byte counts are retained. A bounded search of previous tuning records found no use of these five originals; this is not proof about unrecorded private history.

Before inspecting errors, the sample was frozen at 10%, 40%, 70% of each source, with 12 seconds of preceding context and 12 seconds evaluated at each location. All 4,536 evaluation frames were scored, totaling 180 seconds: 72 seconds of animation, 72 of digital live action and 36 of outdoor reality footage. The outdoor source is texture-heavy, not a claim of globally clean content. This is an intentionally clean-safety-oriented sample, not a random library sample or an estimate of the library's genre mix.

The source, played output and grain-disabled output are timestamp aligned. Both output decodes use the **same AV1 bitstream**, changing only libdav1d's grain application. Native 10-bit values are expressed on an 8-bit code scale without range or transfer conversion. Source-only masks and active-picture boundaries were inspected; letterbox bars and their ringing are excluded. Legitimate animation fills remain eligible.

Two complementary checks are retained:

- Every frame has source-relative amplitude, HF sigma and horizontal/vertical lag 1/2 autocorrelation for Y/Cb/Cr, by source-luma band, with occupancy and source-only low-structure selection. Source residuals can contain texture; they are not a perfect grain estimator.
- Every complete 32×32 luma / 16×16 chroma grid patch inside the active picture is checked for **exactly constant original samples**, including patches outside the selected low-structure masks. These have zero resolved spatial grain. Added noise is the difference from the closer whole-patch no-grain result: unchanged decoded base or base clipped to legal range. This excludes clipping-only correction and uses no noise floor, minimum group size or brightness-band averaging to hide a positive.

Reference-self, one tiny added sample in an otherwise constant patch, and clipping-only controls pass. Earlier clipping-unaware receipts remain historical; final positive counts use the corrected check. Three earlier zero-change negatives remain valid under either check. The small quarter-code bin in the band census is descriptive, not an acceptance threshold.

## Incidence and size

Each count below means a frame with **at least one** affected constant patch in that plane; it does not mean the whole frame has excessive grain. Plane counts overlap.

| Original sample | Frames | Y affected | Cb affected | Cr affected | Largest added patch RMS, Y / Cb / Cr |
|---|---:|---:|---:|---:|---|
| Knightfall, animation |864|0|6|45|0 /0.199 /0.225|
| Marshals, digital live action |864|0|0|0|0 /0 /0|
| Homegrown, outdoor reality |1080|0|0|9|0 /0 /0.202|
| Insidious, live action |864|53|88|0|0.835 /0.634 /0|
| Toy Story5, animation |864|53|0|3|0.475 /0 /0.295|

Across the frozen sample,212/4,536 frames (4.67%) have a positive constant patch in at least one plane. This is a **sample incidence**, not a library-wide rate. Knightfall contains no exactly constant luma grid patches, so its zero Y count is not evidence that clean luma is protected.

The footprint is much smaller than the affected-frame count suggests. Averaged over the three sampled windows per title, positive patch area occupies 0.0084% of Insidious luma area×time and 0.109% of Cb; Knightfall Cr occupies 0.116%; Toy Story5 Y occupies 0.0046%. These count the entire positive patch, so actual changed-pixel footprints are smaller. No perceptual visibility threshold is claimed for the sub-quarter-code chroma cases.

The largest clean-source witnesses are inside the active image: black hair/shadows in Insidious and the first animation window, plus bright sky in the later animation window. Toy Story5's late-window Y witness has source code 234, RMS 0.354 and peak 1.0; its Cr witness has constant source 128, RMS 0.295 and peak 0.75. Thus the problem is not confined to black bars or dark luma.

## Full-history confirmation and temporal behavior

Insidious was separately encoded from frame zero through 103,930 frames using the same production binary and video settings. A 16-frame witness around source 4326.36–4326.99 seconds was decoded with grain on/off. Actual PTS and independent pixel-offset checks pass; its source pixels and selection arrays exactly match the corresponding frozen-window source subset. Eleven frames contain an affected constant Y patch and15 an affected constant Cb patch. Maximum added RMS is 0.831Y /0.639Cb; Y changes reach4.0 codes. These selected confirmation frames are **excluded** from the census denominator.

The other confirmed failure is temporal over-strength in Knightfall, documented in [the temporal findings](FINDINGS-2026-10-05-PRODUCTION-TEMPORAL-EXCESS.md). With full preceding history, two dark-band frames have added sigma 0.917/0.891 against source 0.625/0.661, followed by 0.381 added against 0.616 source. The grain falls57% while source strength falls7%, within the same shot. Played texture also falls; this is stronger evidence than a film-grain-table switch by itself.

Other titles have large changes in synthesized strength that are offset by the decoded base. Those are not automatically visible flicker defects. Shot changes are retained in the measurements, but a source change alone is not an encoder defect. The census reports paired source-coordinate changes, stationary-source coverage and exact unchanged-source counts rather than treating every table change as wrong.

## Likely mechanism and limits

Production's existing `protectSource` path ignores evidence whose luma range is at or below 20 or at or above 232, then also excludes protected-plane means outside that interval. Its comment explains that black/white bars must not constrain neighboring picture levels. The confirmed source 16 shadow and source 234 sky cases sit inside these exclusions. The existing source-variance and quiet-source guards also tolerate small modeled excess; tiny chroma additions require separate diagnosis. This is a code-supported hypothesis, not yet a causal demonstration that one condition explains every witness.

AV1's grain curves depend on brightness and apply across the picture. A clean patch and a grainy patch may share a lookup value. Protecting the clean patch can therefore require less synthesis elsewhere and retaining more source signal in the base, at a bitrate cost. Reopening broad R3–R8 retention is not justified. The proposed next step is a bounded correction to the existing production safety path, with explicit byte and heavy-grain regression limits.

## Evidence

Scratch root: `/tmp/downloads/codex-work/fgs-submission-20261005/task4/`.

- `heldout-window-plan.json`: frozen source-only sampling plan.
- `heldout-census-summary.json`: all 15 windows, per-plane counts, brightness bands, footprints, maximum witnesses and hashes of underlying per-frame measurements.
- `heldout-windows-capture2/knightfall-p10/` and `heldout-windows-capture3/<window>/`: exact command/source/decode/alignment receipts, reviewed masks, every-frame statistics and constant-patch checks.
- `constant-restore-series.json`: nine byte-identical raw regenerations from existing encodes; no new AV1 encodes for this correction.
- `insidious-full-history-confirmation/`: full production encode receipt and 16-frame witness.
- `knightfall-full-history-confirmation/`: independent full-history temporal witness.

Large original copies and full-history outputs remain in scratch; small reports and reproducibility tools are retained with the branch. No library file was read for this census, repaired, replaced or downloaded.
