# R18: delivered spatial precision with real encoder decisions

Primary question: can an absolute qindex4 cap on the two fixed E05 texture
regions preserve their texture when real prediction, partition and transform
decisions can respond, and what actual packet/runtime cost does that incur?

R16 at99.9310%source fails both texture screens. R17's new TF-off fixed-choice
q4 reconstruction restores much of the shirt but leaves a deficit concentrated
in64x64 support. R15's real global near-fine policy preserves both screens at
19.6777xsource. Thus another fixed-choice precision point cannot answer whether
localized precision changes real decisions affordably. This round measures that
missing real policy; it does not assume finer SB quantizers reopen every search
gate or force smaller transforms.

## Fixed policy and selection

- Use the untouched E05-1440 fixture,336frames with96preroll and240scored.
- Preserve R16's common policy, TFoff, normal public QP bounds and static-QP
  behavior. Initial request10042kbps, fresh two-pass statistics.
- Keep the original first-pass statistics-collection route unchanged and
  generate fresh statistics. Enable the spatial cap only on the second-pass
  coding route, with pass identity recorded. First-pass outputs are not evidence
  of delivered final quantization. Both policy and policy observation are disabled
  in pass one; fresh statistics must exactly match admitted R16 statistics before
  pass two begins. A policy hook reached during pass one is a hard failure.
- Select every native64x64 SB intersecting either frozen rectangle
  shirt[1200,650,200,100] or background[950,50,250,180], for the complete input.
  This is28SBs/114688pixels per full frame (5.53%luma), fixed before encoding.
  Explicitly validate nativeSBsize and selection; do not silently accept128SBs.
- These coordinates are a mechanistic fixture intervention, selected from
  already-known source regions. They are not a general-purpose detector or
  held-out generalization result. Entire-window controls remain mandatory.
- On selected SBs, cap the final stored qindex at4 after variance/TPL/taper/
  normalization, then refresh the affected TPL lambda factors from the original
  factors where that path applies. Reapply after every recode reset.
  The initial hook follows the normalization conditional; the recode hook follows
  that conditional inside the `do_recode` branch, before its closing brace.
  Store `post = min(pre,4)` and require exact delivery of that value.
- Use legal delta-q resolution1 when the cap is active, retaining uncapped
  normalized SB q values. This makes q4 representable regardless of frame-base
  remainder. Require nonzero quantizers, enabled delta-Q, no segmentation
  ALT-Q for a capped luma call, and no unintended frame-base/public-QP change.
  Resolution1 is a declared whole-frame syntax component, not a selected-only
  syntax change. Verify unselected stored q values are unchanged by the helper;
  observe their encoded/decoded q where available. Capture lambda entries before
  and after refresh and prove no unselected entry receives a direct write.
- Do not alter partition/TX search controls, skip choices, coefficient optimizer,
  loop filters, synthesis, or unselected quantizers directly. Real encoder
  feedback and RC compensation outside the selected regions are measured effects.

## Controls and evidence

1. Fresh scratch clone/build from the pinned R11 observer source. Preserve
   previous source/builds. Disable-cap output must reproduce R16's selected
   pass-two IVF and all336 reconstructions using the exact admitted statistics.
   This is a code neutrality control, not an additional quality measurement.
2. Cap policy is independent of observation output. The on-policy observation
   toggle must be byte-neutral. Record commands, source/build patches and hashes,
   effective settings, fresh statistics, versions and bounded wall times.
3. For every initial/recode application, record source picture/decode identity,
   attempt, frame base, old/new delta-Q resolution, selected SB geometry,
   pre-cap/post-cap q and whether lambda refresh applied. Verify complete28SB
   selection per application and all applicable recode coverage.
4. Bind the selected SB q to actual MD q, final committed residual/skip state,
   and the actual effective luma q passed to final quantization. Audit selected
   calls across the complete encode; never describe a skip as quantizer execution.
   Every executed selected luma call must equal its stored `min(pre,4)` value,
   with zero segmentation ALT-Q. A stored or requested value alone is insufficient.
   Require one committed geometry/skip record for each of28 selected SBs per
   accepted attempt, separately from the number of actual quantizer executions.
   Assert the preset4/10bit normal EncDec route has bypass disabled at runtime.
   If it does not, stop interpretation and resolve the unexpected producer route;
   do not treat an EncDec update/copy as quantizer execution.
5. Independent syntax binding and native decoder joins on the representative
   frame must confirm target ownership, actual q/DQ/EOB and final reconstruction.
   Retain all336 decoder agreement and instrumentation-neutrality checks.
   This is representative native q export plus whole-stream decode identity;
   do not claim an independently exported q map for every frame unless produced.
6. Record resulting target TX-size/skip coverage and the exercised search-control
   state where available. A smaller chosen TX is observable; candidate availability
   or a particular rejected RD decision requires separate evidence.
7. Use campaign.py and unchanged GPU/CUDA scoring, exact frame/color handling,
   actual scored/full packet counts, full-reference scores and tails, fixed
   texture amplitude+ACF, whole-window clean/edge/detail, banding and temporal
   controls. Inspect stills honestly; actual player/display remains unobserved.

## Decisions and rate

Initial bitrate may exceed source. This arm is an unconstrained real policy
diagnostic until its actual rate and full quality are measured. Do not calibrate
the rate or build an allocator before preservation is established.

If texture still fails with a genuinely delivered cap, use actual remaining
TX/support/search and filter evidence to choose the next single discriminator.
Do not repeat a relative allocation request, infer a codec limit, or sweep caps.
If it preserves texture, test original-budget redistribution next, with all
displaced damage measured. Decisive matched-rate arms require99–100% of the
untouched source9.6765224Mbps; practical candidates must remain at or below it.
E04, additional windows, episode cost and human playback remain necessary before
a production proposal. No acceptance gate changes.

The independent R17 reviewer suggested a cheap local64→four32 transform split.
The parent defers that useful narrower isolation: R15 already demonstrates legal
preservation with different decisions, whereas selected absolute precision,
adaptive choices and actual packet cost remain unmeasured. If the real cap
retains the deficient64x64 support, the local split becomes a targeted design
test before adding a TX/search intervention. Raw HF is not a mathematical ceiling
on every quantized reconstruction; another fixed-q sweep is low value, not proven
incapable of crossing a numerical threshold.

## Ownership and resource bounds

Parent owns design, integration and Git; worker owns fresh
`worker/psyex-r18-cap`; reviewer owns `reviewer/round18-*`. No recursion,
production/library/Tdarr/torrent changes or shared-index use by children.
Source/patch preparation precedes independent review and build/encode release.
CPU encode0–7/lp1/nice10; analysis8–11; GPU serialized. Initial additional scratch
allowance40GB, staging floor120GB. Check live jobs, memory and storage before
substantial work. Preserve immutable archives and active dependencies.
