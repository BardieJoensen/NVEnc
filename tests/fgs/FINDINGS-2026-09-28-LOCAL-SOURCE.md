# Local source-reconstruction checks

D81 closes a second demonstrated blind spot in the experimental source-fallback
veto. On a nonconstant source, opposite constant offsets in different tiles
can cancel in both spatial-half means. Independent ramps can disappear during
tile detrending. All 18 constructed cases passed the earlier D78 policy despite
the deliberately wrong reconstruction. These are acceptance counterexamples,
not evidence of new faults in library media or actual NVENC output.

The existing visible-sample scan now also accumulates each native tile's signed
error and twice-centered first moments. It bounds the absolute tile mean and
each independently fitted slope's edge excursion to 0.125 in normalized 8-bit
units. Luma tiles are 64x64, chroma tiles 32x32, with every smaller visible edge
included and padding excluded. Opposite signs across tiles or axes cannot
compensate. The three basis components are bounded independently; their sum at
a corner does not have a combined 0.125 bound.

The report names `native_variance_means_local_planes_v3` and records each
component's maximum local mean, both maximum slope excursions, a worst tile and
pass/fail. Previous variance, global/spatial-half means and exact constant-plane
requirements remain. A rejected source row cannot publish its model or complete
the diagnostic. No ordinary-path allocation, GPU readback or synchronization is
introduced. Full detail, temporal fidelity and the file-level failure policy
remain separate requirements.

Independent NumPy least-squares measurements cover 120 frames and 661,518,312
source/reconstruction samples: the 18 counterexamples, six numerical geometry
controls at 8/10 bit and ragged/1080p/UHD dimensions, and 96 previously captured
actual NVENC pairs. Every old/new reported moment agrees within 1e-10. The new
check rejects all 18 counterexamples. In the captured pairs, 56 of 64 explicit
source rows pass; all prior acceptance decisions remain unchanged. Temporary
raw measurements are removed with size/hash receipts.

Full CPU, complete native API replay and actual encoder qualification are in
progress. The stricter diagnostic has not been deployed. Production stays
ordinary `cb903a17`, retention/FEL off; the reserved corpus is unopened. R3–R8
and the separate D80 periodic regression alert remain open.

Local evidence: `roadmap-r3-local-source-reconstruction-20260928/` under the
[current handoff root](WORK-TO-PRODUCTION.md), beginning with `plan.json`,
`counterexamples.json`, `independent-report.json`, `full-cpu.json` and
`replay-report.json`.
