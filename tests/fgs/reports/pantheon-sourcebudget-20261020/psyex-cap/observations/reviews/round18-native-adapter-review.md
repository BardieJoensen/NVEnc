# Round 18 native decoder replay adapter review

## Disposition

**Blocked before execution.**

Reviewed:

- `worker/psyex-r18-cap/native-replay-adapter/replay_cap.py`
  SHA-256 `f39b902709bdcd2ebbac69ff830eac764a94b1c43ac8d277274561362f882617`
- `README.md`
  SHA-256 `263f4dad1d97707fc9d969f1c1f2f09e53c24a41b8a387d5eeeed9450712e98e`
- cap receipt `6c90d0a52582d82fd6c0697848aad9cdcfd1c7cc84b72c4643321342ec660587`
- cap outer receipt `a3650328b7a792080c0a3eeead0214165c88951b54543c6b5fbb75f1dd959207`
- binding result `4ae3911b52a192e89f70504ad4088c3fc46266150742fee61195f145b8ffb47f`
- binder `2fcce467cbd6ef3a09f5adb076db47289472ed93441cabc3e89bcc08e05e235d`

No decoder command was run.

## Blocking defects

1. **The experiment root is wrong.** At line 12, `HERE.parents[3]` resolves
   to `/tmp/downloads/codex-work`, while the experiment root is
   `HERE.parents[2]`,
   `/tmp/downloads/codex-work/pantheon-sourcebudget-20261020`. Therefore
   lines 13-19 point at nonexistent helpers before any provenance check.

2. **The adapter selects the R18 encoder build, not the R10 decoder build.**
   Lines 120-131 load the cap build pins and treat their app/library as an AOM
   decoder. The pinned R18 file is `SvtAv1EncApp` SHA
   `2288851074fd31fd4ddf26519f48bcdd301b99c9a918c60fc7f74641985ef45f`
   with `libSvtAv1Enc.so.3.0.2`, and its pins schema has top-level
   `app`/`library`, not `files`. Thus line 122 already raises
   `KeyError`; if adapted only for the schema, line 129 would pass decoder
   switches to an encoder.

   The reusable observer is instead
   `parent/aom-decoder-r10-v2/completed-build-pins.json`, SHA
   `4c221ef0112291bcdd541b87a80c21f74ebef39e5b0ff507921d014b091f1af5`,
   whose `files.app` is `aomdec` SHA
   `ce8a2cf182077c7f9f285666ca64a7d56f54bfbc2f0e5e3ee19eb04b0aab7015`
   and `files.library` is the instrumented libaom SHA
   `6b621938f270dd3b7e5fef167730cf7177191247a1566c4056b22501dac490bd`.
   The `ldd` resolution must bind those exact decoder artifacts.

3. **The off/on selector has no effect.** `--variant` is recorded but never
   used to construct the child environment. Both arms inherit the same
   environment and run the same command. The accepted R10 interface requires
   `PANTHEON_R10_DIR=<fresh output>` only for the on arm. The on arm must
   require the native observer outputs (`trace.jsonl` and `payload.bin`);
   the off arm must require both absent. Both reconstructions must independently
   equal cap-1's full 336-frame YUV.

4. **The advertised fixed cap/binding identities are not enforced.**
   `CAP_CMD_SHA`, `CAP_OUTER_SHA`, and the result `BINDING_SHA` at lines
   22-24 are never compared with the CLI SHA arguments. This permits a caller
   to nominate different self-consistent artifacts. Require the three supplied
   SHA arguments to equal those constants, require
   `binding.encode_receipt == ident(cap_path)`,
   `binding.outer_execution == ident(outer_path)`, and
   `binding.input_ivf == cap.outputs['out.ivf']`.

5. **Outer command validation is self-derived rather than reconstructed.**
   Line 104 slices the arguments from the outer receipt being tested and then
   asks `provenance.outer` whether that receipt contains those same arguments.
   Reconstruct the exact expected cap invocation from the admitted inner
   receipt:
   `cap, tag, pins path/SHA, --control, control path/SHA, --parent, parent
   path/SHA`, then pass that sequence to `provenance.outer`. The pinned
   `run.read_receipt(..., 'cap')` remains useful because it recursively binds
   the cap policy, pass-1 parent, baseline control, settings, source, and live
   outputs.

6. **The fixed observer population guard is incomplete relative to the README.**
   Lines 113-119 check 336 packets/coded events and the target tuple but omit
   the independently derived 502-frame-header count. Reuse is valid only with
   `frame_headers == 502`, `display_actions == 336`, and
   `all_packets_exactly_one_display_action is True`, in addition to the
   existing target event 314 / coded ordinal 210 / packet 209 / hidden /
   order-hint 88 / normalized-refresh 16 checks.

## Minimum sound correction

Start from the already admitted R15 `replay_decoder.py` interface and replace
only its encoder/binding provenance with the exact R18 cap and binding chain.
Keep the R10-v2 completed-build pins, its `aomdec`/libaom `ldd` binding,
one-thread/row-mt-off command, arm-specific observer environment and artifact
presence checks, full reconstruction equality, fresh outputs, resource floor,
and before/after identities. Add the exact R18 outer reconstruction described
above.

With those changes, reuse of the R10 observer is methodologically valid because
the independent R18 binding derives exactly the fixed event/ordinal/order-hint/
refresh guards compiled into that observer. Until then, this adapter cannot
produce an off/on native admission result, and the README's reuse claim is not
true of the literal program.
