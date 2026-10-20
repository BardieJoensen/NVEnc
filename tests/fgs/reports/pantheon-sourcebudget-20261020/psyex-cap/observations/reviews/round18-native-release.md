# Round 18 native decoder replay release

Reviewed the focused parent delta from worker v3
`2564ea58d6c845202c4172bb626e12e7fb7940b9fa2985c594aa41fbbff14c29`
to:

- `parent/psyex-cap-r18/replay_decoder.py`
- SHA-256
  `f76c275c4553ea1061af5fbbae71f521517907541ce1a7c0d6a483251382250d`

No decoder command was run.

The delta is limited to the reviewed corrections:

1. `HERE` now derives from the actual parent-owned script location, while the
   experiment root and all fixed R18/R10 paths remain unchanged.
2. Both `Path(__file__)` and the actual `Path(sys.executable)` are included
   in the deduplicated before/after identity closure. The existing pinned venv
   path is retained as an additional identity; an invocation through the
   standard outer wrapper will also bind the actual command/interpreter.
3. In the on arm, `trace.jsonl` and `payload.bin` must both exist, be
   readable regular-file inputs to `ident`, and have positive size. Their
   full path/size/SHA identities are stored in the completed receipt. The off
   arm continues to require both absent.

The focused changes close both blockers in
`round18-native-v3-review.md` without altering the previously reviewed cap,
binding, R10 build, decoder command, loader, reconstruction, resource, or
off/on controls. Python compilation and help parsing succeed.

**Released for fresh, separately outer-bound native off and on decoder
replays.** Admission still requires both successful receipts, exact full
336-frame reconstruction agreement, structural validation of the on-arm
trace/payload, and their explicit cross-binding. This source review makes no
coefficient, quality, rate, or playback claim.
