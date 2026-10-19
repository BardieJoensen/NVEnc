# Pantheon: measured precision, texture and repair feasibility

**No tested arm currently qualifies as a faithful whole-picture repair. Lower
realized quantization can preserve the difficult texture in legal encodes, but
local preservation displaces damage at the original bitrate.** Independent
same-codec controls also change texture; neither defective NVENC nor an AV1 limit
is established. Production, Tdarr, torrents, library files and previous archives
were untouched. Motion playback has not been observed.

This continues the [quantization investigation](../pantheon-quantization-20261019/README.md),
which was newer than the supplied causal-report pointer. Starting branch was
`master` at `031569ae`, coord task `pantheon-fix` revision7. New work uses fresh
`/tmp/downloads/codex-work/pantheon-rd-20261019` scratch. The detailed evolving
[hypothesis/experiment ledger](LEDGER.md) states each discriminator and decision.

## Causal findings and limits

**High confidence, these exercised SVT blocks:** coefficient pruning contributes
to texture loss, but does not explain it all. At effectiveq32, retaining the actual
initial FP coefficients raises E05 shirt HF0.2587→0.5031 versus0.6063 source;
ACF changes+0.1761→−0.0940 versus−0.2224 source. It still fails both unchanged
screens. Same-q regular-B quantization is worse. The unquantized inverse under
the same exercised<=32 transform/predictor is close on quantizer-run neighborhoods
(HF0.6215 versus0.6178, ACF−0.2294 versus−0.2268, correlation0.9936). This isolates
quantizer loss in those TUs; it does not isolate search over other decisions or
establish a universal codec bound. Bypassed blocks are explicitly separated.

Private same-algorithm FP q24 passes E04, but misses E05 ACF. One midpoint
bisectionq20 passes the E05 whole-ROI screens. Current-q private FP exactly equals
actual initial coefficients/dequant/EOB/reconstruction, and the full encoded
streams/reconstructions remain byte-identical to controls. **These are diagnostic
counterfactuals, not independently decodable repair candidates.** The E05q20
transformed-only neighborhood overshoots HF by10.71%, a retained limitation.

**High confidence, local coder cost:** full private arithmetic-coder/CDF clones,
identical-vector state/byte/CDF controls and exact eligible-population audits
validate4,750 E04 and6,389 E05 TU comparisons. Retention costs more. For example,
fully contained E05 shirt TUs at frame120 cost1518.75→3838.625bits; E04 purple
frame134 costs253837.25→274929.75bits. These are sums of independent fixed-prestate
coder deltas, in bits with1/8-bit precision. They are not sequential alternate
stream sizes or packet bitrate, and exclude whole-block skip revival.

**High confidence, combined real strategy:** absolute selected-SB q24(E04) or
q20(E05), global TX32 and final FP retention preserve the selected texture at high
rate. Absolute q acts before mode decision, so these encodes also change search,
partitions, transforms and reference feedback. Every selected block over240
scored frames realizes its target q; retained arrays/hashes/EOB and all240 decoded
planes validate. Only manual oracle rectangles are selected, not an automatic
production classifier or every textured region.

## Measured preservation and collateral damage

Original packet rates are10.029359Mbps(E04) and9.676522Mbps(E05). Every comparison
scores240 frames after96 preroll frames. New source/input/frame/color checks
reconfirm the untouched originals; full decoder and packet receipts are retained.

