# Immutable retained fractions for each input picture

D60 qualifies `48a5c471`. A finite diagnostic can now specify one `[Y,Cb,Cr]`
row for every consecutive input ordinal with `pre_encode_retention_frames`.
The old constant request remains supported. Parsing, source attachment,
reconstruction and model fitting share the same bounded immutable plan; NVENC
receive order cannot select another picture's row. This carries decisions but
does not invent their source eligibility or make the fractions automatic.

## Qualification

- Full CPU: 214 Python tests / 30 suites and 46 C++ programs. Tests cover exact
  row counts, conflicting styles, nonfinite/non-numeric values, float rounding
  to the source endpoint, ordinary guard precedence and ordinal-bound decisions.
- Six previous outputs are byte-identical with both constant and scheduled
  requests. Eleven negative replays reject malformed, missing, changed or
  source-preserved requests. A changed request at ordinal 5 is rejected there;
  source preservation introduced at ordinal 9 cannot receive a partial model.
- Twelve positive/six negative GPU encodes. Both native depths pass changing
  partial fractions and whole/component-source transitions. Four ordinary
  controls, including original Shining HDR and the labeled Amphibia derivative,
  preserve exact payloads, clocks and metadata. No qualification pixels opened.
- AOM and dav1d agree across 672 fresh decoded observations. Independent checks
  verify 100,663,296 source samples, 100,663,296 native rounded candidates and
  100,663,296 reconstructed samples. Pristine denoised bases stay identical
  across schedules. There are 120 partial and eight whole-source pictures;
  twenty preserve at least one component. Capture-only output stays grain-off.
- Constant and changing native output reproduce all 64 CPU models, readiness
  states and packet payloads. An independent AOM oracle matches 50,331,648 final
  samples; NumPy passes 64 frame guards, 36 windows and 384 half-mean comparisons.
  Every modeled output picture signals grain. Original strict single-picture
  results remain 16/16 for each 8-bit arm and 15/16 for each 10-bit arm.
- Missing/extra input, mixed configuration styles, short plans, a full-source
  model request and file-source model mode all reject. Full-source rows remain
  incompatible with native replacement fitting: preserving the source is not
  permission to synthesize over it.

The first Python negative fixture reused one list for repeated rows. Its
changed-request mutation therefore changed multiple rows before serialization.
The original evidence is preserved; the canonical fixture now copies rows, and
three isolated-row controls were rerun. This did not change encoder code.

Binary SHA: `a932254be03f4ad70feac7e6644ec41ec00f8a31ec90b8c900b827e686c13b17`.
Read `roadmap-r3-frame-fractions-20260923/` (`cpu-report`, `encodes`, `comparison`,
`drain-pause`) and the [manifest contract](MODEL-OUTPUT-TRIAL.md).

## Continuing implementation

The diagnostic native fitter still requires dimensions divisible by 64. Extend
its complete native measurements and oriented source/base fitting to ordinary
1080p/2160p geometry, with disjoint full-raster partitions and independently
checked observation counts. Cropping cannot qualify unmeasured edges. Then bind
the bounded source/fraction selector to actual candidate evidence and proceed
through R4–R8. Changing explicit fractions alone is not automatic retention or
complete temporal/real-source qualification; the original admission gaps remain.

All owned pauses are released with current limits preserved. Production remains
ordinary `cb903a17`, retention/FEL off; reserved footage is unopened. No automatic
restart is scheduled. Continue the roadmap without stopping at this checkpoint.
