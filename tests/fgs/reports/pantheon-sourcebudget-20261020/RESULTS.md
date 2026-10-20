# Round1: slower SVT at the original-rate ceiling

The preset0/tune0 arm fails both established texture amplitude gates. Its actual
scored video rate is **9.5227592Mbps**,98.4110% of the9.6765224Mbps original.
This is a valid under-cap practical screen, not a matched preset comparison.
No perceptually qualified repair has been demonstrated.

| Five-frame midpoint average | Source HF | Preset4 HF | Preset0 HF | Preset0 HF error | ACF1 error |
|---|---:|---:|---:|---:|---:|
| E05 shirt |0.619353|0.071789|0.157202|−74.618%|0.001026|
| E05 background |1.778495|0.624360|0.923415|−48.079%|0.044833|

Both ACF1 errors satisfy the0.05 tolerance; both amplitudes fail the±10%
tolerance. Source HF correlations rise from0.03355 to0.20070 for shirt and
0.27374 to0.49937 for background. Amplitude, structure and source correlation
remain distinct observations. Independent review found only7/240 shirt and
6/240 background frames within the HF tolerance; changing content in the fixed
ROIs makes these traces corroboration, not a replacement confirmatory gate.

Descriptive full-reference gains against the preserved preset4 baseline include
VMAF93.57→94.16, NEG92.03→92.67, VMAF p1 excluding frame0
79.9185→80.5200, SSIMULACRA2 mean52.87→55.13 and p5
26.23→29.88, and Butteraugli p95 maximum8.84→7.32. CAMBI full-reference
mean falls0.429431→0.409151 and maximum2.739248→2.356200.
These pooled gains do not compensate for the failed texture gate.

The frozen12,870-tile controls retain source descriptors exactly. Outside the
historical target mask, mean MSE falls9.32905→8.31422 and p95
30.99966→27.74936. Face MSE falls6.83988→4.75492; edge-gradient MAE
falls4.06676→3.19685. Regressions remain: the51 quiet tiles' mean absolute
HF error rises0.08861→0.09925, with38/51 worse, and quiet MSE p95 rises
1.15775→1.20908. Outside-mask edge HF error rises0.72633→0.72853.
The largest positive quiet HF excess is0.010206. All raw tiles and traces are
preserved, including results that pooled means hide.

Encoding336 frames took **2740.622s**,39.64× the preserved preset4 wall time
of69.142s. This is an observed short-window runtime on one SVT worker; host
load was not fixed and it is not a whole-episode speed forecast. All336 frames
and planes match between application reconstruction, dav1d and NVDEC; all240
scored frames match the corresponding full reconstruction. Full input bytes
match the historical fixture. Exact commands, versions and hashes are linked
from [the machine result](preset0-result.json) and [reproduction](REPRODUCE.md).

Native10-bit shirt/background/face comparison clips and stills are in
`parent/visuals/e05-1440/preset0-1x0/` under the experiment root; all240 panel
samples were checked. Parent inspected shirt/background stills. **No motion
playback was observed.** No candidate is advanced to human playback because
it already fails the numerical texture screen.

The result rejects this actual under-cap arm. It does not isolate preset
causality at matched rate or prove that additional allowed bits could not
matter. The next experiment tests one independent libaom policy under the
same source cap. That choice addresses implementation policy more directly
than another45.7-minute run intended only to calibrate the preset contrast.
The matched preset effect remains unresolved. [Independent review](REVIEW.md)
accepted that scope and retained quiet/edge regressions. No codec-limit or
production-change claim follows.

# Round2: independent libaom policy at matched source rate

The calibrated two-pass libaom3.8.2 SSIM/variance-AQ arm also fails. Actual scored
rate is **9.6243504Mbps**,99.4608% of source and99.4628% of the preserved SVT-B
baseline. Total two-pass runtime is **389.179s/336frames**,5.63× the observed
SVT-B wall time with different declared worker settings. The first request
undershot at8.319776Mbps; only TBR changed10003→11576 for calibration. Pass1
statistics were byte-identical across requests and unchanged through pass2.

| Five-frame midpoint average | Source HF | Libaom HF | HF error | ACF1 error | Source HF correlation |
|---|---:|---:|---:|---:|---:|
| Shirt |0.619353|0.09680|−84.37%|0.10866|0.08676|
| Background |1.778495|0.87477|−50.81%|0.12137|0.48419|

Both amplitude and ACF fail the unchanged gates. Source-linked texture retention
improves over SVT-B, but not enough to qualify. All336 decoded frames/planes match
between libaom, dav1d and NVDEC; all240 scored positions match. The raw file is a
dav1d decode, not an encoder reconstruction export. Exact source/hash/color/rate
checks pass. [Machine result](aom-result.json) retains complete provenance.

Broad controls improve: all-tile mean MSE9.314→6.978, HF absolute error
0.915→0.714, ACF error0.252→0.174 and MSE p9531.13→24.52. CAMBI
full-reference mean/max fall0.429/2.739→0.311/2.110. SSIMULACRA2 mean rises
52.87→55.11 and Butteraugli p95 falls8.84→8.30. These are not uniform gains:
23.3% of tiles worsen in MSE and37.7% in HF error.

