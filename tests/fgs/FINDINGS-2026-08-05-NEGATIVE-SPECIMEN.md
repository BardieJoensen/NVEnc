# The constructed negative fails: FGS is safer on recompressed input — 2026-08-05

> Offline measurement only. No `NVEncCore/` change, nothing deployed,
> `modelsrc` default-off, Tdarr untouched.

Executes the protocol frozen in `PLAN-2026-08-05-NEGATIVE-SPECIMEN.md` (commit
`c37f9f03`), written before any number below was measured.

## Result

**Frozen pass condition 1 fails. Condition 3 therefore applies: the
architecture is safer on recompressed input than feared, and the experiment
stops here rather than iterating.**

| clause | met |
| --- | ---: |
| A — synthesis closer to `C`'s codec-noise axis than to `O`'s grain axis | 4/8 |
| B-texture — `C_fgs` played total no closer to `O` than `C_plain` | 1/8 |
| B-amplitude — same, on amplitude | 0/8 |
| **valid negative (A and both halves of B)** | **0/8** |

Condition 1 required a majority on A *and* clause B. A is exactly half, and B
fails almost everywhere.

## The specimens

`O` recompressed by the production binary at the frozen qvbr 44 and 50, then
plain- and FGS-encoded at qvbr 29. All amplitudes are relative to `O`'s
adjacent-frame grain truth, all layers measured on one `O`-derived mask.

| specimen | synth→`O` | synth→`C` | synthesis matches | `C` retained | `C_plain` | `C_fgs` |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Taxi Driver q44 | 0.1389 | **0.0749** | codec noise | 0.234 | 0.219 | 0.366 |
| Taxi Driver q50 | 0.1605 | **0.0597** | codec noise | 0.123 | 0.115 | 0.288 |
| The Shining q44 | **0.1507** | 0.2274 | source grain | 0.259 | 0.252 | 0.402 |
| The Shining q50 | **0.1754** | 0.1824 | source grain | 0.258 | 0.249 | 0.533 |
| Tuner q44 | **0.0822** | 0.3900 | source grain | 0.508 | 0.500 | 0.755 |
| Tuner q50 | **0.0763** | 0.4312 | source grain | 0.523 | 0.507 | 0.741 |
| Train to Busan q44 | 0.2846 | **0.2504** | codec noise | 0.376 | 0.362 | 0.680 |
| Train to Busan q50 | 0.3265 | **0.2066** | codec noise | 0.369 | 0.356 | 0.491 |

## What the failure actually shows

**On every specimen, the FGS arm lands closer to the pre-compression original
than a plain re-encode does** — amplitude on 8/8, texture on 7/8. The gap it
closes is large:

| specimen | amplitude gap to `O`: plain → FGS |
| --- | --- |
| Taxi Driver q44 | 0.781 → 0.634 |
| Taxi Driver q50 | 0.885 → 0.712 |
| The Shining q44 | 0.748 → 0.598 |
| The Shining q50 | 0.751 → 0.467 |
| Tuner q44 | 0.500 → 0.245 |
| Tuner q50 | 0.493 → 0.259 |
| Train to Busan q44 | 0.638 → 0.320 |
| Train to Busan q50 | 0.644 → 0.509 |

This is a directly useful production result and it had not been measured. The
library is already AV1, so re-encoding it is exactly this case. On that
material FGS recovers texture energy the plain path leaves permanently lost,
and it does so even when the input's noise is substantially codec artifact.

## The mechanism the specimen did establish

Clause A holds on Taxi Driver and Train to Busan, and on Taxi the margin widens
with harshness: synthesis sits `0.075` from the codec-noise axis against
`0.139` from real grain at qvbr 44, and `0.060` against `0.161` at qvbr 50 —
2.7x closer to the artifact. So the analyser *can* be made to fit codec
structure, and harsher recompression pushes it further that way. What does not
follow is harm: on those same two titles the played result is still closer to
the original than plain.

Tuner is the opposite and the more surprising case. Its `C` noise is strongly
artifact-shaped (lag-1 `0.85`, lag-2 `0.75`) against an original grain of
`0.43`/`0.14`, yet synthesis lands at `0.076`--`0.082` from the *original's*
texture and `0.39`--`0.43` from the artifact. The candidate reconstructed the
pre-compression grain character from a source that no longer contained it.

One untested hypothesis for why: the guarded covariance response subtracts the
encoded base's covariance from the AR fit, and codec artifact lives largely in
that base, so the closure may discount it structurally. That would be an
accidental safety property rather than a designed one. It is not uniform —
Taxi and Train to Busan still track the artifact — so it is a hypothesis for a
separate pre-registered test, not a claim.

## Rates are not tuned further

Clause A's margin grows with harshness, so a rate beyond qvbr 50 would likely
manufacture a valid negative. The pre-registration's discard criteria forbid
exactly that: rates were frozen at 44 and 50 after a probe, and moving them
after seeing the result is the fixture-threshold mistake this project has
already named twice. Any further attempt must freeze new rates in advance.

## Discriminator evaluation is moot

Frozen condition 2 makes a discriminator a candidate only if it separates
**valid negatives** from all positives. There are none, so the shadow axes,
block-count CV and the stochastic descriptors were not evaluated. Running them
against specimens that are not established negatives would produce a
separation with nothing behind it.

## A second, separate concern this surfaced

Re-encoding already-compressed input grows it substantially at qvbr 29:

| specimen | `C` | `C_fgs` | growth |
| --- | ---: | ---: | ---: |
| Taxi Driver q44 | 4,175,733 | 6,885,368 | +64.9% |
| Tuner q50 | 601,188 | 1,737,678 | +189.0% |
| Train to Busan q50 | 745,520 | 2,184,635 | +193.0% |

Both FGS and plain arms grow; this is a rate-selection and routing question,
not a grain-model one, and it reproduces the 2026-07 campaign's finding that
re-encoding already-small files enlarges them. It is orthogonal to admission
and should be handled by a source-bitrate skip rule, which the flow does not
currently have.

## Integrity

- 24 generated streams, all passing complete `libdav1d -xerror` decoding;
- frame counts equal across arms within every specimen (288 each);
- the runner aborts if the encoder logs `ignoring`, so the guarded response arm
  is confirmed active on every FGS encode — verified in the logs as "fitting
  the test-only source model from temporally static blocks" plus "applying
  test-only response-selected temporal luma covariance closure";
- delivered synthesis amplitude used throughout, never the emitted table's mean
  scaling point;
- 14 harness unit tests pass.

The secondary `--source C` divergence pass was unavailable on 6 of 8 specimens:
at these rates `C` has too few static flat blocks on a frozen frame (as few as
5). It is the divergence column, not the decisive test, so the runner records
the reason and continues. That scarcity is itself a coverage signal about
heavily recompressed material.

## Standing conclusion

The question shadow admission left open — is there a known harmful admission —
remains open, and this attempt did not close it. What it adds is a bound in the
other direction: on recompressed input at two harsh rates across four titles,
the source-fit candidate does not degrade the result relative to plain
re-encoding, and usually improves it materially.

`modelsrc` stays default-off. Nothing here is a routing recommendation.
