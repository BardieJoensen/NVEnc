# R10 decoder-side final-map design assessment

## Disposition

A decoder-side map is the cheaper and more authoritative implementation for R10's current branch question. The decoder observes the committed AV1 syntax, normative prediction, decoded coefficients/dequantization, inverse residual, and pre-loop reconstruction without resolving SVT's normal EncDec, MD-skip, and whole-EncDec-bypass lifetimes. It can directly classify where the final stream carries no luma residual versus nonzero residual and measure the reconstruction effect.

It cannot observe the encoder's pre-quant coefficients, forward scalar-quantizer invocation, trellis/dropout history, candidate costs, or why residual syntax was omitted. Those questions remain conditional encoder-side work after R10.

## Full-stream and target-event binding

Decode the exact admitted R8 IVF from the beginning. Do not decode a target packet/OBU in isolation: picture 216 is a hidden coded update and its displayed sample depends on full reference history and a later show-existing operation. Do not assume one IVF packet equals one coded frame.

Use the existing independent OBU/header parser and framing machinery to enumerate every frame header, including hidden coded frames and show-existing-only events. Bind each decoder coded-frame trace to an independent compressed-event key containing at least coded-event ordinal, exact packed frame/OBU byte hash and size/offset, frame type, show/show-existing state, order hint, and refresh information available from the parser. Parser and decoder event counters/multisets must agree.

Identify the target by all of the following, not by ordinal alone:

1. the coded hidden event's completed post-loop reference buffer is byte-equal to admitted R9 `postloop.yuv` on all visible Y/U/V samples;
2. the reference-slot lifecycle shows that exact buffer later produces display frame 216 through the parsed display/show-existing event;
3. emitted display frame 216 is byte-equal to the admitted R8 app/dav1d/libaom/NVDEC frame hash;
4. R9 pre-loop and original/coding-input identities remain independently bound.

If a post-loop hash is not unique, the coded-event key plus explicit refresh-slot/show-existing lifecycle must disambiguate it. A matching display hash alone is insufficient.

## Neutrality and decoder agreement

Run unmodified-private and instrumented-private decoders over the same immutable IVF. Require all 336 displayed frames, all planes, and frame order/timing to match each other and the already admitted app/dav1d/libaom/NVDEC outputs. Bind exact decoder source, build, loaded library, commands, logs, bitstream, and trace. Instrumentation errors, unsupported syntax, trace overflow, or incomplete target coverage are fatal.

The new path does not need a new quality campaign when its decoded output is exactly the admitted R8 output. It adds structural evidence only.

## Minimum normative map

For the target coded event, record final leaf-block geometry and authoritative decoded syntax:

- intra/inter mode class, reference/motion identifiers, segment ID, skip mode, and block transform-skip/no-coded-residual state;
- final luma transform layout and transform type/size where the syntax defines them;
- per-luma-TU coefficient absence or presence and decoded EOB, with coefficient scan bounds checked;
- explicit unsupported category for any path whose geometry or ownership cannot be represented.

Use mutually exclusive luma-pixel categories matching the refined R10 contract: skip mode; non-skip final block with no coded residual; residual-bearing block with coefficient-absent luma TU; residual-bearing block with coefficient-present/EOB-positive luma TU; unsupported. These are bitstream/reconstruction facts, not claims about encoder execution.

Final leaf blocks must cover every visible luma sample exactly once. Luma TU layouts must exactly cover their applicable residual-bearing owners. Retain coded geometry and clip only for visible analysis. Reject overlap, holes, duplicate owners, illegal transform nesting, or unexplained pixels. Chroma syntax may be retained, but complete luma coverage is the minimum for the fixed texture question; all-plane sample identity remains required.

## Predictor, residual, and reconstruction

Copy private samples at decoder points with proven lifetime:

- final predictor after intra/inter prediction and before the native inverse path;
- normative dequantized coefficients and EOB before their storage is cleared or reused;
- reconstructed owner samples immediately after the native inverse/add path and before any loop filter.

Never retain decoder pointers, infer a predictor by subtraction, or label `reconstruction - predictor` as the unclipped inverse residual. Validate, for every owned luma sample:

- coefficient-absent syntax has no coded residual and predictor equals pre-loop reconstruction;
- coefficient-present syntax is bound to the copied normative dequantized coefficients/EOB and to the same native predictor/reconstruction surfaces;
- the assembled pre-loop mosaic is byte-equal to admitted R9 `preloop.yuv`;
- the completed post-loop target is byte-equal to admitted R9 `postloop.yuv`.

If the decoder applies any loop filter incrementally before a whole-frame pre-loop snapshot, use per-owner private reconstruction copies taken before that write. Do not call a partially filtered live buffer pre-loop.

Raw unclipped inverse-residual samples are not required for this first syntax/predictor branch. Capturing them inside every optimized inverse kernel would enlarge the patch without changing coefficient-absent versus coefficient-present classification. If coefficient-present owners later become decisive, validate coefficient-to-reconstruction behavior in a separate scratch inverse seeded with the admitted predictor, exact transform/EOB/dequant state, and an exact match to native pre-loop reconstruction before drawing coefficient-stage conclusions.

## Coded-Q semantics

The decoder can authoritatively report the **normative reconstruction qindex/dequantization state** derived from base Q, segmentation, delta-Q, plane deltas, quant matrices, and the dequant table actually used for each decoded TU. Call these fields `coded_qindex`/`decoder_dequant`, not `actual_forward_q`.

This evidence is useful: it conditions coefficient-present reconstruction on the precision committed to the stream and can show whether absent/present strata coexist under different normative Q states. It cannot show that SVT invoked a forward quantizer for a coefficient-absent region, which pre-quant values existed, or whether optimization/RD later discarded them. Coded Q must therefore never be used alone to assign the absence mechanism.

## Frozen analysis and decision value

Join the map to the fixed shirt/background/face rectangles, all 858 frame-120 controls, R9 coding input, predictor, and pre-loop pixels. Report block/TU and pixel populations before descriptors. Compute HF/ACF/correlation only on connected owner intersections or same-owner neighborhood support; retain null/evaluable counts and avoid flattened disconnected masks.

- Loss concentrated in coefficient-absent syntax establishes that final predictor-only reconstruction dominates there, but leaves never-quantized, all-zero quantization, optimization, and RD discard unresolved. The next discriminator is a narrow encoder producer/execution token plus initial/final coefficient capture for those exact owners.
- Loss concentrated in coefficient-present TUs, with source-like predictor but degraded decoded residual/reconstruction, justifies deeper encoder coefficient-stage capture at those exact TUs. Normative coded Q provides context, not forward-quantizer causality.
- Predictor already lacking texture points toward prediction/reference ancestry; it does not make decoded metadata a source-causal test.

No new quality threshold, bitrate conclusion, whole-window prevalence, repair, or playback claim follows from this single-frame map.
