# Finite grain-template calibration, September 22

The new offline luma-template helper accounts for AV1's integer rounding,
finite borders and internal clipping. It resolves the main cause of the
stationary-power mismatch in the joint-colour study. It has **no encoder call
sites** and changes neither ordinary Tdarr nor automatic retention policy.
Production remains ordinary `cb903a17`; retention and FEL remain disabled.

## Cause and implementation

The earlier stationary calculation assumes an unbounded linear recurrence.
Actual AV1 synthesis bounds its internal grain samples. In three Shining
models, about 1.19–1.54% of filtered template samples hit that bound, reducing
the averaged-luma energy relative to the linear prediction. This is internal
noise-template clipping, not evidence of clipped picture highlights or a new
library defect.

A private probe of pinned AOM `18c52422b835` compares its actual template with
an independent integer recurrence and an unclipped floating recurrence.
Across 512 seeds, the floating prediction is about 1.1% below the stationary
averaged-luma power; the rounded/clipped template is about 5.9–7.4% below it.
Halving the internal innovation removes the observed clipping and most of
that additional difference. Changing only displayed scaling does not change
the internal clipping. The alternative grain-scale setting is a diagnostic
control, not an enabled encoding change; current amplitude guards deliberately
admit only the existing scale setting.

[`NVEncFilmGrainTemplate.h`](../../NVEncCore/NVEncFilmGrainTemplate.h) generates
the finite 82x73 luma template for explicit AV1 coefficients, seed, bit depth
and shifts. A separate function measures second moments over all 256 possible
block offsets. It returns both the unrounded 2x2 mean and AV1's rounded chroma
driver, plus native mean and internal clipping fraction. An equivalent weighted
sum avoids repeatedly visiting identical positions. Normalization uses the
normative Gaussian innovation's second moment. This is a finite-template
calculation, not an implementation of displayed grain or a statistical
confidence guarantee.

The normative Gaussian table retains its AOM BSD notice and patent terms.
Signed rounding is explicit and portable under C++17. Invalid parameters
reject the calculation; a failed generation clears the old output. A valid
result only means the calculation completed. Source support, coefficient
representability and the existing stability/texture/amplitude policies remain
separate requirements.

## Verification and real fits

An independent AOM build matches **all 4,597,248 samples in 768 complete
templates** across 8/10/12-bit input, all four lags, all four coefficient shifts,
all four grain shifts and four seeds including zero. Twenty-four fixed syntax
vectors and full-template hashes are retained in the CPU suite; they contain
no private media. A separate exhaustive offset enumeration also agrees on all
four measured fields for those 24 vectors. Analytic white-noise, correlated
clipping, low-strength rounding and invalid-parameter controls supplement the
independent vectors.

Four real, previously supported targets use 512 calibration seeds and 512
different holdout seeds. Their averaged-luma driver powers differ by at most
**0.32%**. All four quantized luma and chroma models pass the existing per-plane
causal-decay and spectral guards. Feeding finite driver power into joint
chroma fitting changes the floating coupling estimate, but its quantized byte
is unchanged in these weak-coupling examples. This does not establish a
visible quality gain or stronger real coupling coverage.

The earlier 48-seed AOM observations remain unchanged, including their two
8% bound failures. The expanded experiment explains the mechanism; it does
not erase failed evidence or widen the acceptance threshold. Finite-template
power excludes overlap, displayed scaling and picture clipping. Actual decoded
source comparisons and transition checks are still needed for integration.

The full CPU suite passes 185 Python tests in 26 suites plus C++ checks,
including the new finite-template regression. The 512-seed calibration costs
about 61–64 ms per model in this host-only measurement. It is currently an
offline reference, not a proposed per-picture production calculation or an
encoder speed improvement.

## Brightness-specific checks

The same accepted source coordinates were divided into the existing twenty
luma-level bins. Source/base pixels are resolved through the archive index and
hash-verified. Reconstructed bin moments sum back to the original moments, and
the training/holdout brightness histograms match exactly. No source selector
threshold changed and no unused cached chroma was reused.

Fourteen frame/component/bin groups have at least sixteen training and sixteen
holdout tiles. All fourteen yield mathematically valid missing-noise targets;
only **nine** pass the existing 8% variance and prediction bounds. Five remain
rejected. In one dark Shining region, the whole-frame fitted shape has about
20% excess predictor error even though brighter regions fit much better. The
other failures include inconsistent target variance. Mathematical validity
therefore remains insufficient evidence for applying recovered grain.

An offline alternative normalizes luma/chroma scales using training data and
gives the supported brightness bins equal fitting weight. It reduces that
worst dark-region error to **9.27%**, still above the unchanged 8% limit. Its
other tradeoffs and original failed results are retained. It is **not accepted
for integration**; holdout variance disagreement is not normalized away.

## Next implementation gate

The next model change needs reliable per-intensity support and a shared grain
shape that meets every covered range's bounds. Unsupported or inconsistent
ranges must retain source detail. Brightness balancing alone has not solved
that requirement. Stronger real luma/colour coupling and integrated temporal
behaviour also remain unqualified. Only a useful, qualified recovery candidate
should proceed to repeated matched-size witnesses, longer-title cost trials
and throughput optimization.

Evidence is in `finite-template-20260922/` under the existing September 22
colour-recovery ledger. Read `report.json`, `port-equivalence.json`,
`calibrated-real-fits.json`, `intensity-report.json`, `balanced-report.json`,
`cpu.json`, build/source provenance and cleanup receipts. The prior comparison
results remain in [the matched-size findings](FINDINGS-2026-09-22-COLOUR-RECOVERY.md).
This follow-up uses CPU only; ordinary Tdarr continues and no experiment starts
automatically.
