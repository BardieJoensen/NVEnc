# Where the release loses colour detail: the encoder, not the separator

The release keeps 0.89-0.995 of the source's structured colour (the most colour-structured tenth of chroma patches, coded base with grain off) on held-out live action, and 0.92-1.00 on animation. The deployed production binary measures the same. But the release hands NVENC the source's colour essentially intact: the submitted picture keeps 0.995-1.000 in 17 of 19 windows and 0.983-0.995 in the other two (Insidious f85, Knightfall p70). At brightness levels where chroma is protected, production blends the source colour back, so the separator's luma-derived chroma threshold does not reach these regions. Almost all of the loss happens when NVENC codes the base at QVBR 30. A chroma range threshold from the chroma noise model can therefore recover at most the separator's share: 0-1.7%, in two windows. The duller lips came from the codec-flat chroma option, which removed that protection. NVENC's chroma QP offset (-2, -4) does not change the retained colour. A chroma base-detail check is now part of the gate and fails the option-on build.

## Measure

`tools/chroma_detail.py` (scratch): per frame and plane (Cb, Cr), the most colour-structured tenth of 16x16 chroma patches inside the reviewed active rectangle, chosen from the lossless source (highest patch standard deviation, exactly flat patches excluded). For each arm, pooled over those patches: amplitude = sqrt(sum arm patch variance / sum source patch variance); peak = sum of patch p95 |C - 128| over the same for the source. AV1 arms are decoded with film grain off. The submitted picture is the exact surface NVENC received (submission-trace raw dump). Release `46d6781c` encodes for held-out and census windows; traced default-mode windows with `725585b8` (option off, trace-identical to the release).

## Results (amplitude / peak)

| Windows | Release, coded base | Submitted picture (separator output) | Production `c6cbd528` |
|---|---|---|---|
| Held-out live action, 9 (Insidious, Marshals, Homegrown) | Cb 0.927-0.995 / 0.944-0.996, Cr 0.961-0.995 / 0.972-0.993 | 0.999-1.000 in 8; Insidious f85 Cb 0.986 / 0.991, Cr 0.992 / 0.995 | identical to the release within 0.001 |
| Census live action, 9 | Cb 0.889-0.995, Cr 0.949-0.996 | not traced | - |
| Animation: Knightfall, Toy Story 5 census, 6 | Cb 0.972-0.995, Cr 0.933-0.994 | 0.995-1.000 in 5; Knightfall p70 Cb 0.995 / 0.996, Cr 0.983 / 0.985 | - |
| Animation: Amphibia, Lost Tapes, 4 windows | 0.992-0.999 | 1.000 | - |

Worst release windows: Insidious census p70 Cb 0.889 / 0.924, held-out Insidious f55 Cb 0.927 / 0.944, Knightfall p70 Cr 0.922 / 0.952 (traced window). In each of them the submitted picture is at 0.983-1.000.

NVENC chroma QP offset, release binary, held-out Insidious f55 and f20 and Homegrown f55: offsets -2 and -4 change retained colour by at most 0.002 and bytes by +0.0 to +0.8%.

For reference, the parked option-on build `725585b8` on the held-out windows: Cr amplitude 0.905-0.977 against the release's 0.961-0.995, because it submits the separator's chroma instead of the source's at levels it no longer protects.

## Gate check

Commit `3d7c5405` adds stage `chroma_base_detail` to `local_gate.sh` (`tests/fgs/chroma_base_detail.py`). It encodes the pinned Gentlemen clip, decodes with grain off and applies the measure above against the lossless source over every second frame. The floor is the reviewed release positive (`gentlemen-clean-source-positive`). The candidate may not fall more than 0.002 below it on any of the four numbers, which is 20x the same-binary repeat variation (about 0.0001). A labelled negative must be rejected on every run: the option-on gate output, pinned as `gentlemen-codec-flat-chroma-detail-negative-33m-150s.mkv` (SHA256 `0e8521d8`).

| Build | Cb amp / peak | Cr amp / peak | Result |
|---|---|---|---|
| Floor (release positive) | 0.9989 / 0.9975 | 0.9971 / 0.9973 | - |
| Release `46d6781c`, fresh encode | 0.9989 / 0.9975 | 0.9971 / 0.9973 | pass |
| Option on `725585b8` | 0.9971 / 0.9920 | 0.9904 / 0.9885 | fail |

Reports: `fgs-submission-20261005/reports/chroma-detail-{rel,opton}-3d7c5405/`. CPU tests pass on `3d7c5405`.

## Evidence

Scratch `/tmp/downloads/codex-work/fgs-fidelity-20261007/sep2/`: `cd/*.json` (heldout-, census-, split-, cqp-, gentlemen-gate), `tr/` (traced windows), `cqp/` (chroma QP offset encodes).
