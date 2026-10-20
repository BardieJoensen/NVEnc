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

Current primary uncertainty: can a different encoder prediction/search/decision
policy retain both texture and clean/edge regions more efficiently than the
previous precision redistribution? An inventory and independent design review
will identify one new bounded discriminator before another encode is launched.
Do not repeat manual ROI escalation, grain fitting on the same failed base,
or a broad settings sweep. [Ledger](LEDGER.md) records contracts and decisions.

Prior evidence: [causal and measured preservation report](../pantheon-rd-20261019/README.md).
Prior source-budget ROI failure is accepted; it does not prove source-budget
preservation impossible. All previous archives remain unchanged. Production,
Tdarr, torrents and library changes remain unauthorized.
