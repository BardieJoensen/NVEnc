# Decisions

- auto: reuse prior verified fixture/metric procedures; fresh scratch and immutable prior archive.
- auto: apply native dav1d synthesis offline on fixed AV1 picture data; verify old model/base against independent FFmpeg and assert input pixels remain identical before/after synthesis. No remux or measured new signaling overhead is claimed.
- auto: estimate missing stochastic covariance from source/base in flat, stationary training tiles; exclude diagnostic ROIs and evaluate different frames/tile parity. Use one frozen rule on regression windows. The source lower-quartile amplitude cap failed quiet-region protection; retain this negative result without refitting.
- auto: archived SVT lp2 VBR is not bit-repeatable; demonstrate preserved/rebuilt binaries agree at lp1, then control both instrumented/uninstrumented arms at lp1 with recon output enabled. Their complete IVF bytes match on both primary fixtures.
- auto: capture reconstructed SB pixels before their deblock call, post-DLF and final recon; original and final traces match source/independent decoder on all240 frames in each fixture.
- auto: collect final entropy-input luma coefficient levels, not mode-search quantizer calls; report counts/magnitudes/EOB as proxies, not bits.
- auto: choose one two-pass allocation intervention: minus12 qindex for source-flat texture SBs with baseline residual amplitude loss, using all frames/regions. Calibrate only actual output rate; do not sweep intervention strengths.
