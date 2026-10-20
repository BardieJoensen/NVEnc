# R7: finer quantization was delivered, but preservation still fails

The qmax8 arm fails both the unchanged texture screen and the original-rate
ceiling. It is a useful negative diagnostic, not a repair candidate. This closes
the ambiguity left by requested allocation that rate control counteracted:
**actual exercised quantizers are substantially lower**, and their real bit cost
is measured. It does not establish an AV1 limit or reject every finer precision.

## Intervention and admission

[The contract](AOM_QMAX_CONTRACT.md) preserves R3's PSNR, variance AQ, objective
delta-Q, predictor/search settings, lookahead, original input and request11671.
The only effective public change is qmax8; explicit qmin0 preserves the previous
minimum. Fresh first-pass statistics exactly match R3. The installed stream and
private same-binary off/trace replays are byte-identical (IVF SHA256
`16aa2b72b4ef0f66b4bc172dd44f7505f682957434677a38db439e8ff9e292f2`).
All336 frames/all planes agree across dav1d, libaom and NVDEC. All240 scored
planes agree with that validated decode, with original alignment/color checks.

Fresh parsing finds363 coded headers, all base qindices16–32. Target input216
(scored120) has base32 and delta-Q present/resolution2. Locations were derived
from the new stream, even though the target event numbers happen to match R3.
Final generation236 has20381 records; every visible pixel is covered once.
Original source, source-minus-predictor residual, final inverse/pre-loop,
post-loop decoded display and packed OBU identities all pass.

| Measured target property | R3 | R7 qmax8 |
|---|---:|---:|
| Shirt exercised-pixel mean qindex |65|32|
| Background exercised-pixel mean qindex |72.6489|35.5537|
| Shirt exercised ROI fraction |46.88%|67.84%|
| Background exercised ROI fraction |72.10%|92.98%|
| Shirt exercised transform support |includes64×64|8×8 and16×16|

All exercised target pixels are at or below48, so both predeclared delivery gates
pass. Background has37172 pixels at qindex36: qmax is a base bound, not a TU cap.
Skip transitions are substantial in both directions. These are changed coding
decisions, so R3→R7 is an end-to-end policy contrast, not isolated quantization.
The remaining6432 shirt pixels and3160 background pixels were not quantized;
they must not be counted as finer-quantization delivery.

[Compact delivery/cost evidence](aom-qmax-delivery.json) links the full receipts,
raw trace, maps and coefficient records. The scratch root is
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`.

## Actual cost and full-window outcome

Scored video payload is **38.8692416Mbps**, **4.01686×** the original9.6765224Mbps
(and4.03246×R3). Full336-frame video payload is41.2324034Mbps. Both installed
passes took441.295s for336frames:15.739s first pass and425.556s second pass.
The observed total is1.12675×R3's391.652s; host load was not held fixed, so this is
not a controlled speed ranking or full-episode throughput estimate.

The required `campaign.py` GPU paths and the frozen12870-tile/15-frame controls
were run. The primary table is the prescribed **five-frame mean** at scored
116,118,120,122,124, not the single-frame trace:

| ROI | Source HF amplitude | R3 HF | R7 HF | R7 relative HF error | R7 ACF1 error | Screen |
|---|---:|---:|---:|---:|---:|---|
| Shirt |.619353|.098604|.322131|−47.989%|.141765|Fail both|
| Background |1.778495|.909357|1.581589|−11.071%|.037634|Fail amplitude|

Background misses the10% amplitude bound by1.071 percentage points; it is not
rounded into a pass. Shirt spatial-structure error worsens from.113094 despite
higher amplitude/correlation. No source-budget redistribution is justified yet,
because the prerequisite preservation was not demonstrated.

Broad scores improve: VMAF/NEG94.00/92.50→98.36/97.45; SSIMULACRA2 mean/p5
54.81/26.85→84.28/82.07; Butteraugli max-p957.76→3.03. CAMBI full-reference
mean/max.381026/2.309536→.000391/.035044. All-tile MSE mean/p95 falls
6.46340/21.44884→1.22325/1.95459. Face edge-gradient error falls4.01288→1.54402.
These improvements at four times the rate cannot override failed texture gates.

Regressions remain:232/12870 tiles have worse HF error; quiet tiles include9/51
with worse HF error and1/51 with worse MSE. One quiet tile has positive excess
HF; its maximum grows.018011→.027670. Quiet mean errors improve but this is not
proof of source-clean protection. Full240-frame HF/ACF/correlation, fixed-location
temporal curves, brightness/color samples and edge errors are retained in the evidence. The
shirt five-frame temporal-correlation error also grows.007282→.015283; fixed
coordinates are not motion compensated and do not establish playback quality.

[Direct R3/R7 machine comparison](aom-qmax-result.json) binds these measurements.
No player/display observation occurred. Numerical and rate failures already
reject this arm; a playback request would not resolve those failures.

## What the coefficient evidence establishes

On single scored frame120, source/raw/initial/final/post-loop shirt HF is
.606320/.518354/.469236/.252078/.252078. Background is
1.676388/1.665372/1.729041/1.416684/1.420784. Initial and raw are local
fixed-predictor mosaics, not coherent legal counterfactual frames. Neither
mosaic has a measured coded rate.

A further analysis of **existing** trace flags avoids an unnecessary new encode.
Inter blocks invoke dropout only when optimization is disabled; flags7 therefore
identify optimizer invocation without dropout. Intra blocks can invoke both
(flags15). The optimizer-only shirt stratum covers9872 pixels, with7204 valid
same-TU3×3 HF samples. Source/raw/initial/final HF is
.622109/.622191/.543688/.214458. Initial→final changes8524 pixels. Background's
19864 optimizer-only pixels similarly change HF1.642088→1.320847, with17421
changed pixels. This directly attributes that stage difference to the optimizer
path, within the final observed decisions. It does not compare randomized groups
or estimate the outcome of a real bypass with changed feedback.

The mixed path covers3696 shirt and21976 background pixels. Its optimizer/dropout
shares remain unresolved, but another snapshot is unnecessary unless that split
would change the next experiment. Skips and initial quantization also remain
material. No single stage is asserted to explain every region or E04.

Parent inspected the native spatial-grid shirt/background/face panels in
`parent/qmax-observation/plots-trace-1/`; their fixed16–235 luma mapping and clipped
out-of-range values are explicit. These are stills, not motion playback.

## Review and next decision

Independent review accepts delivery, binding, arithmetic and the negative result
(`reviewer/round7-outcome-review.md`, SHA256
`f2a926f4dd58faa2e327836fdfb0261b21346a461dbc01a21121a05cd5c880ae`).
Rejected decoder drafts never ran. Parent corrected wrong FFmpeg option placement,
missing identity assertions and a malformed framemd5 parser; the final rewrite
was independently reviewed and admitted. A binder symlink-path mismatch failed
closed and was corrected while retaining exact file hash/size checks.

Next uncertainty is whether a different texture-sensitive coding decision policy
can avoid the measured optimizer/skip losses within the original budget. A
bounded source/policy inventory is underway before choosing another arm. Do not
repeat global qmax or add a mixed-stage snapshot without a discriminating reason.
No production change, repair candidate or external blocker is established.
