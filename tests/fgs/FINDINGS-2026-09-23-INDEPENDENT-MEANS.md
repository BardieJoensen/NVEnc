# Independent native means and retained colour candidates

D57 qualifies `649d41a9` and explicit `full_picture_means`. Each fixed
checkerboard half now measures all of its native samples before detrending.
Only training mean/spatial evidence selects among four seeds. Independent mean,
spatial and global-mean failures veto the first training pass, without retry.
The unchanged limit is 0.125 in 8-bit code units. Missing means cannot pass,
and opposite half-image shifts cannot cancel. Earlier policies stay explicit.

## Qualification

- Full CPU: 214 Python tests in 30 suites, 46 C++ programs. Coverage includes
  padding, odd/even tile grids, native depths, exact boundary, cancellation,
  missing/invalid measurements, old interchange and independent vetoes.
- Native measurements match independent NumPy on 32 source/reconstructed
  pictures: 192 exact component means, 256 moment arrays, maximum matrix
  error `5.60e-14`. Twenty attempted candidate pictures independently reproduce
  their mean/spatial decisions, including every failed 10-bit seed.
- Four prior fraction outputs remain byte-identical; both prior strict controls
  preserve their outcomes/models. Four invalid/older-library controls reject.
  The strict 8-bit control passes; strict 10-bit still rejects all four seeds.
- Four positive/three negative live GPU encodes. Both AOM and dav1d agree on
  256 fresh decoded observations. Independent source, candidate, reconstruction
  and synthesis checks verify 50,331,648 samples per role. All 64 fitted models,
  readiness and reference payloads match. Both older policy outputs are exact.
  The new live output also matches all 96 independently measured half means.
- Private library retains nine ABI-2 exports and no dynamic AOM/FFmpeg dependency.
  Binary SHA: `d92cc8907e0e1951169ee7d61380460f3c105e532ae0a468b88d6e92589e3ccf`.

D58 then tries equal colour residual fractions 0.1, 0.25, 0.5 and 0.75 on that
same constructed 10-bit control, with Y fixed at zero. None qualifies: three
fail bounded seed/independent checks and 0.5 fails the frozen native shape fit.
This diagnostic subset is not the independent R1 component selector. A fresh
whole-source, grain-off encode verifies the terminal fallback mechanics.
All five grain-off captures pass 320 independent decoded observations and
62,914,560 exact samples per source/base/reconstruction role: 64 partial and
16 complete-source pictures. Nothing is installed in the library.

The native check script initially shadowed its imported mean helper with a
list; the corrected complete check was rerun into separate evidence paths.
D58 initially lacked a scratch parent directory and stopped before GPU work;
its pause was released, the setup was corrected and all trials completed.
These setup/verification failures and original strict model rejections remain
recorded. No encoder quality threshold was changed to obtain a pass.

## Continue the roadmap

The calibrated D42 frame/window policy addresses finite random-grain variation;
its original single-picture spatial failures must stay visible. Its legacy
seed selector still uses a global mean containing check pixels. Apply the new
independent means to that policy, then continue bounded fractions, source/detail
eligibility, temporal integration and R3–R8. A passing model never grants source
admission. Constructed normative footage is not unseen-media qualification.

Private evidence: `roadmap-r3-fold-means-20260923/` (`cpu-report`, `measurement-report`,
`witness-report`, `encodes`, `comparison`, `library-isolation`, `drain-pause`) and
`roadmap-r3-fraction-candidates-20260923/` (`plan`, `encodes`, `comparison`, `drain-pause`).
All owned pauses are released with current limits preserved. Production stays
ordinary `cb903a17`, retention/FEL off; reserved footage remains unopened.
Manual work continues; no automatic restart is scheduled.
