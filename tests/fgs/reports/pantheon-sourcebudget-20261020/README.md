# Pantheon repair at or below original video rate

On2026-10-20 the user set a hard practicality ceiling: **at or below the original
video bitrate**. The preserved4x x264 arms are useful preservation diagnostics
and no longer practical repair candidates, regardless of their playback result.
Their playback is not a prerequisite for further authorized source-budget work.
No tested arm currently meets the complete repair requirement at this ceiling.

Use actual video packets at the same240 scored positions after96 preroll frames:
E04 <=10.029358641Mbps and E05 <=9.676522400Mbps. Decisive matched-rate contrasts
must lie in99–100% of source rate; the prior1% matching tolerance does not permit
an overshoot. Lower-rate arms may qualify for the cap but are not automatically
matched-rate causal controls. All texture/quiet/detail/banding/temporal/playback
requirements remain unchanged. Full-episode qualification is still required
before any production proposal; these are known difficult fixtures.

The first new arm, SVT preset0/tune0, fails the texture screen at9.5227592Mbps,
98.4110% of the E05 original. It is a valid under-cap practical screen, **not a
matched-rate preset comparison**. Shirt/background HF amplitude remains74.6%/
48.1% below source. Spatial structure, face errors and full-reference tails
improve descriptively against preset4, while some quiet/edge errors worsen.
Encoding336 frames took2740.622s on one SVT worker,39.64x the preserved preset4
wall time. No motion playback was observed.

[Measured result](RESULTS.md), [machine evidence](preset0-result.json),
[independent review](REVIEW.md) and [reproduction](REPRODUCE.md) document scope.
The ancillary [original H264 QP-state observation](ORIGINAL_QP.md) is validated;
it does not equate original QP with re-encode preservation.

The independent libaom SSIM/variance-AQ arm also fails at9.6243504Mbps,
99.4608% of source,389.179s/336frames. Shirt/background HF deficits84.37%/50.81%
and ACF errors .10866/.12137 fail. Broad controls improve but face detail and
VMAF/NEG regress. [Machine evidence](aom-result.json) and the same result/review
reports preserve this mixed outcome. All3decoder/sample gates pass.

The matched PSNR-tuned arm also fails at **9.639088 Mbps**, 99.613% of source,
391.652 s/336 frames. Removing the extra SSIM source-variance weighting improves
face/edge detail but leaves shirt/background HF deficits of 84.08%/48.87% and
failed spatial structure. Quiet and flat-texture controls regress on several
measures. [Direct comparison](aom-tune-comparison.json) and independent review
reject this actual policy as a repair; they do not establish a codec limit.

Next discriminator: observational tracing of libaom coding-source samples versus
the exact original input, with unchanged encoded bytes required for admission.
Source audit shows temporal preprocessing is reachable despite requested ARNR
strength zero; only a sample comparison can establish whether it changes pixels.
[Ledger](LEDGER.md) records the bounded contracts and conclusions.

Prior evidence: [causal and measured preservation report](../pantheon-rd-20261019/README.md).
Prior source-budget ROI failure is accepted; it does not prove source-budget
preservation impossible. All previous archives remain unchanged. Production,
Tdarr, torrents and library changes remain unauthorized.

A reviewed [fixed-input grain diagnostic](GRAIN_FIXED_INPUT.md) on the improved
preset0 base preserves a local quiet/texture input conflict. It rejects the
measured white16 probe, not all legal grain models or other bases. No estimator
was fitted and no source-clean criterion was relaxed.
