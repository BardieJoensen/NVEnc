# Source-bound recovery measurements on natural footage

D79 follows the constructed [ordinary recovery study](FINDINGS-2026-09-28-ORDINARY-RECOVERY.md)
using retained original development footage and already completed deployed
`cb903a17` encodes. A read-only trace census covers four excerpts and 4,320
pictures. Two contain recovery starts: House of the Dragon's selected HDR
passage and The Gentlemen's SDR jacket passage. The two other HDR controls
contain none. These are selected development excerpts, not a library sample.

The measurement plan selects the first recovery start in each applicable
excerpt, 40 frames before and after, with one additional preceding source
picture. Selection uses existing trace events, never the measured output
quality. No new encode or GPU pause is required. Source files and archived
outputs must match their pinned hashes; original and decoded clocks must align.

The new `recovery_audit_reference.py` measures every complete native Y64/C32
tile in batches of at most 128. It applies the existing necessary variance,
mean-drift, temporal-correlation and gradient-coherence screen to each component
using source pixels only. Candidate pixels cannot change that screen. Constant
source areas, unsupported tiles and partial borders remain separate. Every
tile retains source, coded-base and final-output energy and mean/error results.

This screen does not establish source admission: fast moving texture can pass,
while persistent grain can fail. Both are retained regression controls. A
changing selected population cannot establish the same area's recovery, so a
separate cohort requires the same coordinates to pass all 40 source frames
covering eight late-hold, sixteen ramp and sixteen following pictures. Empty
cohorts remain empty; no threshold relaxation or output-based reselection occurs.
Native PQ code variance is not display luminance or a perceptual score.

The helper's eight CPU regressions pass, including independent least-squares
measurements across its batch boundary. The complete CPU suite passes 275
Python tests in 38 suites and 54 C++ programs. The actual comparison is complete:
5,760 fresh AOM observations match the prior independently decoded dav1d traces,
and 492 new source/base/output frames match their clocks and output hashes.
Each role covers 1,161,907,200 native samples. All six source/output raw files
were hashed and removed after measurement, releasing 6,971,443,200 bytes.

Local energy attenuation occurs in both windows. In the SDR hold, eleven
screened luma tile observations have median output/source variance 0.0889;
the HDR hold has just four, with median 0.7045. Those small, changing populations
are inadequate for a causal or perceptual recovery claim. No fixed 40-frame
cohort survives in either title or component. The measurements do not justify
shortening the hold, boosting grain or classifying library files as damaged.
`natural-recovery.png` and `.pdf` expose the missing coverage as gaps.

A separate exact-source witness does identify a bounded follow-up. At SDR
output ordinal 115 (source clock 2008.792), a 64x64 black letterbox region is
constant Y=64/Cb=512/Cr=512 in both the original and coded base. With synthesis
enabled, its luma ranges from 64 to 71 at 10-bit depth. Added luma RMS is
0.369466 in 8-bit code units, with mean increase 0.203735. These are small
numeric changes, not a playback-severity verdict. The existing quiet guard
deliberately excludes clipped endpoints. D80 will isolate protection for exact
constant endpoints while retaining the separate treatment of uncertain shadow
grain and colour. The temporal hold/ramp remains unchanged.

Evidence lives in `roadmap-r4-natural-recovery-20260928/` under the handoff
root: `plan.json`, `census.json`, `manifest.json`, `full-cpu.json`, `comparison.json`,
`constant-review/report.json` and `report.json`. Production, retention/FEL settings, source
protections and reserved qualification footage are unchanged. R3–R8 continue.
