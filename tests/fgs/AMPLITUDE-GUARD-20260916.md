# Mandatory amplitude support in ordinary mode

The deployed `ef5c61fe` build could hold a strong model after source noise fell.
Its existing current-picture strength fit, recovery and source fallback were
enabled only by optional automatic retention. The correction applies that same
guard in ordinary mode too. It reuses collected statistics; no extra GPU pass
or automatic retention is enabled.

The initial default-mode reproducer and complete movie trials are recorded at
`/opt/docker-apps/logs/fgs-ripple-repair-20260906/full-temporal-audit-20260912/followup-20260916/`.
The candidate SHA is
`ef4799f6e7110e1057d8f728586d45e382b1ce3aa75c035403da35f05ca4b946`.
Read the canonical ongoing handoff in the fidelity checkout before deployment;
this test document is not production approval.

## Structured-scene regression

`amplitude_regression.py` tests two exact Play Dirty SDR/QVBR30 witnesses:
city at 856.333 seconds and dialogue at 5727.583 seconds, 12 frames each.
These scenes contain picture structure; a perfectly flat source patch is not
required. Source, candidate, known-bad deployed output and independently encoded
ordinary NVENC reference are all SHA-pinned. Each source/output timestamp must
match within 2.1 ms. Grain-on/off decoding is explicit. The reference must have
identical decoded grain-on/off luma.

The first diagnostic used a fixed source-RMS ceiling of four. Both the candidate
and ordinary no-FGS reference exceed it in the city: peaks 4.910 and 4.908.
Their 12-frame mean VMAF values are 88.961 and 88.959, versus 71.631 in the bad
encode. The original failed report is retained under
`city-amplitude-qualification/amplitude-negative-control/`; the independent
control is `city-plain-reference/quality/`. This is ordinary compression loss at
these settings, not a remaining excessive-grain result. Scores from these short
witnesses are not whole-movie scores.

The release regression limits synthesis RMS to three normalized 8-bit luma
levels and compares source error with that independent reference: maximum
per-frame RMS excess 0.15, mean excess 0.05. These tight, scene-specific margins
bound new damage; they are not a universal quality threshold. The original
absolute diagnostic remains in every report. The retained bad encode must
fail synthesis in both witnesses. Genuine-grain retention is separately tested
by the full gate's oracle and mixed-source positive controls.

Prepare a manifest with `source`, `negative`, `candidate`, and `reference`
objects. Each needs `path` and `sha256`; `candidate.encoder_sha256` must identify
the exact tested encoder. All outputs must derive from the identical source,
frame timing and ordinary production settings. The reference removes only
`--av1-film-grain`; it retains QVBR, preset, lookahead and colour settings.
The full-movie history is part of this qualification. The live validated example
is `city-amplitude-qualification/amplitude-manifest-v2.json` in the ledger.

Run the check or include it in the full local gate:

```bash
python3 tests/fgs/amplitude_regression.py --manifest /path/to/manifest.json \
  --candidate-nvencc /path/to/nvencc --output /path/to/new-report
tests/fgs/local_gate.sh --full --candidate-nvencc /path/to/nvencc \
  --amplitude-manifest /path/to/manifest.json
```

`--full` refuses to proceed without this input; quick checks remain unchanged.
The stage verifies externally prepared, pinned candidate media for the selected
binary. It does not silently create or substitute a candidate encode. Keep the
encode command and source/build provenance with the manifest. Media remain
private; the repository contains checks and hashes rather than film payloads.

## Deliberate periodic-regression change

The mandatory guard removes synthesis from 263 pictures in the pinned
3,600-frame Gentlemen regression. It introduces no new grain-on pictures.
An all-frame source comparison reduces mean normalized luma error from 0.994 to
0.924, with maximum frame error increase 0.194; mean chroma errors also improve.
Original jacket and periodic-texture assertions pass. Worst changed stills were
reviewed. The original change alert and every earlier positive/negative are
retained. `gentlemen_amplitude_guard_positive` is a separate reviewed fixture;
a fresh same-binary encode passes all existing numerical limits against it.

Full-movie strict decoding, real HDR10 pairs, ordinary runtime qualification,
release/rollback and library scope are separate requirements. Neither this
fixture decision nor a short-window pass clears an entire library.
