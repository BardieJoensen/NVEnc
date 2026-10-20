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

Next discriminator: one independently implemented libaom AV1 policy at source
budget. The large amplitude misses make that more informative for practical
feasibility than calibrating the preset0 rate solely to estimate a clean preset
effect. That matched preset effect remains unresolved. No inference of a codec
limit follows. [Ledger](LEDGER.md) records contracts and decisions; no broad
settings sweep, repeated manual ROI escalation or failed-base grain fitting.

Prior evidence: [causal and measured preservation report](../pantheon-rd-20261019/README.md).
Prior source-budget ROI failure is accepted; it does not prove source-budget
preservation impossible. All previous archives remain unchanged. Production,
Tdarr, torrents and library changes remain unauthorized.

A reviewed [fixed-input grain diagnostic](GRAIN_FIXED_INPUT.md) on the improved
preset0 base preserves a local quiet/texture input conflict. It rejects the
measured white16 probe, not all legal grain models or other bases. No estimator
was fitted and no source-clean criterion was relaxed.
