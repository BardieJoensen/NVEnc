# R14: original samples with fixed native coding decisions

Primary question: how much of the remaining R13 discrepancy is caused by the
changed coding-input samples, versus the retained transform/skip decisions?
R13 q1 approaches the raw local inverse but the shirt still misses the original.
This is a source-sample intervention at fixed decisions, not another q sweep.

Use all2187 invoked R11 final TUs and retain all720 uninvoked owners as their
actual predictors. Keep native predictor, partition, transform size/type, scan,
QM/IQM, nonlossless10bit state and q1 FP rows fixed. Replace only visible native
source samples with the untouched original frame120, then calculate native
residual and native DEFAULT_SHAPE forward coefficients. Any native padding
outside visible frame height remains captured and is reported separately.
Do not invent transformed residuals for originally skipped owners or propagate
changed pixels into later predictors. No ROI/TU selection based on improvement.

Build a fresh private helper in `parent/psyex-source-r14` by reusing R11 codec
objects read-only, with the R12 quantizer/inverse helper plus a forward wrapper.
Never edit an old source/build/archive. Use the eight observed transform sizes,
correct type-dependent C/native dispatch and native adjusted64 coefficient
packing. The final observed encoder calls DEFAULT_SHAPE; assert this source
route and do not accidentally invoke reduced-shape or lossless kernels.

Admission precedes interpretation: every captured-source/predictor native
forward coefficient must equal the R11 prequantized coefficient exactly, with
directC and initialized-runtime outputs equal. Captured-source q1 q/DQ/EOB and
native inverse through the new helper must match admitted R13 arrays exactly.
Require directC/runtime equality on EVERY original-source forward, q1 quantizer
and inverse. Match captured visible source to admitted R9 coding-input pixels;
match original raw10bit samples to the verified untouched original. Verify only
visible source positions change and all other input bytes stay fixed. Reject
any unsupported geometry, state, layout, source identity or native disagreement.

Bind all source/object/tool/helper/library/contract and R11/R12/R13 dependencies
before/after; preserve actual compile/run commands, clocks and failures. Reuse
existing baseline metrics where bytes agree; new local ROI measurements retain
original and coding-input references separately. Preserve raw forward coeffs,
raw inverse, q1 q/DQ/EOB/inverse and exact token/offset mapping for every TU.
Report whole frozen-ROI HF with ACF/source correlation, MSE, edge error, invoked
and skipped support separately, source-change counts, and local distances to
original/coding input. Full ROI including skipped support is required. Do not
call the raw arm an upper bound for nonlinear descriptors.

A joint local recovery would support upstream sample processing as a necessary
part of this fixed-state repair mechanism; it would not show that public TF-off
is an isolated source-only operation. If raw or q1 still loses texture, quantify
which support remains impaired and use that to choose the next discriminator.
Do not add q points or new transform/search policies in this round.

No encode, packet bitrate, GPU campaign, full-window quiet/tails/banding/temporal
or playback conclusion is generated here. A real encode is still required to
prove preservation, then packet cost, and ultimately original-budget feasibility
with complete quality/playback gates. No criterion changes or production work.

Parent owns this scratch/helper/contract, integration and Git. Reviewer owns
new `reviewer/round14-*` records; worker stays on its assigned R13 packaging.
No recursive delegation. Bound build and execution to4CPUs and <2GB new scratch;
keep the >120GB staging floor. Stop on failed controls or unexpected resource
use; preserve evidence and diagnose the exact discrepancy before any rerun.
