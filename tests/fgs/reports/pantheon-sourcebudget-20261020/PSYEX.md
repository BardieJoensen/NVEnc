# Fixed PSYEX policy at the original packet budget

The fixed PSYEX policy is a **valid matched-rate negative**. Both texture
screens fail, and edge, face and quiet-region errors regress against R3.
No candidate qualifies. No playback was observed.

| Measure | Original / R3 | PSYEX |
|---|---:|---:|
| Scored video rate | 9.67652 / 9.63909 Mbps | 9.62790 Mbps |
| Two-pass time, 336 frames | R3: 391.652 s | 370.336 s |
| Shirt HF amplitude | Source: 0.61935 | 0.10515 (−83.02%) |
| Shirt ACF1 absolute error | R3: 0.11309 | 0.08587 |
| Background HF amplitude | Source: 1.77849 | 1.03007 (−42.08%) |
| Background ACF1 absolute error | R3: 0.10617 | 0.11624 |
| Face MSE / edge-gradient MAE | R3: 5.874 / 4.013 | 8.562 / 5.061 |
| Quiet MSE / ACF error | R3: 0.230 / 0.145 | 0.354 / 0.216 |

The unchanged texture screen requires HF amplitude within ±10% and ACF1 error
at most 0.05; both regions fail both requirements. The full 12,870 frozen tiles
show mixed effects: mean MSE improves from 6.463 to 5.617, but mean ACF error
worsens from 0.1689 to 0.2126. Edge MSE worsens from 6.441 to 9.285.
Quiet MSE worsens in 47/51 tiles and ACF error in 34/50 evaluable tiles.
These are correlated descriptive populations, not significance tests.

VMAF/NEG decline from 94.0/92.5 to 92.6/90.9, SSIMULACRA2 mean from 54.81 to
53.74, and Butteraugli maximum p95 worsens from 7.76 to 8.56. Conversely,
SSIMULACRA2 p5 improves from 26.85 to 38.59 and full-reference CAMBI mean from
0.3810 to 0.1415. Full-window fixed-coordinate temporal correlation errors also
improve. They are not motion-compensated measurements or playback evidence.
Quiet signed-HF p95 stays negative and only one tile has excess amplitude;
the evidence does not support a claim of widespread new quiet-region noise.

[Machine comparison](psyex-result.json) retains all ten frozen control groups,
paired regressions, tails, temporal statistics and provenance.
[Independent outcome review](psyex-observation/round8-outcome-review.md) agrees
with this scoped rejection. Parent inspected the native shirt/face stills and
full-window temporal plot: the shirt is visibly smoothed in the still, while
face texture and line detail change. This was still inspection only.

Native synchronized 10-bit shirt/background/face clips and stills are under
`parent/visuals/e05-1440/psyex-psyex-1x1` in the scratch root. All 240 frames of
each crop are sample-exact to the scored source/candidate planes. The temporal
plot is `parent/psyex-observation/quality-summary-1.png`. These artifacts are
diagnostics of a rejected arm, not a playback-qualified repair.

The frozen [Round8 policy](ROUND8_POLICY_CONTRACT.md) requested10313kbps after
one rate-only calibration. Actual scored-window video packets are9.6279048Mbps,
99.49757% of the original9.6765224Mbps and99.88398% of R3's9.639088Mbps.
The full336-frame stream averages10.25718343Mbps; the240-frame scored window
is the defined comparison, not the full14s input. Both passes took370.33577s
for336frames. This is observed execution cost, not a controlled speed ranking
or a full-episode prediction.

The original legal encode receipt is
`worker/psyex-r8/runs/e05-1440/psyex-1x1/command.json` beneath the scratch root
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`.
Its SHA256 is
`ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`.
IVF SHA256:
`26f51de25b0d1374cfb5bd274d04af13495c94caa4b28b9c4ddd97a5727baeca`.
Application reconstruction SHA256:
`162c2eb85dc9d036912aa5c3a20e613d4ce0fe2ecbc0505ea96bd6d0288d7099`.

[Decoder admission](psyex-decoder-result.json) verifies application
reconstruction, dav1d, libaom and NVDEC agree on every Y/U/V sample of all336
frames. Frame cadence, timestamps, dimensions, limited BT709 and10-bit format
also pass. This validates samples, not preservation quality.
[Independent review](psyex-decoder-review.md) required binding the actual
resource-wrapper executables; the corrected validator was accepted and run.

Reproduce the admitted decoder check in a fresh run directory with
`validate_psyex_decoders.py psyex-1x1 ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`.
The script intentionally refuses to overwrite its existing validation directory.
Do not rerun this unchanged check merely to recover its result.

The [runtime observation](psyex-runtime-result.json) is also admitted. Both
disabled and enabled hooks reproduce the unmodified full336-frame IVF and
application reconstruction exactly. All336 pictures reach observed candidate
selection. At input216/scored120,149806 luma optimizer entries reach the sharp
guard and actual zero rate weight;5776 full spatial prediction/reconstruction
terms are nonzero. Spatial residual-zero comparisons number17709 and spatial
skip-mode comparisons849. There are20666 spatial and51804 high-bit-depth
candidate-selection events. These are repeated search events, not final blocks,
pixels or coded bits.

The observed fast-term sites were never called; the transform-search and full
spatial sites provide the required nonzero-term evidence. Final partition
survival remains unobserved. Static CDEF/restoration values remain automatic
sentinels. This establishes delivery of the fixed bundle in search, not a
component-specific causal effect or successful preservation. The observation
replays took311.495s/314.530s for pass2 only; practical runtime remains the
unmodified370.336s across both passes.

[Patch, build and reproduction](psyex-observation/README.md) retain the accepted
implementation and independent review, including rejected drafts and their
corrections. No production binary was replaced.

The result rejects this fixed bundled policy at this measured rate. It does
not isolate psy, noise normalization, quantization or filtering, and does not
establish an AV1 limit. The next experiment observes final selected blocks and
the pre-loop/post-loop reconstruction boundary in this exact stream. That
distinguishes loss already present in final coding decisions from later
filtering, while avoiding another undirected settings sweep.
