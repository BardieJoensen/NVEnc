# NVEnc 9.29 integration check

Date: 2026-08-04

## Decision

Rigaya 9.29 is safe as the upstream baseline for both the conservative
production branch and the experimental FGS branch.  This check does **not**
deploy either branch to Tdarr and does not change the production FGS options.

The upstream tag is `9.29` at `fc47aaefe6cf34bcc50187ac1317818f8f8df70f`.
The verified conservative merge is `db045100dcd5e55f933093a91e7a58593f1bded7`.
The verified research merge is
`47ebe9708544b19cd641fd894bc46a4daae08738`.

## Conservative branch

The merge had one mechanical conflict in
`NVEncCore/NVEncCore.vcxproj.filters`: both sides added filter entries.  The
resolution retains the FGS files and Rigaya's new `NVEncFilterOnnx.cu` entry.
Rigaya changed no `NVEncFilmGrain*` source file.

Verification:

- the CPU solver/parser/Python tier passed;
- a clean pinned CUDA 13.3 build completed;
- the quick local gate passed, including every GPU KAT fixture and both model
  controls;
- 96 Taxi Driver frames analyzed with the production bilateral/residual
  options produced a grain table byte-identical to the deployed r4069 binary
  (`5da24c0a0a86bac97e23659f5c1fdc07411eec70318137d5caeb8ebe8d12f483`);
- a direct 96-frame AV1 encode decoded end to end with `libdav1d -xerror`.

The pinned 9.29 binary SHA-256 was
`372a3cf97620ba9d8abe94e0b03fd993c6acf2d8ba486ed8eaa3c2050a62dd06`.

## Research branch

The research merge was conflict-free.  It compiled both sets of code that
could plausibly interact: the experimental motion/degrain path and Rigaya's
early-SAD/degrain changes.

Verification:

- the solver and parser tests plus 182 Python tests passed;
- a clean pinned CUDA 13.3 build completed;
- the default 22-fixture GPU KAT passed;
- the model negative and shipping-positive controls passed;
- the motion subset (`coarse_detail_occl`, `coarse_detail`,
  `coarse_detail_pan`, `coarse_detail_move`, and `cut_grainy`) passed and every
  reported measurement was numerically identical to the retained pre-merge
  research binary.

The pinned research binary SHA-256 was
`f96bf3e4254f2ecfa6d145d867e9d35e3c66d282998c58441d5d8fe2402f60d7`.

## Bilateral KAT interpretation

A full `denoiser=bilateral,modelsrc=on` KAT run was 21/22.  The only failure was
the static `coarse_detail` systematic edge bound: 1.95 codes against a 1.5
limit.  This is not a 9.29 or source-fit regression:

- the KAT has long documented that this fixture fails with bilateral;
- the same merged binary gives exactly 1.95 with `modelsrc=off`;
- `denoiser=fft3d,modelsrc=on` passes at 1.44;
- the bilateral cleaned-base transfer is otherwise above its guard (0.531 vs
  0.25).

It remains evidence of a real bilateral separator weakness on this synthetic
static detail pattern.  It must not be relabelled as a green bilateral result,
but it also must not be attributed to source fitting or the upstream merge.

## Remaining scope

This closes upstream-merge compatibility only.  It does not approve
`modelsrc=on`, the motion separator, per-luma closure, chroma amplitude, or
coarse-grain representability for production.  Those retain their separate
quality gates.
