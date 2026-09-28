# Retention R1: whole-picture decision and measurement contract

Revision 1, September 22, 2026. This defines the experimental implementation
following `c08bf2dc`; it does not change ordinary FGS or qualify deployment.
The [roadmap](RETENTION-ROADMAP.md) tracks implementation and acceptance.

## Representation and source preservation

The first implementation selects a uniform retained residual fraction for each
component. It does not introduce a spatial retention mask. For native source S,
denoised base B and fraction r, its pre-encode base is
`round_to_nearest_even(B + r * (S - B))`, clipped to the native code range.
Measure this rounded picture. The missing-grain target is source covariance
minus retained-base covariance; applying r again to those moments is wrong.

The decoder uses component strength curves indexed by picture code values.
In 4:2:0, its chroma strength lookup uses the rounded horizontal pair from the
upper corresponding luma row; the chroma AR driver uses a different luma
average. High-bit-depth lookup interpolates between the 256 strength entries.
Coverage therefore includes native-depth lookup values and curve interpolation,
not just the mean brightness of accepted training patches.
See the [AV1 decoding process](https://github.com/AOMediaCodec/av1-spec/blob/master/08.decoding.process.md#film-grain-synthesis-process)
and pinned AOM `18c52422b835` `av1/decoder/grain_synthesis.c`.

The encoder can preserve a component by copying the source and signalling zero
grain strength for that component. Both 4:2:0 chroma point counts still obey AV1
syntax. A component-level change invalidates any dependent joint fit: recheck
cross-component compatibility before accepting the frame. Copying one component
does not automatically preserve its correlation with another synthesized one.
If those checks cannot establish compatibility, preserve the entire source
frame and signal no grain. This is still followed by lossy NVENC compression.

Consequently, "source preservation" describes the input/fraction decision,
not a successful decoded-output guarantee. A compressed source fallback that
loses required source grain/detail is rejected too. D76 adds a necessary
reconstruction energy/mean veto to the finite whole-source diagnostic; complete
quality qualification and the bounded file-level failure policy remain R5/R8.
Do not install a rejected fallback or silently lower its quality settings.

D81 strengthens that necessary veto with native-tile local picture checks.
Detrending must not hide a brightness step or gradient on a nonconstant source,
and opposite errors in other tiles must not cancel it. For each visible luma
64x64 or chroma 32x32 tile, including smaller edge tiles, bound the absolute
mean error and each independently fitted slope's edge excursion to 0.125 in
normalized 8-bit code units. These are three independent basis-component
bounds, not a combined bound on their sum at a corner. Preserve the existing
8% variance, global/spatial-half mean and exact constant-plane checks. The
diagnostic names this stricter policy `native_variance_means_local_planes_v3`;
it is still neither source eligibility nor complete local-detail qualification.

## Decisions, in order

| Condition | Action |
| --- | --- |
| Retention option disabled | Existing ordinary path; no new allocation, history copy, fitting or synchronization |
| Invalid format/history, discontinuity or explicit scene reset | No correlated recovery from that history; preserve source where required by existing guards |
| Source-selected training and independent check populations support all active brightness ranges | Try the bounded component candidate sequence below |
| Quiet source region would receive excess grain | Reject the candidate, including when an average over other regions passes |
| Texture, edge or persistent structure is removed beyond the existing detail bounds | Reject the candidate; apparent grain fit cannot override picture detail |
| Nonzero curve enters an occupied brightness/population range without independent support | Reject; absence of evidence is not a zero-grain observation |
| Curve is zero while retained base demonstrably loses source energy/detail | Reject; zero synthesis alone does not make a partially retained base safe |
| Invalid/non-PSD target, failed solve, coefficient clipping, instability or failed actual-synthesis/source check | Reject; do not regularize away the failure or widen the acceptance threshold |
| No eligible component candidate | Copy that source component, zero its grain, and check joint compatibility again |
| Final luma/colour or Cb/Cr compatibility remains unproven | Copy the complete source frame and signal no grain |
| Final candidate passes all spatial and source checks | Pass it to the existing temporal recovery policy; R4 must qualify the new transitions |

Final decisions record every applicable reason, source-preserved components,
chosen fractions, candidate count and unsupported coverage. A successful fit
alone is not the final outcome.

## Bounded candidate policy for development

Keep the existing bounded luma auto-retention proposal and its source-detail
guards as the initial Y choice. Changing that luma policy is a separate measured
revision. For each colour component, try residual fractions
`0, 0.1, 0.25, 0.5, 0.75`, stopping at the first independently admissible result.
Full source preservation (`1`, no synthesis) is the terminal fallback.
These are development operating points, not storage allowances or defaults.

Use the same original-source training/check coordinates for all candidates.
Recompute retained-base evidence for each fraction. Select with development
training/check data; the reserved qualification corpus never selects fractions
or thresholds. Mathematical, quantized-model, coverage and reconstructed-source
checks must all pass. The fraction search cannot repair an unsupported source
classification by changing that classification.

Limit a frame to five evaluated colour fractions per component and one final
joint compatibility decision. Do not backtrack indefinitely across combinations:
an unresolved final combination preserves the frame. This finite first policy
can be revised with a new experiment if measured coverage/cost warrants it.
Smaller residual amplitude is a preference among admissible candidates, not a
promise of smaller compressed output. R6 determines quality per byte.

## Source measurements and coverage

For both Cb and Cr, use 32x32 chroma tiles and the corresponding 2x2-averaged
luma. Detrend each tile with a fitted plane. The existing development selector
uses only current/previous original-source pixels: variance 0.04..256 in 8-bit
code units, positive previous variance, mean change at most one code, previous /
current variance ratio 0.5..2, absolute temporal correlation at most 0.15 and
central-gradient coherence at most 0.18. Apply the tests independently to luma
and the colour component. Gates are experimental source evidence, not proof
that arbitrary accepted pixels contain only grain.

Keep disjoint training/check tiles by checkerboard parity. A brightness group
requires at least 16 blocks in each half before fitting. The existing 20 broad
brightness groups describe joint shape; finer brightness/strength-population
checks remain independent vetoes. Never merge a quiet population into a noisy
average to make it pass. Account separately for rejected tiles, image borders,
textured/quiet regions and occupied lookup ranges. The selected patch count is
not the percentage of the picture that has been qualified.

An unchanged native base with zero grain strength also requires proof that the
actual decoder range clamp leaves that population unchanged. A present zero
curve still invokes the AV1 restricted-range clamp; a legal full-depth source
code can therefore change. The exact-source shortcut must measure and pass
`FGS_RETAIN_NATIVE_RANGE`, including the final active-component/range/matrix
state. A missing check remains unknown, and a clipping failure rejects the
candidate. The complete-component preservation helper provides this proof for
an exactly copied component; a grain classification is unnecessary in that case.

The per-component 26-variable vector contains 24 causal lag-three colour
neighbours, averaged luma, and current colour. Collect source, actual rounded
base and asymmetric source/base cross moments on the inner 26x26 samples.
The source/base cross matrix must retain its orientation. It is not symmetric.
Record native-depth code units and normalization explicitly.

The two colour components also need an independent compatibility check.
Separate Y/Cb and Y/Cr fits alone do not establish Cb/Cr covariance. R2/R3 must
retain evidence of both colour components on common source coordinates;
R5 must evaluate the synthesized/retained combination, including spatial colour
cross-correlation. Until such evidence passes, real coupled-colour recovery
remains outside the qualified scope. A quiet unsupported component is not
evidence that this requirement passed.

Previous-source state requires all three planes, matching format and geometry,
adjacent input frame IDs, increasing presentation timestamps and no reset.
Copy on the same stream after all consumers of the previous picture finish.
An allocated UV plane is not a valid previous-colour picture. Invalid history
must never be read. Preserve the ordinary luma-only cache behaviour when the
new experimental collection is disabled.

## Evaluation rules frozen before new candidate results

- Existing source/detail, amplitude, quiet-region, causal/spectral and temporal
  regressions remain required; known bad controls must still fail.
- For the new patch model, preserve the 8% worst variance and 0.08 normalized
  covariance exploratory bounds. Record missing-noise diagnostics and final
  reconstructed-source checks separately, including their original failures.
  These limits do not replace visible-detail or compressed-output qualification.
- R2 CPU/GPU measurement comparison uses independently decoded originals and a
  separate CPU implementation. Counts, selected coordinates, native rounding
  and code lookups must match exactly. Floating moments are compared relative
  to source energy with an explicit predeclared numerical error budget, not
  by loosening a quality threshold when a kernel differs.
- Reserved qualification uses six packet-identical excerpts from three titles:
  The Bear S04E10 (SDR), Pantheon S02E08 (animation), Transformers (2007, PQ).
  Fixed seeks are 300 and 900 seconds, each with 12 seconds of context and a
  following 60-second evaluation window. Admit only verified original AVC/HEVC
  packet copies; exclude AV1 library derivatives and Dolby Vision profile 7.
- Read/hash/probe/packet-copy checks may prepare those excerpts. Do not inspect
  grain results, fit models, select favorable frames or tune against them before
  freezing the R5 candidate. If qualification informs a fix, relabel those
  results development evidence and reserve a new independent set.
- Existing Gentlemen, South Park, Dragon, Bridge and Shining references remain
  development/regression material. Historical campaign scores remain attached
  to their own builds. Unverified old reference files are not admitted merely
  because their filenames call them originals.
- Reserved footage has not yet established strong real Cb/Cr coupling, coarse
  SDR grain or HLG coverage. Add verified development references or restrict
  the deployment scope; do not claim those properties from title names.
- After R3/R4, all tested output pictures require complete decode, source clock
  and metadata checks. Source detail, gradient/banding, ripple, grain covariance,
  temporal stability and playback remain separate quality axes. Freeze each
  metric's model, colour/display assumptions and sample schedule before scores.
- Use the existing tradeoff tool's 3% maximum video-byte mismatch for the first
  matched-size comparison; seek tighter points when a small claimed improvement
  could be explained by that mismatch. Equal QVBR is not equal size. Full-title
  storage allowance and throughput budget remain decisions based on R6 evidence.

The private source manifest, packet proofs and preparation result are in
`colour-recovery-20260922/roadmap-r1-r2-20260922/` under the existing evidence
root. They pin the source identity and exact excerpt hash without decoding or
scoring reserved pixels. No whole-picture or production qualification follows
from this contract alone.
