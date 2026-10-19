# Independent review resolution

A separate read-only reviewer checked input hashes, alignment, actual rates, metric tooling, exported-stage equivalence and reporting scope.

- Fixed stale tag-based caching with input/tool/options fingerprints and rejection of unverified artifacts. A fresh run of the final adapter passed scoring, equal cache reuse and changed-input rejection; see cache-validation.json. It also reproduced every historical E04 frame metric after correcting supplementary CAMBI workers from 8 to the required 16.
- Describe HF as amplitude, paired with ACF and source residual correlation, rather than a percentage of texture preserved.
- Hash both FFmpeg binaries; record the decoder and actual grain application rather than a requested flag on predecoded data.
- Reviewer withdrew the initial concern about whole-frame grain equality after examining the separate full-frame hashes. The report limits the E05-1460 claim to frames 95–125.
- Exact external/raw versus integrated FGS replay validates stage separation for this sample, not analyzer correctness. SVT conclusions apply only to the tested current-version settings and window.

The report deliberately leaves proprietary reconstruction internals and actual player/display behavior unresolved. No production repair is declared.
