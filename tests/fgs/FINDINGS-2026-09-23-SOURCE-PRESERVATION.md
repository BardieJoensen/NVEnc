# Complete source preservation, frame-wide curves and rare grain seeds

September 23, 2026. Automatic retention remains experimental and unfinished.
R1/R2 are complete; R3–R8 remain open. Production stays ordinary `cb903a17`,
with retention and FEL disabled. No library file was changed by this work.

## Post-reboot qualification

The reboot resolved the NVIDIA driver/library mismatch. The host and GPU now
report driver 595.91.07. Finite, manually started trials acquired and released
their own Tdarr pause. The current node's existing two GPU transcode workers
and two CPU healthcheck workers were preserved; the old all-zero limits were
not restored. No experiment is scheduled to restart automatically.

`ca6f355c` final-model capture now passes its previously blocked comparisons:
3,840 decoded observations across SDR/software and HDR/hardware input match
the previous build, in both grain modes. Clocks, metadata and grain decisions
match; the 12 selected native base captures and signalled final models match
their independent references. Eight invalid diagnostic requests fail safely.

`a7b54f7f` adds complete native source/base counters and a source-preserving
colour proof. `696a7b40`, built with working CUDA header dependencies, qualifies
the new diagnostic integration: another 1,920 decoded observations match, and
93,312,000 component samples reproduce independent native counts exactly.
The last built and ordinary-output-compared diagnostic encoder is:

```
696a7b4087b97f00eab2236dffb1a34c8eee88a6
SHA256 0d5253aa137c020a4721a838fa8713be90fb16014c4bf4a6022e2a6119a9a66b
```

Later `324eb073` changes the offline coverage guard; `fd896e6d` adds a manual
seed experiment. Those helpers have no encoder output call sites. The complete
CPU suite passes 185 Python tests in 26 suites and 27 C++ programs.

## Exact preservation of one colour component

An unsupported colour component can be retained exactly, while the other
component uses a qualified grain model. This requires evidence over the entire
native component, including partial borders, and an actually inactive or
zero-strength synthesis curve. Counters bind to the exact frame, source
population, base and model; invalid native codes or P010 padding reject proof.

An active zero curve still invokes AV1's final range clamp. Therefore copying
source pixels and setting strength to zero does not by itself prove exact
preservation. The shared syntax/range proof accounts for component activation,
chroma-from-luma, restricted range and matrix interpretation. `324eb073` also
closes the older coverage shortcut that bypassed this native range check.
The old coverage code fails the new negative; the corrected code passes it.

Independent AOM controls cover 2,304 component/seed cases and 14,676,480 sample
observations: 1,272 accepted cases are pixel-exact, 1,032 are conservatively
rejected, including 96 active-zero-curve clipping negatives. Native GPU counts
match 78 synthetic/real cases, 324,627,360 samples and 1,092 rejected invalid calls.

The retained-colour helper still checks the actual common-coordinate Y/Cb/Cr
covariance and 49 spatial Cb/Cr lags. It keeps the original cohort divisor and
does not pretend that all pixels passed the other component's grain gate.
This proof is before lossy NVENC compression, not a lossless-output guarantee.

## Frame-wide model still fails

The eight reused development patch groups pass their 48-seed average with
10% Y residual, 25% Cb residual and exact source Cr. However, **65 of the 384
individual seed/group evaluations fail** the unchanged model bounds. An average
pass does not establish a per-frame pass or independent qualification.

The subsequent test renders 48 complete native HDR pictures using AOM, with
actual image coordinates, overlap, brightness curves and four frozen stress
seeds. It compares a single piecewise curve with the old constant-bin controls.
Exact source Cr survives, but the frame-wide model is rejected. Individual
nonzero seeds also have failures; removing seed zero is insufficient to qualify
the model. Native endpoint occupancy is recorded, not a count of actual clipping
events.

Only 282–393 source-gated Cb blocks per tested frame are supported. The frozen
curve adds grain to 1,671,168–1,784,832 unqualified Cb pixels out of 2,073,600,
including borders. R1 revision 1 has no acceptance proof for those populations.
This is a limitation of the candidate's evidence, not proof of damaged library
media. The strict bounds and reserved, unopened qualification corpus remain intact.

