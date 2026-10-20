# R15 scoring preflight

Reviewed unexecuted `worker/psyex-r15-real/score_r15.py` SHA256 `92489819d493abdc0305cc5ea9ac4ad90f969963d4a8d288421f017f4685d977`.

## Required before execution

1. Add an explicit `if not __debug__: raise ...` before assertion-based admission. The script currently relies throughout on `assert`; optimized Python would bypass the run, provenance, decoder, packet, source, and population gates.
2. Update lines 53-54 to the corrected narrow admission fields after the native-admission review. It must require full pre/postloop identities plus the explicit traced-ROI owner/predictor/q/EOB and positive-unit DQ/IQM fields; it must not preserve the overbroad old names merely to satisfy this scorer.
3. After `admit.py` is finalized, pin its reviewed SHA in the scorer and require `validation['script']['sha256']` to equal it. The caller-provided admission-result SHA is necessary but does not independently establish which admission implementation produced the JSON.

## Correctness and scope

The scorer correctly binds the completed R15 receipt/output/recon, final runtime admission, exact neutral off/on replays, native admission artifacts, and the all336 app/dav1d/libaom/NVDEC receipt. It independently remeasures the 96:336 Matroska packet rate, separates `practical_rate_eligible` (0–100% source) from descriptive 99–100% matched comparability, and verifies all 240 scored decoder planes against the admitted 336-frame hashes.

It uses the untouched original reference, the established GPU campaign path through `x.score`, the full 240-frame texture analysis, the frozen 12,870 tiles across 15 frames with exact source-descriptor replay, every kind/outside group, MSE p95 and signed-HF p95, and the fixed face/edge check. Raw tile rows are retained, so means do not hide individual tails. The inherited campaign/texture outputs carry full-reference, CAMBI/banding, and temporal evidence for the later bound summary.

The provisional HF ±10% and ACF ≤.05 screens are unchanged for both prescribed boxes. There is no rate-gate weakening, matched-rate claim, or playback claim. The final scope string should say that statistical quality and decoder admissions were performed and **playback remains unobserved**; its current “full quality/decoder ... remain required” wording inaccurately describes work this script completes.

Later summarization should bind the raw campaign/texture artifacts and all 240/12,870 populations rather than rely only on the compact assessment. With the three admission fixes above, I found no wrong reference, frame offset, pixel scaling, rate unit, GPU path, or frozen-control regression in the scoring method.

## Corrected scorer — cleared

Final `score_r15.py` SHA256 `65d194a38ca0c6ccd0a70c2356ea35e64b7e926507fcc3b413c5a015d6d76e8a` implements all requested corrections: it rejects optimized Python before imports/admission, hard-pins final `admit.py` `7dc554ff…`, requires the two accurately scoped traced-ROI/positive-unit evidence flags, and states that decoder/numerical quality measurements are performed while playback remains unobserved. No scoring, reference, control, rate, or threshold code changed. Cleared for execution after successful final native admission.

## Identity-schema repair

Cleared corrected `score_r15.py` SHA256 `bdb6991391f52fe9c21644144c038bed05784c918a896eb133a67cda227d207c`. Its exact diff from preserved failed draft `score_r15.py.v1-failed-schema` SHA256 `65d194a38ca0c6ccd0a70c2356ea35e64b7e926507fcc3b413c5a015d6d76e8a` replaces one overstrict whole-dictionary comparison with five lines that require the independently recomputed fingerprint's recorded canonical path and SHA to equal the receipt and require live `stat().st_size` to equal its recorded size. It does not bypass identity or alter scoring. The intermediate tautological-path draft `316291…` is correctly excluded.
