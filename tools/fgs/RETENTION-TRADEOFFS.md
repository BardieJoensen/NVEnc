# Preparing the retention quality/space comparison

The running repair has resource priority. These tools parse existing reports
and logs or prepare a job plan; they do not execute encoders, probes, metrics
or production changes. Heavy qualification and hardware profiling come later.

## Diagnose existing logs

```sh
python3 tests/fgs/retention_diagnostics.py \
  --log /path/to/completed/encode.log --frames 1440 --fps 24/1 \
  --output /path/to/new-diagnostics.json
```

The output binds the log hash/identity, verifies ordered unique final frame
decisions and reports missing decisions. Incomplete logs cannot qualify.
Covariance first blockers are exclusive per event; whole-source reasons can
overlap. Legacy omissions stay unknown. These are not visible-damage labels.

Schema 2 adds `source_reason_overlap` and `decision_profiles`. The first
partitions source-preserved frames into exact recorded reason combinations
and an unknown bucket for legacy logs. The second joins each frame's final
model outcome, source mask, covariance blocker/colour subconditions, logged
local mismatch and rejected colour-restoration components. It records counts
and the longest uninterrupted run of each combination for choosing diagnostic
excerpts. Runs stop at changed decisions and missing frame IDs.

Use these joins before choosing an optimization target: a successful covariance
fit may still end in source preservation after another check fails. Marginal
reason counts alone cannot show that overlap. An absent event does not prove a
check passed, and a single recorded reason does not predict that removing it
would recover the frame. A changed model changes subsequent checks and temporal
state. These reports estimate neither byte savings nor visible quality.
Legacy local-mismatch/restoration events can be joined, but they do not supply
the missing source mask or colour subconditions.

Profile frame IDs locate decisions in the original logged run. Convert them to
nominal times only for candidate selection; verify actual frame alignment later.
Short excerpts reset model history. Include context and confirm the target
decision recurs before using an excerpt to diagnose or qualify a change.

Trace version 1 uses these colour codes:

| Code | Meaning |
| --- | --- |
| 0 | Eligible under the existing rule |
| 1–4 | Invalid plane, scaling from luma, unsupported lag, invalid shift |
| 5 | Signalled luma coupling |
| 6 | Insufficient observations |
| 7–9 | Invalid variance, missing residual energy, missing predictor energy |
| 10 | Spatially correlated colour residual |
| 11–12 | Invalid correlation, measured luma coupling |
| 254 | Inactive component, exempt from this check |
| 255 | Check not reached |

`sourceReasons` is a bit mask: 1 no model, 2 feedback rejection, 4 missing
adjacent picture, 8 strength mismatch, 16 local mismatch, 32 rejected colour
restoration, 64 covariance recovery, 128 DC limit, 256 recovery hold, and
512 insufficient flat blocks. A recovered fit may fail a later condition.
Recovery hysteresis alone uses 256. Thresholds are unchanged.

## Prepare operating points

```sh
python3 tests/fgs/retention_tradeoff.py prepare \
  --manifest /path/to/comparison-manifest.json \
  --encode-output-root /path/to/after-repair-encodes \
  --output /path/to/new-comparison-plan.json
```

The manifest has `binaries.production` and `binaries.qualified_auto`, each with
an absolute `path` and `sha256`. Its `cases` extend the production-comparison
manifest with `source_kind` (`original` or `lossless_original_excerpt`),
`content_class`, and optional `role`. Each case pins source path/hash/identity,
frame count, video properties, reader `prefix`, and encode `arguments`.
Put excerpt `--seek` in `prefix`; the planner owns input/output, frame count
and logging flags. Each case needs one explicit QVBR and grain option.

The planner prepares ordinary FGS, auto capped at 0.1 residual blending, and
plain AV1 at current QVBR and one/two steps lower. It adds a same-candidate
ordinary control at current QVBR. These are experimental points, not silent
production changes. Actual sizes may require more points. Nothing is executed.

Before later execution, verify source/binary hashes, use a bounded sequential
scheduler respecting playback, and preserve originals. Existing qualification
tools must check complete decodes, frame alignment and required metadata before
scoring. Keep playback and grain-off diagnostics separate. Record metric/model
versions and HDR display assumptions; examine worst scenes and aggregate
scores. Timing requires controlled repeats and separate pause accounting.

## Compare measured results

```sh
python3 tests/fgs/retention_tradeoff.py compare \
  --results /path/to/measured-points.json \
  --output /path/to/new-size-comparisons.json
```

Results contain `rows`. Each names `case`, unique `arm`, `mode` (`current_fgs`,
`auto`, `plain` or `svt`), the plan's `reference_id`, complete primary-video
`video_bytes`, and `quality_checks_passed`. Current-QVBR auto has `anchor: true`.
Optional `metrics` map names to
`{"value": NUMBER, "definition": "PINNED_MODEL_AND_MEASUREMENT_CONFIGURATION"}`.
Definitions include playback mode, model/revision and display/transfer/sampling
assumptions. Keep timing and playback-review evidence alongside these rows;
the comparator does not adjudicate either.

The closest passing point within 3% of auto's actual bytes is a size match.
Otherwise more points are needed; equal QVBR never implies equal size. Only
identical metric definitions produce score differences. A numerical delta
does not establish visible benefit or approve a storage policy.

See the [preparation findings](../../tests/fgs/FINDINGS-2026-09-10-RETENTION-PREPARATION.md)
for the retained corpus, CPU checks and deferred GPU work.
