# Round8: a fixed texture-sensitive policy at the original rate

Primary question: can pinned PSYEX's integrated texture-sensitive decision
policy preserve the established E05 texture and controls within the original
packet budget? R7 demonstrated finer actual quantization but failed preservation
at4.01686×source. Its optimizer-only inter stratum also lost substantial amplitude
after initial quantization. This motivates a policy that reaches coefficient,
residual-versus-zero and mode decisions together.

This is one bundled feasibility arm, not an isolated psy-rd or RD-multiplier
experiment. No ROI allocation, result-fitted strength, new grain estimator or
settings sweep is permitted. The practical ceiling remains9.6765224Mbps on the
E05 scored window; aim99.5%, require99–100% for decisive matched-rate claims and
within1% of R3's9.639088Mbps. Calibration may change requested bitrate only.
All failed/calibration runs remain recorded. An under-cap run below99% may be
screened only with an explicit nonmatched label, under the existing Round1 rule.

## Fixed policy and build

Source is clean pinned master59d1a025698f2ca7b4c4b0e833937dd15e382494, not the
v3.0.2-B tag. The1217-file root-tracked manifest is
8cf0314d5ee329b662c32021020c8299ef47bb87681d87508328c1b28eeb5c69.
Independent source review traced guarded RDOQ rate-weight removal, AC-energy
distortion, actual residual-zero/skip comparisons and full mode costs. It found
documentation mismatches: actual defaults are psy-rd1 and noise normalization1.
CLI values and runtime evidence take precedence over documentation.

Freeze preset4, tune0, psy-rd1, sharp-tx1, sharpness1, spy-rd0, complex-hvs0,
full high-bit-depth mode decision1, noise normalization1 and noise-adaptive
filtering0. Preset4 already chooses full HBD at this psy strength; explicitly
setting it removes an automatic-mode ambiguity. Preserve the fork's QM
(luma4–15/chroma10–15), AQ2/variance boost1/strength2/octile5/curve0, QP compression1,
TF1/strength1/keyframe strength1, overlays0, deblock1 and automatic CDEF/restoration.
No film grain or film-grain denoise. Noise normalization is a coefficient policy,
not a permission to introduce noise: the unchanged clean-region tests apply.

Use two-pass VBR with fresh stats, random access, keyint240/closed GOP,
hierarchical levels4, scene detection0, lp1, nice10 and CPUs0–7. The explicit GOP
and search settings are part of the bundle. Input is the exact established336
frames (96 preroll+240 scored), 1920×1080,24fps,10-bit exact lift, limited BT709.
Input SHA232abb5ffee869be4bedf682aa103c166eb473bb3fdad5daf28956cca60148d4.
First requested bitrate is10000kbps; subsequent calibration uses actual packet
response only, without consulting quality to tune settings.

The reviewed private Release/Ninja build completed2026-10-20T12:51:58Z with four
compile jobs on CPUs0–7. Source manifests and compiler/build configuration hashes
were unchanged; both tracked and untracked source paths were checked. No install.
Final build runner SHA4cf939e20445e130970fdf09983a774e1f71adf1ea6240038cc557fe9ef66a7b.
App SHA f4867ae287fa34cc50f927b7aa52611973adbc7231785117e5d32ce077b2461c;
private library SHA cd408a2f31f871cf9da924dd943607e2b8aa2e5366e513fc82d959434414f20b.
The loaded SONAME resolves to that private library. Scratch contains source,
tool/config/binary manifests, logs, help/version output and all runner revisions.

Provenance correction before encoding: configure fetched an ignored nested
cpuinfo dependency, explicitly pinned by `cmake/cpuinfo.cmake` to
e649baaa95efeb61517c06cc783287d4942ffe0e. The root1217-file manifest does not cover
it. Parent verified the clean nested commit (including ignored/untracked paths),
all570 tracked files and build.ninja's compiled source paths after the build.
`cpuinfo-audit.json` and `cpuinfo-manifest.json` supplement the original receipt;
the manifest SHA is2374575a0aba9b941152770a2374ec048eb540868366bbbb46df846896a4a63f.
This is a post-build provenance audit, not a nonexistent pre-build manifest.
The compiled app/library hashes remain pinned; no unchanged build is repeated.

## Delivery and acceptance

First produce the unmodified legal stream and measure its actual packet budget,
two-pass wall time and complete decoder/color/cadence agreement. Then use a
separate observational build to verify actual guarded policy execution. Disabled
and enabled observation must reproduce the unmodified full336-frame stream
exactly. Timing from instrumentation is not the practical runtime measurement.
Counter coverage and limitations must be explicit; counts are neither pixel
ownership nor measured coded bits.

Minimal runtime evidence covers optimizer entry/early exits/sharp guard/actual
zero rate weight; spatial versus transform-domain distortion routes; nonzero
psy terms; actual residual-zero and skip-mode comparisons; selected mode and
partition paths. It must identify pictures/stages without treating repeated
candidate evaluations as final blocks. No altered coefficient or decision state.
The exact observation implementation receives focused independent review.

Quality uses the established campaign.py GPU paths, exact336 app/dav1d/NVDEC
agreement and exact240 scored planes, both five-frame texture regions (HF±10%
and ACF error≤.05), source-HF correlation, full240 temporal traces, all12870 frozen
tiles, quiet/edge/face controls, full-reference scores/tails and CAMBI. No gate
changes. Parent inspects decisive artifacts. A numerical pass is provisional;
E04 transfer, broader episode evidence and actual playback are still required.

Worker owns only fresh PSYEX scratch source/build/instrumentation, preserving
the unmodified checkout and others' files. Parent owns encode/scoring runners,
scientific decisions and NVEnc index. Reviewer owns independent review documents.
No recursive delegation, production changes or concurrent GPU benchmarks.
Stop a run for missing source/provenance, non-neutral observation, invalid
alignment/color/rate accounting or resource exhaustion; correct the specific
defect before interpreting quality.

If this arm fails, reject only this pinned configuration at its measured rate.
The next experiment must distinguish a remaining mechanism; failure does not
prove that AV1 or faithful re-encoding is impossible.
