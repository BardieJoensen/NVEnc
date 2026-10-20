# R8 observation admission review

Reviewed `validate_psyex_observation.py` SHA `f61c712524243c397d42e92bff91c960e8e0c7c7882c11a4f3b46bfab6696250` against replay SHA `fed5d3a539ad72c1e36b86257578995901adc714a191a7d6d8050b7f5ff4f3bf`, schema SHA `f15b2ef12fb9dca3e85e81651df7ff7d1aa047f348946d73a51973f734445e30`, patch SHA `740a90af1352368e907a0aa8f1a4a2f5e96d46ff3686d31b1df570f9fe27552a`, and the C hooks. No runtime counters were inspected.

## Blocking before admission

1. **The validator still does not independently bind the reviewed source/patch/build domain.** The newly added fixed app/library checks at lines 16–17 and 58 correctly bind the executable artifacts (`fef149...` / `9e05ca...`). However, line 60 merely rehashes whichever patch and build receipt paths the replay receipt names. It does not require the reviewed patch SHA, source-manifest-before/after SHA `b004b855...`, build-receipt SHA `cdc82e5e...`, artifact-list SHA `76ec207d...`, or reviewed build runner SHA `ba90de74...`. The pinned replay checked these inputs when it ran, but the aggregate admission should bind them rather than infer them from a claimed command receipt. Smallest correction: add the fixed expected hashes and verify the live canonical files; require both replay receipts' patch/schema/build receipt identities to equal those canonical identities. Include the source manifests and build-artifact list in admitted artifacts. The exact app/library hashes make this a provenance blocker rather than a neutrality blocker, but it is necessary for a source-hook delivery claim.

2. **`policy_delivery_pass` does not establish the contract's selected spatial-mode route, and no hook establishes partition selection.** The target list at lines 124–126 requires `PO_MODE_HBD`, which only records `ctx->hbd_md` at the selected-candidate commit hooks (`observation.patch` lines 267/282). It does not require `PO_MODE_SPATIAL`, even though that adjacent counter directly records `ctx->mds_spatial_sse`. Add `PO_MODE_SPATIAL` to the preregistered target requirements if the intended claim includes a mode selected under the spatial policy. There is no partition-choice/survival counter anywhere in schema 3; the existing scope warning correctly says selected candidates may lose partition search. Remove “partition paths” from any claimed runtime coverage, or label it explicitly unobserved. A final-partition hook is unnecessary for the narrower, valid claim that the bundled policy was exercised in search.

## Nonblocking scope and hardening

- `--keyint 240` correctly becomes `intra_period_length=239`: `str_to_keyint()` stores `keyint - 1` for an unsuffixed value (`enc_settings.c:1583–1600`). The validator's value is correct.
- `cdef_level=-1` and `enable_restoration_filtering=-1` are also correct **static-config auto sentinels**, not resolved filter states. They are copied unchanged into `static_config` (`enc_handle.c:4348–4352`); actual sequence settings are derived later (`enc_mode_config.c:2127–2146`). Therefore the result's `effective_config` label at line 130 overstates these two fields. Rename it to `postprocessed_static_config`, or annotate those fields as auto/unresolved. Emitting resolved sequence flags is not scientifically necessary because the replays are byte-identical and these filters are not the intervention.
- Consider requiring `mode_selection_pictures == list(range(336))`. The fixed array shape proves addressable population, not that every input picture reached a mode-selection hook. Target picture 216 is already protected by required nonzero counters, so this is a completeness hardening for whole-run aggregate totals rather than a blocker for the target delivery claim.
- The per-picture/per-stage invariants are appropriate and fail closed. `OPT_ENTER = EARLY_RATE + EARLY_EOB + COMPLETE` matches the instrumented exits; paired TX/full calls and selection inequalities match the literal hooks. The scope text correctly avoids treating counts as pixels, bits, or paired causal outcomes.
- Keeping `status="admitted"` separate from `policy_delivery_pass` is sound only if every downstream scorer requires both fields, as the planned scorer does. A false delivery result admits neutral observations but must never admit a quality claim.

Subject to the two blocking corrections, the validator adequately establishes byte-neutral observation, the frozen static policy, aggregate route execution, and the stated limited causal scope.

## Final disposition after focused correction

Reviewed validator SHA `c0cf3cc62c248bb834b282cf66989c94033c307d490d819176bece179ed010ce`; no runtime counters were read.

**Accepted for execution and admission.** Lines 18–54 now pin and live-verify the reviewed patch, both complete source manifests, build receipt, artifact list, build runner, and every artifact named by the pinned list. Lines 74–78 require both replay receipts to use the fixed app/library, exact canonical artifact map, patch, schema, and build receipt. This resolves the provenance blocker.

Lines 140–147 now require all 336 input-picture indices to reach mode selection and require target picture 216 to have both `PO_MODE_HBD` and `PO_MODE_SPATIAL`, alongside the preregistered optimizer, nonzero-term, residual-zero, and skip-mode routes. Lines 151–157 correctly call the dump `postprocessed_static_config`, identify CDEF/restoration as unresolved automatic fields, and disclaim final partition selection/survival. The contract revision was recorded explicitly as a scope correction before counters were inspected; it does not alter a quality threshold or select a favorable outcome.

The corrections match the literal implementation. No blocking issue remains.
