# R10: final residuals are present but do not recover shirt texture

**Validated, independently reviewed single-frame diagnosis. No repair qualifies.**
The original-rate cap and texture/clean-region/detail/banding/temporal/playback
requirements are unchanged. This round observes the exact R8 bitstream; its cost
remains9.6279048Mbps over the240 scored frames (99.49757% of9.6765224Mbps source),
10.25718343Mbps over all336 frames, and370.335769s for the two encode passes.
Instrumentation and decoder time are diagnostic overhead, not encode speed.

## Result and scope

Final coefficient-bearing TUs cover91.84% of the shirt and94.84% of the background.
Thus the narrow hypothesis that final predictor-only syntax spatially dominates
these targets is rejected. Positive EOB means at least one coefficient; it does
not mean fine texture survived. The transmitted shirt residual improves pixel
error but hardly restores high-frequency source structure. Background residuals
help much more, followed by substantial filtering loss.

Full fixed-ROI luma HF sigma, in8-bit-equivalent code units:

| ROI | Source | Coding input | Native local predictor | Preloop | Postloop |
|---|---:|---:|---:|---:|---:|
| Shirt | .606320 | .441324 | .090378 | .093667 | .054543 |
| Background |1.676388|1.665486|.368026|1.280496|.847762|
| Face |2.700847|2.691176|1.799546|2.454111|2.150404|

Shirt predictor→preloop source-HF correlation is−.00563→.00818, MSE3.01359→1.52822,
and ACF1.05423→−.02589 versus source−.22242. Background correlation improves
.03798→.53894 and MSE13.12842→5.79406. Postloop further reduces amplitude while
improving MSE. These are different ROI behaviors, not a universally harmful filter.
Full descriptors and all858 frozen tiles/840 outside tiles are retained in the
[compact machine result](decoder-map-result.json) and linked complete artifacts.
There are zero quiet tiles at this frame; no quiet-region safety claim follows.

Whole-frame category coverage: skip-mode31,424pixels (1.52%); other no-coded-
residual352,832 (17.02%); coefficient-absent luma TU1,984 (.10%); EOB-positive
1,687,360 (81.37%). Face differs:36.40% absent and63.60% present. Both intra and
inter owners occur in absent and present populations.

All24 shirt EOB-positive units are DCT_DCT and use normative coded_qindex71.
Their retained coefficients are sparse (1–11 nonzero values per admitted TU),
but23/24 have at least one non-DC coefficient. This is neither a coded-bit
measurement nor evidence about encoder initial quantization. Background qindices
are79/83/87; whole-frame normative range71–115. Decoder dequant/IQM/EOB observations
cannot establish actual forward-q, prequant values, optimizer invocation or RD
removal. A poor predictor does not prove a defective prediction search.

## Validity and review

The independent compressed-header parser derives502events/336codedframes,
including166hidden and166show-existing events. Hidden coded210/event314,
orderhint88, refreshslot4, feeds display216 through show-existing event325.
Target frame OBU48723bytes, IVFoffset10507088, SHA
9169308b8f10753bf26caebb191e9d7ea869ae748a0fe64823e7ddd7b3e3543a.
No packet-equals-frame or source-order assumption was used.

Pristine private, observer-off and observer-on decoders reproduce every sample
of all336 admitted R8 frames. Every consumed span and frame OBU matches the
independent parser. Complete target ownership has9843leaves/9843analysisunits,
including8138actualTUrecords plus skipped-inter owners. Captured predictor
precedes native inverse, full dequant coefficients precede clearing, reconstruction
copies precede filtering. Assembled preloop luma equals R9 exactly; target
postloop matches all planes and displayed216. Every absent-residual sample has
predictor equal to preloop. Nine deliberately malformed traces fail structural
admission; this is targeted checking, not exhaustive parser proof.

Independent review caught stale show-existing metadata, incomplete coefficients,
EOB-zero TX typing, byte bounds and provenance gaps before admission. The first
observer-on run failed a mistaken inactive super-resolution denominator guard;
source review proved it should check actual coded/upscaled dimensions. That
failed run remains preserved. The corrected build uses only the reviewed guard
change and passes all identities. One redundant unsigned-enum lower-bound
compiler warning is documented; its upper bound remains effective.

Analysis corrections included raw10 scaling/frame size, small connected-region
ACF handling, nullable counts, complete/outside semantics and frozen validator
binding. A separate supplement supplies missing full-ROI descriptors without
rerunning connected analysis. The main analysis wrapper misstated both input and output paths. Its
inaccurate receipt is preserved; a correction binds the successful result's
actual inner argv, script and admitted data. Its outer affinity/timing are not
claimed independently verified. Connected analysis was not rerun. The small
full-ROI supplement was rerun with truthful inner/outer argv and result binding. Parent examined native-pixel rounded-luma stills, **not motion playback**.

[Independent outcome review](decoder-map/round10-outcome-review.md),
[contract](ROUND10_DECODER_CONTRACT.md), [reproduction](decoder-map/README.md).

## Next discriminator

Capture initial and final coefficients and actual quantizer/optimizer provenance
for exact final-committed EOB-positive shirt owners, with no-residual comparison
owners retained. Match source/predictor/finalDQ/preloop to the admitted decoder
map and preserve entire-output neutrality. MD reuse and EncDec bypass need real
producer tokens; coordinate matching alone cannot establish candidate ancestry.
No new settings sweep or bitrate redistribution is justified by R10 alone.
