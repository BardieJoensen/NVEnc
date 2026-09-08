# Repeatable detail and strength-curve follow-up — 2026-09-08

This follows `FINDINGS-2026-09-08-FIDELITY.md`. The isolated branch adds a modest
matched-size improvement on woven textures and corrects auto strength-curve
coordinates. It does not establish perfect separation, an HDR perceptual
objective, or a reason to enable automatic retention throughout a library.

## Implementation

In bilateral `retain=auto`, directional coherence remains the primary detail
guard. An additional confidence signal compares detrended 2x2 luma averages
across adjacent source frames in 32x32 blocks. Nine translations (0 or +/-2
pixels on each axis) cover limited motion. Two consecutive agreeing frame
pairs are required, and confidence drops immediately when agreement is lost.
Partial edge blocks keep the directional guard. Gaps, resets and bypasses
invalidate the reference; scene disagreement rejects the local match.

Confidence only reduces current-frame smoothing. No historical pixel is
blended into the output, and no output frame is delayed. Protection is capped
at 20% and still uses the existing weak-grain ramp. An earlier full-protection
variant preserved more structure but cost almost four times as many bytes on
the SDR weave fixture at QP 20; no encoding fit the baseline size through
QP 32. That version is retained as a rejected control.

Only automatic bilateral mode allocates the extra reference/confidence
buffers. Only reference luma is copied, inside the existing analysis
synchronization barrier. Completing that copy before returning also makes it
safe for a later call using another CUDA stream, without an additional host
wait. Fixed retention and the default do not allocate or execute this path.

Auto grain-strength fitting now uses the centres of the GPU's twenty equal
intensity intervals: `(bin + 0.5) * 256 / 20` in 8-bit curve coordinates. The
legacy endpoint grid stretched brightness-dependent measurements sideways.
The previous amplitude guard already used physical centres; now the fitted
curve does too. Fixed/default retention keeps the legacy fit for compatibility.
Native 8/10-bit linear-curve controls pass; deliberately restoring the old grid
fails 44 assertions, including the reduced curve's physical slope.

## Controlled measurements

Sixteen deterministic 48-frame sources separate known clean pictures from
independent grain. New fixtures include static, diagonal and odd-pixel moving
weave, disappearing weave, coarse/weak-grain weave and ten-bit PQ weave.

The detail projection is now also computed per frame before aggregation.
A unit control shows why: reversing texture with half its contrast can cancel
in the mean reference, making the old static projection report full retention.
The per-frame projection correctly reports 0.5. This is a measurement fix, not
an encoder gain. For static sources the two formulations agree.

Compared with the deployed encoder's **existing opt-in auto mode**:

| Fixture | Old detail gain | New gain within old size | Candidate QP | Bytes vs old auto |
| --- | ---: | ---: | ---: | ---: |
| Fine directional detail | 0.6220 | 0.7086 | 26 | -2.48% |
| Coarse-grain directional detail | 0.7252 | 0.8062 | 25 | -2.10% |
| Static woven detail | 0.3611 | 0.3989 | 25 | -2.81% |
| Woven detail moving 2px diagonally/frame | 0.3603 | 0.3997 | 25 | -3.58% |
| Woven detail moving 1px horizontally/frame | 0.3591 | 0.3903 | 24 | -2.19% |
| PQ woven detail | 0.4125 | 0.4433 | 26 | -4.51% |

The original baseline is QP 20. The search selects the first candidate no
larger than baseline auto; it is a discrete size bound, not exact rate matching.
These gains describe the controlled detail projection, not overall perceptual
quality. Much of the weave still gets softened. The incremental weave gain
over the preceding fidelity prototype is also positive at matched size.

At fixed QP, the accepted SDR weave variants cost 15–23% more bytes and PQ
weave costs 46% more. Weak-grain bases remain pixel-identical and cost no extra
bytes. Corrected strength coordinates slightly change their synthesized grain
samples; the existing weak-detail fixture's median output/source amplitude
changes from 0.83949 to 0.83928. This does not fix its existing weak-grain loss.

After woven detail disappears, base-error standard deviation stays within the
fixture's 5% plus 0.03-code-unit bound relative to the baseline on every remaining
frame. Flat/coarse controls show no new large grain or bitrate change. Coarse
grain remains imperfect: the flat coarse fixture renders about 83% of source
amplitude. The prior strong-change/alternating-strength source fallbacks still
cost about twice as many bytes on those two-second fixtures.

Both fixture-specific regression checks pass. The rejected full-protection
variant fails the matched-size controls. The earlier weak-grain/pumping
prototype still fails five checks after updating the weak-grain assertion to
allow the intended strength-coordinate change.

