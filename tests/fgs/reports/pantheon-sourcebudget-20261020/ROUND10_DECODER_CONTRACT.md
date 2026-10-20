# R10 final syntax and predictor diagnostic (frozen before capture)

Primary question: on exact R8 E05 scored frame120/input216, does final
predictor-only syntax explain the observed coding-input to preloop texture loss,
or do coefficient-present TUs dominate it? This is a diagnostic, not a repair.

The original-rate ceiling remains9.6765224Mbps E05 /10.029358641Mbps E04.
Reuse R8 quality campaign only after all336 decoded frames match exactly.
No new rate, runtime or playback benefit follows from instrumentation.

## Work contracts and ownership

Parent owns this contract, implementation under parent/aom-decoder-r10, admission,
analysis, scientific conclusions and Git index. Worker owns fresh pristine libaom
source/build under worker/aom-decoder-r10-pristine; exact1344-file baseline,
seven Ubuntu patches, source/tool/command/build receipts, no production writes.
Reviewer owns independent framing/lifecycle and hook/correctness review under
reviewer/round10-*. Neither child delegates or changes production; all preserve
others' changes. Build at nice10, CPU0–7, four jobs; decoding CPU8–11, one thread,
row-mt0. Stop on unexpected input/source identity, unsupported path, failed
neutrality, ownership holes/overlap, framing mismatch or invalid sample identity.

## Frozen observations and controls

Decode exact R8 IVF26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca
from beginning. Independent header/OBU lifecycle binds hidden coded ordinal210,
event314/orderhint88, refreshslot4, OBU48723bytes at IVFoffset10507088, SHA
9169308b8f10753bf26caebb191e9d7ea869ae748a0fe64823e7ddd7b3e3543a,
to show-existing event325/display216. Do not assume one packet equals one frame.
Require all502 events and336 coded frames to agree with independent parser,
including consumed packed bytes and show-existing reference history.

Run private pristine and instrumented off/on decoders. All336 emitted all-plane
frames must equal admitted app/dav1d/libaom/NVDEC recon. Target completed postloop
all planes must equal R9; luma preloop assembled from copies immediately after
native reconstruction must equal R9 before any incremental filtering. Trace
must fail closed; missing/truncated metadata or payload is not admissible.

Capture final luma leaf-block geometry, mode/reference/MV identity, segment,
skip_mode/skip_txfm, actual TU geometry/type/EOB, normative coded_qindex and
actual decoder dequant state/QM where applicable. Exact visible luma ownership
must cover1920x1080 once; residual-bearing owners need complete TU coverage.
Read coefficient buffers only where actual decoded lifetime is proven; absent
syntax has no fabricated coefficients or forward-quantizer inference.

Copy native predictor before inverse/add, dequant coefficients before clearing,
and native reconstructed samples immediately afterward. Skipped inter blocks
have whole-owner predictor/reconstruction; skipped intra still has its actual
prediction units. Predictor-only samples must equal their preloop reconstruction.

Mutually exclusive categories: skip_mode; non-skip block with no coded residual;
residual-bearing owner/luma TU with EOB0; residual-bearing owner/luma TU with
EOBpositive; unsupported. Unsupported target pixels reject admission.
Normative coded_qindex/dequant are not encoder actual_forward_q. This route
cannot reveal encoder prequant values, forward-quant invocation, optimizer or
RD discard. Zero/absent final coefficients never mean quantization was not run.

Scope refinement agreed with independent reviewer before implementation:
raw unclipped inverse residual is deferred. Native before/after copies and exact
preloop identity answer this branch without modifying optimized inverse kernels.
Do not derive or call reconstruction-minus-predictor an unclipped residual.
If needed later, separately validate a scratch inverse against native samples.
No quality acceptance gate is changed.

## Analysis and next discriminator

Use fixed shirt[1200,650,200,100], background[950,50,250,180],
face[160,600,500,480] and all858 frozen frame120 controls, no selected examples
as population evidence. Retain source, packed coding-input, predictor, preloop,
postloop. Report ownership/category counts and measured descriptors; HF/ACF
must use connected rectangles or same-owner neighborhood support, with explicit
null/evaluable counts. Preserve complete/outside groups, including zero quiet.

Compare amplitude AND structure/ACF/correlation/MSE; no single-score inference.
Five-frame texture gate remains ±10%HF and ACFerror<=.05, with whole-window
quiet/edge/tails/banding/temporal and actual playback required for a candidate.
R10 is one-frame diagnosis only. No human playback has occurred.

If absent-syntax owners dominate loss, next discriminator is narrow encoder
producer/execution provenance plus initial/final coefficients for those exact
owners. If coefficient-present owners dominate, follow their coefficient path.
Poor predictor texture suggests reference/prediction ancestry, not causal proof.
Reviewer forms independent assessment before parent conclusion. Correct
implementation/admission errors with minimal new versions; accept valid negative
results without weaker criteria. Preserve all commands/hashes, faults and limits.
