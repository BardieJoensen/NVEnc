# Round 8 PSYEX observation replay review

Reviewed unexecuted `replay_psyex_observation.py` SHA
`fed5d3a539ad72c1e36b86257578995901adc714a191a7d6d8050b7f5ff4f3bf`.

**Status: accepted for separate off/on replays after the private build receipt
passes.**

## Command and provenance

- The exact completed matched arm receipt is pinned by SHA
  `ceea9943cb7b0fd31331a7505089ac72bb06dc78c7e150589f0972d469cfa138`.
  The replay copies its literal pass-2 argv and permits only four explicit path
  substitutions: private app, an exact copied stats file, output IVF, and app
  reconstruction (`:73–80`). Pass remains exactly 2; input and all quality/rate
  settings remain inherited from the pinned command.
- The reviewed build runner, complete pre/post source manifests, observation
  patch, schema, terminal build receipt, and every build-artifact hash are
  checked live (`:45–59`). CLI app/library hashes must also equal the exact
  private artifacts listed by that build.
- Original input, IVF, reconstruction, stats, and stats snapshot are all rehashed
  from the immutable original receipt. The private loader environment is cleanly
  constructed, `ldd` must resolve the SONAME to the exact private library, and
  app/library/tools/scripts/stats/evidence are checked before and after replay
  (`:60–93,122`).

## Observation and neutrality

- `off` inherits no observation descriptor. `on` alone creates one fresh,
  append-only output and passes only that open descriptor to the child
  (`:94–104`). The removed environment pass marker is correctly forbidden and
  not fabricated.
- Both arms must return zero and reproduce the complete 336-frame unmodified IVF
  and app reconstruction byte for byte. The copied pass-1 stats must remain
  identical (`:105–115`). Thus timing/interleaving changes cannot be mistaken for
  neutral instrumentation.
- The on arm additionally requires one bounded, parseable, complete schema-3
  `[336,4,34]` JSON document; the aggregate validator can enforce config values,
  counter invariants, cross-arm/build/receipt bindings, and live artifact hashes.
  Off/on timings are correctly labeled diagnostic replay costs.
- A fresh run directory and persistent `prepared`/`running`/`failed` receipt
  prevent overwrites and preserve failures after replay creation.

The replay itself intentionally does not interpret counters. Before scoring,
the forthcoming admission validator must pin this reviewed runner SHA, the final
build app/library hashes, both replay receipts, exact off/on/original stream and
reconstruction identity, the schema/kind order, actual frozen config, and the
documented invariants. No quality evidence is reusable merely because replay is
neutral.