## Rare seed degeneration and a bounded correction experiment

AV1's random generator has a zero state. Seed 0 degenerates the luma template;
46372 and 18904 do so for Cb and Cr respectively. Visibility depends on the
model, component activity and picture. AOM's encoder already avoids luma seed
zero in its seed increment, but NVENC's public grain parameter struct exposes
no seed control. Changing an input grain-table seed does not control NVENC's
actual emitted seeds.

A 65,536-frame, 256x256 synthetic encode with the ordinary deployed encoder
emits every possible seed once. All frames signal grain. Independent dav1d
decoding confirms three one-frame component dropouts, with variance falling
from roughly 16 to 0.095 native 10-bit code units squared. They occur at displayed
frames 37074 (Cb), 52534 (Cr) and 63422 (Y). This is distinct from the earlier
ripple and apply-grain/reference-state fixes. Library prevalence and visibility
have not been audited, and this does not justify redownloading titles.

The new **manual IVF experiment**, `seed_patch_ivf.cpp`, locates seeds using
FFmpeg's AV1 parser and independently checks OBU boundaries and field values.
It changes only those three seed values to their next nondegenerate value,
preserves every other bit and writes a new file. It rejects parser/input failures
and an existing output. It is not a production encoder hook or a Matroska repair
tool; its serial trace callback is unsuitable for direct multithreaded reuse.

On the full synthetic sequence:

- Exactly three bits change; every other byte, IVF timestamp and packet size is exact.
- All 65,536 grain-disabled pictures and clocks remain exact.
- Grain-enabled pixels differ only on the three affected displayed frames.
- Their affected-component variances recover to 15.83, 16.09 and 15.73.
- AOM and dav1d agree on all 65,536 corrected grain-enabled pictures.
- IVF conversion also preserves the original test MKV's decoded pixels/clocks.
- Repeating the correction is byte-identical; malformed inputs and an existing
  output are rejected. Exhaustive unit checks cover all 65,536 seeds at eight
  bit alignments without changing neighboring bits.

Thus a seed-only correction is feasible without re-encoding the picture.
Production parser integration, wider reference/show-existing coverage, full
container/nonvideo preservation and runtime cost remain unqualified. No seed
correction has been installed in Tdarr or applied to library files.

## CUDA build reliability

The first incremental `a7b54f7f` build silently reused the old CUDA object and
old binary. Meson 1.3.2 supplied no CUDA dependency-generation arguments; Ninja
recorded zero header dependencies. This was detected and invalidated before
using that binary in an encoder trial. It is not evidence that earlier deployed
fixes were absent; those have their own runtime comparisons.

`696a7b40` requires Meson >=1.4.0 and CUDA >=10.2 for this build path. A regression
changes only an included CUDA header: 1.3.2 incorrectly keeps the old result,
while isolated Meson 1.4.2 recompiles and produces the new result. The full encoder
was rebuilt and its actual header dependency list checked. No host/image package
was replaced to run this test.

## Evidence and next work

Under the evidence root named in [the handoff](WORK-TO-PRODUCTION.md):

- `roadmap-r3-final-model-20260923/report.json`: post-reboot final-capture qualification.
- `roadmap-r3-preserved-colour-20260923/report.json`: native preservation, range,
  integration and build-dependency evidence, including retained negative controls.
- `roadmap-r3-frame-curves-20260923/report.json`: rejected full-frame model and coverage.
- `roadmap-r3-seed-cycle-20260923/attempt-v2/patch-report.json`: seed-only byte,
  clock and independent-decoder proof. The first 128x128 attempt failed NVENC's
  minimum dimensions before encoding; its failure remains recorded separately.

Next, complete population-aware model acceptance and actual bounded encoder
selection, while addressing emitted-seed handling before any new release.
R4–R8 then cover moving transitions, unseen compressed pictures, quality/bytes,
speed and a Tdarr canary. Ordinary-output equivalence of the diagnostic build
does not qualify an automatic retention policy.
