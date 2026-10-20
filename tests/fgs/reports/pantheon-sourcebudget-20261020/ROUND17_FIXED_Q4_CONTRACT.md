# R17: fixed-decision q4 on admitted TF-off support

Primary question: how much target texture does native FP qindex4 recover on the
actual R16 TF-off decisions, and what deficit remains when predictor, partition,
transform, scan and quantization-matrix choices are held fixed?

R16 is a reviewed matched-rate negative at9.6698472Mbps. Original coding input
is exact on the observed frame; every shirt pixel invokes quantization with
positive EOB at actualq71. Raw local shirt HF is86.74% of source, initial scalar
HF21.01%, and final postloop11.32%. Background raw HF is99.30% of source with
97.69% invoked coverage. This is sufficient evidence for a precision diagnostic,
while the shirt's raw deficit already warns that fixed choices can constrain it.

This is one q4 point, plus exact baseline controls, not a precision sweep.
Unlike R12–R14, it uses the newly admitted TF-off predictor/partition/transform
population and feedback. R15's real q4 preservation also changed those choices.
R17 measures the fixed-choice remainder before another real allocation test.

Inputs:

- R16 command SHA256
  `00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497`.
- R16 admission SHA256
  `a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab`,
  produced by P16R `admit.py` SHA
  `fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb`.
- Exact source, predictor, trace, token manifest, native decoder and syntax
  artifacts bound by that admission; dynamic coded ordinal from the binding.
- Existing R12 native helper, R13 methodology, and admitted packing controls,
  all with live hashes checked. Preserve existing sources and results.

Required controls before interpretation:

1. Reconstruct all2870 admitted tokens and their exact joins. Establish native
   table/DC-delta semantics from captured tables and independent syntax/native
   evidence. The current helper's zero-DC-delta assumption is not permission to
   assume that state for R16.
2. On every invoked token, reproduce the captured initial scalar q/DQ/EOB and
   inverse exactly through both direct C and runtime-dispatched native paths.
   Reproduce raw inverse with native dimensions, scan/iscan and packing; retain
   captured64-wide adjusted support without expanding1024 coefficients to4096.
   Verify baseline mosaics against the admitted stages and final native map.
3. Change only the q-dependent FP table rows needed for q4, keeping all other
   token inputs fixed. Require exact direct/runtime equality for every new
   q4 q/DQ/EOB/inverse array. If a required input is absent, stop and report the
   exact unsupported state; do not invent coefficients.
4. Keep uninvoked owners explicitly separate. Retain their predictors only in
   the descriptive whole-ROI mosaic; never count them as having received q4.
   Establish complete nonoverlapping ROI coverage and additive spatial SSE.
5. Report unchanged original-referenced HF amplitude, ACF and source-HF
   correlation for whole shirt/background/face ROIs, plus invoked/uninvoked and
   transform-size strata. HF and ACF are not additive. Include native arrays,
   provenance, commands, runtime and unchanged baseline outputs.

These are single-frame local diagnostics. The existing full-window five-frame
texture gates and clean/detail/banding/temporal/playback requirements remain
unchanged and cannot be passed by this replay. There is no entropy coding,
rate-control feedback, reference update, loop-filter or packet-rate claim.
Do not label a reconstruction a legal encode or a repair.

A favorable fixed-choice result supports an actual allocation intervention,
whose delivered quantizers, packet cost and displaced damage must be measured.
An unfavorable result identifies a fixed-choice limitation; it does not prove
that a real lower-q policy, which can change search and transform choices, will
fail. Use the measured remaining support/transform deficit to choose the next
discriminator. No unchanged R16 encode or broad settings sweep is warranted.

Worker owns fresh `worker/psyex-r17-q4` scripts and artifacts. Parent owns
`parent/psyex-q4-r17`, design, execution admission and Git integration; reviewer
owns `reviewer/round17-*`. No recursion or production changes. Preserve others'
files and immutable archives. Use nice10/CPU8–11, no GPU or encode/build unless
the parent explicitly revises this bounded assignment. Initial scratch2GB;
check resources before execution. Review the prepared runner before running it.
