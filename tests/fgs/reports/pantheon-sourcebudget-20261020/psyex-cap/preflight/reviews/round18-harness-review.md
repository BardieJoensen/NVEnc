# R18 build and execution harness review

## Scope and identities

Read-only review of:

- `parent/psyex-cap-r18/prepare_build.py` — `0a676f5adaac2b15922a27dc7fdec8b965e992a691b28ece23ba6bb08758898f`
- `parent/psyex-cap-r18/pin_build.py` — `5d907a56dfb364b5c18143a952440c0c347fa865f0ec647b997131dc5798715e`
- `parent/psyex-cap-r18/run.py` — `6d18a5c4434a1768a9de20ea16e0b403bb25a8a007d7b3d42fc804e01978eca9`
- `parent/psyex-cap-r18/README.md` — `7b1014afcf36007eb2518da36bcbedd67a47e9eb28eed36d3ad2f81868be31c9`
- `parent/psyex-cap-r18/runner-data-preflight.json` — `8d14f4dcf5f28cfc1fc9b23da02c3653f1c34a2869921487eda1964b53da192d`

No build, encoder, native observer, metric, GPU, Git, or production action was run. The worker's moving source and observer implementation were excluded.

## Disposition

**Not released for build/encode in this revision.** The execution structure is substantially right, but the completed-build provenance and prerequisite-receipt admission need exact producer bindings. Early failures also lack the persistent receipt expected of this campaign. These are small harness corrections rather than changes to the experiment.

## Blocking findings

### 1. Completed-build pins do not bind the reviewed preparer

`pin_build.py:29-34` accepts a caller-supplied `preparation.json` hash and verifies whichever `script`, `seed`, `manifest`, and `runner` identities that file names. It never requires:

- `prep.status == "prepared_not_built"`;
- `prep.script` to equal the reviewed `prepare_build.py` identity above;
- `prep.seed` to equal the admitted R11 build runner and its fixed SHA;
- the copied `build_root/source-manifest.json` to equal the prepared manifest identity, independently of assertions inferred from the text log.

Consequently `completed-build-pins.json` proves internal consistency with an arbitrary preparation receipt, not that the reviewed preparation path created the build wrapper. `run.py` then treats those completed pins as authoritative.

Smallest correction: hard-pin the reviewed preparer and admitted seed in `pin_build.py`, require the expected preparation status/source/manifest/runner fields, and directly compare the build-root manifest copy to `prep.manifest`. Preserve those identities in the completed result. The existing source walk, before/after manifest equality, tool equality, measured runner, artifact hashes, app/library identities and build log checks are otherwise appropriate.

### 2. Prior run receipts are admitted by broad shape rather than exact producer and mode semantics

`run.py:44-54` checks status, return code, mode, identity equality, contract, live identity rows, and live outputs. It does not require the receipt's `script` to equal this reviewed `run.py`, or check the prior receipt's case, original receipt, request, input/validity, actual `argv --pass`, and mode-specific environment. Caller checks at `:124-128` add only the build-pin SHA.

This is especially relevant because the cap arm trusts the supplied `pass1` receipt as its fresh-stat producer, and the trace arm trusts the supplied cap receipt as the policy stream. Exact stats SHA at `:175-178` is valuable but does not establish how that stats file or cap stream was produced.

Smallest correction: in `read_receipt`, require the reviewed producer identity and fixed experiment fields, parse the saved argv to verify pass number/TBR/no public QP bounds, and require exact mode environments:

- baseline and pass1: private library only, cap/trace FDs absent;
- cap: cap enabled, trace FDs absent;
- trace: cap enabled and the three expected FDs present.

Also bind the original R16 receipt/input/validity and request 10042 in every prerequisite. The current live identity and output rehashes should remain.

### 3. Preflight failures are not persisted

`run.py` performs environment, disk, contract/original/lineage, build pins, complete source walk, prerequisite-receipt, and command checks at `:91-155`. The run directory and initial `command.json` are created only at `:157-170`; therefore any earlier failure leaves no owned receipt. `prepare_build.py` and `pin_build.py` similarly have no failure receipt of their own.

This does not invalidate a later successful, fully admitted run, but it fails the requested failure/partial-receipt workflow and makes rejected attempts hard to distinguish from commands never invoked. Smallest correction: invoke each through an already pinned outer execution wrapper that writes before launch and records argv/log/return code, or create an owned receipt before fallible preflight and update it in a top-level exception hook. Record that wrapper in the README and downstream pins.

## Resource-bound correction

The contract declares a 120 GiB staging floor and 40 GiB additional scratch allowance. `run.py:95` requires only 130 GiB free; the inherited build runner also checks 130 GB. That does not reserve the declared allowance above the floor. Require at least 160 GiB before the first build/run, or compute and record a smaller defensible remaining peak for each step while preserving at least 120 GiB. Record free space after each run as well as before it. This is a release condition for resource discipline, not a scientific gate.

## Controls that are sound

- `prepare_build.py` verifies the complete symlink-free source manifest, derives from the SHA-pinned admitted R11 runner, changes only the absolute source path and reviewed manifest pin, and creates a fresh output directory (`:30-58`). Optimized Python is rejected.
- The build recipe is private, disconnected, CPU-bounded and checks source before/after, tool identities, CMake/Ninja stability, the app and resolved private library.
- `run.py` derives its argv from the validated R16 command, changes only binary/stats/output paths, asserts pass/TBR and absence of public min/max QP, uses CPU 0-7/nice 10, and verifies private library resolution (`:131-193`).
- The pass-one run uses a fresh path and must reproduce the admitted R16 stats exactly. Baseline pass two must reproduce R16 IVF and all 336 reconstruction bytes. Cap pass two consumes the fresh exact stats. Trace pass two consumes the cap arm's stats and must reproduce its IVF, reconstruction and stats exactly (`:221-238`). This is the right policy/observer neutrality ordering.
- Trace FDs are fresh, append-only, inherited explicitly, and closed on success or exception. Renaming the R18 binary trace from `.jsonl` is cosmetic but should be done before its hash is frozen.
- IVF parsing checks the header, 1920x1080 geometry, 24/1 cadence, 336 packets, sequential PTS and exact EOF. The 14-second full and 10-second scored payload-rate formulas are correct. The scope correctly says this is IVF payload accounting and that remux accounting remains separate; the preflight's `9.6702312 Mbps` therefore must not be substituted for R16's remux/scored rate.
- Successful receipts rehash inputs, tools, scripts, pins, prior receipts, stats, app/library artifacts and recorded outputs. All-336 10-bit 4:2:0 reconstruction size (`1920*1080*3` bytes/frame) is correct.

## Preflight evidence limit

`runner-data-preflight.json` binds the three script hashes and demonstrates parsing of the admitted original IVF as 336 packets with the expected payload rates. It has no recorded argv, tool identity, self identity, or outer execution receipt, and no completed private build exists yet. Treat it only as a small data/syntax preflight, not as execution release or evidence about the forthcoming native observer.

## Filename-only revision

I compared the preserved `run-v1.py` SHA `6d18a5c4434a1768a9de20ea16e0b403bb25a8a007d7b3d42fc804e01978eca9` with revised `run.py` SHA `3993eb96f0de0711f2522bea64c8dfe1db315b3d9a429e8bc19dbcac03b816d8`. The only four changed occurrences consistently rename `r18-trace.jsonl` to `r18-trace.bin`: FD creation, output collection, trace-size admission and absence checks. This accurately labels the framed binary artifact and introduces no new issue. The blocking findings above remain unchanged.
