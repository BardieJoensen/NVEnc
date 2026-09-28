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

Full CPU passes 278 Python tests in 38 suites and 55 C++ programs. Native tests
include 14 positives, 170 rejection controls and terminal failures at ordinals
0, 8 and 15. All 20 complete native API replays preserve prior decisions,
measurements, models and readiness; nine accepted IVF outputs remain byte-exact.
Implementation `3dd646b8` also passes the finite ten-job actual encoder trial.
Eight encodes succeed and two reject at the expected source ordinals (0 and 8),
before publishing the offending model. AOM/dav1d agree on 320 decoded
observations. Original, rounded candidate and reconstructed roles each match
273,997,824 independently checked native samples; AOM synthesis adds 18,874,368
oracle samples. All 40 accepted source rows pass independently solved local
means/slopes. Ordinary SDR/HDR pairs preserve packets, clocks, metadata,
models and decoded pictures exactly. The owned Tdarr pause is released.

The qualified diagnostic binary SHA256 is
`19397de6e61ca4a3830eb6414bc8a6921b9953d095716d7fb116b49efd0f8ab0`.
The stricter diagnostic has not been deployed. Production stays ordinary
`cb903a17`, retention/FEL off; the reserved corpus is unopened. R3–R8 remain
open. D80's separate periodic comparison is now explicitly reviewed with a
versioned development reference; its original failed comparison is retained.
Neither result is a full release verdict.

Local evidence: `roadmap-r3-local-source-reconstruction-20260928/` under the
[current handoff root](WORK-TO-PRODUCTION.md), beginning with `plan.json`,
`counterexamples.json`, `independent-report.json`, `full-cpu.json` and
`replay-report.json`, `gpu-comparison.json` and `report.json`.
