# PSYEX absolute per-SB qindex route audit

Scope: pinned R11 PSYEX source, read-only. This is a route/design audit, not an experiment recommendation or outcome.

## Effective route in the admitted R8 policy

R8 uses VBR (`rate_control_mode=1`), AQ2, variance boost, 10-bit, preset 4. In `rc_process.c` SHA `5187c76a...`, VBR first chooses a frame qindex at lines 3535-3546, applies reference-QP constraints, and finally rewrites `base_q_idx` from `picture_qp` at 3613. It then:

1. initializes every `sb_ptr->qindex` to that base at 3693-3698;
2. applies variance boost and may readjust the frame base at 3700-3705 through `svt_variance_adjust_qp` (1507-1615);
3. applies AQ2/TPL offsets at 3707-3714 through `svt_aom_sb_qp_derivation_tpl_la` (1623-1657), which also derives the SB lambda map;
4. applies low-q taper when configured at 3721-3724; and
5. rounds every SB onto the delta-q signaling lattice at 3726-3730 through `normalize_sb_delta_q` (1665-1718).

`normalize_sb_delta_q` chooses resolution 1/2/4/8, preserves the base-q remainder, and prevents qindex 0. Thus the final stored SB qindex is an **absolute internal AV1 qindex**, but only values congruent to `base_q_idx` modulo `delta_q_res` are directly representable. It is not an FFmpeg `qmax`/QP value.

The MD/final route is direct:

- `enc_dec_process.c` SHA `e5731e17...` passes `sb_ptr->qindex` into `svt_aom_mode_decision_configure_sb` at 3390-3395.
- `md_process.c` SHA `8e19f6e5...` selects SB q when delta-q is present and assigns lambdas at 627-638.
- `product_coding_loop.c` SHA `bf652cad...` copies that value into every searched block at 10206-10218; final selected block state retains it. In final EncDec, `coding_loop.c` SHA `50a4a6df...` reads `blk_ptr->qindex` at 309-333 and passes it to the actual quantizer at 421-438.
- Final block transport copies qindex to the entropy object at `product_coding_loop.c:7155-7191`.
- `full_loop.c` SHA `e6942d07...` uses the passed qindex when delta-q is present at 1596-1620; segmentation ALT-Q and chroma offsets are then applied separately.

Syntax is consistent with that state. `entropy_coding.c` SHA `497acf4a...` writes `delta_q_present` and `delta_q_res` and initializes each tile's previous qindex from frame base at 3498-3504. At the first eligible block at an SB upper-left, it writes `(blk_ptr->qindex - prev_qindex) / delta_q_res` and updates the predictor (intra 4846-4865; inter 4988-4998). A fully skipped full-SB may carry no new delta-q symbol; its stored qindex must not be described as an executed or independently signaled quantizer.

## Minimal consistent absolute-cap hook

For a selected SB and absolute upper bound `C` (smaller is finer), derive the largest legal value `C' <= C` having the same remainder as `base_q_idx` modulo `delta_q_res`, require `C' > 0`, then set `sb->qindex = min(sb->qindex, C')`. Record requested and realized caps separately.

The helper should be called **after all existing SB adjustments and final normalization**, immediately after the route ending at `rc_process.c:3729`, but before RC posts the picture to MD. Applying it earlier allows variance boost, TPL AQ, taper, or normalization to overwrite it. If changed SBs use TPL block-lambda tuning, refresh their `tpl_sb_rdmult_scaling_factors` from the original TPL factors with final qindex using the existing `sb_setup_lambda` logic (`rc_process.c:1148-1202`); that function writes from the original factor array rather than compounding its output.

The same cap and lambda refresh must run in every recode attempt. `enc_dec_process.c:2693-2759` can replace frame base, reset every SB qindex, and rerun variance/AQ/normalization before restarting MD at 3583-3599. The second hook belongs after line 2758. Initial-only application is not an absolute cap.

For the fixed R8 policy, delta-q is already active. A generalized helper must define the previously-disabled case: if any SB changes, enable delta-q with legal resolution and align all changed values. It must also fail closed on segmentation ALT-Q if the intended claim is a cap on the *effective luma quantizer*, because `full_loop.c:1615-1626` adds segment/chroma offsets after the stored SB qindex. R11's target used segment 0 and zero segment delta; that fact cannot be assumed globally.

## Confounds and public controls

`--max-qp` bounds the frame-level RC choice for VBR/CBR (`Docs/Parameters.md:96`; frame clipping at `rc_process.c:3543-3550`), not a chosen spatial subset after AQ/variance. `--aq-mode`, variance-boost options, and qindex-offset options are bundled relative policies. The pinned app exposes no public absolute per-SB map.

An absolute cap prevents RC/AQ from making a selected SB coarser **within each capped attempt**, unlike the old signed-relative map (`pantheon_alloc.h` SHA `8a795068...`). It does not prevent the recode loop from raising frame base or shifting bits into/out of uncapped SBs; reapplication preserves the selected cap while global allocation, modes, references, chroma, and bitrate can change. Any real result is therefore an end-to-end spatial policy contrast, not isolated quantization causality.

## Minimum observational proof

Before a quality claim, require an instrumentation-neutral off stream and, for every frame/recode generation/SB, a complete record of base q, pre-cap q, delta-q resolution, requested cap, aligned cap, post-cap q, selected state, and lambda refresh. Join this to:

- MD `sb_q -> ctx->qp_index` for every selected SB;
- final committed block qindex, segment ID/ALT-Q, skip/residual status, and the effective luma qindex actually supplied to quantization;
- an independent parsed header/syntax map of base q, delta-q resolution, and decoded current q for every signal-bearing SB; and
- complete attempt coverage proving the cap was reapplied after every recode.

For selected coefficient-bearing blocks, stored SB q, MD q, final EncDec q, effective luma q, and independently decoded syntax q must agree and satisfy the realized cap. Full-SB skips are reported separately without quantizer-execution claims. Report all selected blocks above the requested/aligned cap as a hard failure, plus actual packet rate and unchanged full quality controls. This proof distinguishes an absolute delivered cap from RC compensation elsewhere; it does not make the map outcome-independent unless its selection was frozen from source-only evidence before encoding.
