# Round 8 parent observation v3 review

Reviewed parent-owned, unbuilt artifacts:

- `observation.patch` SHA `badc33e8b0c478f630ea219f6a85ac723ddded384675da971974203f998ba1f5`
- `apply_observation.py` SHA `34bb7f0dab83d1beda7f9cc67731f0e666e5b2d421b7aa700ac7f1e59c268495`
- `psy_observe.c` SHA `2c5e10ad150fe89eb7c49832561443284cfd727bd4914b9dc6e9e5b8711a099e`
- `psy_observe.h` SHA `99cf90fe4035550f8eedc0ff3d4193af3e51daeca1bdc47bdf2cac5c39c71a07`

## One focused correction before build

The JSON config is nearly complete but omits fixed command values that affect
the experiment or source interpretation: `scene_change_detection` (`--scd 0`),
`level_of_parallelism` (`--lp 1`), and the four color fields
`color_range`, `color_primaries`, `transfer_characteristics`, and
`matrix_coefficients`. All are fields of `EbSvtAv1EncConfiguration`. Add them to
the `CFG_I` sequence and have admission assert their expected actual values.
The literal runner and encoder log/probe also bind them, but the observation's
claim of actual fixed-policy config should not leave these six out.

## Correctness and neutrality

I found no value-changing hook or serialization defect analogous to rejected v2:

- `[336][4][34]` exactly matches the input-picture domain, `MdStage` 0–3, and
  enumerated kinds. All additions use GCC atomics with checked saturation;
  invalid indices or overflow make the enabled run fail at flush.
- Initialization safely publishes the inherited descriptor once and requires a
  fresh writable append-only regular file. Flush happens after worker shutdown,
  permits one encoder/channel only, checks actual config pass 2 and fixture
  geometry, and treats duplicate flush and write/flush/close errors as fatal.
  The disabled channel only performs the state check.
- `psy_obs_term` receives an already evaluated `uint64_t`, records call/nonzero,
  and returns it unchanged. The six wrapped existing terms preserve arguments,
  type, and addition. No SSIM signature or decision state changes.
- Luma full-loop spatial versus transform-domain counters are on the actual
  mutually exclusive branches. Transform-search predictor/reconstruction,
  full-loop predictor/reconstruction, and two fast luma terms count actual
  evaluations and nonzero returned AC-energy terms.
- Optimizer entry, luma, the two real return sites, sharp/delta-Q/luma guard,
  actual zero rate weight, and ordinary completion are correctly placed.
  `enter = early_rate + early_eob + complete` is a useful admission invariant.
- Residual-versus-zero and skip-mode comparisons and their selected outcomes are
  distinct at the actual `RDCOST` decision sites. Final mode counters are after
  lowest-candidate selection and separate HBD, spatial, inter/intra, skip, and
  coefficient state. Candidate totals remain search counts.
- The observation module writes only process-local counters and its private FD.
  It does not write encoder coefficient, predictor, rate, CDF, or mode state.
  Disabled and enabled builds must still reproduce the exact unmodified IVF;
  that empirical identity is needed because instrumentation changes timing.

## Interpretation limits

The nonzero-term and zero/skip comparison counters are aggregate by picture and
MD stage. They prove that the bundled routes were exercised, but do not pair a
specific nonzero psy term with a specific final zero/skip decision. Likewise,
`PO_NOISE_CALL` proves invocation under the existing outer guard, not a
coefficient modification, and mode/candidate counts are not pixel ownership or
partition counts. Reports should preserve those scopes and make no per-pixel or
isolated-feature causal claim.

`apply_observation.py` is fail-closed on the pinned clean commit, unique source
needles, and absent new files; its repository-relative patch and per-file
before/after hashes are internally consistent. The later build receipt still
needs to bind the complete root plus nested cpuinfo source domains.

**Status: approve after adding and admitting the six actual config fields, and
after the planned original-flag syntax checks pass.**

## Final config/build-runner delta review

Reviewed final patch SHA
`740a90af1352368e907a0aa8f1a4a2f5e96d46ff3686d31b1df570f9fe27552a`
and build runner SHA
`ba90de74c22b6e4767d8825747314c43e2365d1553efa2e7cd2c2c4b507c9dd1`.

The six requested actual-config fields are present in both standalone/template
helper source and the regenerated patch: scene-change detection, level of
parallelism, and the BT.709/range quartet. Patch provenance now binds final
helper SHA `86005185c3704851e6a2a3b53853cb9130d44050dade17236eb0fb950eb97553`.
`schema.json` accurately names the `[336,4,34]` axes and states the aggregate,
unobserved-site, and final-partition limits.

The build-runner changes preserve the accepted runner's resource, tool,
compiler/config, failure-receipt, binary, loader, and smoke-test checks. Replacing
the clean tracked manifest with the exact reviewed recursive content manifest is
appropriate for an intentionally patched tree. I independently verified all
1,789 unique live entries, including all 570 nested cpuinfo files and both new
observer files, against manifest SHA
`b004b855c0605f7b0f340d7b0bf30a240d46a3f75e7e229aa049cbc10877d490`.
The same byte-exact manifest is required before and after the build.
`FETCHCONTENT_FULLY_DISCONNECTED=ON` is consistent with the already populated,
pinned cpuinfo source and prevents a configure-time replacement.

One cited receipt is stale: original-flags syntax receipt SHA
`e4f658e590cdde20bdbe3391d39eba8716ed96ee1fff55e98bd3b7e831768bf1`
was produced at 13:09 and records `psy_observe.c` SHA `2c5e10ad...`; the six-field
final helper was written at 13:10 and is SHA `86005185...`. Its source maps also
contain the old hash. Therefore that receipt proves the five unchanged modified
units and pre-delta helper, not the final helper. Rerun just the final helper with
the captured original compile argv and preserve an updated rc0/before-after hash
receipt, or explicitly label the old receipt pre-delta and let the full build be
the first original-flags validation of the final helper.

**Build-runner status: accepted. Observation release remains conditional only on
an actual compile of final helper SHA `86005185...`; the full reviewed build itself
would satisfy that condition.**

### Final-helper condition resolved

Parent-owned receipt SHA
`e4ee2b318779a648e313cb51d2e2ccf87bde9e80c4af97e7ed8591557115a759`
uses the captured original compile flags with the actual final
`Source/Lib/Codec/psy_observe.c` argument, returns zero with an empty log, and
binds unchanged before/after source SHA
`86005185c3704851e6a2a3b53853cb9130d44050dade17236eb0fb950eb97553`.
It explicitly supersedes the rejected worker receipt whose argv named
`full_loop.c`. The final-helper condition is resolved; observation v3 and the
accepted build runner are cleared for the private build.
