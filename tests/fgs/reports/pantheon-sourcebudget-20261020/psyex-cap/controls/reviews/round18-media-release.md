# Round 18 parent media admission release

Reviewed the focused delta from immutable worker v3 to the parent-owned media adapter. No media command was executed for this review.

## Identities

- Parent adapter: `parent/psyex-cap-r18/media_admission.py`
  - SHA-256: `750e11a1bb75e7cb0b39c60316c29715a13899f2581c6e63242b64c87b1919a5`
- Immutable worker v3: `worker/psyex-r18-cap/media_admission.py`
  - SHA-256: `0c75a0eb5e9f3719091f00d2c388cb52453954d8d0e52962d413eccbb2d156ef`

## Focused verification

Every literal import/provenance SHA in the parent adapter is 64 hexadecimal characters and matches the current file it names. In particular:

- shared decoder helper: `bb2e0256100ad70e02753c0fc19c0cc62f2ed189f08d50335b3ab421983b5ca9` (the missing terminal `9` is restored);
- provenance helper: `b6c923ec919c27e55c3be1a432bce225f582064212ad68ac1590388c00e95d8f`;
- trace reader: `08fe4c552b576e30b91f000246f3a6f39235383f0cb6aa1c19991af3323561d8`;
- R18 runner: `ebfce2b97bd8002db2e866086ed44ac8dece936d64bfeaa01062f29dc5bf6bb3`.

The adapter now binds the cap receipt's complete pins dictionary to the supplied pins file and retains the provenance and reader identities in both the initial and reconstructed final input maps.

The reconstructed inner arguments are exactly the argument sequence required by `provenance.outer` for a cap invocation:

`cap, tag, pins path, pins SHA, --control, control path, --control-sha, control SHA, --parent, parent path, --parent-sha, parent SHA`.

This includes the two omitted SHA flags from worker v3. `provenance.outer` then compares the recorded outer command with the fixed outer prefix, the exact R18 runner path, and this complete sequence; it is not a substring or presence check.

The earlier v3 resource, launcher/tool, probe, command-output/log, media-output, and before/after identity checks remain intact. The parent additions close the previously reported undefined-constant, unstored-helper, cap-pins, truncated-helper-hash, and incomplete-outer-argv defects.

## Disposition

**Released** for one fresh, pinned-outer media admission execution. This is a code-preflight disposition only. It makes no claim about decoder agreement, rate, quality, playback, or the R18 policy result until the resulting receipt passes the script's checks.

I found no remaining validity defect in the reviewed delta. A failed preflight or command remains evidence only of that failed execution, while a successful result must still contain all 336 full-plane agreements and the exact color, cadence, packet-window, and identity bindings enforced by the adapter.
