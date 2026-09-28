# Full-resolution copied colour and source/model transitions

D75 completes the current-build comparison of D73's source-bound schedules.
Constant modeled 1080p 8-bit SDR and UHD 10-bit PQ controls pass. Source/model
transitions fail grain-energy qualification: copying source into lossy NVENC
does not preserve its grain. D76 addresses the acceptance gap with a necessary
[reconstruction energy/mean veto](FINDINGS-2026-09-28-SOURCE-ENERGY.md).

The finite experiment uses four known constructed sources, 16 frames each,
QVBR30, and both transition directions after eight frames. Two sources reuse
the earlier 1024×512 mechanisms; the others exercise full 1920×1080 and
3840×2160 geometry. PQ is a metadata/geometry mechanism here, not natural HDR
qualification. Source-bound selector fixtures remain labelled unit evidence;
range measurement alone does not grant luma or whole-picture eligibility.

Ten captures and ten native output trials use qualified `524a98f6`, binary SHA
`35dcffc13b8100e3961455cdcbea7fa862823971ccd102747382d4e41de7a275`.
Nine output mechanisms complete and one 10-bit source-to-model case rejects on
its independent model check. Headers, clocks, native reconstruction, exact
copied input, model readiness and complete reference packet bytes agree. AOM
and dav1d independently agree in both grain modes across 1,216 observations.
Original, rounded-candidate and reconstruction comparisons each cover
1,581,072,384 samples; the independent synthesis oracle checks 516,538,368 more.
All 88 modeled frames and 25 modeled temporal windows retain the pinned checks.

The source rows expose the missing quality condition. Across all 64 current
captured source rows, 56 retain below 1% of original luma grain variance after
NVENC compression. The median ratio is 0.000590 and maximum 0.178368. In the
seven emitted transition controls, 56 grain-off source rows show the loss and
all seven boundaries fail the source-normalized energy check. The two constant
modeled controls pass it. The 56 windows containing source rows were measured,
not relabelled as qualified. Correct grain headers do not close this gap.

Earlier D62 transitions established transport/header correctness only; the
historical control remeasurement also finds source grain loss. No result here
establishes new library damage or changes production `cb903a17`, where automatic
retention remains off. R3/R4 and later qualification remain open. D76 additionally
retains a clean-transition counterexample: its strict zero-energy policy rejects
20 one-code luma differences after compression. That conservative rejection is
not evidence of visible damage or permission to widen the frozen limits.

Local evidence: `roadmap-r3-preserved-transitions-20260928/report.json`,
`preflight-report.json`, `phase2-comparison.json` and their pinned inputs under
the handoff root. The initial capture manifest incorrectly requested source
segments without native model output; the existing configuration guard rejected
it before processing. Its failed receipt and the corrected capture-only manifests
are retained. D75's owned pauses are released. D76's separate finite GPU work
has its own receipt; read the live handoff for operational state. No experiment
is scheduled and the reserved corpus remains unopened.
