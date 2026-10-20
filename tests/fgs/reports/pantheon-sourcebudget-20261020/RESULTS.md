# Round1: slower SVT at the original-rate ceiling

The preset0/tune0 arm fails both established texture amplitude gates. Its actual
scored video rate is **9.5227592Mbps**,98.4110% of the9.6765224Mbps original.
This is a valid under-cap practical screen, not a matched preset comparison.
No perceptually qualified repair has been demonstrated.

| Midpoint ROI | Source HF | Preset4 HF | Preset0 HF | Preset0 HF error | ACF1 error |
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