| Arm | Actual Mbps | Primary texture | Whole-picture result |
|---|---:|---|---|
| E04 selectedq24/FP, high rate |23.81770|Purple HF+2.46%, ACF error0.00177: pass|Outside errors improve vs source-budget SVT; no whole-picture qualification|
| E05 selectedq20/FP, high rate |18.15288|Shirt HF−1.88%, ACF error0.04655: pass|Background HF−49.5%, ACF error0.1888: fail|
| E04 selectedq24/FP, matched source budget |10.00999(−0.193%)|Purple still passes|Outside MSE5.926→9.501; VMAF90.59→85.42; SSIMU61.02→44.18|
| E05 selectedq20/FP, matched source budget |9.61704(−0.615%)|Shirt still passes|Outside MSE9.329→10.847; face MSE6.840→9.537; SSIMU52.87→47.75|
| E04 x264slow/grain two-pass |20.16340|HF−1.18% passes; ACF error0.06229 fails|Broad control improvements; CAMBI mean1.486/max16.31 requires artifact scrutiny|
| E05 x264slow/grain two-pass, AQ0.5 |19.25284|Shirt HF−30.56%; background ACF error0.05154: fail|Quiet, edge and face errors improve vs source-budget SVT|
| E05 same, AQ1 |19.35914|Shirt HF−18.94%; background ACF error0.05067: fail|Quiet improves; edge/face regress versus AQ0.5|
| E05 same, AQ2 |19.34029|Shirt amplitude passes but ACF error0.07887 fails; background narrowly passes|VMAF90.78/SSIMU63.49; displaced damage grows|
| E05 AQ1/subme11,2x |19.36834|Background passes; shirt HF−15.84% fails|VMAF95.16/SSIMU67.63; modest broad improvement|
| E05 AQ1/subme11,3x |29.01377|Shirt HF−5.25% passes but ACF error0.05736 fails; background passes|VMAF96.85/SSIMU76.70; whole-tile/face errors improve|
| E05 x265slow/grain10bit,2x |19.25875|Background passes; shirt HF−39.66%/ACF error0.19511 fail|VMAF96.30 coexists with SSIMU62.82/p555.08; not a repair|
| E05 AQ1/subme8,3x |29.00634|Shirt HF−2.53% passes but ACF error0.05768 fails; background passes|Similar structure miss to subme11;40.43s two-pass|
| E05 AQ1/subme11/deblockoff,3x |28.97162|Shirt ACF error0.06649 worsens; background passes|8-pixel grid excess rises39%; reject this intervention|

The provisional texture screen remains HF amplitude within10% and ACF1 error<=0.05,
paired with source correlation/structure, controls, edges, banding and temporal
evidence. Passing either amplitude or one ROI is insufficient. Full GPU campaign
VMAF/NEG, PSNR/SSIM/CIEDE, SSIMULACRA2/Butteraugli, CAMBI and tails accompany every
interpreted real arm. Fixed-coordinate temporal traces are descriptive, not
motion-compensated proof of artifact-free playback.

## Allocation was measured, not inferred from a requested setting

A separate H264 decoder reader exports QP_Y state for all336 frames and all
2,741,760 unique16x16 macroblocks, with two decoder threads, checked delayed-frame
drain, exact grid/PTS validation and input/tool/header/map hashes. Visible-area
weighting clips the padded bottom8rows. Skipped MB QP is decoder state and does
not prove residual quantization executed.

At virtually equal actual rates, AQ0.5→1 lowers midpoint shirt QP22.250→20.370;
the same-frame shirt-minus-outside contrast falls0.999QP. Face QP rises
24.028→24.421. Keyframes and picture types are identical. The intervention really
redistributes precision, but raises edge-tile MSE33.3% and face MSE4.511→5.807
versus AQ0.5. It does not solve preservation by increasing a single score.

## Independent review and practical status

[Review and corrections](REVIEW.md) records rejected worker instrumentation,
complete-population and writer-ownership fixes, parser corruption tests, packet
position accounting, real intervention verification and H264 export corrections.
Only validated evidence enters the findings. The parent inspected decisive raw
checks and native stills; still inspection is not motion playback.

No production proposal is supported. The best local SVT preservation and the
stronger whole-window x264 controls have different regressions; neither can be
presented as an accepted repair. Measured short-window runtime includes the
stated CPU restrictions and, for SVT, instrumentation overhead; it is not a
clean episode-throughput forecast. Practical bitrate tolerance and the user's
actual player/display remain unassessed.
