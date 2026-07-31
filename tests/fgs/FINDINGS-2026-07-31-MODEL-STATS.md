# Analyzer model-stats optimization and rejected variants, 2026-07-31

## Result

Two bit-exact changes -- one to `kernel_fgs_model_stats`, one to
`kernel_fgs_flat_metrics` -- reduce all named FGS kernels by 10.1% on real
film. Seven variants were measured in total; two were kept. The five rejected
ones are recorded here in full because every one of them looks obviously
correct on paper and will otherwise be retried.

Nsight Systems, RTX 5060 Ti, 60 frames of Silo S03E05 (1918x802 P010, ffv1
fixture cut seek-free from 00:18:00):

| Stage | Before | After | Change |
| --- | ---: | ---: | ---: |
| model stats, luma (1/frame) | 48.8 us | 34.6 us | -29.1% |
| model stats, chroma (2/frame) | 113.8 us | 81.6 us | -28.3% |
| Flat-region analysis | 44.6 us | 41.4 us | -7.4% |
| Bilateral, luma (2/frame) | 192.0 us | 192.5 us | unchanged |
| Bilateral, chroma (2/frame) | 89.6 us | 89.7 us | unchanged |
| Level compensation | 15.9 us | 13.9 us | unchanged |
| **All named FGS kernels** | **504.6 us** | **453.7 us** | **-10.1%** |

Note that `model_stats` is a much larger share of the profile on real film
(32%) than on the generated fixtures the 2026-07-29 profile used (14%). The
kernel early-outs on `flatMask`, so its cost scales with how many blocks
survive flat selection. Profile analyzer changes on real film.

The change is uncommitted at the time of writing and has not been deployed.

## The measurement that decided every variant

Splitting each kernel into setup and accumulation is what made the rejections
obvious, and it needs no profiling counters. Cap the accumulation loop at one
element per thread (`packed < threads` instead of `packed < triCount`), which
leaves the setup phase intact, then solve `T_full = S + nA`:

| Kernel | full | capped | setup | accumulation |
| --- | ---: | ---: | ---: | ---: |
| model stats, chroma | 41.2 us | 21.6 us | 17.7 us (43%) | 23.5 us (57%) |
| model stats, luma | 34.9 us | 17.0 us | 12.5 us (36%) | 22.4 us (64%) |

The capped build produces wrong statistics and is a timing instrument only.

## What was kept

Three changes, all bit-exact.

**Block-local sums accumulate in int32.** Residuals are differences of two
samples in the same plane, so `|residual| <= 1023` at the deepest supported
bit depth; the chroma luma-predictor is a 2x2 mean of residuals and obeys the
same bound. A product is therefore at most `1023*1023`, and the sum spans
exactly `threads` (64) samples, so the magnitude cannot exceed 66,977,856 --
about 32x inside int32. The global accumulators stay 64-bit because they sum
every block in the frame. A `static_assert` encodes the bound.

**Invalid samples are zeroed instead of branched on.** A zero predictor
contributes exactly zero to every normal-equation product, so hoisting the
`valid[]` test out of the two accumulation loops changes no statistic. The
`tid == 0` accounting loop still needs `valid[]` and keeps it.

SASS for the P010 luma instantiation, before and after:

| | Before | After |
| --- | ---: | ---: |
| Widening/high multiplies | 69 | 39 |
| LDS | 120 | 99 |
| ISETP | 105 | 78 |
| SHF / LOP3 | 53 / 53 | 55 / 53 |

The win is smaller than the instruction counts suggest because the surviving
widening multiplies are 64-bit *pointer* arithmetic for shared and global
addressing plus the `tid == 0` block, neither of which int32 sums can remove.

A second pass staged `kernel_fgs_flat_metrics` through shared memory. Both of
its passes walk the same block and the gradient pass adds four neighbour taps,
about six global loads per pixel; those taps are guarded to stay strictly
inside the block, so the working set is `bw*bh` with no halo. Staging it once
is bit-exact and worth 44.6 -> 41.4 us, **-7.4%**.

