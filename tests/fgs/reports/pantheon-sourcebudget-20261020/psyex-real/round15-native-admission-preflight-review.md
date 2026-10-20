# R15 native observation/admission preflight

Reviewed without execution:

- `parent/psyex-real-r15/replay_decoder.py` SHA256 `99ccb7993dcf720f9f0f8835d3f0e41750db6bd27acd638299717f6b52efaf7b`
- `parent/psyex-real-r15/admit.py` SHA256 `72c894e903e7a45b7aa4ce3e910bc0355ecd598ed4caebbad0eb05ecd1f87cad`
- parameterized parser/control already reviewed separately.

## Required provenance corrections

1. **Pin the reused R9 boundary parser and its admission by fixed hashes.** `admit.py:122-127` currently reads the old admission and trusts its embedded script identity, which is self-referential if both files drift. Require the known old admission SHA `f6a7a6d3221f15fb789419a43cd3f1b61372ffb99e325cd1ee131962ed5be7fc` and parser SHA `763eeebf43017e79aba6c8ffdce531462f262000290ba9846ad7ae8065e70f8d`, then retain both in `artifacts`.

2. **Hard-pin the native replay wrapper.** `admit.py:43,147` accepts `decoder_replay_sha` from its own command line and then treats that caller value as authority. Replace/compare it against `99ccb7993dcf720f9f0f8835d3f0e41750db6bd27acd638299717f6b52efaf7b`. The actual receipt and live script are otherwise well bound.

3. **Pin the exact parser-control receipt/generator used to substantiate unchanged semantics.** Lines 73-79 bind the control without an expected digest and then trust its embedded generator. Require control SHA `afb324e1c891990816383bdfc0ecc281268692c96003adc9729e55163cf947e4` and generator SHA `8a1f29866cfdecbebfbbac1b9b0df2c5cf6102e65c840634e4d77d4529b00b9d`, retaining both as artifacts. The actual generated parser is already hard-pinned.

These corrections affect admission provenance only and require no replay or decode change.

## Structural assessment

The decoder wrapper correctly refuses to reuse the R10 native observer unless the independently bound stream still has target event314/coded210, hidden/order-hint88/refresh16, and total 502/336 populations. A mismatch stops before decoding and requires a private retargeted build. It pins the completed R10 build, checks its loaded libaom, decodes single-thread/row-mt-off, requires the entire 336-frame output to equal the R15 app reconstruction, and distinguishes trace-off from trace-on. This is a sound reuse gate.

The aggregate correctly obtains all dynamic event identities and counts from the independent binder, domain-checks them, verifies display216 resolves to that event, and checks the target type-6 OBU. It then:

- verifies all336 app/dav1d/libaom/NVDEC agreement;
- requires exact neutral R11 off/on IVF and app reconstruction with fresh R15 stats;
- parses exhaustive R9 source/preloop/postloop boundaries for input216 and binds postloop to decoded display216;
- parses the native decoder with dynamic event/count parameters and requires full visible-luma ownership, R9 preloop equality, and all-plane postloop equality;
- byte-joins every native decoder event, in order, to independently framed IVF packet OBUs, including normalized refresh/coded ordinal metadata;
- joins every traced final encoder owner to one decoder owner, source/coding input, predictor, preloop reconstruction, committed q, EOB, TX, DQ/dequant, and effective IQM; and proves the complete positive-EOB population in all three frozen ROIs;
- records invoked/uninvoked support and actual-q distributions, including pixels above qindex1 and qindex4.

The storage-layout normalization and effective-QM handling remain the admitted R11 logic. Visible edge clipping and adjusted 64-point coefficient populations remain guarded. I found no altered geometry, q unit, DQ/IQM convention, or event-byte assumption in these joins.

## Scope wording and failure receipt

The result booleans `source_predictor_preloop_exact` and `final_dq_eob_iqm_exact` at line233 are broader than the evidence: full-frame pre/postloop are exact, while predictor/owner/coefficient joins cover the three traced ROIs, and DQ/IQM exist only for positive-EOB units. Rename them to state `all_traced_roi_owners_source_predictor_preloop_exact` and `all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact` (or equivalent). This prevents a full-frame coefficient claim.

`admit.py` creates its output before assertions but has no failure receipt. That is a workflow limitation rather than a false-pass risk; preserve stdout/stderr and partial artifacts if it stops. A nominal `admission.json` must be treated as valid only after every assertion completes.

With the three fixed provenance pins and narrower booleans, the pipeline is adequate to admit actual R15 intervention delivery. It still makes no quality, bitrate-practicality, isolated-TF, repair, or playback claim.

## Corrected final admission — cleared

Final `admit.py` SHA256 `7dc554ff79d8b9c8b206e10f5326394dcc4483e5c679cfcb22529340aa7c9da4` implements the requested changes exactly. It hard-pins decoder replay `99ccb799…`, parser control `afb324e…`, generator `8a1f298…`, prior R9 admission `f6a7a6d…`, and R9 parser `763eeeb…`, retaining them in the artifact graph. The two final evidence booleans now accurately distinguish complete traced-ROI owner/source/predictor/preloop joins from positive-EOB DQ/IQM joins plus all traced EOB/q checks. The scope separately states full-frame boundary and all336 output identities. The final admission implementation is cleared for execution through the planned outer failure/log receipt.
