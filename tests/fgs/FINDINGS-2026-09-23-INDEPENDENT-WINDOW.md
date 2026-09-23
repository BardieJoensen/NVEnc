# Independent selection with the calibrated temporal grain policy

D59 qualifies explicit `frame_window_means` in `52bab816`. It applies the new
disjoint native means to the previously calibrated D42 policy: per-picture
native Y spatial and all-channel variance guards, complete colour-spatial and
cross-component checks on eight-picture windows, and unchanged mean bounds.
The training half alone chooses a seed. Independent and global failures veto
that choice without retry. All older policy names remain reproducible.

## Results

- Full CPU: 214 Python / 30 suites and 46 C++ programs. Four old fraction outputs
  remain byte-exact; four strict-policy replays preserve their models/outcomes.
  Invalid and older-library configurations reject.
- Both constructed native 8/10-bit controls pass all 16 pictures and nine windows.
  Independent NumPy reproduces 34 attempted pictures / 26,738,688 native samples.
  Their original full-spatial single-picture results remain 16/16 and 15/16.
  The 10-bit picture-0 failure is still present under the separately declared
  strict policy; the calibrated temporal policy does not erase that evidence.
- Four earlier zero/mixed candidates now reject at ordinal 9. Their training
  Cb mean passes, while the independent half exceeds 0.125 code units: for the
  zero candidates, 0.1266785 at 8-bit and 0.1398735 at 10-bit. The global means
  alone passed. The independent failure does not select the next seed.
- Five positive/seven negative GPU encodes confirm these outcomes, including
  all four late failures after one packet had been released. Each terminates
  with an error and an incomplete/failed report; none becomes accepted output.
  The complete model/readiness/selection evidence matches the CPU replay.
- Both AOM and dav1d agree on 320 fresh decoded observations. Original source,
  pre-encode base, NVENC reconstruction and independent AOM synthesis each match
  62,914,560 samples. All 80 successful reference models/payloads match, with
  80 per-frame guards, 45 sliding windows and 192 new half-mean comparisons.
  Earlier policies preserve exact payloads. Original full-spatial failures stay
  in the report; these diagnostics still do not admit real source populations.

The diagnostic binary SHA is
`26dad6c8096e80f75ab8b23d515d89f15856a9da1c541d76d952922c2fd98802`.
Read `roadmap-r3-independent-window-20260923/` (`cpu-report`, `witness-report`,
`encodes`, `comparison`, `drain-pause`) in the private evidence root.

## Continuing implementation

Next connect changing per-picture retained-fraction decisions to the actual
pre-encode/native-model path. Its current fixed fraction applies to all 16
pictures; automatic selection needs immutable ordinal-bound choices and
transition/fallback checks. Then bind the R1 selector to genuine source/detail
and candidate evidence. R3–R8 remain open; reference CPU synthesis is expensive
and these constructed controls do not predict real-file size/quality/speed.
All owned pauses are released with current worker limits preserved. Production
stays ordinary `cb903a17`, retention/FEL off; reserved footage is unopened.
No experiment is scheduled to restart automatically.
