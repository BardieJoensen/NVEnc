# Grain diagnostics and reliability, 2026-09-07

The synthesis policy and production encoder remain e778a88b. This pass adds
grain-header semantic checks, a portable decoded-grain inspector, and complete
decoded-sequence regression comparisons. The existing inexpensive header scan
can check the additional syntax without reconstructing video pixels. The large
decoded comparisons belong in release testing and background audits.

## Kept: decoded analysis optimization

Convert each sampled pixel to display values once for all three channels;
reuse centered patch values and the common autocorrelation normalization sum.
Preserve floating-point evaluation order. Four native packet-copy clips were
measured in old/new/new/old order. CSV bytes matched in every run:

| Clip | Frames | Old seconds | New seconds | Throughput factor |
|---|---:|---:|---:|---:|
| Ford garage | 327 | 4.100 | 3.641 | 1.126 |
| Ford podium | 292 | 3.286 | 3.018 | 1.089 |
| South Park | 360 | 3.208 | 2.811 | 1.141 |
| Adventure Time | 264 | 1.711 | 1.533 | 1.116 |

These are bounded clip measurements, not a promised library-wide completion
time. The compact default CSV is unchanged. Optional signed correlation vectors
support release comparisons without enlarging the normal audit's stored data.

## Rejected: encoder certification cache

An exact-key, 128-entry per-thread cache preserved every policy decision and
produced identical AV1 payloads to e778a88b in four 3,600-frame encodes. However,
instrumenting the real model-fit path found only **1 hit and 7,825 misses**.
The model is refitted before temporal output selection, so repeated emitted
headers do not imply repeated candidate coefficients.

On the shared host, old/new/new/old wall times were 42.36/49.59/48.24/49.09 seconds.
CPU totals did not improve either. Contention prevents attributing the entire
variation to the cache, but there is no useful demonstrated benefit. The cache
was removed. No encoder speedup or shorter repair ETA is claimed from it.

## Header syntax and decoded controls

An old library file failed decoding because one 4:2:0 chroma component had grain
points while the other did not. Both decoders diagnose that rule over the same
35-second interval. The current encoder and table parser already prevent it;
the fast bitstream scanner had only inspected model stability/texture and now
also enforces point ordering and chroma syntax.

The whole-sequence fixture measures all 3,600 displayed frames in luma/red/blue,
including grain on/off scheduling, amplitude, recurrence, and twelve signed
autocorrelations. Source comparisons at the three reproduced failure timestamps
also check raw U/V. Comparing only the winning correlation offset produced
false alarms at near-ties, including on unchanged encoder output. Comparing the
full vector keeps directional coverage without that unstable winner test.

These fixture-specific change detectors do not certify arbitrary films. HDR
display calibration, broader real coarse-grain fixtures, and coverage outside
the nine spatial patches remain separate quality work. A header violation or
large diagnostic score does not authorize downloading or replacing media.
