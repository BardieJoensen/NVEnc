# Neutral observation of the fixed R8 policy

These scratch-only hooks observe the pinned PSYEX source without changing
encoder decisions. The admitted app, shared library, patch, source manifests,
toolchain, build configuration and full replay receipts are bound by
`../psyex-runtime-result.json`.

To rebuild, create a fresh scratch directory containing these templates and
a clean `source/` checkout of PSYEX commit
`59d1a025698f2ca7b4c4b0e833937dd15e382494`. Populate its ignored
`third_party/cpuinfo` checkout with pinned commit
`e649baaa95efeb61517c06cc783287d4942ffe0e`, matching the separately audited
570-file manifest. Run `python3 apply_observation.py`, then `bash build_runner.sh`.
The patcher guards the original source text; the build rejects existing output,
unexpected source content, unsafe environment overrides and insufficient space.
It builds privately and never installs anything.

The preserved experiment uses
`/tmp/downloads/codex-work/pantheon-sourcebudget-20261020/parent/psyex-observation`.
Its complete build/source manifests, original tools and binary identities,
logs and neutral off/on replays remain there. The reproduction commands were:

```bash
REPORT=/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020
APP_SHA=fef14903f17127f7ad5c143fd306a2a88e68270c4dcf858a472096154d1f1c02
LIB_SHA=9e05ca22b16c3fb68c6fb69bf8f4cff6446af84469529b597a0610513c554736
python3 "$REPORT/replay_psyex_observation.py" off off-1 "$APP_SHA" "$LIB_SHA"
python3 "$REPORT/replay_psyex_observation.py" on on-1 "$APP_SHA" "$LIB_SHA"
python3 "$REPORT/validate_psyex_observation.py" off-1 on-1 \
  /tmp/downloads/codex-work/pantheon-sourcebudget-20261020/parent/psyex-observation/admission-1.json
```

Existing output is deliberately immutable; do not rerun those tags. A rebuild
in another path/toolchain needs separately recorded and reviewed artifact
identities. The validator's fixed hashes bind this measured experiment.

Worker observation drafts v1/v2 were rejected before build: they confused
configured settings with executed terms, copied skip state with actual cost
comparisons, and contained unsafe output framing and misplaced hooks. Parent
replaced them and independent review checked the literal C code. A worker
helper-syntax receipt was also rejected because its command compiled another
file; the retained parent receipt compiles the actual final helper.

The final counters establish aggregate search-route delivery. Candidate
selection is not final partition survival, event counts are not pixel coverage
or coded bits, and automatic filter config values are unresolved sentinels.
The unchanged legal output is evaluated separately for quality and packet cost.
