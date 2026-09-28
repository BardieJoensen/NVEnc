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
combinations; only the explicitly eligible combination can proceed. Packet replay,
GPU copy-proof controls and fresh encoder comparisons are being qualified.
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
