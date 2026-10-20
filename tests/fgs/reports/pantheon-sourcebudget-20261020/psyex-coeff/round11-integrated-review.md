# R11 integrated-report review

## Disposition

Accepted. I found no material numerical, attribution, provenance, or reproduction
error in the integrated R11 report.

Reviewed artifacts and SHA-256:

- `PSYEX_COEFFICIENTS.md`: `33490ae659f94bcf2cb6e562f5ef4fd9b3d3772f9f255b0e0f51bd7e6db6354e`
- `psyex-coeff-result.json`: `14d6aa117f7f54a157bd96ae56704a822e90e75ce1044167462ab0c8a4e15b8a`
- `HYPOTHESES.md`: `cc56ae8d24a355b63812297901bdbd8ec2d8a028c336bfa5c8c2ce75ca3362b4`
- `LEDGER.md`: `48cffb6519e8bdc802e1dea3be8929db8d1116f3caec5273dbca66d1531e7113`
- `psyex-coeff/README.md`: `a796af65d17ab8c860d9a188f976df4fd9ef60787ae2a96a04ec32a4fb54e476`

## Evidence checks

The headline population and branch claims reproduce the compact and detailed
evidence: 2,907 committed tokens, 2,187 actual scalar-FP calls, 2,151 positive
units, optimizer invocation on all 2,151 positives, six optimizer changes
(shirt 0, background 1, face 5), and no noise/final changes. The fixed-ROI
population split also agrees: shirt 18,368/384/1,248, background
42,680/64/2,256, and face 152,640/4,864/82,496 pixels for positive/zero/no
quantizer.

The reported HF, correlation, ACF, MSE context, qindex ranges, effective QM
levels, representative unit 6203, and all-336 byte identity agree with the
admitted result. In particular, the report correctly treats the decisive
raw-to-scalar change as a local fixed-predictor/partition/transform finding on
exercised frame-120 support. It does not turn coefficient counts into bits, the
single frame into a five-frame gate, still inspection into playback, or the
diagnostic into a repair.

The storage-order correction is described accurately: SVT native arrays remain
in their native order, while the exact adjusted-domain transpose is used only
for the independent libaom join. The 21 one-dimensional transforms' effective
flat-QM treatment is also retained. The reproduction commands select the final
validator and analyzer; failed/rejected revisions remain explicitly noncanonical.

The hypotheses and ledger preserve the two important residual uncertainties:
upstream shirt loss and the no-final-quantizer population. Their next-step
wording does not imply that a scalar-only counterfactual has encoder feedback,
packet cost, or source-rate feasibility.

## Scope note

“Decisive coefficient-stage loss” is supported only with the qualifiers already
present in the report: this R8 policy, E05 frame 120, the three fixed ROIs, and
the actually exercised local TUs. The report consistently carries those
qualifiers, so no wording correction is required.

Inspection commands were read-only (`sha256sum`, `rg`, `cat`, and JSON field
inspection); no metric or encode was rerun.
