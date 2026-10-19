# Independent review disposition

A bounded read-only reviewer checked the native synthesis/model methodology, SVT hooks/allocation path, and final report against stored evidence.

- The lower-quartile source-amplitude cap does not guarantee quiet-region protection. The report now explicitly rejects the candidate on held-out quiet-luma regression, rather than calling the cap safe.
- Positive source/base marginal PSD subtraction is an independent-noise hypothesis, not unique identification of authentic grain. The headline describes recovery of amplitude/spatial statistics; temporal appearance remains unproven.
- Held-out color and active/inactive-model coverage were added without refitting. Frames are held out from fitting/calibration only, because all thumbnails influence segmentation.
- The first E04 coefficient hook produced incomplete coverage. Only the corrected, byte-identical rerun in coeff-trace supplies E04 coefficient statistics; the validator asserts 240 files and is baseline-only. Fresh reproduction with the final hook can use its complete main trace directly.
- Requested minus12 is not necessarily the realized delta after AQ/normalization. Conclusions use actual SB traces, including the rate-control increase in frame base. Reviewer found no cumulative double application in the inspected VBR/recode path and found delta-q signaling consistent.
- Final luma coefficient counts/magnitudes are entropy-input proxies, never claimed as bits. Fully contained transform coverage and skipped-block exclusions are explicit.
- Reviewer verified sampled pre-SB-deblock/post-DLF/final frames were byte-identical and accepted the local pre-filter-loss inference. Full-window TF/DLF activity is reported separately.
- Final review found no other material inconsistency between report, metrics, stage validation and actual rates (+0.366%/+0.746%). Local report links resolved. No production approval or perceptual-equivalence gate is implied.

Verification also includes native/independent decoder agreement, complete baseline/instrumented IVF equality, final combined-patch disabled equality, exact patch replay to all nine build files, syntax checks, and scalar/vector allocation-map agreement on three representative E04 frames. Patch context lines intentionally contain a leading space; the patch was validated by application rather than stripping unified-diff syntax to satisfy whitespace lint.
