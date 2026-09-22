# R1 contract and experimental GPU joint measurements

R1 of the [retention roadmap](RETENTION-ROADMAP.md) is complete. The
[decision contract](RETENTION-CONTRACT.md) defines whole-picture eligibility,
bounded component candidates, source fallback and separate qualification rules.
Six reserved video excerpts from The Bear S04E10, Pantheon S02E08 and
Transformers (2007) retain exactly the original compressed packet sequences.
They occupy 1,487,984,476 bytes. No grain measurements or candidate results from
those excerpts were used for development.

R2 now has a tested GPU measurement module. Encoder lifecycle integration and
its disabled/enabled output-equivalence trial remain open; the new headers
currently have no production encoder call sites. Automatic retention and FEL
remain disabled in production.

## Implementation

`NVEncFilmGrainJointCollect.h/.cuh` supports native 8/10-bit planar input and
NV12/P010 views with independent pitches and component offsets. It validates
source/base frame identity, complete previous colour, frame adjacency, reset
epoch and presentation order before using temporal source evidence.

A dedicated history object copies all three components on the owning CUDA
stream. Reset, failed update and a different stream cannot expose valid history.
The existing encoder luma-only cache is not used as colour evidence. Invalid
native codes reject measurements without indexing outside the lookup histogram.

The collector measures each prospective base after native nearest-even rounding.
It retains the orientation of source/base cross moments and collects both colour
components' relation to luma. Additional common-coordinate Y/Cb/Cr covariance
and 49 Cb/Cr spatial cross lags prevent the measurements from silently omitting
the relationship between the colour components. These measurements alone do not
qualify a recovery model for that relationship.

Full-picture native-code lookup counts include borders and rejected tiles. The
lookup helper is explicitly restricted to the current Y-referred chroma curves;
it is not an implementation of arbitrary chroma multipliers. Its horizontal
upper-row average differs from the 2x2 luma average used in joint fitting.

Calls process at most 512 requested tiles. GPU reduction accumulates fixed
component/check-fold/brightness groups, so a future caller can reuse under
9 MiB of tile scratch and transfer about 1.38 MiB of group moments per decision
instead of every block matrix. History allocation is separate and proportional
to input dimensions. The caller must supply unique tile coordinates and keep
each accumulated decision's source, base, retention and stream consistent.

## Independent verification

The separate NumPy oracle reads the native planes, performs its own detrending,
selection, retained-base rounding and matrix products, and compares them to the
CUDA output. Sixteen synthetic cases cover all four layouts, colour coupling
of both signs, six retention fractions, quiet/structured/persistent regions,
level changes, missing history, invalid coordinates, invalid native codes and
high contrast. Every requested tile is checked, including rejected ones.

Two original development frames (Bridge SDR and Shining PQ) are independently
decoded with their actual preceding pictures. All current source planes and
the archived preceding luma agree exactly. Previous colour comes from the
independent decoding; unused cached UV is never read. Shining is tested in
both native planar 10-bit and P010 layouts.

| Evidence | Result |
| --- | --- |
| Synthetic requests | 432 tiles, 238 accepted joint measurements |
| Real requests, including the alternate Shining layout | 8,880 tiles, 640 accepted joint measurements |
| Per-tile moment arrays checked | 8,780, including both mixed colour orientations |
| Tile decisions, folds, brightness bins and native lookup counts | Exact agreement |
| Worst source-energy-normalized moment error | 1.43e-8, below the predeclared 5e-6 numerical tolerance |
| GPU grouped counts and sums | Match independent CPU aggregation within the same tolerance |
| CPU regression suite | 185 Python tests in 26 suites and 19 C++ checks pass |

The first real comparison exposed an absolute scalar-variance error of
2.4752e-5 on a high-contrast Bridge patch, above the unchanged 2e-5 tolerance.
Scalar variance and temporal covariance now use exact native products and
analytical plane subtraction in double, before the float residual scratch.
A reproducible synthetic negative fails the old calculation at 3.3243e-5 and
passes the correction at 9.10e-13. The failed result remains recorded.

A separate harness correction removes an invalid requirement that one entire
real picture must be rejected. Each exact per-tile rejection comparison remains;
the real pictures contain both accepted and rejected tiles. No source or
quality threshold changed.

Three repeated measurements per real arm take approximately 3.64 ms for the
1920x1080 Bridge picture and 21.71–21.76 ms for the 3840x2160 Shining picture
on the RTX 5060 Ti. This includes all-plane history copying, collection,
reduction and full-picture histograms. It excludes allocation, upload, result
download, CPU fitting and encoding. These are collector costs, not encoder
throughput or the cost of searching all retention candidates.

## Next integration work

Connect the module behind an explicit experimental control, including every
early exit, reset, scene change and drain in the actual encoder. Verify that
source/base identities survive real pipeline ordering, that ordinary mode adds
no collection work, and that diagnostics alone leave decoded pictures unchanged.
Then R3 can consume the grouped evidence for candidate selection, representable
whole-picture curves and actual model integration. Cr recovery, compatible
coupled colour, temporal output, compressed detail and full-title cost remain
unqualified.

The evidence root is the existing local `colour-recovery-20260922/` ledger.
Read `roadmap-r1-r2-20260922/`:

- `r1-completion.json`, `corpus-report.json`: source and reserved-corpus proofs.
- `gpu-snapshot-v5.json`: exact compiled collector/harness sources.
- `synthetic-v5-comparison.json`, `real-v5-comparison.json`: CPU/GPU comparisons.
- `precision-negative.json`, `real-v3-comparison-failure.json`: precision fix and negative.
- `real-preparation.json`: independent source/previous-picture decoding.
- `cpu.json` and `*-pause.json`: regressions and released study pauses.

All GPU studies were finite and manually started. Tdarr's owned study pauses
were released after each run, preserving the separate playback watchdog.
