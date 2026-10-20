# R17 parent implementation

One fixed-choice native FP qindex4 diagnostic on admitted R16 captures.
No encoder, build or GPU work. All2870 joins,2169 invoked baseline controls
(including39 final zero-EOB),701 uninvoked owners remain explicit.
Preserve this directory and worker/reviewer evidence until final archival.

The parent took implementation ownership after four rejected worker drafts.
The v3 runner source was not preserved; its reported hash is not a substitute
for inspectable source. Rejected drafts did not execute the native diagnostic.
The stale contract hash supplied by the parent was also corrected.

Run through the pinned R15 outer execution wrapper, analysis venv, nice10 and
CPU8–11. `experiment.py OUT --preflight` validates schemas, dependencies and
captured mosaics without loading the native library. The actual run omits
`--preflight` and requires independent release. Each invocation uses fresh OUT.

The native build closure, admitted trace/source surfaces, exact frame-header
DC evidence and metric dependencies are checked before use and again after.
All baseline direct/runtime/capture q/DQ/EOB/inverse and raw-inverse controls
finish before the novel arm. q4 replaces only FP table rows0,1,6. Packed64
transforms retain at most1024 coefficients. No uninvoked owner receives q4.

Whole-ROI descriptors reuse the established helper unchanged. Population and
transform strata reuse `pantheon-rd-20261019/analyze.py:masked`: high-pass is
computed on the full rectangular ROI, then only pixels with a complete3x3
mask neighborhood contribute; lag1 ACF uses pair-valid horizontal/vertical
neighbors separately. We report both complete pixel counts/SSE and eroded
descriptor/pair counts. Empty supports produce null metrics. Do not compare
these masked descriptors as if they used the whole-ROI support, add their
HF/ACF values, or infer a causal fraction from them.

Complete full-mask SSE versus original and raw closes across invoked/uninvoked
and native-TX strata. q/DQ/EOB/inverse/raw-inverse arrays have cumulative offsets;
the admitted trace supplies exact original tables/raw/scan/QM and binary offsets.
Full mosaics and masks are saved for independent reconstruction.

The result has no packet-rate, deployability, full-window or playback claim.
Fixed-choice failure cannot reject a real low-q policy that changes decisions.
