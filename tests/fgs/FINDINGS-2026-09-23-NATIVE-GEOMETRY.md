# Complete native-frame geometry in retention diagnostics

D61 is complete. Commits `2767f460` and `0a2ee9cc` support complete even native
4:2:0 dimensions through 4096×2160, including uncropped 1920×1080 and 3840×2160.
Ordinary production remains `cb903a17`; retention and FEL remain off.

The diagnostic uses disjoint rectangles with even boundaries and luma spans
of 32–64 pixels. Both spatial halves must contain samples. Every native pixel
contributes to its half's mean; spatial and oriented source/base moments use
actual inner-support sample counts. Aligned 64-pixel geometry is unchanged.
This is measurement geometry, not a revision to R1 population classification,
border eligibility or detail/quiet-region evidence.

Independent direct sums and NumPy vector products agree for 14 size/depth
combinations, including minimal ragged, 1080p, UHD and 4096×2160 layouts.
There are 223,174 checked values at the frozen absolute 1e-9 / relative 1e-10
arithmetic tolerance. Raw accumulated pair sums have larger absolute magnitudes;
the maximum absolute discrepancy is 2.17e-5, within the relative bound.
Independent variance differs by at most 1.60e-12. Coverage/count, unequal support,
padded-plane, invalid layout and training/check separation controls pass.

The final twelve positive GPU cases and one expected older-library rejection
pass independent verification. They include two prior model controls, four
ordinary SDR/HDR controls, complete 1080p/UHD candidate and whole-source captures,
and both complete live model outputs. Earlier aligned models, packet payloads,
clocks and metadata remain identical. There are 672 fresh decoded observations
with exact AOM/dav1d agreement, 859,035,648 exact original and reconstructed
samples per role, and 248,832,000 exact independent synthesis samples.
All 32 models/readiness records/packet outputs match their CPU references.

The complete-raster model positives are constructed controls, not real-media
admission. Their 32 frame guards, 18 full-spatial windows and 192 separate-half
means pass. Original strict per-picture spatial results remain 16/16 at 1080p8
and 15/16 at UHD10; the failed UHD picture is not hidden or reclassified.
Four actual uncropped Shining/Amphibia source-frame measurements independently
agree; the Amphibia input remains explicitly a library derivative.

The initial UHD capture correctly rejected its insufficient 512 MiB combined
disk budget before encoding. Explicit diagnostic output may now use at most
1 GiB, enough for sixteen UHD source/reconstruction pairs. Source-memory and
device limits remain unchanged. The failure and corrected runs are preserved.
Full CPU: 214 Python tests across 30 suites and 46 C++ programs; the later disk
budget change also passes its targeted boundary/negative tests.

Latest diagnostic `build-0a2ee9cc/nvencc`, SHA256
`fffc9f48b87d21cb60d8a000a368168e258e24437abcf528f7f0a79897abf8bc`.
Private native library v7 remains ABI2 with nine isolated exports. Manual
commands, inputs, hashes, timings, decoder evidence, cleanup and pause receipts
are in `roadmap-r3-native-geometry-20260923/` under the evidence root recorded
in [the handoff](WORK-TO-PRODUCTION.md). All owned pauses were released with
current worker limits preserved. No experiment restarts automatically.

Next implement explicit whole-source segments alongside modeled output, so a
fallback cannot inherit grain or fitting state. Bounded automatic source/fraction
evidence and R4–R8 remain open. The reserved corpus remains unopened; this
reference fitter's measured CPU cost is not a production-speed qualification.
