# R11 DQ mismatch review

Disposition: **the failed v1 assertion compared two correct native arrays in different storage orders.** The normalization in `validate.py` SHA `258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3` is justified and retains exact equality; I found no blocker to rerunning admission.

## Direct evidence

My independent parser/source check is preserved in `round11-dq-mismatch/analyze_mapping.py` (SHA `91c0c353b51836b654b29eb1e5469d56d730c61253e9f79f50d3207c97f1594d`) and `result.json` (SHA `9092df2757413ec13ac8705ef7823df2ab7196d16adb782ee199a30fc5df00a4`). It joins each accepted-generation R11 token to the admitted R10 unit map and decoder payload.

For the original failure, token 1 / R10 unit 187 is a 32x16 DCT_DCT TU with EOB 77. Its coded nonzeros occupy scan positions 0, 20, and 76. SVT native DQ indices/values are `0:-141, 5:-161, 42:166`; libaom native indices/values are `0:-141, 80:-161, 161:166`. The coordinate map

`decoder_index = (svt_index % width) * height + svt_index // width`

maps `[0,5,42]` exactly to `[0,80,161]`. There is no changed magnitude or sign.

Across all 2,151 EOB-positive joined units, transposing the adjusted `min(h,32) x min(w,32)` SVT matrix gives exact libaom DQ equality with no tolerance. 2,085 arrays require the permutation; 66 happen to be transpose-symmetric. The same mapping gives exact IQM equality for all 2,130 nonempty matrices; the remaining 21 are empty on both sides.

## Source proof

- SVT's inverse consumes each row contiguously and then advances by transform width (`Source/Lib/Codec/inv_transforms.c:2495-2509`). Libaom instead addresses coefficient `(r,c)` as `input[c * txfm_size_row + r]` (`av1/common/av1_inv_txfm2d.c:270-283`). These are the two native layouts related by the map above.
- SVT quantization writes `qcoeff_ptr[rc]` and `dqcoeff_ptr[rc]` at its scan index (`Source/Lib/Codec/full_loop.c:166-195`); libaom entropy decoding writes dequantized values to `tcoeffs[pos]` using its scan (`av1/decoder/decodetxb.c:280-313`). The decoder passes that same buffer to native inverse before clearing it (`av1/decoder/decodeframe.c:144-155`).
- I parsed every scan family actually exercised: 13 default/mrow/mcol tables spanning adjusted 8x8, 16x16, 32x32, 8x16, 16x8, 16x32, and 32x16. Every captured R11 scan equals its pinned SVT table, and transposing every SVT scan index gives the corresponding pinned libaom table exactly. This covers observed transform types 0,1,2,3,10,11; both projects' tables select mrow for type 10 and mcol for type 11 (`coefficients.h:2197-2215`; `scan.c:1666-1684`).

This rules out quantizer rounding and stale post-EOB lanes: values are identical at identical coded scan positions, the full arrays map by one bijection, and IQM independently follows the same mapping. It is best described as a validator representation mismatch, not an encoder or decoder capture error.

## Effective QM correction

The updated type gate is also correct. SVT selects frame QM only when `tx_type < IDTX` and QM signaling is enabled; otherwise it selects flat level 15 (`full_loop.c:1607-1614`). Libaom likewise returns the segment IQM only for 2-D transforms and its level-15 flat matrix for identity/1-D transforms (`quant_common.c:247-274`). Thus the 21 positive V_DCT/H_DCT units legitimately have effective level 15 and empty IQM even though their R10 leaf records the frame-level Y value 11. The revised validator compares the effective value and still requires exact normalized IQM bytes.

The correction changes only cross-implementation representation. EOB, transform type, adjusted dimensions, qindex, scan/iscan, native inverse, committed ownership, and exact decoder reconstruction remain independently checked. It does not itself establish the R11 scientific outcome; admission and analysis must still complete.