That is far less than the -15.6% the same technique gave the bilateral in
`ec413f96`, and the reason is worth keeping: a 32x32 block of 10-bit samples is
2 KB and already resident in L1, so the redundant taps were L1 hits rather than
DRAM traffic. Shared staging only moves them between two on-chip levels. The
bilateral benefits because its 5x5 neighbourhood overlaps across threads *and
across blocks*; flat metrics has four neighbours and a tiny working set.

## Rejected variants

**Closed-form triangular index.** The packed normal-equation index is decoded
by re-walking rows (`for rowLength = coeffCount; j >= rowLength; --rowLength`),
averaging 7.7 iterations per element. Replacing it with the positive root of
`i*(2C+1-i)/2 = packed` plus two boundary corrections was bit-exact and moved
chroma 41.2 -> 40.8 us and luma 34.9 -> 34.7 us: about 1%, inside run noise.
The decode is only ~11% of loop iterations and each iteration is a compare and
a subtract. Not worth a `sqrtf` and two correction loops.

**int16 predictors.** Residuals fit in int16 with 32x headroom, so holding
`predictors[64][coeffCount]` and `values[64]` as int16 halves the shared
footprint (6.4 KB -> 3.2 KB) and halves the shared traffic of the accumulation
loops, which are 57-64% of the kernel. It was bit-exact and **9% slower**:
chroma 41.2 -> 45.0 us, luma 34.9 -> 38.1 us. Shared-memory banks are 4 bytes
wide, so 16-bit elements need sign-extension on load and place two samples in
one bank. That cost more than the smaller footprint saved, which also shows
the kernel is not occupancy-limited at 64 threads and 6.7 KB per block.

**Transposing to `predictors[coeffCount][64]`.** Rejected on analysis, not
measured. In the accumulation each thread holds a fixed `(i, j)` and loops over
`sample`. The current `[sample][i]` layout has `sample` uniform across threads
and `i` varying, so a warp spreads across banks. Transposed, the address is
`i*64 + sample` with `i` varying per thread: stride 64 ints, and `64 mod 32`
is 0, so every thread in the warp hits the same bank -- a 32-way conflict. The
existing layout is already the correct one.

**Decoupling the block size from the sample count.** `threads` was used both as
the observation count (`sample < threads`) and as the work-distribution stride
(`packed += threads`). Only the first must be 64 -- it is the 8x8 stratified
grid. Carrying extra threads in z, gated out of the sampling phase, splits the
normal-equation elements further: at 64 threads each does `ceil(325/64) = 6`
elements, at 128 threads 3, at 256 threads 2.

Bit-exact, and much smaller than expected:

| Block | model stats, chroma | model stats, luma |
| --- | ---: | ---: |
| `dim3(8,8,1)`, 64 threads | 41.2 us | 34.9 us |
| `dim3(8,8,2)`, 128 threads | **39.2 us** | **34.0 us** |
| `dim3(8,8,4)`, 256 threads | 50.8 us | 41.3 us |

Extra threads raise accumulation parallelism but *lower* it for setup, because
shared memory per block is unchanged while blocks per SM falls. At 64 threads
the kernel is shared-limited to about 14 blocks (28 warps); at 256 threads the
warp cap binds first at 6 blocks, so only 12 warps per SM remain to run the
sampling phase, which is 43% of the chroma kernel. z=2 nets -4.2% on the kernel,
about 1.1% of total FGS -- real, but it buys that with a hardware-tuned launch
constant that will not survive a different shared-memory or warp budget. Not
kept. Re-measure before assuming either direction on new hardware.

**`__frcp_rn` for the bilateral range weight.** `1.0f/x` under the default
`-prec-div=true` and `__frcp_rn` are both correctly rounded, so the intrinsic
was expected to be bit-exact and possibly cheaper by skipping the `FCHK` path.
It is bit-exact and exactly as fast (96.3 vs 96.0 us): nvcc already emits the
same sequence. There is no free precision-preserving win here, which is why the
only remaining bilateral lever is the *approximate* reciprocal and its quality
A/B.

