# R18 contract and implementation-plan review

## Disposition

The real selected-SB cap is a justified next experiment. It answers a different and now higher-value question than another local scalar replay: whether delivered fine precision changes real prediction/partition/transform decisions, and at what whole-stream cost. The design is falsifiable and retains the existing quality gates. It is a bundled real policy contrast; it cannot isolate the effects of q, lambda, delta-q syntax, search changes, and rate-control displacement.

The current contract/plan are **conditionally accepted for implementation design, not yet for build or encode**. The parent-announced pass-routing amendment and the concrete corrections below must be present in the implementation contract/code review.

Reviewed:

- `ROUND18_ABSOLUTE_CAP_CONTRACT.md` SHA256 `29f5a8266f377afe17df81359d43a5492026330f5c6fafa551c6de3eeba120ff`
- worker `implementation-plan.md` SHA256 `537db0307d48d00ede84ea15150e09aa8da929bb656b786c6c225bf3dda93759`
- worker `README.md` SHA256 `cc5ada22d7ac7f670e0857a52a5b465c0e7795c447b970389b6b7393577a9473`
- pinned PSYEX source `rc_process.c` SHA256 `5187c76a6f9d132ab05c445f71b26258d83499b9c17118f76b3c294dc65531e5`
- `enc_dec_process.c` `a5233ac2ed205502e7d6a9c829841119a7e73a83eddf068596cf57ac47e12dc1`
- `entropy_coding.c` `497acf4a6e62fad039d657da0811d867f7d8f6c173402775d2ab3f6cfa34dc28`
- `full_loop.c` `bf49b663847a0cb0666e359131f728a3d19c28db1cff2630cb50b2f8fd4d9d4c`

## Required corrections and admission conditions

1. **Make pass routing explicit and testable.** The cap and its policy observation must be disabled during the fresh first pass. The fresh pass-one statistics must exactly match the accepted R16 first-pass statistics before pass two starts. The cap applies only to pass two, which consumes that exact fresh stats file. Separately, a cap-disabled private pass-two control using the admitted R16 stats must reproduce the selected R16 IVF and all 336 reconstructions. Record pass identity at every cap hook and fail if the policy is reached in pass one. This is the correction the parent already proposed.

2. **Place the recode hook inside the recode branch.** `enc_dec_process.c:2722-2757` resets base q, clears delta-q, rebuilds every SB q, reapplies variance/TPL, and conditionally normalizes. The helper must run unconditionally after that conditional normalization but before the closing brace at 2757. Describing line 2758 as the call site is ambiguous because 2758 begins the `else` branch; a hook after the branch could duplicate the initial application on a no-recode attempt or mislabel generations. The initial hook analogously belongs after the normalization conditional at `rc_process.c:3726-3730`, whether or not normalization executed.

3. **Bind actual final q to the stored post-cap value, not merely `<=4`.** Record `post = min(pre,4)` with nonzero enforcement. With no ALT-Q, every executed selected luma quantizer must receive exactly that post-cap value; selected final syntax blocks that skip quantization remain separately identified. A value below four can be valid only if its pre-cap value was already below four. `full_loop.c:1614-1619` proves that delta-q selection and segmentation offset determine the effective quantizer, so a loose `<=4` check could hide an unintended second adjustment.

4. **Treat resolution one as a necessary whole-frame policy component.** In this SVT tree `delta_q_res` stores the actual resolution (1/2/4/8), and entropy coding writes `log2(resolution)` (`entropy_coding.c:3498-3504`); setting the field to 1 is correct. It is nevertheless frame-global. Require every unselected stored q to remain numerically unchanged by the cap helper, validate its encoded/decoded q where observed, and report syntax overhead and RC displacement. Do not describe the intervention as changing only selected syntax bits.

5. **Prove lambda refresh has selected-only direct effects.** `sb_setup_lambda` reads the original `tpl_rdmult_scaling_factors` and writes `tpl_sb_rdmult_scaling_factors` (`rc_process.c:1148-1202`), so recomputation is feasible without compounding. Capture the selected entries before/after and assert the helper writes no unselected entry. Downstream rate-control effects outside the regions remain expected measured consequences.

6. **Use final committed-route coverage, with the simplest fail-closed bypass rule.** At exact 10-bit preset4, `svt_aom_get_bypass_encdec` returns zero (`enc_mode_config.c:7756-7771`). Assert that realized state for every target picture. If it holds, observe the normal committed EncDec route and actual quantizer calls; no candidate-to-final bypass provenance machinery is necessary. If runtime contradicts it, stop before interpreting rather than treating `svt_aom_encdec_update` as a quantizer producer—the bypass coefficients were produced earlier during search.

7. **Count selected decisions separately from quantizer executions.** Whole-64×64 skip blocks may not signal a delta-q at that SB (`entropy_coding.c:4846-4856`) and execute no final quantizer. Every one of the 28 selected SBs must still have a final committed geometry/skip record per accepted attempt, while the exact-q requirement applies to the executed luma TUs. State both denominators.

## Validity and confounds

The geometric selection is correct: shirt intersects 8 native 64×64 SBs and background 20, with no overlap; 28×4096 = 114,688 luma pixels or 5.53% of 1920×1080. Validate `super_block_size == 64` (or the equivalent `seq_header.sb_size == BLOCK_64X64`) and the exact coordinate manifest rather than relying on a similarly named field.

Changing delta-q resolution, selected q, selected lambda and real decisions is one declared policy. Rate control may coarsen unselected regions or change recode behavior in response. Those are part of the result, and the unchanged full-window controls/tails/temporal checks are necessary to measure displaced damage. The fixed regions were chosen from prior outcomes, so success is fixture-specific and not held-out evidence.

The initial request may overshoot and remains an unconstrained diagnostic. Texture preservation at high cost justifies a later original-budget redistribution test; it does not create a candidate by itself. Failure after proven delivery should be interpreted using retained TX/skip/support/filter evidence. A retained 64×64 shirt population would make the already proposed local 64→four-32 diagnostic informative; otherwise the real decision change itself supplies the more relevant discriminator.

No expected result was used in this review, and no implementation, build or encode was inspected or run.
