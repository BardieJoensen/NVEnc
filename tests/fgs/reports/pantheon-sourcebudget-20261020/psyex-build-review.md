# R8 private build runner v3 review

Reviewed `worker/psyex-r8/build_runner.sh` SHA-256 `2adb0dea44c9ed55687b98f1d35d8ef6c6ab2919dabda79128512c060a7a043a` and `build-plan.md` SHA-256 `73b18b20acbd97c0f26ef987527c15420d9615bb0950b8c5c547efda93716e40`. No build was run.

## Disposition

**Conditional acceptance after two small corrections.** The earlier substantive runner defects are resolved. I found no reason to change the build configuration or provenance scope, but the literal v3 runner should not be released unchanged.

### 1. Source-domain cleanliness omits untracked paths

Lines 54-55 reject tracked worktree and index changes, while lines 57-80 and 130-132 manifest only `git ls-files`. An untracked path under the source tree is outside both checks. Even though the source is independently clean now (`git status --porcelain=v1 --untracked-files=all` returned empty), the runner's admission should fail closed on any untracked path both before configure and after build. This also proves that the out-of-tree build did not leave source-side generated files.

Smallest correction: capture or assert empty `git status --porcelain=v1 --untracked-files=all` before manifesting and again after the build/smoke operations. Preserve the status output or its hash in the receipt. Do not merely add untracked files to the 1,217-file reviewed manifest.

### 2. Owned receipts get duplicate terminal records

After line 42, both stdout and stderr point to `build-receipt.log`. The trap writes `final_status`, `end_utc`, and `exit_code` to stderr at lines 19-21 and then appends the same three keys directly at lines 22-24 when `receipt_owned=1`. Every owned receipt therefore has two terminal blocks, potentially with different `end_utc` seconds. This is deterministic but needlessly ambiguous to downstream parsers.

Smallest correction: for an owned receipt, write one terminal block through the already redirected stream; for pre-ownership refusal/failure, write one block to stderr. Keep the existing `receipt_owned` guard so refusing an existing receipt cannot alter it.

## Verified behavior

- The live source currently has exactly 1,217 tracked files, no status entries, and `tracked-manifest.tsv` hashes to the pinned `8cf0314d5ee329b662c32021020c8299ef47bb87681d87508328c1b28eeb5c69`. Lines 54-80 bind clean tracked content, HEAD `59d1a025698f2ca7b4c4b0e833937dd15e382494`, and byte-identical reviewed manifest.
- Lines 27-31 refuse all declared outputs, including the build directory, logs, manifests, measured runner, and identity files. Lines 94-97 direct configure/build products to the fresh out-of-tree build and `build/bin`; there is no install action.
- The corrected options are literal: Release, Ninja, `BUILD_TESTING=OFF`, `BUILD_APPS=ON`, and shared libraries. Lines 103-127 bind compiler paths, CMake cache, Ninja file, and tool identities before/after.
- Resource bounds are explicit: 130 GB floor, niceness 10, CPUs 0-7, and four parallel build jobs (lines 33-37, 95-116). Build-affecting inherited compiler/linker and loader variables are rejected.
- Lines 128-155 bind the measured runner, post-build tracked manifest, application, regular versioned library, resolved `libSvtAv1Enc.so.3` loader path inside the private build, application/library hashes and sizes, `ldd`, version/help output, logs, configuration, and tool identities.
- Configure and build return codes are captured before fail-closed exits (lines 96-121). Once receipt ownership begins, implicit failures also reach the EXIT trap. Pre-ownership refusals safely leave existing evidence untouched and report on stderr.

No broader reproducibility requirement is needed for this bounded private build once the two corrections above are applied and the final script hash is reviewed/bound.

## Final focused re-review

Accepted for execution at final runner SHA-256 `4cf939e20445e130970fdf09983a774e1f71adf1ea6240038cc557fe9ef66a7b`.

The delta from reviewed v3 is limited to the requested corrections: the duplicate direct append was removed from `on_exit` (current lines 15-22), and empty `git status --porcelain=v1 --untracked-files=all` is now required before configure (line 51) and after the application version/help smokes (line 153). Because stderr is redirected to the owned receipt at line 39, the trap emits exactly one terminal triple after ownership; before ownership it emits the same single triple to the caller's stderr without touching pre-existing evidence. Both source-domain guards fail closed. No new defect was introduced by this delta.
