# R9 replay-script review

Reviewed `/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/replay_psyex_boundary.py`, SHA-256 `77b5407e435e27ce1ddc888ac7ab01537171cda48bb9744251b118f99330300a`, against the admitted R8 replay (`fed5d3a539ad72c1e36b86257578995901adc714a191a7d6d8050b7f5ff4f3bf`) and the accepted R9 source/contract.

## Disposition

**Accepted for the off/on private replay. No consequential defect found.** The script preserves the exact R8 pass-2 policy and changes only the private app/library, local stats/output paths and boundary-trace FD.

The following admission properties are implemented:

- The exact R8 command receipt is hash-pinned (`ceea9943...`), must be complete, and supplies the original pass-2 argv. The script changes the binary at the same fixed position and exactly one each of `--stats`, `-b` and `-o`; all policy, rate-control, input and resource flags remain inherited.
- The original input, IVF, reconstruction, stats and stats snapshot are rehashed against that receipt before run creation. Pass-2 stats are copied to a fresh run-local file, supplied to the command, and required unchanged and equal to the original stats after execution.
- The accepted R9 build runner, pre/post source manifests, patch and schema hashes are exact. Every build artifact listed in the build receipt is rehashed, and the caller-supplied app/library hashes must equal both the live files and the artifact list.
- The child environment starts without preload/audit/library or boundary-FD contamination; all `PANTHEON_`, `SVT_PSYEX_` and `SVT_PANTHEON_` variables are removed before the private library path and, for `on`, the single intended FD are added. `ldd` must resolve the app's SONAME to the exact private library.
- The trace is created only for `on` with `O_CREAT|O_EXCL|O_APPEND|O_WRONLY`, passed explicitly via `pass_fds`, and the parent descriptor is closed after the child. The run directory itself is fresh. `off` requires no trace path to exist.
- Both modes require the complete IVF and application reconstruction to equal the admitted 336-frame R8 artifacts byte for byte. Inputs, stats, tools, script snapshot, build evidence, app and library are all rehashed after the replay.
- Successful `on` replay requires a bounded nonempty trace and the exact first R9 envelope magic/version/type/generation/picture/sequence. The receipt explicitly states that this is only a neutrality replay; full record framing, generation, YUV and stage admission remain the separate parser's responsibility.
- Failures retain a command receipt with status/error/end time. Normal subprocess failures retain log and any created output/trace identities before the decisive assertions.

## Limits and minor wording

The replay's `neutral` status proves only byte/sample neutrality and the existence of the first envelope. It must not be treated as boundary admission until the separate validator proves the end record, exact sequence and length consumption, complete per-generation SB mosaics, unique accepted attempt, and exact source/pre/post bindings.

The module docstring still says “R8 observation replay,” and the trace receipt key remains `observation`. Renaming them to R9/boundary wording would reduce ambiguity, but neither affects execution or evidence binding and is not a blocker.