The face regresses: MSE6.840→8.523 (+24.6%), edge-gradient MAE4.067→5.110
(+25.7%) and gradient ratio0.8849→0.8578. VMAF93.57→92.56 and NEG
92.03→90.92 worsen, while VMAF p1 improves79.92→81.40. SSIMULACRA2 p5
slips26.23→25.79. Quiet HF error rises slightly0.08861→0.08996, despite
strong quiet MSE improvement. Shirt temporal HF correlation0.0936 is closer to
source0.1186 than SVT-B0.2448; background0.00843 is slightly farther from source
0.01711 than SVT-B0.01537. Fixed-coordinate temporal correlation is descriptive.

Independent review accepts this failed matched-rate arm and all identity gates,
retains the regressions, and rejects global-superiority or codec-limit claims.
Parent inspected native shirt/face stills; all240 visual panels pass exact10-bit
checks. No motion playback was observed. The next discriminator will change only
libaom's public tune policy SSIM→PSNR plus necessary TBR calibration, retaining
all other settings and gates. This tests whole-encoder objective policy; it does
not hold mode/allocation/quantization decisions fixed.


# Round3: remove the extra SSIM variance weighting

The PSNR-tuned arm fails both texture screens at **9.639088 Mbps**, 99.613% of
source and 0.153% above the matched SSIM arm. Two-pass runtime is **391.652 s
for 336 frames**, versus 389.179 s for SSIM. Both policies use the same in-block
distortion metric; PSNR omits the additional normalized source-variance RDMULT
weighting. Predictor, mode, partition, transform and later coding decisions can
change. This is a rate-calibrated policy contrast, not a fixed-decision ablation.

| Five-frame midpoint average | Source HF | SSIM HF | PSNR HF | PSNR HF error | PSNR ACF1 error |
|---|---:|---:|---:|---:|---:|
| Shirt | 0.619353 | 0.096799 | 0.098604 | −84.080% | 0.113094 |
| Background | 1.778495 | 0.874773 | 0.909357 | −48.869% | 0.106166 |

Source HF correlations are 0.08904 and 0.50089. Shirt ACF error worsens from
0.108665; background improves from 0.121372. Both remain outside the 0.05 gate.
The small amplitude changes do not explain or repair the severe deficit.
The full 240-frame traces corroborate similar suppression through the affected
shot. Parent inspected the native shirt still and complete trace plot; no motion
playback was observed.

Removing the weighting improves face MSE 8.523→5.874, gradient MAE 5.110→4.013
and gradient ratio 0.8578→0.8939. Edge-tile MSE falls 8.556→6.441. All-tile
mean MSE improves 6.978→6.463, but 7,020/12,870 tiles worsen; improvements are
uneven. Frozen flat-texture tiles worsen in mean MSE 3.217→3.366 and HF error
0.6291→0.6590. Quiet mean MSE rises 0.2187→0.2299, HF error 0.08996→0.09038
and MSE p95 0.3911→0.4046. Maximum positive quiet HF excess rises slightly
0.01750→0.01801, with one positive tile in each arm.

VMAF/NEG improve 92.56/90.92→94.00/92.50; VMAF p1 improves 81.396→82.231,
SSIMULACRA2 p5 25.79→26.85 and Butteraugli p95 8.30→7.76. SSIMULACRA2 mean
falls 55.11→54.81, SSIM 0.9906→0.9903 and CAMBI full-reference mean/max worsen
0.3113/2.1098→0.3810/2.3095. These mixed changes reject any uniform-superiority
claim. Fixed-coordinate temporal correlation remains descriptive, not a motion-
compensated or playback assessment.

All 336 frames and planes agree across native libaom, dav1d and NVDEC; all 240
scored frames agree with positions 96:336. Source bytes, color, binary/library,
commands, first-pass statistics and frozen control definitions are bound by
hashes. First-pass statistics and keyframe positions match between tune arms.
The initial PSNR requests produced 9.504154 and 9.700590 Mbps; neither was
quality-scored. The final request was selected solely by packet-rate calibration.
Native shirt/background/face clips have exact checks on all 240 panel frames.

[Machine result](aom-psnr-result.json) and [direct paired evidence](aom-tune-comparison.json)
retain the complete metrics and provenance. This result rejects the proposed
SSIM-weighting removal as a repair under the tested controls. It does not exclude
an interaction with other settings or establish a codec limit.


# Rounds4–5: coding-source boundary and pixel neutralization

The [byte-neutral trace](AOM_SOURCE_BOUNDARY.md) binds all336 original frames
and363 coded events. The midpoint source is unchanged;32 other events contain
sparse changes no greater than two raw10-bit levels. The complete1344-file
source provenance audit closes an earlier manifest-subset omission.

The [all-original coding-source arm](AOM_SOURCE_NEUTRALIZATION.md) demonstrably
removes every measured pixel difference, with unchanged traced selection and
retained upstream filtering/analysis. At9.6256032Mbps (99.4738%source,
99.8601%parent), both texture screens still fail: shirtHF.097788/.619353source,
ACFerror.074420; backgroundHF.915182/1.778495source, ACFerror.098892. Whole240-frame
traces remain suppressed. Face/quiet averages improve slightly; overallMSE/tails
andCAMBI regress slightly. Independent review accepts a valid failed matched-rate
intervention, not a repair. No playback; original pixel substitution is not an
ablation of retained TF/GF/TPL/pass1 effects or downstream coding decisions.

Enabled/disabled instrumented replay pass2 costs373.697/371.444s. These reuse
installed pass1 statistics and cannot establish end-to-end production runtime.
The existing installed parent cost remains391.652s for both passes/336frames.
[Paired machine evidence](aom-neutralization-result.json) includes all controls,
rawGPU metrics, native validated clips, and temporal provenance.
