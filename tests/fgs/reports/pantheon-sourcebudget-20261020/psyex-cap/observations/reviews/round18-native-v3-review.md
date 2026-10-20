# Round 18 native replay adapter v3 review

## Identity and disposition

Reviewed `worker/psyex-r18-cap/native-replay-adapter/replay_cap_v3.py`,
SHA-256
`2564ea58d6c845202c4172bb626e12e7fb7940b9fa2985c594aa41fbbff14c29`.

**Blocked pending two small but material receipt/provenance corrections.** No
decoder command was run.

## Resolved v1 defects

The v3 adapter fixes the incorrect experiment root and uses the exact R10-v2
decoder pins
`4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5`.
It selects the pinned `aomdec` and instrumented libaom, checks all build-pin
files, and verifies live `ldd` resolution.

It now hard-pins the cap inner/outer and binding paths and SHAs, cross-binds the
binding to the cap IVF, reconstructs the literal cap outer argv including
`--control-sha` and `--parent-sha`, and invokes the reviewed recursive cap
receipt validator. The fixed R18 binding and native observer guards are
compatible: 502 headers, 336 coded events/packets, target event 314, coded
ordinal 210, packet 209, hidden frame, order hint 88, refresh flags 16.

`--trace` now sets `PANTHEON_R10_DIR` only for the on arm; the off arm
forbids the two native trace outputs. Both arms use the exact one-thread,
row-mt-off R10 command and require their 336-frame reconstruction to equal
cap-1 byte-for-byte. Input/build/tool before/after checks and 160/120 GiB
resource gates are present.

## Remaining blockers

1. **The on-arm trace artifacts are not bound into the receipt.**
   Lines 94-96 test only `.exists()`. A directory or empty/stale-looking file
   satisfies that condition, and neither `trace.jsonl` nor `payload.bin`
   appears in the completed receipt. Native admission therefore has no
   immutable artifact identity to consume.

   Minimal correction: after successful decode, require both paths to be
   regular files with the established bounded/nonempty conditions and store
   `ident(path)` for each in the receipt. For off, continue requiring both
   absent. The completed receipt must be saved only after these identities are
   present.

2. **The executing adapter and actual Python runtime are not in the
   before/after closure.** Line 76 appends a hard-coded venv Python path but
   neither asserts it is `sys.executable` nor includes `__file__` in
   `paths`. The initial `script` field records the file once, but a
   mid-execution change would not fail the final equality check.

   Minimal correction: add `Path(__file__).resolve()` and
   `Path(sys.executable).resolve()` to `paths`; if a particular venv is
   required, assert the latter resolves to that pinned interpreter rather than
   recording a separate unused path.

## Nonblocking tightening

Because the binding result itself is fixed by path and SHA, its embedded
display lifecycle is already immutable. Explicit checks for
`display_actions == 336` and
`all_packets_exactly_one_display_action is True` would make the reuse reason
locally legible but are not needed to repair the two blockers above.

After the two corrections, the adapter is suitable for separate off/on
replays. It still establishes decoder neutrality and native payload
provenance only; it makes no policy-quality, rate, or playback claim.