**Merging the two chroma launches.** For semi-planar formats U and V are
launched separately (`collect_model_stats_typed`), and both launches recompute
the same sample positions, the same flat-mask read, and the same 2x2 luma
residual predictor. `load_code` indexes `row[x*components + component]`, so U
and V are adjacent `uint16`s: each launch also pulls full cache lines and uses
half of every one, and merging would halve DRAM traffic for the chroma AR
gather.

It is still not worth it. Merging can only touch the setup half, which is
17.7 us of 41.2 us per launch, and the duplicated luma gather is only 8 of the
~58 global loads per thread. The realistic ceiling is ~12 us/frame, about 2.6%
of total FGS. Against that it needs a two-component kernel variant, doubled
shared predictors (6.4 -> 12.8 KB), and a new launch and output path -- and
doubling shared memory halves blocks per SM (14 -> 7 at 64 threads), which can
consume the entire gain.

## Fusing the two bilateral passes is not the next step

The 2026-07-29 "Next measurements" section proposed profiling a fused
bilateral. That should not be pursued, and the reason generalizes: **fusion
trades memory traffic for recomputation, and this kernel has traffic to spare
and no compute to spare.**

SASS for the P010 luma bilateral is 143 FFMA, 68 FADD, 52 FMUL, 33 MUFU.RCP
and 4 FCHK against 25 LDS, 9 LDG, 1 STG and 1 STS -- ten global memory
instructions against ~298 math instructions. Achieved DRAM bandwidth is
6.15 MB / 95.98 us, about 64 GB/s, or 14% of the card's 448 GB/s. The kernel
is bound by the 33 SFU reciprocals from
`1.0f/(1.0f + difference*difference*invRange2)`; `meson.build` passes no
`-use_fast_math` and no `-prec-div=false`, so each is the IEEE-precise
sequence with Newton-Raphson refinement and an FCHK fixup.

Two chained radius-2 stencils give an effective radius of 4, so a fused kernel
must compute pass 0 over its output tile plus a 4-pixel halo:

| Fusion strategy | Redundant pass-0 work | Compute cost | Traffic saved |
| --- | ---: | ---: | ---: |
| Naive, current 32x8 tile | 36x12 / 256 = 1.69x | +65 us | <=13.7 us |
| Large tile 128x32 | 132x36 / 4096 = 1.16x | +15 us | <=13.7 us |
| Y-sliding window, 128x64 | 132x68 / 8192 = 1.10x | +9.6 us | <=13.7 us |

Naive fusion is about 4.7x net negative; the sophisticated variants converge on
break-even, and 13.7 us is the saving only if memory were the bottleneck, which
it is not. The bilateral is also **not separable**: the `[1 4 6 4 1]` spatial
term is, but the range weight depends on the center pixel and couples the axes.

The real lever on the bilateral remains the reciprocal, already measured at
-23.5% of total FGS time in the 2026-07-29 notes and still blocked on a
real-content A/B rather than on engineering.

## Verification

Bit-exact changes permit a much stronger gate than metric comparison: the
encoded elementary stream must be identical. Following the determinism
methodology in `FINDINGS-2026-07-29-PERFORMANCE.md` -- video stream only, no
container hashes, pre-cut seek-free fixtures, no `--seek` --
`ffmpeg -i out.mkv -map 0:v:0 -c copy -f md5 -` matched the pre-change build
in every configuration:

| Configuration | MD5 |
| --- | --- |
| 1080p 10-bit, bilateral | `5568ca01823d21f595ddd69abee4e0ee` |
| 1080p 8-bit, bilateral | `6d4577a73d0532f41d383447e584a02e` |
| 1080p 10-bit, fft3d | `d1072af36d711d5f495d8be0c282e5f8` |
| 4K 10-bit, bilateral | `167b7f78de64bd85cbce257e76207469` |

The 8-bit and 10-bit arms matter separately: they are different template
instantiations of the kernel. The 4K arm exercises a different block count and
occupancy. All 18 GPU known-answer fixtures, the CPU tier and the mutation
meta-check also pass.

A metric-only gate would have accepted the int16 variant, which was 9% slower,
and would not have distinguished it from the kept change.