## Evidence identities

Controlled measurements were made with core commit `f845174b`, binary SHA-256
`61b36af27ce7136c8530947d1f571d382315896ecc97542398658aa81b8186fb`.
The final reference-copy hardening is core commit `55d27813`, binary SHA-256
`bfdcfa1979a7cfa24a2a68f92e42baa785403d2bf4348415c411685b62fd9533`.

An explicit replay links them: 28 fixed-QP/selected-size encodes, 1,344 frames,
all decoded pixels identical with grain both on and off, all complete syntax
scans valid. The original measurement report retains its original binary SHA.
The default encoder used for baseline comparison is `e778a88b`, SHA-256
`5423d8abda1d2c248f25508c311ed4ca0eda08462e1ebc6bce95fba22e830249`.

The full CPU suite passes. With `55d27813`, all 16 real-film outputs pass
complete synthesis/texture scans, full grain-on/off decoding, frame-count and
colour-tag checks. The three short clips' default decoded pixels remain
identical to the deployed encoder. The two known jacket passages still disable
synthesis on all planes and stay within the source-preservation bounds.

The 150-second Gentlemen outputs are 48,271,914 / 48,273,224 bytes versus
48,004,704 bytes for old auto, about +0.56%. Additional source-fidelity fallback
occurs on 171 of 3,600 frames (4.75%). Taxi's 24-frame PQ sample increases from
2,978,460 to 2,988,614 bytes (+0.34%). Silo and Alien retain their previous sizes;
their auto grain samples change slightly because of the intended curve fix.

Gentlemen wall times in old/new/new/old order are 99.7 / 155.0 / 104.4 / 97.0
seconds. Both candidate runs are slower in this pass, with a large spread. This
does not support a single reliable overhead percentage on the shared server.

The two candidate repeats differ in decoded pixels on interframes 1–239 and
241–479; their keyframes and all frames from 480 onward match. All 3,600 logged
model rows agree. Five selected base frames show an initial maximum difference
of one 10-bit code step, later interframe drift up to 8 code units in the
8-bit-equivalent domain, and zero difference after the next matching GOP.
This is compatible with small numerical differences propagating through lossy
interframe coding, but its precise cause has not been established. It is not a
bit-exact real-film result. Both complete outputs pass the independent syntax,
texture, decoding and jacket checks. See the retained repeat comparison.

The local quick gate passes all 21 bilateral GPU fixtures, export/failure-path
checks and the positive/negative model controls. The four additional auto
checks across FFT3D and motion also pass.

## Shared-memory optimization

Core commit `6e531477` stages both reference tiles once for the nine candidate
translations, preserving integer samples and accumulation order. This reduces
global sample loads in a full analysis block from 14,112 to 2,048, with two 4-KiB
shared tiles. Binary SHA-256:
`23e4da014bda4d84414e287d44312ab125b323d0ddcab555f631c10dab1b3d57`.

The same 28-encode replay passes with all 1,344 frames identical in both grain
modes, and all selected arms retain their original size bounds. The complete
four-stage quick gate also passes with this binary.

A 240-frame filter-profile comparison in old/cached/cached/old order measures
5.194 / 3.365 / 2.929 / 2.501 ms per film-grain filter invocation; complete
encode wall times are 9.85 / 9.55 / 10.45 / 10.65 seconds. The ranges overlap,
so no measured end-to-end speedup is claimed. Lower global-memory traffic is
established by the implementation, while runtime benefit remains uncertain.
The profiling wrapper's first attempt failed to parse ANSI colour prefixes;
that attempt was labelled and excluded, then the four-run sequence repeated.

The cached real-film check replays the three short auto encodes and the full
Gentlemen sequence. Final results are pending completion of that last check.

Private sources, commands, reports, logs and immutable binaries are under
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/unfinished-20260908/`.
The initial replay wrapper incorrectly expected the texture scanner's `stable`
verdict from syntax-only mode; the scanner correctly returned `valid_syntax`.
The wrapper was corrected and the complete replay rerun. Its failed attempt
is labelled separately and is not an encoder defect or acceptance evidence.

## Remaining limits

This confidence heuristic covers small translations and repeatable texture,
not general motion-compensated grain separation. Spatially coarse grain can
obscure the repeated signal. Fixed or temporally correlated noise may also be
preserved as structure, at a bitrate cost. Full-frame fallback, limited strength
bins and the AV1 model's texture limits remain. PQ-labelled fixtures test native
code-value behaviour and metadata; they do not calibrate an HDR perceptual
objective for a viewer's display.

These are optional encoder developments. They add no checks to normal Tdarr
validation, and the production flow remains on its existing default retention.
