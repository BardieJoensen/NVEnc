# Grain recovery after compression of a fully retained source

D84 tested the existing complete native model on four fixed eight-picture
windows from recorded 8/10-bit NVENC captures. The encoder input was the full
source, without pre-encode denoising. Independently decoded originals and
compressed pictures match 50,331,648 captured samples exactly.

Both 8-bit windows pass the existing full-picture spatial, covariance, mean and
window checks. In these constructed grain controls, compression removed over
99.9% of luma variance in the worst picture/fold. The recovered result's worst
luma variance error is 1.63% and 3.96% respectively. These are grain measurements,
not percentages of perceptual picture quality. Independent NumPy measurements
agree with the native implementation on 58,982,400 source/base/rendered samples,
including the retained failed candidates.

Both 10-bit windows reject: the first has a Cr mean error around 0.236 normalized
8-bit codes, above 0.125; the other fails independent colour covariance at its
last picture. Recovering variance does not excuse either failure. No bound was
relaxed and no output from those failed fits was installed.

D85 implements a separate explicit `pre_encode_modeled_source` diagnostic to
test the successful mechanism through the encoder. It requires a full-source
8–16-picture plan, all three ordinary components active, original-source binding,
exact independent pre-NVENC copy proof for all three planes, a memory-source
engine and `full_picture_means`. Ordinary fallback, missing base, limited support
or inactive components still prohibit synthesis. Source-segment grain-off
semantics remain unchanged. Older libraries must fail if they cannot acknowledge
the explicit mode. No automatic source rule or retry is introduced.

CPU qualification passes 287 Python tests in 39 suites and 56 C++ programs.
The full-source decision controls exercise all 256 ordinary guard/component
combinations; only the explicitly eligible combination can proceed.
GPU copy-proof controls pass 16 cases with 202,752 exact samples and 36 expected
rejections. Fresh actual encoding accepts the complete eight-picture 8-bit case
and rejects the 10-bit case before releasing a model. AOM/dav1d agree on 160
decoded observations including the captures; independent synthesis matches all
6,291,456 accepted output samples. Across capture and replay, 24,379,392 original,
pre-encode and reconstructed samples are checked separately for each role.
The failed receive persists seven of its eight source/reconstruction pairs;
the eighth is covered by the matching runtime engine state and bound input,
not claimed as an independently persisted raw witness. Ordinary SDR/HDR packets,
clocks, metadata, models and decoded pictures remain exact. Both owned pauses
are released.

The full captured 16-picture 8-bit sequence rejects at picture eight: retaining
the first window's frozen shape fails the later colour covariance checks. D84's
two separately fitted successes did not qualify that longer model lifetime.
Next test bounded shape refresh with a continuous global seed phase and check
all windows across the boundary; merely resetting the seed sequence would not
establish temporal stability.

A first attempt to truncate old 16-picture packet captures at eight packets
failed on incomplete AV1 reference/reorder state; the original failed report is
retained and replay now uses complete captured sequences.

This is a finite development mechanism, not production or real-source admission.
In particular, fitting compression loss from a textured source could still
confuse removed detail with grain. D83's real-picture coverage limitation remains
open. Production is unchanged, retention/FEL disabled, and the reserved
qualification corpus remains unopened.

Local evidence: `roadmap-r3-compression-recovery-20260928/` for D84's plan,
fitting and independent measurements; `roadmap-r3-modeled-source-20260928/`
for D85's plan, implementation and qualification. Start at each current report
under the [handoff root](WORK-TO-PRODUCTION.md).
The qualified finite mechanism is core `dc9498cb`; its binary SHA256 is
`f5b3d2099767ac48a1a2989ac8c5494b72c07b3887301115c6ec4fb4e94057df`.
