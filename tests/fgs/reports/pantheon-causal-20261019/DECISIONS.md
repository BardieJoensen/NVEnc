# Decisions

- auto: reuse prior verified fixture/metric procedures; fresh scratch and immutable prior archive.
- auto: apply native dav1d synthesis offline on fixed AV1 picture data; verify old model/base against independent FFmpeg and assert input pixels remain identical before/after synthesis. No remux or measured new signaling overhead is claimed.
- auto: estimate missing stochastic covariance from source/base in flat, stationary training tiles; exclude diagnostic ROIs and evaluate different frames/tile parity. Use one frozen rule on regression windows. The source lower-quartile amplitude cap failed quiet-region protection; retain this negative result without refitting.
- auto: archived SVT lp2 VBR is not bit-repeatable; demonstrate preserved/rebuilt binaries agree at lp1, then control both instrumented/uninstrumented arms at lp1 with recon output enabled. Their complete IVF bytes match on both primary fixtures.
- auto: capture reconstructed SB pixels before their deblock call, post-DLF and final recon; original and final traces match source/independent decoder on all240 frames in each fixture.
- auto: collect final entropy-input luma coefficient levels, not mode-search quantizer calls; report counts/magnitudes/EOB as proxies, not bits.
- auto: choose one two-pass allocation intervention: minus12 qindex for source-flat texture SBs with baseline residual amplitude loss, using all frames/regions. Calibrate only actual output rate; do not sweep intervention strengths.
- auto: retain failed primary allocation results; do not expand B to regression windows after clear full-window/edge regressions. E05 rate calibration needed a request bracket after proportional calibration oscillated; no quality setting or map strength changed.
- auto: reviewer caught mixed E04 coefficient-hook versions; use only the validated 240-frame coeff-trace rerun, assert coverage, and restrict the raw stage validator to baseline. Final combined patch with both environment switches absent remains IVF-exact to unmodified baseline.
- auto: reject both candidates for qualification; preserve local A improvement separately from failed quiet controls and B allocation tradeoffs. No production plan or installation is justified.
