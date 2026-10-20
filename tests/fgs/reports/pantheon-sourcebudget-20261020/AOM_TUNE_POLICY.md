# libaom 3.8.2 PSNR/SSIM tune audit

The scratch evidence directory `reviewer/aom-tune-source-v382` preserves the
source used to interpret the E05 `libaom-av1`
`-tune ssim` versus `-tune psnr` experiment. It is an audit of configured
encoder behavior, not proof of which downstream decisions a particular encode
made.

## Pinned inputs

- Official AOM v3.8.2 annotated tag object:
  `80708309620c178e2f3a03ea452495ec83617079`
- Peeled commit: `615b5f541e4434aebd993036bc97ebc1a77ebc25`
- Commit tree: `6c752cdc321eb9ba5b2a9b30fd6047d49a8a1a64`
- Official tag archive: `aom-v3.8.2.tar.gz`, SHA-256
  `63238bcefc514e3e454e7ebab8470174c9a237a578e3e4ee3e9872e9bfc70078`
- Ubuntu patch archive for installed package `3.8.2-2ubuntu0.2`:
  `aom_3.8.2-2ubuntu0.2.debian.tar.xz`, SHA-256
  `d1fb459395296901e6aed6348828c6a5a29e2364d5b0c809a5ba1def73d599e7`
- FFmpeg n6.1.1 wrapper source: `ffmpeg-n6.1.1-libaomenc.c`, SHA-256
  `ba82de949413ba49915e4601303481c68713e4e0dfc0303cc67acdaedc490369`
- Executed `/usr/bin/ffmpeg`, SHA-256
  `ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41`
- Linked `/usr/lib/x86_64-linux-gnu/libaom.so.3.8.2`, SHA-256
  `8237d4144def32f99903834d4a11892f8e133ae8592b6fe3325e541a917e1bbf`

The exact fetch URLs, per-file hashes, inspected line ranges, and Ubuntu patch
inventory are in [aom-tune-provenance.json](aom-tune-provenance.json).
Source paths below are relative to that evidence directory.

## Direct behavior

`src/aom/aomcx.h:1622-1644` defines `AOM_TUNE_PSNR` and `AOM_TUNE_SSIM` and
distinguishes tune policy across blocks from the separate in-block distortion
metric. The latter remains at its unchanged default in this experiment.

The FFmpeg wrapper maps `-tune psnr|ssim` to the single
`AOME_SET_TUNING` control (`ffmpeg-n6.1.1-libaomenc.c:947-951,1499-1501`).
LibAOM copies that value into `tune_cfg->tuning`
(`src/av1/av1_cx_iface.c:1296-1307,1725-1729`).

For SSIM tune, libaom computes source-luma variance over 8x8 cells, averages it
within 16x16 regions, applies a fitted saturating curve, and normalizes all
factors to a frame geometric mean of one
(`src/av1/encoder/encoder_utils.c:1316-1382`). It computes this field once per
frame (`encoder.c:3732-3734`) and multiplies the already established block RD
multiplier by the appropriate geometric-mean factor during partition/mode RDO
(`encodeframe_utils.c:20-63`, `partition_search.c:590-615`). The explicit
variance AQ therefore remains active in both arms; SSIM tune adds another
source-variance-dependent RD weighting. PSNR tune omits that extra multiplier.

Higher local source variance maps to a larger pre-normalization factor and thus
generally a larger relative rate price. Whether either prescribed ROI receives
a factor above or below one depends on its variance relative to that frame's
geometric mean and cannot be inferred from the source audit alone.

## Scope and confounds

A complete search of v3.8.2 `tune_cfg.tuning` conditions found no direct
PSNR/SSIM-specific switch for ARNR, alt-reference construction, loop filters,
CDEF, restoration, prediction tools, or reference settings. The changed RD
multiplier can still alter partitions, modes, transforms, coefficients,
reconstructed references, later prediction, and selected filter parameters.
The experiment is therefore a **rate-calibrated source-variance RDMULT
allocation / whole decision-policy contrast**, not a pure distortion-metric,
quantizer, or fixed-structure test.

`firstpass.c` contains no tune/SSIM/PSNR reference; the only tune condition in
`pass2_strategy.c` is for VMAF modes. Identical pass-1 statistics between the
two executed arms remain a required runtime check. A difference would reveal
an unaccounted command or build path despite this static source result.

Ubuntu's package patches cover documentation/system-library integration, image
allocation checks, an LAP-mode first-pass statistics buffer fix, and SVC layer
bounds checks. None changes the SSIM factor construction or application. The
LAP fix touches `firstpass.c` and `pass2_strategy.c`, but its hunks concern
buffer bounds/window movement rather than tune selection.
